import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database import async_session_maker
from models.document import Document
from models.extraction import Extraction
from models.snapshot import ModelSnapshot
from models.deal import Deal
from models.template import Template
from models.expense_comp import ExpenseComp
from services.pdf_extractor import detect_format, extract_pdf_text
from services.excel_extractor import extract_excel_text
from services.docx_extractor import extract_docx_text
from services.extraction_service import extract, detect_conflicts
from services.model_populator import (
    build_luckysheet_json, build_t12_extraction_from_session,
    repopulate_model, DEFAULT_CELL_MAPPING,
)
from services.flag_service import create_flags_from_extraction
from services.format_detector import detect_t12_format
from services.t12_extractor import extract_t12_line_items
from services.classification_service import (
    classify_line_items,
    create_classification_session,
    get_auto_accept_threshold,
)
from services.seed_classifications import THE_21_CATEGORIES

logger = logging.getLogger(__name__)

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---------------------------------------------------------------------------
# Helpers: build extraction records without Claude
# ---------------------------------------------------------------------------

def _build_rent_roll_extraction(parsed_units: list[dict]) -> dict:
    """Build a rent-roll extraction dict from locally-parsed unit data."""
    total = len(parsed_units)
    occupied = sum(1 for u in parsed_units if u.get('status') == 'occupied')
    occ_rents = [u.get('base_rent', 0) for u in parsed_units
                 if u.get('base_rent') and u.get('status') == 'occupied']
    mkt_rents = [u.get('market_rent', 0) for u in parsed_units if u.get('market_rent')]

    avg_current = round(sum(occ_rents) / len(occ_rents), 2) if occ_rents else 0
    avg_market  = round(sum(mkt_rents) / len(mkt_rents),  2) if mkt_rents else 0

    return {
        'property_name': None,
        'total_units': total,
        'occupied_units': occupied,
        'occupancy_rate': round(occupied / total, 4) if total else 0,
        'avg_current_rent': avg_current,
        'avg_market_rent': avg_market,
        'total_current_monthly_income': round(sum(u.get('base_rent', 0) for u in parsed_units), 2),
        'total_market_monthly_income': round(sum(u.get('market_rent', 0) or 0 for u in parsed_units), 2),
        'loss_to_lease': round(sum((u.get('market_rent', 0) or 0) - u.get('base_rent', 0)
                                   for u in parsed_units), 2),
        'unit_mix': parsed_units,
        'ancillary_income': {},
        'flags': [],
        'confidence_scores': {
            'total_units': 0.99,
            'occupancy_rate': 0.99,
            'unit_mix_completeness': 0.95,
            'rent_data': 0.95,
        },
    }


def _build_t12_extraction(classified_items: list[dict]) -> dict:
    """Build a T12 extraction dict by aggregating classified line items."""
    by_category: dict[str, float] = {}
    monthly_by_cat: dict[str, dict] = {}

    for item in classified_items:
        cat = item.get('category')
        if not cat or cat == 'SKIP':
            continue
        total = float(item.get('trailing_total') or 0)
        by_category[cat] = by_category.get(cat, 0) + total

        mv = item.get('monthly_values') or {}
        if cat not in monthly_by_cat:
            monthly_by_cat[cat] = {m: 0.0 for m in MONTH_LABELS}
        for m in MONTH_LABELS:
            monthly_by_cat[cat][m] = monthly_by_cat[cat].get(m, 0.0) + float(mv.get(m, 0) or 0)

    # Build trailing_totals using legacy field names so model_populator can still consume them
    # (model_populator looks for t12.get("trailing_totals", {}))
    return {
        'trailing_totals': by_category,
        'monthly_by_category': monthly_by_cat,
        'classified_items_count': len(classified_items),
        'confidence_scores': {'classification': 0.95},
    }


# ---------------------------------------------------------------------------
# Expense comp builder
# ---------------------------------------------------------------------------

