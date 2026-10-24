# -*- coding: utf-8 -*-
"""电阻值解析：`阻值[/公差][/额定功率][/额定电压][/封装]`（见 references/wca-formulas.md）。

原先的分压求解器、线性反馈窗口和命令行只剩测试在用，已删去（SR 自查 5.7，用户：两个都删）；
分压与反馈窗口的计算由审查员按 wca-formulas 做，`calc.py` 复算。这里只留被出计划、检查器和改版比对共用的解析。
"""
import math
import re
from fractions import Fraction


def parse_resistor(value, default_tol=None, exact=False):
    """解析 R/K/M、显式毫欧单位与公差；exact=True 保留十进制分数。"""
    raw = str(value or '').strip()
    upper = raw.upper().replace('Ω', 'R')
    # Preserve the SI prefix's case before uppercasing: lowercase m is milli
    # (10mR, 10mohm, bare 10m, RKM 7m5 = 7.5 mOhm); uppercase M is mega (4M7).
    milli = re.match(r'^(\d+(?:\.\d+)?)\s*(?:m(?:[rRΩΩ]|(?i:ohms?))?|'
                     r'(?i:milliohms?))(?=$|[ /±+])', raw)
    milli_rkm = re.match(r'^(\d+)m(\d+)(?=$|[ /±+])', raw)
    leading_unit = re.match(r'^([RKM])(\d+)', upper)
    embedded = re.match(r'^(\d+)([RKM])(\d+)', upper)
    if milli_rkm:
        decimal_number = f'{milli_rkm.group(1)}.{milli_rkm.group(2)}'
        number = float(decimal_number)
        unit = 'mR'
        end = milli_rkm.end()
    elif milli:
        decimal_number = milli.group(1)
        number = float(decimal_number)
        unit = 'mR'
        end = milli.end()
    elif leading_unit:
        decimal_number = f'0.{leading_unit.group(2)}'
        number = float(decimal_number)
        unit = leading_unit.group(1)
        end = leading_unit.end()
    elif embedded:
        decimal_number = f'{embedded.group(1)}.{embedded.group(3)}'
        number = float(decimal_number)
        unit = embedded.group(2)
        end = embedded.end()
    else:
        normal = re.match(r'^(\d+(?:\.\d+)?)\s*([RKM]?)', upper)
        if not normal:
            return None
        decimal_number = normal.group(1)
        number = float(decimal_number)
        unit = normal.group(2)
        end = normal.end()
    remainder = upper[end:]
    remainder = re.sub(r'^OHMS?', '', remainder)
    # Explicit trailing resistor package is metadata, not resistance/tolerance.
    # Reject all other suffixes through the existing full tolerance match.
    package = re.fullmatch(r'(.*?)\s*/\s*R(?:01005|0201|0402|0603|0805|1206|1210|1812|2010|2512)\s*', remainder)
    if package:
        remainder = package.group(1)
    # A rated power and a rated voltage between the tolerance and the package (1k5/1%/1W, 100k/1%/250mW,
    # 1M/1%/250V), each at most once, are read and kept; mW is uppercased to MW here, and no resistor is rated in
    # megawatts. Any other word still makes the value unreadable.
    ratings = {}
    while True:
        rating = re.fullmatch(r'(.*?)\s*/\s*(\d+(?:\.\d+)?)\s*(M?W|V)\s*', remainder)
        if not rating:
            break
        field = 'voltage_v' if rating.group(3) == 'V' else 'power_w'
        amount = float(rating.group(2)) / (1000.0 if rating.group(3) == 'MW' else 1.0)
        if field in ratings or not (math.isfinite(amount) and amount > 0):
            return None
        ratings[field] = amount
        remainder = rating.group(1)
    # Only a single complete tolerance may follow the value/unit. Searching
    # anywhere in the input would accept junk or skip a conflicting tolerance.
    tol_match = None
    if remainder.strip():
        tol_match = re.fullmatch(r'\s*(?:(?:/|±|\+/-)\s*)?'
                                 r'(\d+(?:\.\d+)?)\s*%\s*', remainder)
        if not tol_match:
            return None
    if not math.isfinite(number):
        return None
    scale = {'mR': 0.000001, 'R': 0.001, '': 0.001, 'K': 1.0, 'M': 1000.0}[unit]
    tol = float(tol_match.group(1)) / 100.0 if tol_match else (float(default_tol) if default_tol is not None else None)
    if tol is not None and (not math.isfinite(tol) or tol < 0 or tol >= 1):
        return None
    result = {'kohm': number * scale, 'tol': tol}
    result.update(ratings)
    if exact:
        result['ohm_exact'] = str(Fraction(decimal_number) * {
            'mR': Fraction(1, 1000), 'R': 1, '': 1, 'K': 1000, 'M': 1000000}[unit])
        result['tol_exact'] = (str(Fraction(tol_match.group(1)) / 100) if tol_match
                               else str(Fraction(str(default_tol))) if default_tol is not None else None)
    return result


NOT_FITTED_WORDS = {'DNP', 'DNI', 'DNF', 'NOPOP', 'NOFIT'}


def parse_resistor_noted(value, default_tol=None, exact=False):
    """parse_resistor, and when it fails only for trailing words of their own (47R/1%/2W/pulse), the value without
    them, the words kept as `notes`; a not-fitted mark is never a note."""
    parsed = parse_resistor(value, default_tol=default_tol, exact=exact)
    if parsed is not None:
        return parsed
    core, notes = str(value or '').strip(), []
    while True:
        word = re.fullmatch(r'(.*?)\s*/\s*([A-Za-z][A-Za-z-]{2,})\s*', core)
        if not word or word.group(2).upper() in NOT_FITTED_WORDS:
            break
        notes.insert(0, word.group(2))
        core = word.group(1)
    parsed = parse_resistor(core, default_tol=default_tol, exact=exact) if notes else None
    if parsed is not None:
        parsed['notes'] = notes
    return parsed

