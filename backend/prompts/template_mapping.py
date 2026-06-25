SYSTEM = """You are a real estate financial modeling expert. Analyze Excel template structure and suggest cell mappings for populating it with multifamily underwriting data. Return only valid JSON."""

SCHEMA = """Return JSON with this exact structure:
{
  "cell_mapping": {
    "summary": {
      "property_name": {"tab": "string", "cell": "string"},
      "address": {"tab": "string", "cell": "string"},
      "total_units": {"tab": "string", "cell": "string"},
      "asking_price": {"tab": "string", "cell": "string"},
      "current_occupancy": {"tab": "string", "cell": "string"},
      "current_noi": {"tab": "string", "cell": "string"},
      "cap_rate_in_place": {"tab": "string", "cell": "string"}
    },
    "rent_roll": {
      "occupancy_rate": {"tab": "string", "cell": "string"},
      "avg_current_rent": {"tab": "string", "cell": "string"},
      "avg_market_rent": {"tab": "string", "cell": "string"}
    },
    "t12": {
      "tab": "string",
      "rows": {}
    }
  },
  "notes": "string",
  "unmapped_sheets": ["string"]
}"""


def build_prompt(sheet_structure: dict) -> str:
    import json
    return f"""Analyze this Excel template structure and suggest cell mappings:

{json.dumps(sheet_structure, indent=2)}

{SCHEMA}"""
