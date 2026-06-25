#!/usr/bin/env python3
"""
Demo data seeder for the underwriting platform.
Run manually: docker compose exec backend python seed_demo_data.py
Or set SEED_DEMO_DATA=true in .env to seed automatically on startup.
"""

import asyncio
import uuid
import logging
from datetime import datetime, timezone, date

from sqlalchemy import select

from database import async_session_maker
from models.user import User
from models.deal import Deal
from models.template import Template
from models.extraction import Extraction
from models.snapshot import ModelSnapshot
from models.flag import Flag

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Luckysheet helpers
# ---------------------------------------------------------------------------

def lc(row: int, col: int, value):
    """Build one Luckysheet celldata entry."""
    t = "n" if isinstance(value, (int, float)) else "s"
    return {
        "r": row, "c": col,
        "v": {"v": value, "m": str(value) if value is not None else "", "ct": {"fa": "General", "t": t}},
    }


def mk_sheet(name: str, idx: int, cells: list, active: bool = False) -> dict:
    return {
        "name": name, "index": str(idx), "order": idx,
        "status": 1 if active else 0, "celldata": cells,
        "config": {}, "scrollLeft": 0, "scrollTop": 0,
        "luckysheet_select_save": [], "calcChain": [],
        "isPivotTable": False, "pivotTable": {}, "filter_select": None, "filter": None,
        "luckysheet_alternateformat_save": [], "luckysheet_alternateformat_save_modelCustom": [],
        "luckysheet_conditionformat_save": {}, "frozen": {}, "chart": [],
        "zoomRatio": 1, "image": [], "showGridLines": 1, "dataVerification": {},
    }


def distribute(annual: float, bumps: list = None) -> list:
    """Spread an annual total across 12 months with slight variation."""
    default = [1.00, 0.97, 1.02, 0.98, 1.01, 1.03, 0.96, 1.04, 0.99, 1.01, 0.98, 1.01]
    factors = bumps or default
    base = annual / 12
    vals = [round(base * f) for f in factors]
    vals[11] = round(annual) - sum(vals[:11])
    return vals


# ---------------------------------------------------------------------------
# Build Luckysheet JSON for a deal
# ---------------------------------------------------------------------------

