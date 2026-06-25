import re
import uuid
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# Maps classification category names → legacy T12 field names used in DEFAULT_CELL_MAPPING
CATEGORY_TO_FIELD: dict[str, str] = {
    "MarketRent":   "gross_potential_rent",
    "LTL":          "loss_to_lease",
    "Vacancy":      "vacancy_loss",
    "Concessions":  "concessions",
    "BadDebt":      "bad_debt",
    "RUBSInc":      "rubs_income",
    "RetailInc":    "retail_income",
    "OtherInc":     "other_income",
    "Payroll":      "payroll",
    "MgmtFee":      "management_fee",
    "Landscaping":  "landscaping",
    "Repairs":      "repairs_maintenance",
    "Turnover":     "maintenance_turnover",
    "Utilities":    "utilities",
    "SecurityLife": "security_life_safety",
    "Advert":       "advertising",
    "Admin":        "admin_other",
    "Insurance":    "insurance",
    "PropTax":      "property_taxes",
    "MiscExp":      "misc_expense",
    "CapEx":        "cap_replacement",
}

FIELD_TO_CATEGORY: dict[str, str] = {v: k for k, v in CATEGORY_TO_FIELD.items()}

INCOME_CATS = ["MarketRent", "LTL", "Vacancy", "Concessions", "BadDebt",
               "RUBSInc", "RetailInc", "OtherInc"]
EXPENSE_CATS = ["Payroll", "MgmtFee", "Landscaping", "Repairs", "Turnover",
                "Utilities", "SecurityLife", "Advert", "Admin",
                "Insurance", "PropTax", "CapEx"]

DEFAULT_CELL_MAPPING = {
    "summary": {
        "property_name":    {"tab": "Summary", "cell": "B2"},
        "address":          {"tab": "Summary", "cell": "B3"},
        "city_state_zip":   {"tab": "Summary", "cell": "B4"},
        "total_units":      {"tab": "Summary", "cell": "B6"},
        "total_sf":         {"tab": "Summary", "cell": "B7"},
        "year_built":       {"tab": "Summary", "cell": "B8"},
        "asking_price":     {"tab": "Summary", "cell": "B10"},
        "current_occupancy":{"tab": "Summary", "cell": "B11"},
        "current_noi":      {"tab": "Summary", "cell": "B12"},
        "cap_rate_in_place":{"tab": "Summary", "cell": "B13"},
    },
    "rent_roll": {
        "occupancy_rate":  {"tab": "Rent Roll", "cell": "B3"},
        "avg_current_rent":{"tab": "Rent Roll", "cell": "B4"},
        "avg_market_rent": {"tab": "Rent Roll", "cell": "B5"},
        "unit_table": {
            "tab": "Rent Roll",
            "start_row": 8,
            "columns": {
                "unit_number": "A", "beds": "B", "baths": "C",
                "sf": "D", "current_rent": "E", "market_rent": "F",
                "lease_start": "G", "lease_end": "H", "status": "I",
            },
        },
    },
    "t12": {
        "tab": "T-12",
        "month_columns": ["B","C","D","E","F","G","H","I","J","K","L","M"],
        "trailing_col": "N",
        "rows": {
            "gross_potential_rent": 5, "vacancy_loss": 6,
            "concessions": 7, "bad_debt": 8,
            "other_income_parking": 10, "other_income_laundry": 11,
            "other_income_pets": 12, "other_income_rubs": 13,
            "other_income_storage": 14, "other_income_late_fees": 15,
            "other_income_misc": 16, "effective_gross_income": 18,
            "management_fee": 21, "taxes": 22, "insurance": 23,
            "repairs_maintenance": 24, "utilities": 25, "payroll": 26,
            "administrative": 27, "marketing": 28, "other_expenses": 29,
            "total_expenses": 31, "noi": 33,
        },
    },
}


def cell_to_rc(cell_address: str) -> tuple[int, int]:
    match = re.match(r"([A-Z]+)(\d+)", cell_address.upper())
    if not match:
        raise ValueError(f"Invalid cell address: {cell_address}")
    col_str, row_str = match.groups()
    col = sum((ord(c) - ord("A") + 1) * (26**i) for i, c in enumerate(reversed(col_str))) - 1
    row = int(row_str) - 1
    return row, col


def col_letter_to_idx(col_letter: str) -> int:
    col_letter = col_letter.upper()
    return sum((ord(c) - ord("A") + 1) * (26**i) for i, c in enumerate(reversed(col_letter))) - 1


def make_cell_entry(row: int, col: int, value: Any) -> dict:
    ct_type = "n" if isinstance(value, (int, float)) else "s"
    str_value = str(value) if value is not None else ""
    return {"r": row, "c": col,
            "v": {"v": value, "m": str_value, "ct": {"fa": "General", "t": ct_type}}}


