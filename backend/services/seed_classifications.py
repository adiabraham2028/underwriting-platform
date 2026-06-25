import re

THE_21_CATEGORIES = [
    "MarketRent", "LTL", "Vacancy", "Concessions", "BadDebt",
    "RUBSInc", "RetailInc", "OtherInc",
    "Payroll", "MgmtFee", "Landscaping", "Repairs", "Turnover",
    "Utilities", "SecurityLife", "Advert", "Admin",
    "Insurance", "PropTax", "MiscExp", "CapEx",
]


def normalize(s: str) -> str:
    """Collapse whitespace, lowercase, strip. Apply to BOTH seed keys AND incoming names."""
    return re.sub(r'\s+', ' ', str(s).lower().strip())


# ---------------------------------------------------------------------------
# GL code → category (CONAM GL format — exact match, zero Claude needed)
# ---------------------------------------------------------------------------

SEED_GL: dict[str, str] = {
    "40000-1000": "MarketRent",
    "40000-1100": "LTL",
    "41000-1798": "SKIP",        # BASE SCHEDULED RENT — subtotal
    "41000-2350": "MarketRent",  # Prior Month Rent Adjustment
    "41000-2400": "Vacancy",
    "41000-2800": "Vacancy",     # Model/Non Revenue Unit
    "41000-2900": "Concessions",
    "41000-4200": "Payroll",     # Employee Unit Loss
    "41000-4300": "Payroll",     # Employee Rent Recovered
    "41000-4500": "BadDebt",     # Write-Off Delinquent Rent
    "41000-4600": "OtherInc",    # Lease Termination
    "41000-5800": "BadDebt",     # Collections/Agency
    "41000-6000": "BadDebt",     # Collections/Resident
    "42100-1000": "OtherInc",    # Carport/Garage/Parking Income
    "42100-1100": "OtherInc",    # Cable TV Reimb
    "42400-1100": "OtherInc",    # Pet Fees
    "42400-1200": "OtherInc",    # Pet Rent
    "42400-1600": "OtherInc",    # Deposits Applied
    "42400-1700": "OtherInc",    # Security Deposits Forfeited
    "42500-1000": "RUBSInc",     # Utility Electric
    "42500-1100": "RUBSInc",     # Utility Gas
    "42500-1400": "RUBSInc",     # Utility Sewer
    "42500-1500": "RUBSInc",     # Utility Trash
    "42500-1600": "RUBSInc",     # Trash Door to Door
    "42500-1700": "RUBSInc",     # Utility Water
    "42500-1900": "RUBSInc",     # Utility Admin
    "42700-2000": "OtherInc",    # Application Fee
    "42700-3100": "OtherInc",    # Late Fees
    "42700-3300": "OtherInc",    # Legal Fees
    "42700-3800": "OtherInc",    # Non Refundable Fee
    "42700-3900": "OtherInc",    # NSF Fees
    "42700-4000": "OtherInc",    # Misc Fee Income
    "42700-4200": "OtherInc",    # Renters Insurance income
    "42800-1000": "OtherInc",    # Interest Income
    # Payroll
    "50000-1000": "Payroll", "50000-1500": "Payroll",
    "51500-0000": "Payroll", "51500-1500": "Payroll",
    "51600-0000": "Payroll", "51600-1500": "Payroll",
    "53100-0000": "Payroll", "53100-1500": "Payroll",
    "53700-0000": "Payroll", "54020-0000": "Payroll",
    "54150-0000": "Payroll", "54170-0000": "Payroll",
    "54171-0000": "Payroll", "54500-0000": "Payroll",
    "56000-1200": "Payroll", "56000-1900": "Payroll",
    "56000-2000": "Payroll", "56000-2100": "Payroll",
    "56000-2600": "Payroll", "56000-2700": "Payroll",
    "56000-2800": "Payroll", "56000-2900": "Payroll",
    "56000-3200": "Payroll",
    # Advertising
    "57000-1009": "Advert", "57000-1010": "Advert",
    "57000-1030": "Advert", "57000-1210": "Advert",
    "57000-1230": "Advert", "57000-1300": "Advert",
    "57000-1610": "Advert", "57000-1900": "Advert",
    "57000-2200": "Advert", "57000-2300": "Advert",
    "57000-3000": "Advert", "57000-3500": "Advert",
    "57800-1000": "MgmtFee",
    # Admin
    "58010-1400": "Admin", "58010-1900": "Admin",
    "58010-2200": "Admin", "58010-2400": "Admin",
    "58010-2600": "Admin", "58010-2700": "Admin",
    "58010-3000": "Admin", "58010-3100": "Admin",
    "58010-3400": "Admin", "58020-1000": "Admin",
    "58020-1200": "Admin", "58030-1100": "Admin",
    "58040-1200": "Admin", "58040-2100": "Admin",
    "58040-2400": "Admin", "58040-2600": "Admin",
    "58040-3000": "Admin", "58060-2000": "Admin",
    "58060-2100": "Admin", "58060-2400": "Admin",
    "58070-1000": "Admin", "58070-1200": "Admin",
    "58070-1600": "Admin", "58070-2100": "Admin",
    "58070-2200": "Admin", "58070-2400": "Admin",
    "58070-2800": "Admin", "58120-1000": "Admin",
    # Utilities
    "60000-1000": "Utilities", "60000-1100": "Utilities",
    "60000-1400": "Utilities", "60000-1500": "Utilities",
    "60000-1700": "Utilities", "60000-1701": "Utilities",
    "60000-1900": "Utilities", "60000-3600": "Utilities",
    "60000-3800": "Utilities", "60000-4000": "Utilities",
    # Repairs
    "61000-1300": "Repairs", "61000-3300": "Repairs",
    "61000-3800": "Repairs", "61000-4000": "Repairs",
    "61000-4700": "Repairs", "61000-5500": "Repairs",
    "61000-6900": "Repairs", "61000-7600": "Repairs",
    "61000-7800": "Repairs", "61000-8000": "Repairs",
    "61000-8100": "Repairs", "61000-9300": "Repairs",
    "61000-9800": "Repairs",
    # Turnover
    "62000-1000": "Turnover", "62000-2000": "Turnover",
    "62000-2400": "Turnover", "62000-2700": "Turnover",
    "62000-2800": "Turnover", "62000-3000": "Turnover",
    "62000-3100": "Turnover",
    "63000-1000": "Landscaping",
    "64000-1300": "SecurityLife", "64000-1400": "SecurityLife",
    "65000-4000": "Insurance",
    "66000-1000": "Admin",
    "66000-1200": "PropTax", "66000-1500": "PropTax",
    # CapEx
    "80000-1600": "CapEx", "80000-2800": "CapEx",
    "80000-4000": "CapEx", "80000-5100": "CapEx",
    "81000-1000": "CapEx", "81000-1100": "CapEx",
    "81000-1600": "CapEx", "81000-2300": "CapEx",
    "81000-3300": "CapEx", "81000-4000": "CapEx",
    "81000-6900": "CapEx", "83000-1600": "CapEx",
    "83000-2500": "CapEx", "83000-3300": "CapEx",
    "83000-4100": "CapEx", "83000-4600": "CapEx",
    "83000-5000": "CapEx", "83000-6100": "CapEx",
    "83000-7000": "CapEx", "83000-7200": "CapEx",
    "83000-8200": "CapEx",
    # Below-NOI items — skip
    "70000-1000": "SKIP",   # Mortgage interest
    "73180-1100": "SKIP",   # Tax prep
    "73280-1000": "SKIP",   # Franchise tax
    "73290-1000": "SKIP",   # Travel
}

