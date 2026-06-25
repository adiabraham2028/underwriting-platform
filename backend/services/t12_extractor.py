import re
import math

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

CONAM_SUBTOTAL = re.compile(r'^\d{5}-(9999|9998|9997)$')
GL_CODE_RE     = re.compile(r'^\d{5}-\d{4}$')


def parse_numeric(s: str) -> float:
    try:
        return float(str(s).replace(',', '').replace('(', '-').replace(')', '').strip() or 0)
    except Exception:
        return 0.0


def should_skip_row(code: str, name: str, total) -> bool:
    """Single skip predicate for all T12 formats — no keyword lists."""
    # Section headers have no total value
    if total is None or (isinstance(total, float) and math.isnan(total)):
        return True
    # CONAM subtotal GL codes (9999 / 9998 / 9997)
    if CONAM_SUBTOTAL.match(str(code).strip()):
        return True
    # Generic subtotal / net rows
    n = str(name).strip().upper()
    if n.startswith('TOTAL ') or n.startswith('NET '):
        return True
    return False


# Kept for backward compat with classification_service.py
def should_skip_conam_gl(code: str, name: str, total) -> bool:
    return should_skip_row(code, name, total)

def should_skip_generic(name: str, total) -> bool:
    return should_skip_row('', name, total)

def is_header_row(name: str) -> bool:
    n = str(name).strip().upper()
    return n.startswith('TOTAL ') or n.startswith('NET ')


def extract_t12_line_items(text: str, source_format: str) -> list[dict]:
    if source_format == 'conam_gl':
        return _extract_conam_gl(text)
    else:
        return _extract_generic(text)


def _extract_conam_gl(text: str) -> list[dict]:
    items = []
    pattern = re.compile(
        r'^(\d{5}-\d{4})\s+(.+?)\s+((?:[\d,.\-()]+\s+){11}[\d,.\-()]+)\s+([\d,.\-()]+)\s*$',
        re.MULTILINE
    )
    for i, m in enumerate(pattern.finditer(text)):
        acct = m.group(1)
        name = m.group(2).strip()
        vals = m.group(3).split()
        total = parse_numeric(m.group(4))

        if should_skip_conam_gl(acct, name, total):
            continue

        monthly = {MONTH_LABELS[j]: parse_numeric(v) for j, v in enumerate(vals[:12])}
        items.append({
            'name': name,
            'account_code': acct,
            'monthly_values': monthly,
            'trailing_total': total,
            'original_order': i,
        })
    return items


def _extract_generic(text: str) -> list[dict]:
    items = []
    i = 0
    for line in text.split('\n'):
        parts = re.split(r'\s{2,}|\t', line.strip())
        if len(parts) < 13:
            continue
        name = parts[0].strip()
        if not name:
            continue
        numeric_parts = parts[1:]
        try:
            vals = [parse_numeric(p) for p in numeric_parts[:12]]
            total = parse_numeric(numeric_parts[12]) if len(numeric_parts) > 12 else sum(vals)
        except Exception:
            continue

        if should_skip_generic(name, total):
            continue
        if all(v == 0 for v in vals):
            continue

        monthly = {MONTH_LABELS[j]: v for j, v in enumerate(vals)}
        items.append({
            'name': name,
            'account_code': None,
            'monthly_values': monthly,
            'trailing_total': total,
            'original_order': i,
        })
        i += 1
    return items