def build_luckysheet(d: dict) -> dict:
    units = d["total_units"]
    t12a = d["t12_annual"]

    # ---- Summary tab ----
    summary = [
        lc(0, 0, "PROPERTY SUMMARY"),
        lc(1, 0, "Property Name"),        lc(1, 1, d["name"]),
        lc(2, 0, "Address"),              lc(2, 1, d["address"]),
        lc(3, 0, "City/State/Zip"),       lc(3, 1, f"{d['city']}, {d['state']} {d['zip_code']}"),
        lc(5, 0, "Total Units"),          lc(5, 1, units),
        lc(6, 0, "Total SF"),             lc(6, 1, units * d.get("avg_sf", 850)),
        lc(7, 0, "Year Built"),           lc(7, 1, d["year_built"]),
        lc(9, 0, "Asking Price"),         lc(9, 1, d["asking_price"]),
        lc(10, 0, "Current Occupancy"),   lc(10, 1, d["occupancy"]),
        lc(11, 0, "Current NOI"),         lc(11, 1, d["noi"]),
        lc(12, 0, "Cap Rate (In-Place)"), lc(12, 1, d["cap_rate"]),
    ]

    # ---- Rent Roll summary tab ----
    rr = [
        lc(0, 0, "RENT ROLL SUMMARY"),
        lc(2, 0, "Occupancy Rate"),    lc(2, 1, d["occupancy"]),
        lc(3, 0, "Avg Current Rent"),  lc(3, 1, d["avg_current_rent"]),
        lc(4, 0, "Avg Market Rent"),   lc(4, 1, d["avg_market_rent"]),
        lc(6, 0, "Unit #"), lc(6, 1, "Beds"), lc(6, 2, "Baths"), lc(6, 3, "SF"),
        lc(6, 4, "Current Rent"), lc(6, 5, "Market Rent"),
        lc(6, 6, "Lease Start"), lc(6, 7, "Lease End"), lc(6, 8, "Status"),
    ]

    # ---- T-12 tab ----
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    t12_cells = [
        lc(0, 0, "TRAILING 12-MONTH OPERATING STATEMENT"),
        lc(1, 0, "Line Item"),
        *[lc(1, mi + 1, m) for mi, m in enumerate(months)],
        lc(1, 13, "TTM Total"), lc(1, 14, "% of EGI"),
        lc(2, 0, "INCOME"), lc(19, 0, "EXPENSES"),
    ]

    # (row 0-indexed, field_key, label)
    t12_row_defs = [
        (4,  "gross_potential_rent",   "Gross Potential Rent"),
        (5,  "vacancy_loss",           "Vacancy Loss"),
        (6,  "concessions",            "Concessions"),
        (7,  "bad_debt",               "Bad Debt"),
        (9,  "other_income_parking",   "  Parking"),
        (10, "other_income_laundry",   "  Laundry"),
        (11, "other_income_pets",      "  Pets"),
        (12, "other_income_rubs",      "  RUBS"),
        (13, "other_income_storage",   "  Storage"),
        (14, "other_income_late_fees", "  Late Fees"),
        (15, "other_income_misc",      "  Misc Other Income"),
        (17, "effective_gross_income", "Effective Gross Income"),
        (20, "management_fee",         "Management Fee"),
        (21, "taxes",                  "Real Estate Taxes"),
        (22, "insurance",              "Insurance"),
        (23, "repairs_maintenance",    "Repairs & Maintenance"),
        (24, "utilities",              "Utilities"),
        (25, "payroll",               "Payroll"),
        (26, "administrative",        "Administrative"),
        (27, "marketing",             "Marketing"),
        (28, "other_expenses",        "Other Expenses"),
        (30, "total_expenses",        "Total Expenses"),
        (32, "noi",                   "Net Operating Income"),
    ]

    vacancy_bumps = d.get("vacancy_bumps")
    egi_annual = t12a["effective_gross_income"]

    for row_idx, field, label in t12_row_defs:
        t12_cells.append(lc(row_idx, 0, label))
        ann = t12a.get(field, 0) or 0
        if ann == 0:
            continue
        bumps = vacancy_bumps if (field == "vacancy_loss" and vacancy_bumps) else None
        monthly = distribute(ann, bumps)
        for mi, val in enumerate(monthly):
            t12_cells.append(lc(row_idx, mi + 1, val))
        t12_cells.append(lc(row_idx, 13, sum(monthly)))
        if egi_annual > 0 and field != "gross_potential_rent":
            t12_cells.append(lc(row_idx, 14, round(ann / egi_annual, 4)))

    sheets = [
        mk_sheet("Summary",     0, summary, active=True),
        mk_sheet("Rent Roll",   1, rr),
        mk_sheet("T-12",        2, t12_cells),
        mk_sheet("Pro Forma",   3, []),
        mk_sheet("Debt",        4, []),
        mk_sheet("Returns",     5, []),
        mk_sheet("Assumptions", 6, []),
    ]
    return {"sheets": sheets, "info": {"name": "Underwriting Model", "lang": "en"}}


# ---------------------------------------------------------------------------
# Build extraction JSON records for a deal
# ---------------------------------------------------------------------------

def build_rent_roll_extraction(d: dict) -> dict:
    units = d["total_units"]
    occupied = round(units * d["occupancy"])
    return {
        "property_name": d["name"],
        "total_units": units,
        "occupied_units": occupied,
        "occupancy_rate": d["occupancy"],
        "avg_current_rent": d["avg_current_rent"],
        "avg_market_rent": d["avg_market_rent"],
        "total_current_monthly_income": round(occupied * d["avg_current_rent"]),
        "total_market_monthly_income": round(units * d["avg_market_rent"]),
        "loss_to_lease": round(units * (d["avg_market_rent"] - d["avg_current_rent"])),
        "unit_mix": [],
        "ancillary_income": {
            "parking": round(d["t12_annual"].get("other_income_parking", 0) / 12),
            "laundry": round(d["t12_annual"].get("other_income_laundry", 0) / 12),
            "pets":    round(d["t12_annual"].get("other_income_pets", 0) / 12),
            "storage": round(d["t12_annual"].get("other_income_storage", 0) / 12),
            "rubs":    round(d["t12_annual"].get("other_income_rubs", 0) / 12),
            "late_fees": round(d["t12_annual"].get("other_income_late_fees", 0) / 12),
            "other":   round(d["t12_annual"].get("other_income_misc", 0) / 12),
        },
        "flags": [],
        "confidence_scores": {
            "total_units": 0.98, "occupancy_rate": 0.95,
            "unit_mix_completeness": 0.40, "rent_data": 0.93,
        },
    }


