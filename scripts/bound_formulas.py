"""Bounding formulas of the operating-point table (catalog.BOUNDS; bounding table proposal of 2026-10-23).

Each takes keyword inputs in one consistent unit system and returns the bound as a number. The gate reruns the
formula a margin names (`basis.formula{name, inputs, value}`) and refuses a value that does not match. The result is
conditional on the inputs the reviewer copied from the datasheet; it is not a verdict.
"""
import math

import model_bounds
from electrical_contract import finite

SIDES = ('UPPER', 'LOWER')
SOA_SEGMENTS = {'CONSTANT_POWER': 1.0, 'THERMAL_INSTABILITY': 0.8}   # decision B: 100 % / 80 % after derating
FORCED_BETA_K = 2   # decision D
TYPICAL_BAND = 0.3   # G9 ③
KELVIN = 273.15


def _n(value, name, positive=False):
    if not finite(value):
        raise ValueError(name + ' must be a finite number')
    if positive and value <= 0:
        raise ValueError(name + ' must be positive')
    return float(value)


def _side(side):
    if side not in SIDES:
        raise ValueError('side is UPPER or LOWER')
    return side


def slope_bound(*, p0, x0, x, slope_max, side):
    """G3: between two test points, the guaranteed value at x0 moved to x by the largest guaranteed slope in the
    interval (for a zener, rdif max at the lower-current point, 1-A), always against the side asked."""
    if _n(slope_max, 'slope_max') < 0:
        raise ValueError('slope_max is a magnitude')
    p0, step = _n(p0, 'p0'), slope_max * abs(_n(x, 'x') - _n(x0, 'x0'))
    return p0 + step if _side(side) == 'UPPER' else p0 - step


def tempco_bound(*, p0, t0, t, s_min, s_max, side):
    """G4: P(T) = P(T0) + S·(T − T0), S the end of [s_min, s_max] that is unfavourable for the side asked."""
    if _n(s_min, 's_min') > _n(s_max, 's_max'):
        raise ValueError('s_min exceeds s_max')
    ends = [_n(p0, 'p0') + s * (_n(t, 't') - _n(t0, 't0')) for s in (s_min, s_max)]
    return max(ends) if _side(side) == 'UPPER' else min(ends)


def table_interpolate(*, table, x, side):
    """G5: linear interpolation in a published table [[x, min, max], ...]; x within the table."""
    rows = _table(table)
    col = 2 if _side(side) == 'UPPER' else 1
    return _interpolate([(r[0], r[col]) for r in rows], _n(x, 'x'))


def ntc_table_bound(*, table, temp_c, side):
    """G5 for a sensing NTC: the maker's R-T table [[temp_c, r_min, r_max], ...], ln R linear in 1/T (decision C)."""
    rows = _table(table)
    col = 2 if _side(side) == 'UPPER' else 1
    if any(r[col] <= 0 for r in rows):
        raise ValueError('table resistances must be positive')
    points = [(1 / (r[0] + KELVIN), math.log(r[col])) for r in rows]
    return math.exp(_interpolate(sorted(points), 1 / (_n(temp_c, 'temp_c') + KELVIN)))


def ntc_beta_bound(*, r25_ohm, r25_tol, beta_k, beta_tol, temp_c, side):
    """No R-T table: the Beta model over R25 and B tolerances is taken as the guaranteed bound (decision C)."""
    found = model_bounds.ntc_resistance_bounds(r25_ohm=r25_ohm, r25_tol=r25_tol, beta_k=beta_k, beta_tol=beta_tol,
                                               temp_c=temp_c)
    return found['r_max_ohm'] if _side(side) == 'UPPER' else found['r_min_ohm']


def ratio_extrapolation(*, typ_at_x, max_at_x0, typ_at_x0):
    """G7: the typical curve scaled by the ratio of guaranteed to typical at one test point (an estimate)."""
    return _n(typ_at_x, 'typ_at_x') * _n(max_at_x0, 'max_at_x0') / _n(typ_at_x0, 'typ_at_x0', True)


def typical_band(*, typ, side):
    """G9 ③: a typical value ±30 % (an estimate; never for damage, overheating or protection)."""
    return _n(typ, 'typ') * (1 + TYPICAL_BAND if _side(side) == 'UPPER' else 1 - TYPICAL_BAND)