def build_luckysheet_json(
    rent_roll_data: dict | None,
    t12_data: dict | None,
    om_data: dict | None,
    cell_mapping: dict | None = None,
) -> dict:
    """Build Luckysheet JSON from extracted data.

    Handles both old field-name keys (gross_potential_rent, vacancy_loss …)
    and new category-name keys (MarketRent, Vacancy …) in trailing_totals.
    """
    mapping = cell_mapping or DEFAULT_CELL_MAPPING
    tab_cells: dict[str, list[dict]] = {}

    def add_cell(tab: str, cell_addr: str, value: Any):
        if value is None:
            return
        if tab not in tab_cells:
            tab_cells[tab] = []
        row, col = cell_to_rc(cell_addr)
        tab_cells[tab].append(make_cell_entry(row, col, value))

    rr = rent_roll_data or {}
    t12 = t12_data or {}
    om = om_data or {}

    # Helper: look up a value from trailing_totals trying category name first,
    # then legacy field name, so both old and new data structures work.
    trailing = t12.get("trailing_totals", {})

    def get_cat(cat_name: str, field_name: str = None) -> float:
        v = trailing.get(cat_name)
        if v is not None:
            return v
        if field_name:
            v = trailing.get(field_name)
            if v is not None:
                return v
        return 0

    # Compute NOI dynamically from category sums (avoids key mismatch)
    total_income   = sum(get_cat(c) for c in INCOME_CATS)
    total_expenses = sum(get_cat(c) for c in EXPENSE_CATS)
    computed_noi   = total_income - total_expenses

    # ---- Summary tab ----
    summary_map = mapping.get("summary", {})

    def sm(field, default_cell):
        return (summary_map.get(field, {}).get("tab", "Summary"),
                summary_map.get(field, {}).get("cell", default_cell))

    add_cell(*sm("property_name", "B2"), om.get("property_name") or rr.get("property_name"))
    add_cell(*sm("address", "B3"),       om.get("address"))

    city, state, zip_c = om.get("city",""), om.get("state",""), om.get("zip_code","")
    csz = f"{city}, {state} {zip_c}".strip(", ") if any([city, state, zip_c]) else None
    add_cell(*sm("city_state_zip", "B4"), csz)

    add_cell(*sm("total_units",       "B6"),  rr.get("total_units") or om.get("total_units"))
    add_cell(*sm("total_sf",          "B7"),  om.get("total_sf"))
    add_cell(*sm("year_built",        "B8"),  om.get("year_built"))
    add_cell(*sm("asking_price",      "B10"), om.get("asking_price"))
    add_cell(*sm("current_occupancy", "B11"), rr.get("occupancy_rate") or om.get("current_occupancy"))

    # NOI: prefer dynamically computed from classifications; fall back to OM
    noi_val = computed_noi if computed_noi != 0 else (
        get_cat("noi", "noi") or om.get("current_noi")
    )
    add_cell(*sm("current_noi",       "B12"), noi_val)
    add_cell(*sm("cap_rate_in_place", "B13"), om.get("cap_rate_in_place"))

    # ---- Rent Roll tab ----
    rr_map   = mapping.get("rent_roll", {})
    rr_tab   = rr_map.get("occupancy_rate", {}).get("tab", "Rent Roll")
    add_cell(rr_tab, rr_map.get("occupancy_rate",   {}).get("cell", "B3"), rr.get("occupancy_rate"))
    add_cell(rr_tab, rr_map.get("avg_current_rent", {}).get("cell", "B4"), rr.get("avg_current_rent"))
    add_cell(rr_tab, rr_map.get("avg_market_rent",  {}).get("cell", "B5"), rr.get("avg_market_rent"))

    unit_table = rr_map.get("unit_table", {})
    unit_tab   = unit_table.get("tab", "Rent Roll")
    start_row  = unit_table.get("start_row", 8)
    col_map    = unit_table.get("columns", {})
    for i, unit in enumerate(rr.get("unit_mix", [])):
        row_idx = start_row - 1 + i
        for field, col_letter in col_map.items():
            val = unit.get(field)
            if val is not None:
                col_idx = col_letter_to_idx(col_letter)
                if unit_tab not in tab_cells:
                    tab_cells[unit_tab] = []
                tab_cells[unit_tab].append(make_cell_entry(row_idx, col_idx, val))

    # ---- T-12 tab ----
    t12_map      = mapping.get("t12", {})
    t12_tab      = t12_map.get("tab", "T-12")
    t12_rows     = t12_map.get("rows", {})
    month_cols   = t12_map.get("month_columns", ["B","C","D","E","F","G","H","I","J","K","L","M"])
    trailing_col = t12_map.get("trailing_col", "N")

    if t12_tab not in tab_cells:
        tab_cells[t12_tab] = []

    # --- Write individual line item rows if the new data structure is available ---
    line_items  = t12.get("line_items", [])
    month_labels = t12.get("month_labels", [])

    DATA_START_ROW = 7  # row 8 in Excel (0-indexed = 7)

    if line_items:
        for i, item in enumerate(line_items):
            row_idx = DATA_START_ROW + i
            # Column A — line item name
            tab_cells[t12_tab].append(
                {"r": row_idx, "c": 0,
                 "v": {"v": item["name"], "m": item["name"], "ct": {"fa": "@", "t": "s"}}}
            )
            # Columns B-M — monthly values
            for col_offset, month in enumerate(month_labels[:12]):
                val = item["monthly_values"].get(month, 0) or 0
                tab_cells[t12_tab].append(
                    {"r": row_idx, "c": 1 + col_offset,
                     "v": {"v": val, "m": str(val), "ct": {"fa": "#,##0.00", "t": "n"}}}
                )
            # Column N — trailing total
            tab_cells[t12_tab].append(
                {"r": row_idx, "c": 13,
                 "v": {"v": item["trailing_total"], "m": str(item["trailing_total"]),
                       "ct": {"fa": "#,##0.00", "t": "n"}}}
            )
            # Column O — Assignment (category name — template SUMIF formulas aggregate on this)
            tab_cells[t12_tab].append(
                {"r": row_idx, "c": 14,
                 "v": {"v": item["category"], "m": item["category"], "ct": {"fa": "@", "t": "s"}}}
            )

    # --- Also write summary/total cells using the cell_mapping rows ---
    # This populates the default template's fixed-row structure as a fallback
    # and fills any summary cells the template has.

    # Monthly data: try new category-keyed months list first
    months = t12.get("months", [])
    for mi, month_data in enumerate(months[:12]):
        col_letter = month_cols[mi] if mi < len(month_cols) else None
        if not col_letter:
            continue
        col_idx = col_letter_to_idx(col_letter)
        for field, row_num in t12_rows.items():
            # Try category name first (new pipeline), then field name (old pipeline)
            cat = FIELD_TO_CATEGORY.get(field)
            val = (month_data.get(cat) if cat else None) or month_data.get(field)
            if val is not None and not line_items:  # don't double-write if individual rows written
                tab_cells[t12_tab].append(make_cell_entry(row_num - 1, col_idx, val))

    # Trailing totals in the summary rows
    trailing_col_idx = col_letter_to_idx(trailing_col)
    for field, row_num in t12_rows.items():
        if field == "noi":
            val = computed_noi if computed_noi != 0 else None
        else:
            cat = FIELD_TO_CATEGORY.get(field)
            val = (trailing.get(cat) if cat else None) or trailing.get(field)
        if val is not None and not line_items:
            tab_cells[t12_tab].append(make_cell_entry(row_num - 1, trailing_col_idx, val))

    # ---- Build sheet list ----
    ordered_tabs = ["Summary", "Rent Roll", "T-12", "Pro Forma", "Debt", "Returns", "Assumptions"]
    extra = [t for t in tab_cells if t not in ordered_tabs]
    for t in extra:
        ordered_tabs.append(t)

    sheets = []
    for idx, tab_name in enumerate(ordered_tabs):
        sheets.append({
            "name": tab_name, "index": str(idx), "order": idx,
            "status": 1 if idx == 0 else 0,
            "celldata": tab_cells.get(tab_name, []),
            "config": {}, "scrollLeft": 0, "scrollTop": 0,
            "luckysheet_select_save": [], "calcChain": [],
            "isPivotTable": False, "pivotTable": {}, "filter_select": None,
            "filter": None, "luckysheet_alternateformat_save": [],
            "luckysheet_alternateformat_save_modelCustom": [],
            "luckysheet_conditionformat_save": {}, "frozen": {},
            "chart": [], "zoomRatio": 1, "image": [],
            "showGridLines": 1, "dataVerification": {},
        })

    return {"sheets": sheets, "info": {"name": "Underwriting Model", "lang": "en"}}