async def _build_deal_expense_comp(
    deal: Deal,
    classified_items: list[dict],
    session: AsyncSession,
    uploaded_by: uuid.UUID,
    tenant_id: uuid.UUID,
) -> None:
    """Create/update an expense comp for this deal from classified T12 items."""
    try:
        metrics: dict[str, float] = {}
        for item in classified_items:
            cat = item.get('category')
            if cat and cat != 'SKIP' and cat in THE_21_CATEGORIES:
                metrics[cat] = metrics.get(cat, 0.0) + float(item.get('trailing_total') or 0)

        if not metrics:
            return

        num_units = deal.total_units
        per_unit_yr = {k: round(v / num_units, 2) for k, v in metrics.items()} if num_units else {}
        per_unit_mo = {k: round(v / 12, 2) for k, v in per_unit_yr.items()}

        # Remove old deal comp
        existing = await session.execute(
            select(ExpenseComp).where(ExpenseComp.deal_id == deal.id, ExpenseComp.source == "deal")
        )
        for old in existing.scalars().all():
            await session.delete(old)

        session.add(ExpenseComp(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            property_name=deal.name,
            city=deal.city,
            state=deal.state,
            num_units=num_units,
            financial_stmt_year=str(datetime.now(timezone.utc).year - 1),
            financial_stmt_type="T12",
            metrics=metrics,
            metrics_per_unit_yr=per_unit_yr,
            metrics_per_unit_mo=per_unit_mo,
            source="deal",
            deal_id=deal.id,
            created_at=datetime.now(timezone.utc),
            uploaded_by=uploaded_by,
        ))
        logger.info(f"Expense comp updated for deal {deal.id}")
    except Exception as e:
        logger.warning(f"Expense comp build failed for deal {deal.id}: {e}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def process_document(document_id: uuid.UUID, deal_id: uuid.UUID, user_id: uuid.UUID):
    """Full async processing pipeline for a document.

    Claude API call budget per document type:
      - Excel rent roll  → 0 calls  (local CONAM parser)
      - CONAM GL T12     → 0 calls  (all GL codes known in seed data)
      - Broker/ext T12   → 1 call   (batch of unknown items only)
      - OM               → 1 call   (keep extraction prompt)
      - other            → 1 call
    """
    async with async_session_maker() as session:
        try:
            doc = await session.get(Document, document_id)
            if not doc:
                logger.error(f"Document {document_id} not found")
                return

            doc.extraction_status = "processing"
            await session.commit()

            # --- Format detection + text extraction ---
            file_format = detect_format(doc.file_data, doc.file_name)
            doc.file_format = file_format
            await session.flush()

            if file_format in ("pdf_digital", "pdf_scanned"):
                text = extract_pdf_text(doc.file_data, file_format)
            elif file_format == "excel":
                text = extract_excel_text(doc.file_data)
            elif file_format == "docx":
                text = extract_docx_text(doc.file_data)
            else:
                text = ""

            # ============================================================
            # Branch by document type
            # ============================================================
            extracted_result: dict = {}
            model_used = "local_parser"
            classification_session_obj = None

            # ------ RENT ROLL — any format (CONAM local or Claude fallback) ------
            if doc.document_type == "rent_roll":
                from services.rent_roll_parser import parse_rent_roll_any_format
                from services.conam_rent_roll_parser import parse_conam_rent_roll_excel
                from services.excel_exporter import (
                    get_template_unit_type_map,
                    map_conam_to_template_codes,
                    map_unit_types_with_claude,
                )
                from services.llm_service import llm as llm_svc

                extracted_result = await parse_rent_roll_any_format(
                    file_bytes=doc.file_data,
                    filename=doc.file_name,
                    llm_service=llm_svc,
                    conam_parser_fn=parse_conam_rent_roll_excel,
                )

                # Build and cache unit type mapping on the deal
                unit_mix = extracted_result.get('unit_mix', [])
                if unit_mix:
                    deal_for_mapping = await session.get(Deal, deal_id)
                    if deal_for_mapping and deal_for_mapping.active_template_id:
                        tmpl = await session.get(Template, deal_for_mapping.active_template_id)
                        if tmpl and tmpl.file_data:
                            tmpl_types = get_template_unit_type_map(tmpl.file_data)
                            mapping = map_conam_to_template_codes(unit_mix, tmpl_types)

                            unmapped = sum(1 for v in mapping.values() if v not in tmpl_types)
                            if unmapped > len(mapping) * 0.3 and tmpl_types:
                                unique_types = list({
                                    u['unit_type']: {
                                        'code':  u['unit_type'],
                                        'sf':    u.get('sf'),
                                        'beds':  u.get('beds', 0),
                                        'baths': u.get('baths', 0),
                                        'count': sum(
                                            1 for x in unit_mix
                                            if x['unit_type'] == u['unit_type']
                                        ),
                                    }
                                    for u in unit_mix
                                }.values())
                                mapping = await map_unit_types_with_claude(
                                    unique_types, tmpl_types, llm_svc
                                )

                            deal_for_mapping.unit_type_mapping = mapping
                            logger.info(f"Unit type mapping cached: {len(mapping)} types")

            # ------ T12 — classification pipeline; Claude only for unknowns ------
            elif doc.document_type == "t12":
                tenant_id = user_id
                source_format = detect_t12_format(text)
                logger.info(f"T12 source format: {source_format}")

                line_items = extract_t12_line_items(text, source_format)
                logger.info(f"T12 line items extracted: {len(line_items)}")

                classified: list[dict] = []
                if line_items:
                    classified = await classify_line_items(
                        tenant_id=tenant_id,
                        line_items=line_items,
                        source_format=source_format,
                        session=session,
                    )
                    threshold = await get_auto_accept_threshold(tenant_id, session)
                    classification_session_obj = await create_classification_session(
                        deal_id=deal_id,
                        document_id=document_id,
                        tenant_id=tenant_id,
                        classified_items=classified,
                        threshold=threshold,
                        session=session,
                    )
                    logger.info(
                        f"Classification session {classification_session_obj.id}: "
                        f"status={classification_session_obj.status}, "
                        f"auto_accepted={classification_session_obj.auto_accepted}, "
                        f"needs_review={classification_session_obj.needs_review}"
                    )

                # Build t12_data from the session items just created (proper structure
                # with line_items + month_labels for model_populator).
                if classification_session_obj:
                    from models.classification import ClassificationSessionItem
                    items_res = await session.execute(
                        select(ClassificationSessionItem)
                        .where(ClassificationSessionItem.session_id == classification_session_obj.id)
                        .order_by(ClassificationSessionItem.display_order)
                    )
                    session_items = items_res.scalars().all()
                    month_labels: list[str] = []
                    for si in session_items:
                        mv = si.monthly_values or {}
                        if mv:
                            month_labels = list(mv.keys())
                            break
                    extracted_result = build_t12_extraction_from_session(session_items, month_labels)
                else:
                    extracted_result = {'trailing_totals': {}, 'line_items': [], 'months': [],
                                        'month_labels': [], 'confidence_scores': {}}

                # Extract period start from source Excel header rows
                # e.g. "Period = Jun 2025-May 2026" → period_start = "2025-06-01"
                if file_format == "excel":
                    try:
                        import pandas as _pd
                        import re as _re
                        import io as _io
                        df_head = _pd.read_excel(_io.BytesIO(doc.file_data), header=None, nrows=5)
                        _month_map = {
                            'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
                            'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12,
                        }
                        for _, hrow in df_head.iterrows():
                            for cell in hrow:
                                if cell and 'Period' in str(cell):
                                    m = _re.search(r'(\w{3})\s+(\d{4})', str(cell))
                                    if m:
                                        mn = _month_map.get(m.group(1)[:3], 1)
                                        yr = int(m.group(2))
                                        extracted_result['period_start'] = f"{yr}-{mn:02d}-01"
                                        logger.info(f"T12 period start extracted: {extracted_result['period_start']}")
                                    break
                    except Exception as _e:
                        logger.warning(f"Could not extract T12 period start: {_e}")

            # ------ OM / other — 1 Claude call each ------
            else:
                extracted_result = await extract(doc.document_type, text)
                model_used = extracted_result.pop("_model_used", "claude-sonnet-4-6")

            # --- Save Extraction record ---
            confidence_scores = extracted_result.get("confidence_scores", {})
            session.add(Extraction(
                id=uuid.uuid4(),
                document_id=document_id,
                deal_id=deal_id,
                document_type=doc.document_type,
                extracted_data=extracted_result,
                confidence_scores=confidence_scores,
                claude_model_used=model_used,
                created_at=datetime.now(timezone.utc),
            ))
            await session.flush()

            # --- Build / update model snapshot ---
            deal = await session.get(Deal, deal_id)

            if doc.document_type == "t12" and classification_session_obj:
                # T12: rebuild snapshot from session items via repopulate_model
                await repopulate_model(deal_id, session, user_id)
            else:
                # Rent roll / OM / other: use the simple extraction-based builder
                extractions_result = await session.execute(
                    select(Extraction).where(Extraction.deal_id == deal_id)
                )
                all_extractions = extractions_result.scalars().all()
                rr_data = t12_data = om_data = conflict_data = None
                for ext in all_extractions:
                    if ext.document_type == "rent_roll":
                        rr_data = ext.extracted_data
                    elif ext.document_type == "t12":
                        t12_data = ext.extracted_data
                    elif ext.document_type == "om":
                        om_data = ext.extracted_data

                if rr_data and t12_data and om_data:
                    try:
                        conflict_data = await detect_conflicts(rr_data, t12_data, om_data)
                    except Exception as e:
                        logger.warning(f"Conflict detection failed: {e}")

                cell_mapping = DEFAULT_CELL_MAPPING
                if deal and deal.active_template_id:
                    tmpl = await session.get(Template, deal.active_template_id)
                    if tmpl and tmpl.cell_mapping:
                        cell_mapping = tmpl.cell_mapping

                luckysheet_json = build_luckysheet_json(rr_data, t12_data, om_data, cell_mapping)

                await session.execute(
                    update(ModelSnapshot)
                    .where(ModelSnapshot.deal_id == deal_id, ModelSnapshot.is_active == True)
                    .values(is_active=False)
                )
                session.add(ModelSnapshot(
                    id=uuid.uuid4(),
                    deal_id=deal_id,
                    snapshot_name=f"Auto-generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                    luckysheet_json=luckysheet_json,
                    template_id=deal.active_template_id if deal else None,
                    created_at=datetime.now(timezone.utc),
                    created_by=user_id,
                    is_active=True,
                ))

            await session.flush()

            # --- Flags ---
            # conflict_data is only computed in the non-T12 path; default to None for T12
            _conflict_data = locals().get("conflict_data")
            await create_flags_from_extraction(
                session, deal_id, document_id,
                doc.document_type, extracted_result, _conflict_data,
            )

            # --- Expense comp (built from classification items for T12) ---
            if doc.document_type == "t12" and deal:
                try:
                    classified_for_comp = []
                    if classification_session_obj:
                        from models.classification import ClassificationSessionItem
                        items_res = await session.execute(
                            select(ClassificationSessionItem)
                            .where(ClassificationSessionItem.session_id == classification_session_obj.id)
                        )
                        classified_for_comp = [
                            {'category': i.final_category, 'trailing_total': i.trailing_total}
                            for i in items_res.scalars().all()
                        ]
                    await _build_deal_expense_comp(
                        deal=deal,
                        classified_items=classified_for_comp,
                        session=session,
                        uploaded_by=user_id,
                        tenant_id=user_id,
                    )
                except Exception as e:
                    logger.warning(f"Expense comp build failed: {e}")

            doc.extraction_status = "complete"
            if deal:
                deal.last_updated = datetime.now(timezone.utc)

            await session.commit()
            logger.info(f"Document {document_id} processed successfully")

        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
            try:
                async with async_session_maker() as err_session:
                    err_doc = await err_session.get(Document, document_id)
                    if err_doc:
                        err_doc.extraction_status = "failed"
                        err_doc.extraction_error = str(e)[:500]
                        await err_session.commit()
            except Exception as inner_e:
                logger.error(f"Failed to update error status: {inner_e}")