def soa_allowed_power(*, p_curve_w, tj_max_c, tc_start_c, segment):
    """Decision B: the power allowed at the board's VDS and duration, read off the chosen 25 °C curve (DC line,
    single pulse not shorter than the event), derated to the starting case temperature, with the margin of the
    segment the point lies on (100 % constant power, 80 % thermal instability)."""
    tj, tc = _n(tj_max_c, 'tj_max_c'), _n(tc_start_c, 'tc_start_c')
    if segment not in SOA_SEGMENTS:
        raise ValueError('segment is ' + '/'.join(SOA_SEGMENTS))
    if tj <= 25:
        raise ValueError('tj_max_c must exceed 25')
    return _n(p_curve_w, 'p_curve_w', True) * max(tj - tc, 0.0) / (tj - 25) * SOA_SEGMENTS[segment]


def soa_case_temperature(*, p_w, p_curve_w, tj_max_c, segment):
    """Decision B: the highest starting case temperature at which p_w stays within soa_allowed_power (a thermal
    requirement handed to thermal and PCB design)."""
    tj = _n(tj_max_c, 'tj_max_c')
    if segment not in SOA_SEGMENTS:
        raise ValueError('segment is ' + '/'.join(SOA_SEGMENTS))
    if tj <= 25:
        raise ValueError('tj_max_c must exceed 25')
    return tj - _n(p_w, 'p_w') * (tj - 25) / (_n(p_curve_w, 'p_curve_w', True) * SOA_SEGMENTS[segment])


def heatsink_requirement(*, tc_allowed_c, ta_max_c, p_w):
    """Decision B: the case-to-ambient thermal resistance the PCB and heatsink must reach, Rθca ≤ (Tc − Ta)/P."""
    return (_n(tc_allowed_c, 'tc_allowed_c') - _n(ta_max_c, 'ta_max_c')) / _n(p_w, 'p_w', True)


def zth_junction_temperature(*, tc_c, p_pk_w, zth_k_per_w):
    """Decision B, repeated transients: Tj = Tc + Ppk·Zth(tp, D), compared with Tjmax (the single-pulse line is
    still checked)."""
    return _n(tc_c, 'tc_c') + _n(p_pk_w, 'p_pk_w') * _n(zth_k_per_w, 'zth_k_per_w')


def forced_beta_base_current(*, ic_a, hfe_min):
    """Decision D: a saturated switch is driven with IB ≥ IC / (hFE_min / 2)."""
    return _n(ic_a, 'ic_a') / (_n(hfe_min, 'hfe_min', True) / FORCED_BETA_K)


def half_sine_i2t(*, ifsm_a, t_s):
    """A half-sine surge rating as I²t = IFSM²·t/2."""
    return _n(ifsm_a, 'ifsm_a') ** 2 * _n(t_s, 't_s', True) / 2


def surge_current_at_width(*, ifsm_a, t_rated_s, t_s):
    """A surge rating moved to a shorter pulse at constant I²t; a longer pulse than rated is not bounded."""
    rated, t = _n(t_rated_s, 't_rated_s', True), _n(t_s, 't_s', True)
    if t > rated:
        raise ValueError('a pulse longer than the rated width is not bounded by the rating')
    return _n(ifsm_a, 'ifsm_a') * math.sqrt(rated / t)


def inrush_peak_current(*, v_peak_v, r_other_ohm):
    """Decision E: a hot inrush limiter is taken as 0 Ω; the peak is set by the rest of the path."""
    return _n(v_peak_v, 'v_peak_v') / _n(r_other_ohm, 'r_other_ohm', True)


def inrush_i2t(*, v_peak_v, r_other_ohm, c_f):
    """Decision E: I²t of charging C from a step through R alone, V²·C/(2R)."""
    return _n(v_peak_v, 'v_peak_v') ** 2 * _n(c_f, 'c_f', True) / (2 * _n(r_other_ohm, 'r_other_ohm', True))


def _table(table):
    if not (isinstance(table, list) and len(table) >= 2 and all(isinstance(r, list) and len(r) == 3 for r in table)):
        raise ValueError('table is [[x, min, max], ...] with at least two rows')
    rows = sorted([_n(r[0], 'x'), _n(r[1], 'min'), _n(r[2], 'max')] for r in table)
    if any(r[1] > r[2] for r in rows):
        raise ValueError('a table row has min above max')
    return rows


def _interpolate(points, x):
    xs = [p[0] for p in points]
    if not xs[0] <= x <= xs[-1]:
        raise ValueError('x lies outside the table')
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if x1 <= x <= x2:
            return y1 if x2 == x1 else y1 + (y2 - y1) * (x - x1) / (x2 - x1)
    return points[-1][1]


FORMULAS = {f.__name__: f for f in (
    slope_bound, tempco_bound, table_interpolate, ntc_table_bound, ntc_beta_bound, ratio_extrapolation, typical_band,
    soa_allowed_power, soa_case_temperature, heatsink_requirement, zth_junction_temperature, forced_beta_base_current,
    half_sine_i2t, surge_current_at_width, inrush_peak_current, inrush_i2t)}