def build_t12_extraction(d: dict) -> dict:
    t = d["t12_annual"]
    month_labels = ["2024-01","2024-02","2024-03","2024-04","2024-05","2024-06",
                    "2024-07","2024-08","2024-09","2024-10","2024-11","2024-12"]
    vacancy_bumps = d.get("vacancy_bumps")
    months = []
    for i, label in enumerate(month_labels):
        def mv(field):
            ann = t.get(field, 0) or 0
            bumps = vacancy_bumps if (field == "vacancy_loss" and vacancy_bumps) else None
            return distribute(ann, bumps)[i]
        months.append({
            "month": label,
            "gross_potential_rent": mv("gross_potential_rent"),
            "vacancy_loss": mv("vacancy_loss"),
            "concessions": mv("concessions"),
            "bad_debt": mv("bad_debt"),
            "other_income_parking": mv("other_income_parking"),
            "other_income_laundry": mv("other_income_laundry"),
            "other_income_pets": mv("other_income_pets"),
            "other_income_rubs": mv("other_income_rubs"),
            "other_income_storage": mv("other_income_storage"),
            "other_income_late_fees": mv("other_income_late_fees"),
            "other_income_misc": mv("other_income_misc"),
            "effective_gross_income": mv("effective_gross_income"),
            "management_fee": mv("management_fee"),
            "taxes": mv("taxes"),
            "insurance": mv("insurance"),
            "repairs_maintenance": mv("repairs_maintenance"),
            "utilities": mv("utilities"),
            "payroll": mv("payroll"),
            "administrative": mv("administrative"),
            "marketing": mv("marketing"),
            "other_expenses": mv("other_expenses"),
            "total_expenses": mv("total_expenses"),
            "noi": mv("noi"),
        })
    trailing = {k: t.get(k, 0) for k in [
        "gross_potential_rent","vacancy_loss","concessions","bad_debt",
        "other_income_parking","other_income_laundry","other_income_pets",
        "other_income_rubs","other_income_storage","other_income_late_fees",
        "other_income_misc","effective_gross_income","management_fee","taxes",
        "insurance","repairs_maintenance","utilities","payroll","administrative",
        "marketing","other_expenses","total_expenses","noi",
    ]}
    return {
        "property_name": d["name"],
        "period_start": "2024-01",
        "period_end": "2024-12",
        "months": months,
        "trailing_totals": trailing,
        "flags": [],
        "confidence_scores": {
            "monthly_completeness": 0.97,
            "income_accuracy": 0.92,
            "expense_accuracy": 0.89,
        },
    }


def build_om_extraction(d: dict) -> dict:
    return {
        "property_name": d["name"],
        "address": d["address"],
        "city": d["city"],
        "state": d["state"],
        "zip_code": d["zip_code"],
        "year_built": d["year_built"],
        "year_renovated": d.get("year_renovated"),
        "total_units": d["total_units"],
        "total_sf": d["total_units"] * d.get("avg_sf", 850),
        "property_class": d.get("property_class", "B"),
        "stories": d.get("stories", 3),
        "asking_price": d["asking_price"],
        "price_per_unit": round(d["asking_price"] / d["total_units"]),
        "cap_rate_in_place": d["cap_rate"],
        "cap_rate_proforma": d.get("cap_rate_proforma", round(d["cap_rate"] + 0.005, 4)),
        "current_noi": d["noi"],
        "proforma_noi": round(d["noi"] * 1.12),
        "current_occupancy": d["occupancy"],
        "submarket": d.get("submarket"),
        "investment_highlights": d.get("investment_highlights", []),
        "value_add_thesis": d.get("value_add_thesis"),
        "seller_proforma_assumptions": {
            "market_rent_growth": 0.04,
            "expense_growth": 0.03,
            "stabilized_occupancy": 0.95,
            "exit_cap_rate": round(d["cap_rate"] + 0.0025, 4),
        },
        "amenities": d.get("amenities", ["Pool", "Fitness Center", "Covered Parking"]),
        "flags": [],
        "confidence_scores": {"property_details": 0.96, "financial_data": 0.91},
    }


