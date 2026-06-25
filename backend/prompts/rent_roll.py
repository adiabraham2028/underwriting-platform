SYSTEM = """You are a multifamily real estate analyst. Extract structured data from rent roll documents. Return only valid JSON matching the schema exactly. Use null for any field you cannot determine."""

SCHEMA = """Return JSON with this exact structure:
{
  "property_name": "string|null",
  "total_units": "integer|null",
  "occupied_units": "integer|null",
  "occupancy_rate": "float 0-1|null",
  "avg_current_rent": "float|null",
  "avg_market_rent": "float|null",
  "total_current_monthly_income": "float|null",
  "total_market_monthly_income": "float|null",
  "loss_to_lease": "float|null",
  "unit_mix": [
    {
      "unit_number": "string",
      "beds": "float",
      "baths": "float",
      "sf": "float|null",
      "current_rent": "float|null",
      "market_rent": "float|null",
      "lease_start": "YYYY-MM-DD|null",
      "lease_end": "YYYY-MM-DD|null",
      "tenant_name": "string|null",
      "status": "occupied|vacant|notice|model|down",
      "renovation_status": "unrenovated|partial|renovated|null"
    }
  ],
  "ancillary_income": {
    "parking": "float|null",
    "laundry": "float|null",
    "pets": "float|null",
    "storage": "float|null",
    "rubs": "float|null",
    "late_fees": "float|null",
    "other": "float|null"
  },
  "flags": [{"field": "string", "issue": "string", "severity": "critical|warning|info"}],
  "confidence_scores": {
    "total_units": "0.0-1.0",
    "occupancy_rate": "0.0-1.0",
    "unit_mix_completeness": "0.0-1.0",
    "rent_data": "0.0-1.0"
  }
}"""


def build_prompt(document_text: str) -> str:
    return f"{SCHEMA}\n\nDocument:\n{document_text}"
