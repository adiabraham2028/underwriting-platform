"""
General-purpose rent roll parser that handles any input format.

Detection order:
  1. CONAM Excel → local parser (0 Claude calls)
  2. Other Excel  → Claude extraction
  3. PDF digital  → text extraction → Claude
  4. PDF scanned  → OCR → Claude
"""

import re
import logging
from io import BytesIO

logger = logging.getLogger(__name__)

CLAUDE_RR_SYSTEM = (
    "You are a real estate analyst parsing a rent roll. "
    "Extract all unit data. Return ONLY valid JSON matching the "
    "schema exactly. Use null for missing values."
)

CLAUDE_RR_SCHEMA = """
{
  "unit_mix": [
    {
      "unit_number": "string",
      "unit_type": "raw code from document or bed/bath label",
      "beds": 1.0,
      "baths": 1.0,
      "sf": 742.0,
      "base_rent": 1615.0,
      "market_rent": 1703.0,
      "move_in": "YYYY-MM-DD or null",
      "lease_expiration": "YYYY-MM-DD or null",
      "status": "occupied|vacant|notice|model",
      "charges": {
        "RENT": 1615.0,
        "GARAGE": 150.0
      }
    }
  ]
}

Rules:
- One dict per unit (not per charge row)
- beds/baths: parse from unit type code or column headers
- status: normalize to occupied/vacant/notice/model
- charges: all charge types found for this unit as a dict
- base_rent: the RENT charge amount, not market rent
- If the document shows individual charge rows per unit,
  aggregate them into the charges dict for that unit
"""


def _is_pdf(filename: str, file_bytes: bytes) -> bool:
    return filename.lower().endswith('.pdf') or file_bytes[:4] == b'%PDF'


def _is_conam_excel(file_bytes: bytes) -> bool:
    """Detect CONAM rent roll by scanning the first 40 rows for CONAM patterns."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True, read_only=True)
        ws = wb.active
        text_parts = []
        for row in ws.iter_rows(max_row=40, values_only=True):
            for cell in row:
                if cell is not None:
                    text_parts.append(str(cell))
        text = ' '.join(text_parts)

        # CONAM GL unit type pattern: G followed by digits, underscore, digits, letters
        if re.search(r'G\d+_\d+[A-Z]+', text):
            return True
        # CONAM header keywords
        if 'Charge' in text and 'Amount' in text:
            return True
        # CONAM column headers
        if 'Market' in text and 'Rent' in text and ('Move' in text or 'Lease' in text):
            return True
        return False
    except Exception:
        return False


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Try digital PDF text extraction; fall back to OCR for scanned pages."""
    text = ""
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text()
    except Exception as e:
        logger.warning(f"PyMuPDF extraction failed: {e}")

    if len(text.strip()) < 200:
        try:
            from pdf2image import convert_from_bytes
            import pytesseract
            images = convert_from_bytes(file_bytes, dpi=200)
            for img in images:
                text += pytesseract.image_to_string(img)
        except Exception as e:
            logger.warning(f"OCR fallback failed: {e}")

    return text


def _excel_to_text(file_bytes: bytes) -> str:
    """Convert Excel sheets to a plain-text representation for Claude."""
    try:
        import pandas as pd
        xl = pd.ExcelFile(BytesIO(file_bytes))
        parts = []
        for sheet in xl.sheet_names[:3]:
            df = xl.parse(sheet, header=None, nrows=300)
            parts.append(f"--- Sheet: {sheet} ---")
            parts.append(df.to_string(max_rows=200))
        return "\n".join(parts)
    except Exception as e:
        return f"Could not parse Excel: {e}"


def _build_summary(unit_mix: list) -> dict:
    """Compute standard summary stats from a unit_mix list."""
    total    = len(unit_mix)
    occupied = sum(1 for u in unit_mix if u.get('status') == 'occupied')
    rents    = [u['base_rent']    for u in unit_mix if u.get('base_rent')]
    mkt      = [u['market_rent']  for u in unit_mix if u.get('market_rent')]
    return {
        "total_units":      total,
        "occupied_units":   occupied,
        "occupancy_rate":   occupied / total if total else 0,
        "avg_current_rent": sum(rents) / len(rents) if rents else 0,
        "avg_market_rent":  sum(mkt)   / len(mkt)   if mkt   else 0,
        "unit_mix":         unit_mix,
    }


async def parse_rent_roll_any_format(
    file_bytes: bytes,
    filename: str,
    llm_service,
    conam_parser_fn,
) -> dict:
    """
    Parse any rent roll format and return a standard rr_data dict.

    - CONAM Excel: local parser, 0 Claude calls
    - Other Excel / PDF: one batched Claude call on truncated text
    """

    # 1. CONAM Excel — local parser, never falls back to Claude
    if not _is_pdf(filename, file_bytes) and _is_conam_excel(file_bytes):
        try:
            summary = conam_parser_fn(file_bytes)  # returns summary dict directly
            logger.info(f"Rent roll: CONAM local parse → {summary.get('total_units', 0)} units (0 Claude calls)")
            return summary
        except Exception as e:
            logger.error(f"CONAM parser failed: {e}", exc_info=True)
            # Do NOT fall back to Claude — CONAM is fully handled locally.
            # Surface the real error so it's visible in the DB.
            return {
                "total_units": 0,
                "unit_mix":    [],
                "error":       f"CONAM parser error: {str(e)}",
                "format":      "conam_gl",
            }

    # 2–4. PDF or non-CONAM Excel → Claude
    if _is_pdf(filename, file_bytes):
        raw_text   = _extract_pdf_text(file_bytes)
        doc_content = raw_text[:5000]
        source_label = "PDF rent roll"
    else:
        doc_content  = _excel_to_text(file_bytes)[:5000]
        source_label = "Excel rent roll"

    content = f"""Parse this {source_label} and extract all unit data.

{doc_content}

Return ONLY this JSON structure:
{CLAUDE_RR_SCHEMA}
"""
    try:
        result   = await llm_service.complete_json_with_retry(
            CLAUDE_RR_SYSTEM, content, max_tokens=4096
        )
        unit_mix = result.get('unit_mix', [])
        summary  = _build_summary(unit_mix)
        logger.info(f"Rent roll: Claude parse → {summary.get('total_units', 0)} units")
        return summary
    except Exception as e:
        logger.error(f"Claude rent roll parse failed: {e}")
        return {
            "total_units": 0,
            "unit_mix":    [],
            "error":       str(e),
        }
