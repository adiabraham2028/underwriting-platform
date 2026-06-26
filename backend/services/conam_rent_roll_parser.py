import io
import re
import math
import logging
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def safe_float(value, default: float = 0.0) -> float:
    """Convert value to float safely; returns default for non-numeric strings."""
    if value is None:
        return default
    try:
        f = float(value)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default


def _sanitize(obj):
    """Recursively replace float NaN/Inf with None so the result is JSON-safe."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def excel_serial_to_date(serial) -> str | None:
    if not serial or serial == 0:
        return None
    try:
        base = datetime(1899, 12, 30)
        delta = timedelta(days=int(float(serial)))
        return (base + delta).strftime('%Y-%m-%d')
    except Exception:
        return str(serial) if serial else None


def parse_conam_rent_roll_excel(file_bytes: bytes) -> dict:
    """
    Parse a CONAM-format rent roll Excel file.

    CONAM structure:
    - Multi-row header at row index 4 (0-based)
    - Columns: Unit | Unit Type | Unit Sq Ft | Resident |
               Name | Market Rent | Charge Code | Amount |
               Resident Deposit | Other Deposit |
               Move In | Lease Expiration | Move Out | Balance
    - Multiple rows per unit (one per charge type:
      RENT, GARAGE, PETRENT etc.)
    - Section headers like "Current/Notice/Vacant Residents"
      appear in the Unit column and must be skipped
    - "Total" rows appear after each unit and must be skipped
    - Pandas renames duplicate headers: Unit Sq Ft -> Unit.1,
      Market Rent -> Market, Charge Code -> Charge,
      Resident Deposit -> Resident.1

    Returns a summary dict (total_units, unit_mix, etc.) — NOT a list.
    """

    def safe_date(value) -> str | None:
        if value is None or str(value) == 'nan':
            return None
        s = str(value).strip()
        if s in ('', 'nan', 'None'):
            return None
        return s[:10]  # YYYY-MM-DD

    # ── Extract "As Of" date from header rows (rows 0-3) ──────────────────
    as_of_date = None
    try:
        df_head = pd.read_excel(io.BytesIO(file_bytes), header=None, nrows=4)
        for _, hrow in df_head.iterrows():
            for cell in hrow:
                if cell and 'As Of' in str(cell):
                    # "As Of = 05/30/2026" → parse MM/DD/YYYY
                    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', str(cell))
                    if m:
                        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
                        as_of_date = datetime(year, month, day)
                    break
            if as_of_date:
                break
    except Exception as e:
        logger.warning(f"Could not extract As Of date: {e}")

    # Read with header at row index 4
    df = pd.read_excel(io.BytesIO(file_bytes), header=4)

    units = {}
    current_unit = None

    SKIP_UNIT_VALUES = {
        'current/notice/vacant residents',
        'current residents',
        'notice residents',
        'vacant residents',
        'unit',
        'nan',
        '',
    }

    for _, row in df.iterrows():
        unit_val    = str(row.get('Unit',   '') or '').strip()
        name_raw    = str(row.get('Name',   '') or '').strip()
        charge_code = str(row.get('Charge', '') or '').strip().upper()
        amount_raw  = row.get('Amount')

        # Skip section headers and blank rows
        if unit_val.lower() in SKIP_UNIT_VALUES:
            # Could still be a charge row for the current unit
            if (current_unit
                    and charge_code
                    and charge_code not in ('NAN', 'TOTAL', '', 'CHARGE')):
                amt = safe_float(amount_raw)
                if amt != 0:
                    units[current_unit]['charges'][charge_code] = (
                        units[current_unit]['charges'].get(charge_code, 0) + amt
                    )
            continue

        # Skip total/subtotal rows
        if charge_code in ('TOTAL', 'NAN', '', 'CHARGE CODE'):
            continue

        # Is this a new unit row?
        is_new_unit = (
            unit_val
            and unit_val.lower() not in SKIP_UNIT_VALUES
            and not unit_val.lower().startswith('total')
        )

        if is_new_unit:
            name_upper = name_raw.upper()
            if 'VACANT' in name_upper:
                status = 'vacant'
            elif 'NOTICE' in name_upper or 'NTV' in name_upper:
                status = 'notice'
            elif 'MODEL' in name_upper:
                status = 'model'
            else:
                status = 'occupied'

            current_unit = unit_val

            # pandas renames duplicate column headers:
            # "Unit Sq Ft" -> "Unit.1", "Market Rent" -> "Market",
            # "Resident Deposit" -> "Resident.1"
            sf_raw  = (row.get('Unit.1')
                       or row.get('Unit Sq Ft')
                       or row.get('SF'))
            mkt_raw = (row.get('Market')
                       or row.get('Market Rent')
                       or row.get('Market\nRent'))
            mi_raw  = (row.get('Move In')
                       or row.get('Move In Date'))
            le_raw  = (row.get('Lease')
                       or row.get('Lease Expiration')
                       or row.get('Lease\nExpiration'))
            mo_raw  = row.get('Move Out')
            res_raw = (row.get('Resident')
                       or row.get('Resident ID'))
            bal_raw = row.get('Balance')

            units[current_unit] = {
                'unit_number':      unit_val,
                'unit_type':        str(row.get('Unit Type', '') or '').strip(),
                'sf':               safe_float(sf_raw) or None,
                'resident_id':      str(res_raw or '').strip(),
                'status':           status,
                'market_rent':      safe_float(mkt_raw) or None,
                'move_in':          safe_date(mi_raw),
                'lease_expiration': safe_date(le_raw),
                'move_out':         safe_date(mo_raw),
                'balance':          safe_float(bal_raw),
                'charges':          {},
            }

            if charge_code and charge_code not in ('NAN', 'TOTAL', '', 'CHARGE', 'CHARGE CODE'):
                amt = safe_float(amount_raw)
                if amt != 0:
                    units[current_unit]['charges'][charge_code] = amt

        else:
            # Charge-only continuation row for current unit
            if (current_unit
                    and charge_code
                    and charge_code not in ('NAN', 'TOTAL', '', 'CHARGE', 'CHARGE CODE')):
                amt = safe_float(amount_raw)
                if amt != 0:
                    existing = units[current_unit]['charges']
                    existing[charge_code] = existing.get(charge_code, 0) + amt

    # Post-process
    result = []
    for u in units.values():
        charges = u['charges']
        u['base_rent']     = charges.get('RENT') or charges.get('MABRENT', 0)
        u['garage_income'] = charges.get('GARAGE', 0)
        u['pet_rent']      = charges.get('PETRENT', 0) or charges.get('PET', 0)
        u['total_charges'] = sum(charges.values())

        # Skip phantom rows with no charges and no market rent
        if not charges and not u.get('market_rent'):
            continue

        result.append(u)

    # Summary stats
    total     = len(result)
    occupied  = sum(1 for u in result if u['status'] == 'occupied')
    rents     = [u['base_rent']   for u in result if u.get('base_rent')   and u['base_rent']   > 0]
    mkt_rents = [u['market_rent'] for u in result if u.get('market_rent') and u['market_rent'] > 0]

    logger.info(f"CONAM rent roll parsed: {total} units, {occupied} occupied")

    summary = {
        'total_units':                  total,
        'occupied_units':               occupied,
        'occupancy_rate':               occupied / total if total else 0,
        'avg_current_rent':             sum(rents) / len(rents) if rents else 0,
        'avg_market_rent':              sum(mkt_rents) / len(mkt_rents) if mkt_rents else 0,
        'total_current_monthly_income': sum(rents),
        'total_market_monthly_income':  sum(mkt_rents),
        'loss_to_lease':                sum(mkt_rents) - sum(rents) if rents and mkt_rents else 0,
        'unit_mix':                     result,
    }
    summary['as_of_date'] = as_of_date.isoformat() if as_of_date else None
    return _sanitize(summary)


def parse_conam_rent_roll(rows: list[dict]) -> list[dict]:
    """Legacy: aggregate pre-parsed rows (list of dicts) into one dict per unit."""
    units: dict[str, dict] = {}
    for row in rows:
        unit_num = str(row.get('Unit') or row.get('unit') or '').strip()
        if not unit_num:
            continue
        if unit_num not in units:
            units[unit_num] = {
                'unit_number':      unit_num,
                'unit_type':        row.get('Unit Type', ''),
                'sf':               row.get('Unit\nSq Ft') or row.get('Unit Sq Ft') or row.get('sq_ft'),
                'resident_id':      row.get('Resident', ''),
                'status_raw':       row.get('Name', ''),
                'market_rent':      row.get('Market\nRent') or row.get('Market Rent'),
                'move_in':          excel_serial_to_date(row.get('Move In')),
                'lease_expiration': excel_serial_to_date(row.get('Lease\nExpiration') or row.get('Lease Expiration')),
                'move_out':         excel_serial_to_date(row.get('Move Out')),
                'balance':          safe_float(row.get('Balance')),
                'charges':          {},
                'total_charges':    0.0,
            }
        charge_code = str(row.get('Charge\nCode') or row.get('Charge Code') or '').upper().strip()
        amount      = safe_float(row.get('Amount'))
        if charge_code and amount:
            units[unit_num]['charges'][charge_code] = amount
            units[unit_num]['total_charges'] += amount

    result = []
    for u in units.values():
        charges = u['charges']
        u['base_rent']     = charges.get('RENT') or charges.get('MABRENT') or 0
        u['garage_income'] = charges.get('GARAGE', 0)
        u['pet_rent']      = charges.get('PETRENT', 0) or charges.get('PET', 0)
        status_raw = str(u.get('status_raw', '')).upper()
        if 'VACANT' in status_raw or not u['base_rent']:
            u['status'] = 'vacant'
        elif 'NOTICE' in status_raw:
            u['status'] = 'notice'
        elif 'MODEL' in status_raw:
            u['status'] = 'model'
        else:
            u['status'] = 'occupied'
        result.append(u)
    return result
