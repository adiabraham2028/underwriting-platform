import uuid
import json
import logging
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.classification import LineItemClassification, ClassificationSession, ClassificationSessionItem
from models.tenant_settings import TenantSettings
from services.llm_service import llm
from services.seed_classifications import (
    THE_21_CATEGORIES, GL_CODE, classify_by_gl, classify_by_name, normalize,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a multifamily real estate analyst expert in chart of accounts classification. Classify financial statement line items into standardized categories. Return only valid JSON, no markdown."""


def _normalize(s: str) -> str:
    return s.lower().strip()


async def get_auto_accept_threshold(tenant_id: uuid.UUID, session: AsyncSession) -> float:
    result = await session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    settings = result.scalar_one_or_none()
    return settings.auto_accept_threshold if settings else 0.90


async def lookup_by_account_code(tenant_id: uuid.UUID, account_code: str, session: AsyncSession):
    result = await session.execute(
        select(LineItemClassification)
        .where(
            LineItemClassification.tenant_id == tenant_id,
            LineItemClassification.account_code == account_code,
        )
        .order_by(LineItemClassification.confidence.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def lookup_by_name(tenant_id: uuid.UUID, normalized_name: str, session: AsyncSession):
    result = await session.execute(
        select(LineItemClassification)
        .where(
            LineItemClassification.tenant_id == tenant_id,
            LineItemClassification.normalized_line_item == normalized_name,
            LineItemClassification.confidence >= 0.90,
        )
        .order_by(LineItemClassification.confidence.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_confirmed_examples(tenant_id: uuid.UUID, session: AsyncSession, limit: int = 30) -> list:
    result = await session.execute(
        select(LineItemClassification)
        .where(
            LineItemClassification.tenant_id == tenant_id,
            LineItemClassification.confidence >= 0.90,
        )
        .order_by(LineItemClassification.confidence.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def classify_with_claude(items: list[dict], examples: list, source_format: str) -> list[dict]:
    examples_json = json.dumps(
        [
            {
                "line_item": e.original_line_item,
                "account_code": e.account_code,
                "category": e.assigned_category,
            }
            for e in examples
        ],
        indent=2,
    )
    items_json = json.dumps(
        [
            {
                "line_item_name": item['name'],
                "account_code": item.get('account_code'),
                "trailing_total": item.get('trailing_total', 0),
            }
            for item in items
        ],
        indent=2,
    )

    categories_str = ', '.join(THE_21_CATEGORIES)
    user_content = f"""Classify these T12 line items into the standard categories.

STANDARD CATEGORIES (use exactly these strings):
{categories_str}

CONFIRMED EXAMPLES FROM THIS CLIENT:
{examples_json}

SOURCE FORMAT: {source_format}
(conam_gl = has account codes like 40000-1000; conam_ext = narrative categories; broker = generic)

LINE ITEMS TO CLASSIFY:
{items_json}

Return JSON:
{{
  "classifications": [
    {{
      "line_item_name": "original name",
      "account_code": "code or null",
      "category": "one of the 21 categories",
      "confidence": 0.0-1.0,
      "reasoning": "one sentence"
    }}
  ]
}}

Rules:
- TOTAL/SUBTOTAL/NET rows: set confidence 0.0, category "SKIP"
- Employee apartment INCOME -> Payroll
- Trash billed to tenants -> RUBSInc; trash expense -> Utilities
- Turnover/MakeReady painting, carpet, cleaning -> Turnover
- R&M NOT related to turnover -> Repairs
- Cap Exp-* -> CapEx
- Management fees -> MgmtFee (not Admin)
- Loss to lease (can be positive or negative) -> LTL
- Write-offs / delinquent rent -> BadDebt
- Late fees -> OtherInc"""

    try:
        result = await llm.complete_json_with_retry(SYSTEM_PROMPT, user_content, max_tokens=2048)
        classifications = result.get('classifications', [])
        # Build lookup by line_item_name
        lookup = {c['line_item_name']: c for c in classifications}
        out = []
        for item in items:
            cl = lookup.get(item['name'], {})
            confidence = float(cl.get('confidence', 0.5))
            out.append({
                **item,
                'category': cl.get('category', 'MiscExp'),
                'confidence': confidence,
                'reasoning': cl.get('reasoning', ''),
                'match_type': 'ai_high' if confidence >= 0.90 else 'ai_low',
            })
        return out
    except Exception as e:
        logger.error(f"Claude classification failed: {e}")
        return [
            {**item, 'category': 'MiscExp', 'confidence': 0.3, 'match_type': 'ai_low'}
            for item in items
        ]


async def classify_line_items(
    tenant_id: uuid.UUID,
    line_items: list[dict],
    source_format: str,
    session: AsyncSession,
) -> list[dict]:
    """
    Classify T12 line items with this priority order:
      1. In-memory GL code lookup (SEED_GL) — zero DB calls, covers 100% of CONAM GL
      2. In-memory name lookup (SEED_NAMES) — zero DB calls, covers most broker items
      3. Tenant DB learned classifications (human corrections from previous deals)
      4. Claude — batched, only for genuinely unknown items

    CONAM GL files: 0 Claude calls. Broker files: 1 batched call for unknowns only.
    """
    results: list[dict] = []
    needs_claude: list[dict] = []

    for item in line_items:
        code = str(item.get('account_code') or '').strip()
        name = item.get('name', '')

        # --- 1. In-memory GL code lookup ---
        if GL_CODE.match(code):
            cat = classify_by_gl(code)
            if cat == 'SKIP':
                continue  # known subtotal, discard entirely
            if cat is not None:
                results.append({**item, 'category': cat,
                                 'confidence': 1.0, 'match_type': 'exact_known'})
                continue

        # --- 2. In-memory normalized name lookup ---
        cat = classify_by_name(name)
        if cat is not None:
            if cat == 'SKIP':
                continue
            results.append({**item, 'category': cat,
                             'confidence': 0.95, 'match_type': 'exact_known'})
            continue

        # --- 3. Tenant DB learned classifications ---
        norm = normalize(name)
        learned = await lookup_by_name(tenant_id, norm, session)
        if learned:
            results.append({**item, 'category': learned.assigned_category,
                             'confidence': learned.confidence, 'match_type': 'exact_known'})
            continue
        if code:
            learned_gl = await lookup_by_account_code(tenant_id, code, session)
            if learned_gl:
                cat = learned_gl.assigned_category
                if cat == 'SKIP':
                    continue
                results.append({**item, 'category': cat,
                                 'confidence': 1.0, 'match_type': 'exact_known'})
                continue

        # --- 4. Queue for Claude (genuinely unknown) ---
        needs_claude.append(item)

    if needs_claude:
        logger.info(f"Sending {len(needs_claude)} unknown items to Claude (batched)")
        examples = await get_confirmed_examples(tenant_id, session)
        claude_results = await classify_with_claude(needs_claude, examples, source_format)
        results.extend(claude_results)
    else:
        logger.info("All items classified from seed data — 0 Claude calls")

    return sorted(results, key=lambda x: x.get('original_order', 0))


async def create_classification_session(
    deal_id: uuid.UUID,
    document_id: uuid.UUID | None,
    tenant_id: uuid.UUID,
    classified_items: list[dict],
    threshold: float,
    session: AsyncSession,
) -> ClassificationSession:
    # Filter out SKIP items — they are known subtotals, never need review or model population
    classified_items = [i for i in classified_items if i.get('category') != 'SKIP']

    auto_accepted = sum(
        1 for i in classified_items
        if i['confidence'] >= threshold or i.get('match_type') == 'exact_known'
    )
    needs_review = len(classified_items) - auto_accepted

    cs = ClassificationSession(
        id=uuid.uuid4(),
        deal_id=deal_id,
        document_id=document_id,
        tenant_id=tenant_id,
        status='pending_review' if needs_review > 0 else 'approved',
        total_line_items=len(classified_items),
        auto_accepted=auto_accepted,
        needs_review=needs_review,
        created_at=datetime.now(timezone.utc),
    )
    session.add(cs)
    await session.flush()

    for i, item in enumerate(classified_items):
        match_type = item.get('match_type', 'ai_low')
        # Validate match_type enum value
        valid_match_types = {'exact_known', 'ai_high', 'ai_low', 'human_override'}
        if match_type not in valid_match_types:
            match_type = 'ai_low'
        session.add(ClassificationSessionItem(
            id=uuid.uuid4(),
            session_id=cs.id,
            line_item_name=item['name'],
            account_code=item.get('account_code'),
            monthly_values=item.get('monthly_values', {}),
            trailing_total=item.get('trailing_total', 0.0),
            ai_suggested_category=item['category'],
            ai_confidence=item['confidence'],
            final_category=item['category'],
            match_type=match_type,
            was_corrected=False,
            display_order=i,
        ))

    return cs


async def apply_session_to_knowledge_base(
    session_obj: ClassificationSession,
    tenant_id: uuid.UUID,
    approved_by: uuid.UUID,
    db: AsyncSession,
) -> None:
    """After approval, upsert human-corrected items into line_item_classifications."""
    result = await db.execute(
        select(ClassificationSessionItem).where(
            ClassificationSessionItem.session_id == session_obj.id,
            ClassificationSessionItem.was_corrected == True,
        )
    )
    corrected_items = result.scalars().all()

    now = datetime.now(timezone.utc)
    for item in corrected_items:
        normalized = item.line_item_name.lower().strip()
        # Check if a mapping already exists
        existing = await db.execute(
            select(LineItemClassification).where(
                LineItemClassification.tenant_id == tenant_id,
                LineItemClassification.normalized_line_item == normalized,
            ).limit(1)
        )
        existing_row = existing.scalar_one_or_none()
        if existing_row:
            existing_row.assigned_category = item.final_category
            existing_row.confidence = 1.0
            existing_row.classification_source = "human"
            existing_row.confirmed_by = approved_by
            existing_row.confirmed_at = now
            existing_row.override_reason = "Human correction via review UI"
        else:
            db.add(LineItemClassification(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                original_line_item=item.line_item_name,
                normalized_line_item=normalized,
                source_format="broker",
                account_code=item.account_code,
                assigned_category=item.final_category,
                confidence=1.0,
                classification_source="human",
                confirmed_by=approved_by,
                confirmed_at=now,
                deal_id=session_obj.deal_id,
                created_at=now,
            ))
