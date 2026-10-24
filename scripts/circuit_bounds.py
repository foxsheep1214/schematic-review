"""Worst-case bounds for everyday circuit blocks, never pass/fail or severity.

Every function enumerates the tolerance corners itself and reports which corner
gave each bound, so a design script that picked the wrong direction disagrees
with it. Units are SI (ohm, F, V, A, W, s, Hz) and temperatures in degrees C.
"""
import itertools
import math

from model_bounds import _n
from electrical_contract import finite

BASIS = 'CONDITIONAL_ON_CALLER_BOUNDS'


def _finite(value, name):
    if not finite(value):
        raise ValueError(name + ' must be finite')
    return float(value)


def _tol(value, name):
    t = _n(value, name)
    if t >= 1:
        raise ValueError(name + ' is a fraction below 1 (0.01 = 1 %)')
    return t


def _window(low, high, name):
    a, b = _n(low, name + '_min'), _n(high, name + '_max')
    if a > b:
        raise ValueError(name + '_min must not exceed ' + name + '_max')
    return a, b


def divider_bounds(*, r_top_ohm, r_bottom_ohm, r_tol, vin_min_v=None, vin_max_v=None,
                   vref_min_v=None, vref_max_v=None):
    """Divider output window: plain (vin given) or feedback (vref given), all corners.

Plain: Vout = Vin*Rb/(Rt+Rb). Feedback: Vout = Vref*(1+Rt/Rb). Exactly one mode.
Also returns the top-resistor current and power at the worst corner.
"""
    rt, rb = _n(r_top_ohm, 'r_top_ohm', True), _n(r_bottom_ohm, 'r_bottom_ohm', True)
    t = _tol(r_tol, 'r_tol')
    plain = vin_min_v is not None or vin_max_v is not None
    feedback = vref_min_v is not None or vref_max_v is not None
    if plain == feedback:
        raise ValueError('give either vin_min_v/vin_max_v (plain) or vref_min_v/vref_max_v (feedback)')
    lo_v, hi_v = (_window(vin_min_v, vin_max_v, 'vin') if plain else _window(vref_min_v, vref_max_v, 'vref'))
    rows = []
    for v, st, sb in itertools.product((lo_v, hi_v), (-1, 1), (-1, 1)):
        top, bottom = rt * (1 + st * t), rb * (1 + sb * t)
        out = v * bottom / (top + bottom) if plain else v * (1 + top / bottom)
        current = (v / (top + bottom)) if plain else (v / bottom)
        rows.append((out, current, current * current * top, v, st, sb))
    low, high = min(rows), max(rows)
    word = {-1: 'min', 1: 'max'}
    corner = lambda r: 'V%s+Rt%s+Rb%s' % ('min' if r[3] == lo_v else 'max', word[r[4]], word[r[5]])
    return {'vout_min_v': low[0], 'vout_min_corner': corner(low),
            'vout_max_v': high[0], 'vout_max_corner': corner(high),
            'mode': 'plain' if plain else 'feedback',
            'divider_current_max_a': max(r[1] for r in rows),
            'r_top_power_max_w': max(r[2] for r in rows), 'basis': BASIS}


