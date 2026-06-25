import uuid
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database import get_db
from models.classification import LineItemClassification
from models.user import User
from routers.auth import get_current_user, get_tenant_id
from schemas.classification import LineItemClassificationOut, KnowledgeBaseStatsOut
from services.seed_classifications import SEED_GL, SEED_NAMES, normalize

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/my/classifications", tags=["knowledge-base"])


@router.get("", response_model=list[LineItemClassificationOut])
async def list_classifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List confirmed line item classification mappings (paginated)."""
    tenant_id = get_tenant_id(current_user)
    result = await db.execute(
        select(LineItemClassification)
        .where(LineItemClassification.tenant_id == tenant_id)
        .order_by(LineItemClassification.assigned_category, LineItemClassification.original_line_item)
        .offset(skip)
        .limit(limit)
    )
    return [LineItemClassificationOut.model_validate(c) for c in result.scalars().all()]


@router.post("/seed")
async def reseed_classifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run seed data for this tenant (adds missing entries, does not overwrite human corrections)."""
    tenant_id = get_tenant_id(current_user)
    added = 0
    now = datetime.now(timezone.utc)

    # Seed GL codes
    for code, category in SEED_GL.items():
        existing = await db.execute(
            select(LineItemClassification).where(
                LineItemClassification.tenant_id == tenant_id,
                LineItemClassification.account_code == code,
            ).limit(1)
        )
        if not existing.scalar_one_or_none():
            db.add(LineItemClassification(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                original_line_item=code,
                normalized_line_item=code,
                source_format="conam_gl",
                account_code=code,
                assigned_category=category,
                confidence=1.0,
                classification_source="seed",
                created_at=now,
            ))
            added += 1

    # Seed name-based mappings
    for norm_name, category in SEED_NAMES.items():
        existing = await db.execute(
            select(LineItemClassification).where(
                LineItemClassification.tenant_id == tenant_id,
                LineItemClassification.normalized_line_item == norm_name,
                LineItemClassification.account_code == None,
            ).limit(1)
        )
        if not existing.scalar_one_or_none():
            db.add(LineItemClassification(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                original_line_item=norm_name,
                normalized_line_item=norm_name,
                source_format="broker",
                account_code=None,
                assigned_category=category,
                confidence=0.95,
                classification_source="seed",
                created_at=now,
            ))
            added += 1

    await db.commit()
    return {"ok": True, "added": added}


@router.get("/stats", response_model=KnowledgeBaseStatsOut)
async def get_knowledge_base_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return stats: total mappings, auto-classifiable %, corrected in last 30 days."""
    tenant_id = get_tenant_id(current_user)

    total_result = await db.execute(
        select(func.count()).where(LineItemClassification.tenant_id == tenant_id)
    )
    total = total_result.scalar() or 0

    high_conf_result = await db.execute(
        select(func.count()).where(
            LineItemClassification.tenant_id == tenant_id,
            LineItemClassification.confidence >= 0.90,
        )
    )
    high_conf = high_conf_result.scalar() or 0

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    corrected_result = await db.execute(
        select(func.count()).where(
            LineItemClassification.tenant_id == tenant_id,
            LineItemClassification.classification_source == "human",
            LineItemClassification.confirmed_at >= thirty_days_ago,
        )
    )
    corrected_last_30d = corrected_result.scalar() or 0

    auto_classifiable_pct = (high_conf / total * 100.0) if total > 0 else 0.0

    return KnowledgeBaseStatsOut(
        total=total,
        auto_classifiable_pct=round(auto_classifiable_pct, 1),
        corrected_last_30d=corrected_last_30d,
    )


@router.delete("/{classification_id}")
async def delete_classification(
    classification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a classification mapping."""
    tenant_id = get_tenant_id(current_user)
    obj = await db.get(LineItemClassification, classification_id)
    if not obj or obj.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Classification not found")
    await db.delete(obj)
    await db.commit()
    return {"ok": True, "deleted_id": str(classification_id)}