# ---------------------------------------------------------------------------
# Deal definitions
# ---------------------------------------------------------------------------

DEALS = [
    {
        "name": "The Marlowe",
        "address": "2847 Barton Springs Rd",
        "city": "Austin", "state": "TX", "zip_code": "78704",
        "lat": 30.2529, "lng": -97.7690,
        "total_units": 247, "avg_sf": 862,
        "status": "active",
        "year_built": 1998,
        "property_class": "B",
        "asking_price": 52400000,
        "occupancy": 0.91,
        "avg_current_rent": 1485,
        "avg_market_rent": 1620,
        "noi": 2890000,
        "cap_rate": 0.055,
        "submarket": "South Austin",
        "investment_highlights": [
            "Value-add opportunity with $135/unit rent upside to market",
            "91% occupancy with strong Austin fundamentals",
            "1998 vintage with no recent cap ex — renovation ready",
        ],
        "value_add_thesis": "Interior renovation of 180 unrenovated units targeting $150/unit premium at $8,500/unit cost. Projected stabilized yield on cost of 6.2%.",
        "amenities": ["Resort-style pool", "Fitness center", "Dog park", "Covered parking", "Package lockers"],
        "t12_annual": {
            "gross_potential_rent": 4401540,
            "vacancy_loss": 396139,
            "concessions": 44015, "bad_debt": 22008,
            "other_income_parking": 37000, "other_income_laundry": 18000,
            "other_income_pets": 24750, "other_income_rubs": 0,
            "other_income_storage": 12000, "other_income_late_fees": 7400,
            "other_income_misc": 4500,
            "effective_gross_income": 4043028,
            "management_fee": 202151, "taxes": 280000, "insurance": 98000,
            "repairs_maintenance": 195000, "utilities": 143000,
            "payroll": 125000, "administrative": 55000, "marketing": 30000,
            "other_expenses": 25000, "total_expenses": 1153151, "noi": 2889877,
        },
        # February vacancy spike (bumps: Feb is 1.40x, rest compensate to maintain annual total)
        "vacancy_bumps": [0.97, 1.40, 0.92, 0.95, 0.98, 0.97, 0.96, 0.98, 0.96, 0.97, 0.95, 0.99],
        "flags": [
            {
                "tab_name": "Rent Roll", "cell_address": "H21", "field_name": "Lease End Date — Unit 114",
                "flag_type": "missing", "severity": "critical",
                "description": "Unit 114 is occupied (current rent $1,495/mo) but has no lease end date on record. Cannot verify lease term or upcoming rollover risk.",
            },
            {
                "tab_name": "T-12", "cell_address": "C6", "field_name": "Vacancy Loss — February",
                "flag_type": "conflict", "severity": "critical",
                "description": "February vacancy loss ($52,430) is 40% above the trailing monthly average ($37,512), inconsistent with the rent roll which shows stable 91% occupancy throughout 2024. Possible one-time concession misclassified as vacancy.",
                "source_a_label": "T-12 February Vacancy Loss",
                "source_a_value": "$52,430",
                "source_b_label": "Rent Roll Avg Monthly Vacancy",
                "source_b_value": "$37,512",
            },
            {
                "tab_name": "Summary", "cell_address": "B11", "field_name": "Current Occupancy",
                "flag_type": "low_confidence", "severity": "warning",
                "description": "Occupancy derived from rent roll (91%) cannot be fully reconciled against T-12 EGI — possible 1–2% discrepancy due to timing of move-ins.",
            },
            {
                "tab_name": "T-12", "cell_address": "B21", "field_name": "Management Fee",
                "flag_type": "unusual", "severity": "warning",
                "description": "Management fee is 5.0% of EGI ($202,151). Typical third-party management in Austin for 200+ unit assets runs 4–4.5%. May compress to 4.25% under new ownership.",
            },
            {
                "tab_name": "Rent Roll", "cell_address": "E12", "field_name": "Current Rent — Unit 208",
                "flag_type": "unusual", "severity": "warning",
                "description": "Unit 208 (1BD/1BA, 760SF) is renting at $1,650/mo — $165 above the market rent for comparable units in this building. No renovation flag. Verify lease terms.",
            },
        ],
    },
    {
        "name": "Palomar Ridge",
        "address": "4521 E Thomas Rd",
        "city": "Phoenix", "state": "AZ", "zip_code": "85018",
        "lat": 33.4794, "lng": -111.9861,
        "total_units": 312, "avg_sf": 938,
        "status": "active",
        "year_built": 2004,
        "property_class": "B",
        "asking_price": 74880000,
        "occupancy": 0.94,
        "avg_current_rent": 1720,
        "avg_market_rent": 1810,
        "noi": 4120000,
        "cap_rate": 0.055,
        "submarket": "Arcadia/Scottsdale Corridor",
        "investment_highlights": [
            "Light value-add in high-demand Arcadia submarket",
            "94% occupancy with 85% of units unrenovated",
            "2004 vintage — strong bones, manageable cap ex",
        ],
        "value_add_thesis": "Interior renovation of 265 unrenovated units at $7,000/unit targeting $90/mo rent premium. 18-month execution timeline.",
        "amenities": ["Heated pool", "Spa", "Fitness center", "Business center", "Gated access", "EV charging"],
        "t12_annual": {
            "gross_potential_rent": 6439680,
            "vacancy_loss": 386381, "concessions": 32198, "bad_debt": 16099,
            "other_income_parking": 72000, "other_income_laundry": 24000,
            "other_income_pets": 48000, "other_income_rubs": 0,
            "other_income_storage": 20000, "other_income_late_fees": 20000,
            "other_income_misc": 16000,
            "effective_gross_income": 6205002,
            "management_fee": 310250, "taxes": 490000, "insurance": 155000,
            "repairs_maintenance": 310000, "utilities": 200000,
            "payroll": 180000, "administrative": 80000, "marketing": 45000,
            "other_expenses": 315000, "total_expenses": 2085250, "noi": 4119752,
        },
        "flags": [
            {
                "tab_name": "Summary", "cell_address": "B13", "field_name": "Cap Rate — Conflict",
                "flag_type": "conflict", "severity": "critical",
                "description": "OM states in-place cap rate of 5.8%, but extracted NOI ($4,119,752) divided by asking price ($74,880,000) equals 5.50%. Seller may be using proforma NOI or a different expense load.",
                "source_a_label": "OM Stated Cap Rate",
                "source_a_value": "5.80%",
                "source_b_label": "Calculated Cap Rate (NOI ÷ Price)",
                "source_b_value": "5.50%",
            },
            {
                "tab_name": "T-12", "cell_address": "B29", "field_name": "Other Expenses",
                "flag_type": "unusual", "severity": "warning",
                "description": "Other expenses line ($315,000) is unusually high at 5.1% of EGI. No breakout provided. Request seller schedule for detail.",
            },
            {
                "tab_name": "T-12", "cell_address": "N31", "field_name": "Expense Ratio",
                "flag_type": "unusual", "severity": "warning",
                "description": "Trailing 12 expense ratio of 33.6% is within normal range but at the low end for a 2004 Phoenix asset. Confirm taxes reflect current assessed value post-sale.",
            },
        ],
    },
    {
        "name": "Vantage at Midtown",
        "address": "870 Peachtree St NE",
        "city": "Atlanta", "state": "GA", "zip_code": "30308",
        "lat": 33.7836, "lng": -84.3825,
        "total_units": 188, "avg_sf": 1020,
        "status": "active",
        "year_built": 2016,
        "property_class": "A",
        "asking_price": 61100000,
        "occupancy": 0.89,
        "avg_current_rent": 2140,
        "avg_market_rent": 2290,
        "noi": 2750000,
        "cap_rate": 0.045,
        "submarket": "Midtown Atlanta",
        "investment_highlights": [
            "Class A 2016 construction in walkable Midtown submarket",
            "Strong employment demand drivers — Midtown tech corridor",
            "$150/unit loss to lease opportunity",
        ],
        "value_add_thesis": "Lease-up of current 89% occupancy to 95% stabilized, targeting natural rent growth as leases roll.",
        "amenities": ["Rooftop pool", "Co-working lounge", "Concierge", "Parking garage", "Bike storage", "Dog run"],
        "t12_annual": {
            "gross_potential_rent": 4827840,
            "vacancy_loss": 530962, "concessions": 48278, "bad_debt": 24139,
            "other_income_parking": 48000, "other_income_laundry": 0,
            "other_income_pets": 28200, "other_income_rubs": 0,
            "other_income_storage": 18800, "other_income_late_fees": 14100,
            "other_income_misc": 10900,
            "effective_gross_income": 4344461,
            "management_fee": 217223, "taxes": 450000, "insurance": 125000,
            "repairs_maintenance": 250000, "utilities": 165000,
            "payroll": 175000, "administrative": 75000, "marketing": 50000,
            "other_expenses": 87238, "total_expenses": 1594461, "noi": 2750000,
        },
        "flags": [
            {
                "tab_name": "Rent Roll", "cell_address": "I9", "field_name": "Model Units",
                "flag_type": "unusual", "severity": "warning",
                "description": "3 units (101, 215, 318) are listed as 'model' status — unusually high for a 188-unit Class A property. These units generate zero income. Confirm whether all 3 are necessary for leasing operations.",
            },
        ],
    },
    {
        "name": "Creekside Commons",
        "address": "3200 Downing St",
        "city": "Denver", "state": "CO", "zip_code": "80205",
        "lat": 39.7580, "lng": -104.9697,
        "total_units": 156, "avg_sf": 748,
        "status": "active",
        "year_built": 1987,
        "property_class": "B",
        "asking_price": 31200000,
        "occupancy": 0.84,
        "avg_current_rent": 1290,
        "avg_market_rent": 1580,
        "noi": 1480000,
        "cap_rate": 0.0475,
        "submarket": "Five Points / Curtis Park",
        "investment_highlights": [
            "Heavy value-add in emerging Five Points neighborhood",
            "$290/unit rent-to-market gap — significant upside",
            "Priced at $200k/unit with potential to stabilize at 6.5%+ yield",
        ],
        "value_add_thesis": "Full interior renovation of 130 units at $12,000/unit targeting $300/mo premium. Exterior upgrade, new leasing office, and dog park.",
        "amenities": ["Laundry facility", "Surface parking", "Community room"],
        "t12_annual": {
            "gross_potential_rent": 2413680,
            # T-12 implies 19% vacancy (vs. 16% on rent roll) — conflict flag
            "vacancy_loss": 458599,
            "concessions": 36205, "bad_debt": 24137,
            "other_income_parking": 18720, "other_income_laundry": 24960,
            "other_income_pets": 9360, "other_income_rubs": 0,
            "other_income_storage": 7800, "other_income_late_fees": 6240,
            "other_income_misc": 2920,
            "effective_gross_income": 1964739,
            "management_fee": 98237, "taxes": 135000, "insurance": 52000,
            "repairs_maintenance": 93600, "utilities": 62000,
            "payroll": 40000, "administrative": 22000, "marketing": 10000,
            "other_expenses": 32243, "total_expenses": 545080, "noi": 1419659,
        },
        "flags": [
            {
                "tab_name": "Summary", "cell_address": "B11", "field_name": "Occupancy Conflict",
                "flag_type": "conflict", "severity": "critical",
                "description": "Rent roll shows 84% occupancy (25 vacant units), but T-12 income data implies a 19% effective vacancy rate based on GPR vs. collected rents. Difference is $61,257 in annualized income. Request clarification from seller.",
                "source_a_label": "Rent Roll Occupancy",
                "source_a_value": "84% (25 vacant)",
                "source_b_label": "T-12 Implied Effective Vacancy",
                "source_b_value": "19.0% of GPR",
            },
            {
                "tab_name": "Rent Roll", "cell_address": "E18", "field_name": "Below-Market Rents",
                "flag_type": "conflict", "severity": "critical",
                "description": "4 units (103, 107, 209, 214) have current rents more than 30% below market with no renovation or income-restricted flag. Units range $890–$970/mo vs. $1,580 market. Verify lease terms and any regulatory restrictions.",
                "source_a_label": "Units 103/107/209/214 Avg Rent",
                "source_a_value": "$935/mo",
                "source_b_label": "Market Rent (1BD comp)",
                "source_b_value": "$1,580/mo",
            },
            {
                "tab_name": "T-12", "cell_address": "B23", "field_name": "Insurance Expense",
                "flag_type": "conflict", "severity": "critical",
                "description": "Insurance expense of $52,000 ($333/unit) is approximately 40% above Denver market comp for comparable 1987-vintage assets ($237/unit). Request current policy and renewal quotes.",
                "source_a_label": "Reported Insurance (T-12)",
                "source_a_value": "$52,000 ($333/unit)",
                "source_b_label": "Denver Market Comp (1980s vintage)",
                "source_b_value": "$37,000 ($237/unit)",
            },
            {
                "tab_name": "T-12", "cell_address": "N33", "field_name": "T-12 NOI vs. Stated NOI",
                "flag_type": "conflict", "severity": "warning",
                "description": "T-12 trailing NOI ($1,419,659) is $60,341 below the seller-stated NOI of $1,480,000 in the OM. Discrepancy likely tied to occupancy conflict. Underwrite to T-12 actual.",
                "source_a_label": "Seller OM NOI",
                "source_a_value": "$1,480,000",
                "source_b_label": "T-12 Extracted NOI",
                "source_b_value": "$1,419,659",
            },
            {
                "tab_name": "Rent Roll", "cell_address": "B3", "field_name": "Occupancy Rate",
                "flag_type": "low_confidence", "severity": "warning",
                "description": "Occupancy rate extracted from rent roll (84%) conflicts with T-12 implied vacancy. Model uses rent roll as primary source. Review actual unit status before finalizing underwriting.",
            },
            {
                "tab_name": "T-12", "cell_address": "B27", "field_name": "Administrative Expenses",
                "flag_type": "unusual", "severity": "warning",
                "description": "Administrative expense of $22,000 appears low for a heavy value-add repositioning. Budget should include legal, accounting, and compliance costs during renovation.",
            },
            {
                "tab_name": "Summary", "cell_address": "B12", "field_name": "Cap Rate vs. Price",
                "flag_type": "low_confidence", "severity": "warning",
                "description": "Stated 4.75% cap rate is calculated on OM NOI of $1,480,000. Using T-12 actual NOI of $1,419,659, the in-place cap rate is 4.55%. Significant execution risk in renovation thesis.",
            },
        ],
    },
    {
        "name": "The Heron",
        "address": "1001 Water St",
        "city": "Tampa", "state": "FL", "zip_code": "33602",
        "lat": 27.9428, "lng": -82.4574,
        "total_units": 204, "avg_sf": 1105,
        "status": "archived",
        "year_built": 2019,
        "property_class": "A",
        "asking_price": 85680000,
        "occupancy": 0.96,
        "avg_current_rent": 2580,
        "avg_market_rent": 2650,
        "noi": 3850000,
        "cap_rate": 0.045,
        "submarket": "Downtown Tampa / Water Street",
        "investment_highlights": [
            "Newly constructed 2019 Class A in the Water Street master-planned development",
            "96% occupancy with minimal near-term cap ex",
            "Strong institutional-quality asset in high-growth submarket",
        ],
        "value_add_thesis": None,
        "amenities": ["Rooftop pool & lounge", "Concierge", "Co-working space", "Valet parking", "Spa", "Wine storage"],
        "t12_annual": {
            "gross_potential_rent": 6315840,
            "vacancy_loss": 252634, "concessions": 63158, "bad_debt": 31579,
            "other_income_parking": 73440, "other_income_laundry": 0,
            "other_income_pets": 36720, "other_income_rubs": 0,
            "other_income_storage": 30600, "other_income_late_fees": 24480,
            "other_income_misc": 14700,
            "effective_gross_income": 6148409,
            "management_fee": 245936, "taxes": 580000, "insurance": 165000,
            "repairs_maintenance": 367200, "utilities": 210000,
            "payroll": 280000, "administrative": 130000, "marketing": 80000,
            "other_expenses": 240333, "total_expenses": 2298469, "noi": 3849940,
        },
        "flags": [
            {
                "tab_name": "Summary", "cell_address": "B10", "field_name": "Occupancy Verification",
                "flag_type": "low_confidence", "severity": "info",
                "description": "Occupancy of 96% extracted from rent roll. Could not be cross-verified against T-12 (document only) — no discrepancy identified, low confidence due to single data source.",
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Main seeder
# ---------------------------------------------------------------------------

async def seed_demo_data():
    """Seed 5 demo deals into the database. Skips if deals already exist."""
    async with async_session_maker() as session:
        existing = await session.execute(select(Deal).limit(1))
        if existing.scalar_one_or_none():
            logger.info("Demo data already exists — skipping seed")
            return

        # Fetch admin user and default template
        admin_result = await session.execute(select(User).where(User.role == "admin").limit(1))
        admin = admin_result.scalar_one_or_none()
        if not admin:
            logger.warning("No admin user found — cannot seed demo data")
            return

        tmpl_result = await session.execute(select(Template).where(Template.is_default == True).limit(1))
        template = tmpl_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        for i, d in enumerate(DEALS):
            deal_id = uuid.uuid4()
            template_id = template.id if template else None

            # -- Deal record --
            deal = Deal(
                id=deal_id,
                name=d["name"],
                address=d["address"],
                city=d["city"],
                state=d["state"],
                zip_code=d["zip_code"],
                lat=d["lat"],
                lng=d["lng"],
                total_units=d["total_units"],
                status=d["status"],
                active_template_id=template_id,
                template_outdated=False,
                created_at=now,
                created_by=admin.id,
                last_updated=now,
            )
            session.add(deal)

            # -- Extraction records (3 per deal) --
            rr_ext_id = uuid.uuid4()
            t12_ext_id = uuid.uuid4()
            om_ext_id = uuid.uuid4()

            for ext_id, doc_type, extracted in [
                (rr_ext_id,  "rent_roll", build_rent_roll_extraction(d)),
                (t12_ext_id, "t12",       build_t12_extraction(d)),
                (om_ext_id,  "om",        build_om_extraction(d)),
            ]:
                session.add(Extraction(
                    id=ext_id,
                    document_id=None,
                    deal_id=deal_id,
                    document_type=doc_type,
                    extracted_data=extracted,
                    confidence_scores=extracted.get("confidence_scores", {}),
                    claude_model_used="claude-sonnet-4-6",
                    created_at=now,
                ))

            # -- Model snapshot --
            luckysheet_json = build_luckysheet(d)
            session.add(ModelSnapshot(
                id=uuid.uuid4(),
                deal_id=deal_id,
                snapshot_name="Initial Model — Demo Data",
                luckysheet_json=luckysheet_json,
                template_id=template_id,
                template_version=template.version if template else 1,
                created_at=now,
                created_by=admin.id,
                is_active=True,
            ))

            # -- Flags --
            for f in d["flags"]:
                session.add(Flag(
                    id=uuid.uuid4(),
                    deal_id=deal_id,
                    document_id=None,
                    tab_name=f["tab_name"],
                    cell_address=f["cell_address"],
                    field_name=f["field_name"],
                    flag_type=f["flag_type"],
                    description=f["description"],
                    severity=f["severity"],
                    source_a_label=f.get("source_a_label"),
                    source_a_value=f.get("source_a_value"),
                    source_b_label=f.get("source_b_label"),
                    source_b_value=f.get("source_b_value"),
                    resolved=False,
                    created_at=now,
                ))

            logger.info(f"Seeded deal: {d['name']}")

        await session.commit()
        logger.info("Demo data seeded successfully — 5 deals created")


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_demo_data())