def rc_crossing_time(*, r_ohm, r_tol, c_f, c_tol_minus, c_tol_plus, v_start_v, v_final_v,
                     v_threshold_min_v, v_threshold_max_v):
    """Time for a first-order RC node to cross a threshold window, all corners.

t = R*C*ln((Vf-V0)/(Vf-Vth)). Rising or falling follows from V0 and Vf. A
threshold the node never reaches (outside V0..Vf) is an error, not infinity.
"""
    r = _n(r_ohm, 'r_ohm', True)
    rt = _tol(r_tol, 'r_tol')
    c = _n(c_f, 'c_f', True)
    cm, cp = _tol(c_tol_minus, 'c_tol_minus'), _n(c_tol_plus, 'c_tol_plus')
    if not all(finite(v)
               for v in (v_start_v, v_final_v, v_threshold_min_v, v_threshold_max_v)):
        raise ValueError('voltages must be finite')
    v0, vf = float(v_start_v), float(v_final_v)
    th = (float(v_threshold_min_v), float(v_threshold_max_v))
    if th[0] > th[1]:
        raise ValueError('v_threshold_min_v must not exceed v_threshold_max_v')
    if v0 == vf:
        raise ValueError('v_start_v equals v_final_v: the node does not move')
    for v in th:
        if not (min(v0, vf) < v < max(v0, vf)):
            raise ValueError('threshold %g V is not crossed between %g V and %g V' % (v, v0, vf))
    times = [(r * (1 + sr * rt)) * (c * (1 + (cp if sc > 0 else -cm))) * math.log((vf - v0) / (vf - v))
             for sr, sc, v in itertools.product((-1, 1), (-1, 1), th)]
    return {'t_min_s': min(times), 't_max_s': max(times), 'direction': 'rising' if vf > v0 else 'falling',
            'basis': BASIS}


def linear_regulator_thermal(*, vin_max_v, vout_min_v, iout_max_a, iq_max_a, theta_ja_c_per_w,
                             ambient_max_c, tj_max_c):
    """Linear regulator dissipation and junction temperature at the worst input/load.

P = (Vin_max - Vout_min)*Iout_max + Vin_max*Iq_max; Tj = Ta_max + P*theta_JA.
theta_JA must be the board-relevant value, not the JEDEC headline, when known.
"""
    vin, vout = _n(vin_max_v, 'vin_max_v'), _n(vout_min_v, 'vout_min_v')
    if vout >= vin:
        raise ValueError('vout_min_v must be below vin_max_v for a linear drop')
    i, iq = _n(iout_max_a, 'iout_max_a'), _n(iq_max_a, 'iq_max_a')
    theta = _n(theta_ja_c_per_w, 'theta_ja_c_per_w', True)
    for value, name in ((ambient_max_c, 'ambient_max_c'), (tj_max_c, 'tj_max_c')):
        if not finite(value):
            raise ValueError(name + ' must be finite')
    p = (vin - vout) * i + vin * iq
    tj = ambient_max_c + p * theta
    return {'dissipation_w': p, 'tj_c': tj, 'tj_margin_c': tj_max_c - tj, 'basis': BASIS}


def _level(absolute, fraction, supply, name):
    if (absolute is None) == (fraction is None):
        raise ValueError('give exactly one of %s_v or %s_fraction' % (name, name))
    if absolute is not None:
        return _n(absolute, name + '_v'), 'absolute'
    if supply is None:
        raise ValueError(name + '_fraction needs its supply bound')
    return _n(fraction, name + '_fraction') * _n(supply, name + ' supply'), 'fraction of supply'


def logic_level_margins(*, voh_min_v=None, voh_drop_v=None, driver_supply_min_v=None, vol_max_v=None,
                        vih_min_v=None, vih_fraction=None, vil_max_v=None, vil_fraction=None,
                        receiver_supply_min_v=None, receiver_supply_max_v=None):
    """High/low noise margins between a driver and a receiver, worst supply direction.

VOH may be absolute or (driver supply min - drop). A VIH given as a fraction of
the receiver supply uses that supply's MAXIMUM; a VIL fraction uses its MINIMUM.
"""
    if voh_min_v is not None and voh_drop_v is not None:
        raise ValueError('give voh_min_v or voh_drop_v, not both')
    if voh_drop_v is not None:
        if driver_supply_min_v is None:
            raise ValueError('voh_drop_v needs driver_supply_min_v')
        voh = _n(driver_supply_min_v, 'driver_supply_min_v') - _n(voh_drop_v, 'voh_drop_v')
    elif voh_min_v is not None:
        voh = _n(voh_min_v, 'voh_min_v')
    else:
        raise ValueError('voh_min_v or voh_drop_v is required')
    vih, vih_basis = _level(vih_min_v, vih_fraction, receiver_supply_max_v, 'vih')
    out = {'voh_worst_v': voh, 'vih_worst_v': vih, 'vih_basis': vih_basis,
           'high_margin_v': voh - vih, 'basis': BASIS}
    if vol_max_v is not None or vil_max_v is not None or vil_fraction is not None:
        vol = _n(vol_max_v, 'vol_max_v') if vol_max_v is not None else None
        if vol is None:
            raise ValueError('low margin needs vol_max_v')
        vil, vil_basis = _level(vil_max_v, vil_fraction, receiver_supply_min_v, 'vil')
        out.update(vol_worst_v=vol, vil_worst_v=vil, vil_basis=vil_basis, low_margin_v=vil - vol)
    return out


