#!/usr/bin/env python3
"""Units a review quantity may carry (item 2 of the 2026-10-26 SR review: the structured fields are the main path).

`parse(unit)` gives (dimension, scale to the base unit) for a spelling the review may write — SI prefixes on the
electrical bases, µ or u, Ω or ohm, ² or 2 — or None for a spelling the table does not know. `plausible(value, unit)`
says whether a board-level quantity of that dimension can lie where the value puts it (a 22 F capacitor, a 5000 A
schematic current, a 30 ms gate delay quoted from a text layer that lost its µ): None when the unit is unknown or the
dimension has no span, otherwise a bool. `quantities(text)` lists the number-with-unit tokens prose carries. Every
consumer treats an unknown unit or an implausible magnitude as a hint for the reviewer, never as an error.
"""
import re

PREFIXES = {'p': 1e-12, 'n': 1e-9, 'µ': 1e-6, 'm': 1e-3, 'k': 1e3, 'M': 1e6, 'G': 1e9}
# base unit → (dimension, plausible span in base units, or None when any magnitude may be legitimate)
BASES = {
    'V': ('voltage', (1e-6, 1e6)), 'A': ('current', (1e-12, 1e5)), 'W': ('power', (1e-9, 1e7)),
    'Ω': ('resistance', (1e-6, 1e14)), 'F': ('capacitance', (1e-15, 1e4)), 'H': ('inductance', (1e-12, 1e3)),
    'Hz': ('frequency', (1e-6, 1e12)), 's': ('time', (1e-12, 1e9)), 'J': ('energy', (1e-12, 1e8)),
    'C': ('charge', (1e-15, 1e6)), 'S': ('conductance', (1e-12, 1e4)), 'T': ('flux_density', (1e-9, 50)),
    'm': ('length', (1e-9, 1e3)), 'g': ('mass', (1e-6, 1e4)),
}
SPECIAL = {
    'Vac': ('voltage', 1), 'VAC': ('voltage', 1), 'Vdc': ('voltage', 1), 'VDC': ('voltage', 1), 'Vrms': ('voltage', 1),
    'Vpk': ('voltage', 1), 'Vpp': ('voltage', 1), 'kVac': ('voltage', 1e3), 'kVdc': ('voltage', 1e3),
    'Arms': ('current', 1), 'Apk': ('current', 1), 'App': ('current', 1), 'Aac': ('current', 1), 'Adc': ('current', 1),
    'min': ('time', 60), 'h': ('time', 3600), 'hr': ('time', 3600), 'd': ('time', 86400), 'cycles': ('count', 1),
    'Ah': ('charge', 3600), 'mAh': ('charge', 3.6),
    '°C': ('temperature', 1), '℃': ('temperature', 1), 'degC': ('temperature', 1), 'K': ('temperature', 1),
    '%': ('ratio', 0.01), 'ratio': ('ratio', 1), 'x': ('ratio', 1), 'V/V': ('ratio', 1), 'A/A': ('ratio', 1),
    'ppm': ('ratio', 1e-6), 'dB': ('level', 1), 'dBm': ('level', 1),
    'deg': ('angle', 1), 'degree': ('angle', 1), 'degrees': ('angle', 1), '°': ('angle', 1), 'rad': ('angle', 57.29578),
    '°C/W': ('thermal_resistance', 1), 'K/W': ('thermal_resistance', 1),
    'mV/K': ('tempco', 1), 'mV/°C': ('tempco', 1), 'µV/°C': ('tempco', 1e-3), 'µV/K': ('tempco', 1e-3),
    '%/°C': ('tempco_relative', 1), 'ppm/°C': ('tempco_relative', 1e-4), 'ppm/K': ('tempco_relative', 1e-4),
    'V/µs': ('slew', 1), 'V/ns': ('slew', 1e3), 'A/µs': ('current_slew', 1), 'A/ns': ('current_slew', 1e3), 'V/s': ('slew', 1e-6),
    'A²s': ('i2t', 1), 'A2s': ('i2t', 1), 'A^2s': ('i2t', 1), 'A²·s': ('i2t', 1),
    'B': ('data', 1), 'kB': ('data', 1e3), 'MB': ('data', 1e6), 'bit': ('data', 0.125), 'bits': ('data', 0.125),
    'W/K': ('thermal_conductance', 1), 'nC': ('charge', 1e-9),
}
SPANS = {dimension: span for _, (dimension, span) in BASES.items()}
SPANS.update({'temperature': (-273.15, 3000), 'angle': (-720, 720), 'thermal_resistance': (1e-4, 1e5),
              'i2t': (1e-9, 1e8), 'ratio': None, 'level': None, 'tempco': None, 'tempco_relative': None,
              'slew': None, 'current_slew': None, 'data': None, 'count': None, 'thermal_conductance': None})
_NO_PREFIX = {'m': ('m', 'c', 'k', 'µ', 'n'), 's': ('m', 'µ', 'n', 'p'), 'g': ('m', 'k', 'µ'), 'C': ('n', 'µ', 'm', 'p'),
              'T': ('m', 'µ'), 'S': ('m', 'µ', 'n', 'k'), 'J': ('m', 'µ', 'k', 'n', 'M'), 'H': ('m', 'µ', 'n', 'p')}

_UNITS = {}
for _base, (_dim, _span) in BASES.items():
    _UNITS[_base] = (_dim, 1.0)
    for _p, _scale in PREFIXES.items():
        if _base in _NO_PREFIX and _p not in _NO_PREFIX[_base]:
            continue
        _UNITS[_p + _base] = (_dim, _scale)
_UNITS.update(SPECIAL)
UNITS = _UNITS

_OHM_RE = re.compile(r'(?i)ohms?')
QUANTITY_RE = re.compile(r'(?<!\w)(?<!\d\.)([-−]?\d+(?:\.\d+)?)\s*([A-Za-zµμΩ°℃%²^/·]+)')


def normalize(unit):
    """The table's spelling of a unit the review wrote: μ/u → µ, ohm → Ω, 2 → ² where a superscript belongs."""
    if not isinstance(unit, str):
        return None
    u = unit.strip().replace('μ', 'µ').replace('·', '')
    u = _OHM_RE.sub('Ω', u)
    if u not in UNITS and u[:1] == 'u' and 'µ' + u[1:] in UNITS:
        u = 'µ' + u[1:]
    if u not in UNITS and u.replace('^2', '²').replace('2', '²') in UNITS:
        u = u.replace('^2', '²').replace('2', '²')
    return u


def parse(unit):
    """(dimension, scale to the base unit) or None for a spelling the table does not know."""
    return UNITS.get(normalize(unit))


def plausible(value, unit, lower=True):
    """Whether a quantity `value unit` can be a board-level quantity: None when the unit is unknown or its dimension has
    no span, else whether value×scale lies in the span (`lower=False` checks the upper end only: a margin may be tiny)."""
    parsed = parse(unit)
    if parsed is None or not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    dimension, scale = parsed
    span = SPANS.get(dimension)
    if span is None or value != value:
        return None
    base = value * scale
    low, high = span
    if dimension in ('temperature', 'angle'):
        return low <= base <= high
    magnitude = abs(base)
    return magnitude <= high and (not lower or magnitude == 0 or magnitude >= low)


def quantities(prose):
    """[(value, unit)] for every number followed by a unit the table knows, in the order the prose writes them."""
    out = []
    for number, unit in QUANTITY_RE.findall(prose or ''):
        if parse(unit) is not None:
            out.append((float(number.replace('−', '-')), normalize(unit)))
    return out
