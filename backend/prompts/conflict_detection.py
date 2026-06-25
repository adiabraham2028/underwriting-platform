SYSTEM = """You are a multifamily real estate analyst performing data quality analysis. You will be given extracted data from multiple documents for the same property. Identify conflicts, inconsistencies, and provide reconciliation recommendations. Return only valid JSON."""

SCHEMA = """Return JSON with this exact structure:
{
  "conflicts": [
    {
      "field": "string",
      "severity": "critical|warning|info",
      "description": "string",
      "source_a_label": "string",
      "source_a_value": "string",
      "source_b_label": "string",
      "source_b_value": "string",
      "recommended_value": "string|null",
      "recommendation_rationale": "string"
    }
  ],
  "reconciliation_notes": "string",
  "recommended_values": {
    "total_units": "value|null",
    "occupancy_rate": "value|null",
    "current_noi": "value|null",
    "asking_price": "value|null"
  },
  "overall_data_quality": "high|medium|low",
  "data_quality_notes": "string"
}"""


def build_prompt(rent_roll_data: dict, t12_data: dict, om_data: dict) -> str:
    import json
    content = f"""Analyze conflicts between these three data sources for the same property:

RENT ROLL EXTRACTION:
{json.dumps(rent_roll_data, indent=2)}

T-12 OPERATING STATEMENT EXTRACTION:
{json.dumps(t12_data, indent=2)}

OFFERING MEMORANDUM EXTRACTION:
{json.dumps(om_data, indent=2)}

{SCHEMA}"""
    return content
