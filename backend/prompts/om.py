SYSTEM = """You are a multifamily real estate analyst. Extract structured data from Offering Memorandums (OM). Return only valid JSON matching the schema exactly. Use null for any field you cannot determine."""

SCHEMA = """Return JSON with this exact structure:
{
  "property_name": "string|null",
  "address": "string|null",
  "city": "string|null",
  "state": "string|null",
  "zip_code": "string|null",
  "year_built": "integer|null",
  "total_units": "integer|null",
  "total_sf": "float|null",
  "avg_unit_sf": "float|null",
  "asking_price": "float|null",
  "price_per_unit": "float|null",
  "price_per_sf": "float|null",
  "cap_rate_in_place": "float 0-1|null",
  "cap_rate_proforma": "float 0-1|null",
  "current_occupancy": "float 0-1|null",
  "current_noi": "float|null",
  "proforma_noi": "float|null",
  "current_egi": "float|null",
  "current_expenses": "float|null",
  "unit_mix": [
    {
      "type": "string",
      "units": "integer",
      "avg_sf": "float|null",
      "avg_market_rent": "float|null"
    }
  ],
  "investment_highlights": ["string"],
  "seller_assumptions": {
    "vacancy_rate": "float 0-1|null",
    "management_fee_pct": "float 0-1|null",
    "expense_ratio": "float 0-1|null",
    "rent_growth": "float 0-1|null",
    "exit_cap_rate": "float 0-1|null"
  },
  "amenities": ["string"],
  "recent_renovations": "string|null",
  "flags": [{"field": "string", "issue": "string", "severity": "critical|warning|info"}],
  "confidence_scores": {
    "pricing": "0.0-1.0",
    "financials": "0.0-1.0",
    "unit_mix": "0.0-1.0",
    "property_details": "0.0-1.0"
  }
}"""


def build_prompt(document_text: str) -> str:
    return f"{SCHEMA}\n\nDocument:\n{document_text}"
