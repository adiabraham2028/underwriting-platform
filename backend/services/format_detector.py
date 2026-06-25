import re


def detect_t12_format(raw_text: str, sheet_data: dict = None) -> str:
    """Detect the source format of a T12 financial statement."""
    gl_pattern = r'\b\d{5}-\d{4}\b'
    if re.search(gl_pattern, raw_text):
        return 'conam_gl'

    conam_ext_markers = [
        'TOTAL RENTAL INCOME', 'TOTAL OTHER INCOME',
        'TOTAL BUILDING REPAIRS', 'TOTAL PAYROLL',
        'TOTAL PROPERTY MANAGEMENT'
    ]
    if sum(1 for m in conam_ext_markers if m in raw_text.upper()) >= 3:
        return 'conam_ext'

    if 'MRI CODE' in raw_text.upper():
        return 'mri'

    return 'broker'
