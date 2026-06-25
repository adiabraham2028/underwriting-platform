SYSTEM = """You are a multifamily real estate analyst assistant. Help users find and compare deals based on their natural language queries. Return only valid JSON."""

SCHEMA = """Return JSON with this exact structure:
{
  "search_interpretation": "string describing what the user is looking for",
  "filters": {
    "states": ["string"],
    "min_units": "integer|null",
    "max_units": "integer|null",
    "status": "active|archived|closed|null",
    "keywords": ["string"]
  },
  "ranked_deal_ids": ["uuid strings in order of relevance"],
  "explanation": "string explaining the ranking logic"
}"""


def build_prompt(query: str, deals_context: list) -> str:
    import json
    return f"""User query: {query}

Available deals:
{json.dumps(deals_context, indent=2)}

{SCHEMA}"""
