import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from models.flag import Flag

logger = logging.getLogger(__name__)

CRITICAL_FIELDS = {"total_units", "occupancy_rate", "current_noi", "asking_price", "effective_gross_income"}


async def create_flags_from_extraction(
    session: AsyncSession,
    deal_id: uuid.UUID,
    document_id: uuid.UUID,
    document_type: str,
    extracted_data: dict,
    conflict_data: dict | None = None,
) -> list[Flag]:
    """Create flag records from extraction results."""
    flags = []
    now = datetime.now(timezone.utc)

    # Tab mapping
    tab_map = {"rent_roll": "Rent Roll", "t12": "T-12", "om": "Summary", "other": "Summary"}
    tab_name = tab_map.get(document_type, "Summary")

    confidence_scores = extracted_data.get("confidence_scores", {})

    # Missing field flags
    key_fields = _get_key_fields(document_type)
    for field_name in key_fields:
        value = extracted_data.get(field_name)
        if value is None:
            severity = "critical" if field_name in CRITICAL_FIELDS else "warning"
            flag = Flag(
                id=uuid.uuid4(),
                deal_id=deal_id,
                document_id=document_id,
                tab_name=tab_name,
                cell_address=_field_to_cell(field_name, document_type),
                field_name=field_name,
                flag_type="missing",
                description=f"Field '{field_name}' could not be extracted from the {document_type} document.",
                severity=severity,
                created_at=now,
            )
            session.add(flag)
            flags.append(flag)

    # Low confidence flags
    for field_name, score in confidence_scores.items():
        try:
            score_val = float(score)
        except (ValueError, TypeError):
            continue
        if score_val < 0.7:
            flag = Flag(
                id=uuid.uuid4(),
                deal_id=deal_id,
                document_id=document_id,
                tab_name=tab_name,
                cell_address=_field_to_cell(field_name, document_type),
                field_name=field_name,
                flag_type="low_confidence",
                description=f"Low confidence ({score_val:.0%}) for field '{field_name}'. Manual verification recommended.",
                severity="info",
                created_at=now,
            )
            session.add(flag)
            flags.append(flag)

    # Unusual value flags from extraction
    for extraction_flag in extracted_data.get("flags", []):
        ef_field = extraction_flag.get("field", "unknown")
        ef_issue = extraction_flag.get("issue", "")
        ef_severity = extraction_flag.get("severity", "info")
        if ef_severity not in ("critical", "warning", "info"):
            ef_severity = "info"
        flag = Flag(
            id=uuid.uuid4(),
            deal_id=deal_id,
            document_id=document_id,
            tab_name=tab_name,
            cell_address=_field_to_cell(ef_field, document_type),
            field_name=ef_field,
            flag_type="unusual",
            description=ef_issue,
            severity=ef_severity,
            created_at=now,
        )
        session.add(flag)
        flags.append(flag)

    # Conflict flags
    if conflict_data:
        for conflict in conflict_data.get("conflicts", []):
            c_severity = conflict.get("severity", "warning")
            if c_severity not in ("critical", "warning", "info"):
                c_severity = "warning"
            flag = Flag(
                id=uuid.uuid4(),
                deal_id=deal_id,
                document_id=None,
                tab_name="Summary",
                cell_address=_field_to_cell(conflict.get("field", "unknown"), "summary"),
                field_name=conflict.get("field", "unknown"),
                flag_type="conflict",
                description=conflict.get("description", "Data conflict detected between documents."),
                severity=c_severity,
                source_a_label=conflict.get("source_a_label"),
                source_a_value=str(conflict.get("source_a_value", "")),
                source_b_label=conflict.get("source_b_label"),
                source_b_value=str(conflict.get("source_b_value", "")),
                created_at=now,
            )
            session.add(flag)
            flags.append(flag)

    await session.flush()
    return flags


def _get_key_fields(document_type: str) -> list[str]:
    """Get the key fields to check for missing values based on document type."""
    if document_type == "rent_roll":
        return ["total_units", "occupied_units", "occupancy_rate", "avg_current_rent", "avg_market_rent"]
    elif document_type == "t12":
        return ["period_start", "period_end"]
    elif document_type == "om":
        return ["property_name", "total_units", "asking_price", "current_occupancy", "current_noi", "cap_rate_in_place"]
    return []


def _field_to_cell(field_name: str, document_type: str) -> str:
    """Map a field name to an approximate cell address."""
    cell_map = {
        "property_name": "B2",
        "total_units": "B6",
        "occupancy_rate": "B3",
        "avg_current_rent": "B4",
        "avg_market_rent": "B5",
        "current_noi": "B12",
        "asking_price": "B10",
        "cap_rate_in_place": "B13",
        "current_occupancy": "B11",
        "income_data": "B5",
        "expense_data": "B31",
        "noi_accuracy": "B33",
        "period_coverage": "B1",
        "rent_data": "E8",
        "unit_mix_completeness": "A8",
    }
    return cell_map.get(field_name, "A1")