# ---------------------------------------------------------------------------
# Name-based lookup (external / broker format)
# Keys are pre-normalized at module load — no double-space mismatches.
# ---------------------------------------------------------------------------

_RAW_SEED_NAMES: dict[str, str] = {
    "gross potential market rent": "MarketRent",
    "market rent": "MarketRent",
    "gain (loss) to lease": "LTL",
    "loss/gain to lease": "LTL",
    "loss to lease": "LTL",
    "vacancy loss": "Vacancy",
    "vacancy": "Vacancy",
    "model apartment": "Vacancy",
    "model/non revenue unit": "Vacancy",
    "employee apartments": "Payroll",
    "employee unit loss": "Payroll",
    "employee rent recovered": "Payroll",
    "concessions - new": "Concessions",
    "concessions - one time": "Concessions",
    "rent concessions": "Concessions",
    "concessions": "Concessions",
    "bad debt expense": "BadDebt",
    "write-off delinquent rent": "BadDebt",
    "collections/agency": "BadDebt",
    "collections/resident": "BadDebt",
    "prior month rent adjustment": "MarketRent",
    "lease termination": "OtherInc",
    "termination / cancellation fee income - residential": "OtherInc",
    "application fee income": "OtherInc",
    "cable fees income": "OtherInc",
    "clubhouse income": "OtherInc",
    "damages/cleaning fee income": "OtherInc",
    "keys/locks/card income": "OtherInc",
    "late fee income": "OtherInc",
    "oth inc-late fees": "OtherInc",
    "nsf fee income - residential": "OtherInc",
    "parking/garage/carport income": "OtherInc",
    "carport/garage/parking income": "OtherInc",
    "pet fee income": "OtherInc",
    "pet fees": "OtherInc",
    "pet rent": "OtherInc",
    "redecorating fee income": "OtherInc",
    "transfer fee income": "OtherInc",
    "convenience fee - residential": "OtherInc",
    "miscellaneous income": "OtherInc",
    "concierge service income": "OtherInc",
    "security deposits forfeited": "OtherInc",
    "deposits applied to cancelled m/i": "OtherInc",
    "oth inc-non refundable fee": "OtherInc",
    "oth inc-nsf fees": "OtherInc",
    "oth inc-misc fee income": "OtherInc",
    "oth inc-renters insurance": "OtherInc",
    "oth inc-interest income": "OtherInc",
    "oth inc-legal fees": "OtherInc",
    "oth inc-credit check/application fee": "OtherInc",
    "tenant billback income": "RUBSInc",
    "trash removal fee income": "RUBSInc",
    "utility - electricity income": "RUBSInc",
    "utility - water income": "RUBSInc",
    "utility - sewer income": "RUBSInc",
    "oth inc-utility-sewer": "RUBSInc",
    "oth inc-utility-trash": "RUBSInc",
    "oth inc-trash-door to door": "RUBSInc",
    "oth inc-utility-water": "RUBSInc",
    "oth inc-utility-electric only": "RUBSInc",
    "oth inc-utility-gas only": "RUBSInc",
    "oth inc-utility-admin": "RUBSInc",
    "property management fees": "MgmtFee",
    "fee exp-management fee": "MgmtFee",
    "landscape interior - contract": "Landscaping",
    "landscape interior- supplies": "Landscaping",
    "r & m-landscape contract": "Landscaping",
    "security patrol/courtesy officer": "SecurityLife",
    "fire protection": "SecurityLife",
    "sec-safety/fire prevention": "SecurityLife",
    "sec-security patrol": "SecurityLife",
    "property casualty insurance": "Insurance",
    "ins - property and casualty": "Insurance",
    "property taxes": "PropTax",
    "taxes-real estate": "PropTax",
    "taxes licenses & other": "Admin",
    "taxes-consultant service": "Admin",
    "marketing expense": "Advert",
    "tenant functions": "Advert",
    "property website & online presence": "Advert",
    "social media": "Advert",
    "bank fees": "Admin",
    "legal fees": "Admin",
    "professional & consulting fees": "Admin",
    "miscellaneous general & administrative expenses": "Admin",
    "office & common area phone/cable/internet": "Admin",
    "cellular phones": "Admin",
    "uniform rental / purchase": "Admin",
    "resident screening": "Admin",
    "resident payment processing equip/fees (cc / ach)": "Admin",
    "software and technology expense": "Admin",
    "training software/tools": "Admin",
    "invoice processing": "Admin",
    "shopping reports": "Admin",
    "ownership software/platform expenses": "Admin",
    "bi/performance/market analytics": "Admin",
    "electric - clubhouse": "Utilities",
    "electricity - interior": "Utilities",
    "gas & fuel - club house": "Utilities",
    "gas & fuel - common": "Utilities",
    "sewer": "Utilities",
    "water": "Utilities",
    "trash removal": "Utilities",
    "swimming pool maintenance & supplies": "Repairs",
    "pest control/extermination contract services": "Repairs",
    "janitorial/cleaning common area": "Repairs",
    "miscellaneous r & m": "Repairs",
    "appliance - other appliances r & m": "Repairs",
    "door/lock/key/card expenses": "Repairs",
    "electric r & m": "Repairs",
    "floor covering - carpet r & m": "Repairs",
    "hvac - supplies/repairs": "Repairs",
    "interior building r & m - operating supplies": "Repairs",
    "painting - exterior": "Repairs",
    "plumbing r & m": "Repairs",
    "roofing r & m": "Repairs",
    "tools": "Repairs",
    "wallcovering r & m": "Repairs",
    "window/glass r & m": "Repairs",
    "appliance repairs/accessories": "Repairs",
    "window repair / blinds": "Repairs",
    "keys / locks / door hardware": "Repairs",
    "electrical/plumbing/hardware fixtures & supplies unit interiors": "Turnover",
    "tub/shower resurfacing/repairs": "Turnover",
    "401k contributions": "Payroll",
    "bonus - manager": "Payroll",
    "bonus - leasing": "Payroll",
    "bonus - maintenance staff": "Payroll",
    "workers comp insurance": "Payroll",
    "administrative staff - benefits/taxes": "Payroll",
    "building manager - salaries": "Payroll",
    "building manager - benefits/taxes": "Payroll",
    "maintenance staff - salaries": "Payroll",
    "maintenance staff - benefits/taxes": "Payroll",
    "leasing agents - salaries": "Payroll",
    "other staff - benefits/taxes": "Payroll",
    "carpet cleaning": "Turnover",
    "flooring repair": "Turnover",
    "painting / wall repair unit interiors": "Turnover",
    "janitorial/cleaning unit interiors": "Turnover",
    "other makeready expenses": "Turnover",
    "painting - interior": "Turnover",
}

# Pre-normalize all keys at module load — eliminates double-space mismatches
SEED_NAMES: dict[str, str] = {normalize(k): v for k, v in _RAW_SEED_NAMES.items()}

# GL code regex pattern
import re as _re
GL_CODE = _re.compile(r'^\d{5}-\d{4}$')


def classify_by_gl(account_code: str) -> str | None:
    """Return category, 'SKIP', or None (unknown code)."""
    return SEED_GL.get(str(account_code).strip())


def classify_by_name(line_item_name: str) -> str | None:
    """Return category or None (unknown name)."""
    return SEED_NAMES.get(normalize(line_item_name))