# ---------------------------------------------------------------------------
# Build t12_data from ClassificationSessionItem ORM objects
# ---------------------------------------------------------------------------

def build_t12_extraction_from_session(session_items, month_labels: list[str]) -> dict:
    """
    Convert ClassificationSessionItem ORM objects into the t12_data structure
    expected by build_luckysheet_json().

    Returns a dict with:
      trailing_totals    — {category: annual_total}
      monthly_by_category — {category: {month_label: value}}
      months             — [{month: label, Category: value, …}, …]
      line_items         — [{name, account_code, category, monthly_values, trailing_total}, …]
      month_labels       — ordered list of month strings
    """
    trailing_totals: dict[str, float] = defaultdict(float)
    monthly_by_cat: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    line_items_out = []

    for item in sorted(session_items, key=lambda x: x.display_order):
        cat = item.final_category
        if not cat or cat == "SKIP":
            continue
        total = float(item.trailing_total or 0)
        trailing_totals[cat] += total
        mv = item.monthly_values or {}
        for month, val in mv.items():
            monthly_by_cat[cat][month] += float(val or 0)
        line_items_out.append({
            "name": item.line_item_name,
            "account_code": item.account_code,
            "category": cat,
            "monthly_values": mv,
            "trailing_total": total,
        })

    # Build months list — one dict per month with category values
    months = []
    for label in month_labels:
        month_dict: dict = {"month": label}
        for cat, mv in monthly_by_cat.items():
            month_dict[cat] = mv.get(label, 0)
        months.append(month_dict)

    return {
        "trailing_totals": dict(trailing_totals),
        "monthly_by_category": {k: dict(v) for k, v in monthly_by_cat.items()},
        "months": months,
        "line_items": line_items_out,
        "month_labels": month_labels,
    }