def _factor(table, x, name):
    if not (isinstance(table, list) and table and all(isinstance(p, list) and len(p) == 2 for p in table)):
        raise ValueError(name + ' is a list of [x, factor] pairs from the datasheet')
    points = sorted((_finite(a, name + ' x'), _n(f, name + ' factor', True)) for a, f in table)
    if len({p[0] for p in points}) != len(points):
        raise ValueError(name + ' has duplicate x values')
    if x < points[0][0] or x > points[-1][0]:
        return None, 'outside-' + name
    below = max(p for p in points if p[0] <= x)
    above = min(p for p in points if p[0] >= x)
    return min(below[1], above[1]), None   # no interpolation: the lower bracketing factor


def capacitor_ripple_capability(*, rated_arms, freq_factors, freq_hz, temp_factors, temp_c):
    """Allowed ripple current = rated x frequency factor x temperature factor.

Factor tables are the datasheet's [x, factor] pairs (frequency in Hz, ambient in
C). Between table points the lower bracketing factor is used; outside the table
the result is withheld and flagged rather than extrapolated.
"""
    rated = _n(rated_arms, 'rated_arms', True)
    f = _n(freq_hz, 'freq_hz', True)
    kf, flag_f = _factor(freq_factors, f, 'freq-table')
    kt, flag_t = _factor(temp_factors, _finite(temp_c, 'temp_c'), 'temp-table')
    flags = [x for x in (flag_f, flag_t) if x]
    allowed = None if flags else rated * kf * kt
    return {'allowed_arms': allowed, 'freq_factor': kf, 'temp_factor': kt,
            'applicability_flags': flags, 'basis': BASIS}


def resistor_power(*, v_max_v, r_ohm, r_tol, rated_w, derating=1.0):
    """Worst resistor dissipation (V_max^2 / R_min) against a derated rating."""
    v, r = _n(v_max_v, 'v_max_v'), _n(r_ohm, 'r_ohm', True)
    t = _tol(r_tol, 'r_tol')
    rated, d = _n(rated_w, 'rated_w', True), _n(derating, 'derating', True)
    if d > 1:
        raise ValueError('derating is a fraction of the rating, at most 1')
    p = v * v / (r * (1 - t))
    return {'power_max_w': p, 'allowed_w': rated * d, 'margin_w': rated * d - p, 'basis': BASIS}


def series_resistor_current(*, v_supply_min_v, v_supply_max_v, v_drop_min_v, v_drop_max_v, r_ohm, r_tol):
    """Current through a series resistor feeding a diode/LED/opto: (Vs - Vf)/R, all corners."""
    s_lo, s_hi = _window(v_supply_min_v, v_supply_max_v, 'v_supply')
    d_lo, d_hi = _window(v_drop_min_v, v_drop_max_v, 'v_drop')
    r = _n(r_ohm, 'r_ohm', True)
    t = _tol(r_tol, 'r_tol')
    i_min = max(0.0, (s_lo - d_hi) / (r * (1 + t)))
    i_max = max(0.0, (s_hi - d_lo) / (r * (1 - t)))
    return {'i_min_a': i_min, 'i_max_a': i_max,
            'resistor_power_max_w': i_max * i_max * r * (1 - t), 'basis': BASIS}
