import logging
from services.llm_service import llm
import prompts.om as om_prompt
import prompts.conflict_detection as conflict_prompt

logger = logging.getLogger(__name__)

MODEL_USED = "claude-sonnet-4-6"

# ~20k characters ≈ ~5k tokens; leaves room under the 30k/min limit
_MAX_TEXT_CHARS = 20_000


def _truncate(text: str, max_chars: int = _MAX_TEXT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    logger.warning(f"Truncating document text from {len(text)} to {max_chars} chars before sending to Claude")
    return text[:max_chars]


async def extract(document_type: str, text: str) -> dict:
    """Extract structured data from document text using LLM.

    Only called for OM and 'other' documents — rent roll and T12 are
    handled locally without Claude (see document_processor.py).
    """
    truncated = _truncate(text)

    if document_type == "om":
        system = om_prompt.SYSTEM
        user = om_prompt.build_prompt(truncated)
    else:
        system = "You are a real estate document analyst. Extract any relevant financial or property data. Return only valid JSON."
        user = f"Extract all relevant data from this document:\n\n{truncated}\n\nReturn JSON with keys for any data found."

    result = await llm.complete_json_with_retry(system, user, max_tokens=2048)
    result["_model_used"] = MODEL_USED
    return result


async def detect_conflicts(rent_roll_data: dict, t12_data: dict, om_data: dict) -> dict:
    """Run conflict detection across all three document types."""
    import json

    # Summarise each dataset down to key fields before sending to Claude
    def _summarise(data: dict, keys: list) -> dict:
        return {k: data.get(k) for k in keys if k in data}

    rr_summary = _summarise(rent_roll_data, [
        'total_units', 'occupied_units', 'occupancy_rate',
        'avg_current_rent', 'avg_market_rent',
    ])
    t12_summary = _summarise(t12_data, ['trailing_totals', 'classified_items_count'])
    om_summary = _summarise(om_data, [
        'total_units', 'current_occupancy', 'asking_price',
        'cap_rate_in_place', 'current_noi', 'year_built',
    ])

    system = conflict_prompt.SYSTEM
    user = (
        f"RENT ROLL SUMMARY:\n{json.dumps(rr_summary, indent=2)}\n\n"
        f"T12 SUMMARY:\n{json.dumps(t12_summary, indent=2)}\n\n"
        f"OM SUMMARY:\n{json.dumps(om_summary, indent=2)}\n\n"
        "Identify conflicts between these three data sources. Return only valid JSON."
    )
    return await llm.complete_json_with_retry(system, user, max_tokens=1024)