# ---------------------------------------------------------------------------
# repopulate_model — rebuild snapshot from current session items
# ---------------------------------------------------------------------------

async def repopulate_model(
    deal_id: uuid.UUID,
    db,             # AsyncSession
    user_id: uuid.UUID,
) -> None:
    """Rebuild the active model snapshot from the latest classification session items.

    Called both from process_document() (after T12 upload) and from
    approve_session() (after analyst approves/corrects classifications).
    """
    from sqlalchemy import select, update
    from models.deal import Deal
    from models.template import Template
    from models.snapshot import ModelSnapshot
    from models.classification import ClassificationSession, ClassificationSessionItem
    from models.extraction import Extraction

    # Get deal
    deal = await db.get(Deal, deal_id)
    if not deal:
        logger.warning(f"repopulate_model: deal {deal_id} not found")
        return

    # Latest classification session for this deal
    sess_result = await db.execute(
        select(ClassificationSession)
        .where(ClassificationSession.deal_id == deal_id)
        .order_by(ClassificationSession.created_at.desc())
        .limit(1)
    )
    cls_session = sess_result.scalar_one_or_none()
    if not cls_session:
        logger.warning(f"repopulate_model: no classification session for deal {deal_id}")
        return

    # Session items ordered by display_order
    items_result = await db.execute(
        select(ClassificationSessionItem)
        .where(ClassificationSessionItem.session_id == cls_session.id)
        .order_by(ClassificationSessionItem.display_order)
    )
    session_items = items_result.scalars().all()

    # Extract month labels from first item with monthly data
    month_labels: list[str] = []
    for item in session_items:
        mv = item.monthly_values or {}
        if mv:
            month_labels = list(mv.keys())
            break

    t12_data = build_t12_extraction_from_session(session_items, month_labels)

    # Rent roll extraction (most recent)
    rr_result = await db.execute(
        select(Extraction)
        .where(Extraction.deal_id == deal_id, Extraction.document_type == "rent_roll")
        .order_by(Extraction.created_at.desc())
        .limit(1)
    )
    rr_ext = rr_result.scalar_one_or_none()
    rr_data = rr_ext.extracted_data if rr_ext else {}

    # Cell mapping
    cell_mapping = None
    if deal.active_template_id:
        tmpl = await db.get(Template, deal.active_template_id)
        if tmpl and tmpl.cell_mapping:
            cell_mapping = tmpl.cell_mapping

    luckysheet_json = build_luckysheet_json(
        rent_roll_data=rr_data,
        t12_data=t12_data,
        om_data={},
        cell_mapping=cell_mapping,
    )

    # Deactivate old active snapshot
    await db.execute(
        update(ModelSnapshot)
        .where(ModelSnapshot.deal_id == deal_id, ModelSnapshot.is_active == True)
        .values(is_active=False)
    )

    db.add(ModelSnapshot(
        id=uuid.uuid4(),
        deal_id=deal_id,
        snapshot_name="Classification Applied",
        luckysheet_json=luckysheet_json,
        template_id=deal.active_template_id,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        created_by=user_id,
        is_active=True,
    ))

    logger.info(f"repopulate_model: new snapshot created for deal {deal_id}, "
                f"{len(session_items)} line items, {len(t12_data['line_items'])} non-SKIP")
