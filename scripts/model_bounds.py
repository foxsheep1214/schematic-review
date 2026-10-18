"""Conditional model bounds that design scripts commonly get backwards, never pass/fail.

Each function evaluates every tolerance corner itself instead of trusting a
hand-picked one, and reports where the model stops being applicable. Units are
SI except temperatures in degrees Celsius.
"""
import math

KELVIN = 273.15


def crm_boost_capacitor_ripple(*, input_rms_v, bus_v, power_w, hf_ripple_factor=1.0):
    """Ideal unity-PF CrM boost, constant bus and constant-power load; not a qualification.

    Over each switching cycle Ipk=2*sqrt(2)*P/Vac*sin(theta), diode duty=v/Vbus.
    <Id^2>=<Ipk^2*v/(3*Vbus)>; capacitor variance subtracts (P/Vbus)^2.
    The twice-line component is P/(sqrt(2)*Vbus); remaining variance is switching ripple.
    hf_ripple_factor is the capacitor's supplied high-frequency/line-frequency rating ratio.
    Run each actual controller bus mode separately; fixed nominal bus cannot cover follower mode.
    """
    vac = _n(input_rms_v, 'input_rms_v', True)
    bus = _n(bus_v, 'bus_v', True)
    power = _n(power_w, 'power_w', True)
    factor = _n(hf_ripple_factor, 'hf_ripple_factor', True)
    if bus <= math.sqrt(2) * vac:
        raise ValueError('bus_v must exceed peak input throughout the ideal boost cycle')
    output = power / bus
    diode_ms = 32 * math.sqrt(2) * power**2 / (9 * math.pi * vac * bus)
    total_ms = diode_ms - output**2
    lf_ms = output**2 / 2
    hf_ms = total_ms - lf_ms
    return {'diode_rms_a': math.sqrt(diode_ms), 'capacitor_rms_a': math.sqrt(total_ms),
            'twice_line_rms_a': math.sqrt(lf_ms), 'switching_rms_a': math.sqrt(hf_ms),
            'equivalent_line_rms_a': math.sqrt(lf_ms + hf_ms / factor**2),
            'diode_conduction_fraction': 'v_instantaneous / bus_v',
            'basis': 'CONDITIONAL_ON_IDEAL_CRM_CONSTANT_BUS',
            'applicability_flags': ['requires-actual-controller-mode-and-bus-envelope',
                                    'excludes-burst-current-limit-bus-ripple-and-load-dynamics']}


def _n(x, name, positive=False):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(name + ' must be finite')
    if x < 0 or (positive and x == 0):
        raise ValueError(name + ' must be ' + ('positive' if positive else 'nonnegative'))
    return float(x)


def _range(value, name):
    if value is None:
        return None
    if not (isinstance(value, (list, tuple)) and len(value) == 2):
        raise ValueError(name + ' must be [low_c, high_c]')
    low, high = (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None for v in value)
    if low is None or high is None or not (math.isfinite(low) and math.isfinite(high)) or low >= high:
        raise ValueError(name + ' must be two finite temperatures, low < high')
    return low, high


def ntc_resistance_bounds(*, r25_ohm, r25_tol, beta_k, beta_tol, temp_c, beta_range_c=None, rated_range_c=None):
    """NTC R(T) min/max over all four R25/B corners of the Beta model.

Above 25 C the minimum resistance uses R25min with Bmax; below 25 C it uses
R25min with Bmin. The tool picks the corner, so a sign slip cannot. Outside the
B-value fit range or the part's rated range the result is flagged, not extended.
"""
    r25 = _n(r25_ohm, 'r25_ohm', True)
    rt, bt = _n(r25_tol, 'r25_tol'), _n(beta_tol, 'beta_tol')
    beta = _n(beta_k, 'beta_k', True)
    if rt >= 1 or bt >= 1:
        raise ValueError('tolerances are fractions below 1 (0.01 = 1 %)')
    if isinstance(temp_c, bool) or not isinstance(temp_c, (int, float)) or not math.isfinite(temp_c):
        raise ValueError('temp_c must be finite')
    if temp_c <= -KELVIN:
        raise ValueError('temp_c must be above absolute zero')
    fit, rated = _range(beta_range_c, 'beta_range_c'), _range(rated_range_c, 'rated_range_c')
    x = 1 / (temp_c + KELVIN) - 1 / (25 + KELVIN)
    corners = {(r_side, b_side): r25 * (1 + r_side * rt) * math.exp(beta * (1 + b_side * bt) * x)
               for r_side in (-1, 1) for b_side in (-1, 1)}
    name = {-1: 'min', 1: 'max'}
    low, high = min(corners, key=corners.get), max(corners, key=corners.get)
    flags = []
    if fit and not fit[0] <= temp_c <= fit[1]:
        flags.append('outside-beta-fit-range')
    if rated and not rated[0] <= temp_c <= rated[1]:
        flags.append('outside-rated-range')
    return {'r_min_ohm': corners[low], 'r_min_corner': 'R25%s+B%s' % (name[low[0]], name[low[1]]),
            'r_max_ohm': corners[high], 'r_max_corner': 'R25%s+B%s' % (name[high[0]], name[high[1]]),
            'applicability_flags': flags, 'basis': 'CONDITIONAL_ON_CALLER_BOUNDS'}


def cc_discharge_with_tail(*, capacitance_f, start_v, end_v, sink_current_a, series_r_max_ohm, tail_r_ohm):
    """Constant-current sink through a series resistor, then the resistive tail below compliance.

The current source holds only while V > I x (series R + tail R); below that the
discharge is exponential through the total resistance. Integrating the constant
current all the way down overstates speed. tail_r_ohm is the sink's effective
resistance out of compliance and must come from the part's I-V data.
"""
    c = _n(capacitance_f, 'capacitance_f', True)
    v0, v1 = _n(start_v, 'start_v', True), _n(end_v, 'end_v', True)
    i = _n(sink_current_a, 'sink_current_a', True)
    rs, rtail = _n(series_r_max_ohm, 'series_r_max_ohm'), _n(tail_r_ohm, 'tail_r_ohm')
    if v1 >= v0:
        raise ValueError('end_v must be below start_v')
    r_total = rs + rtail
    if r_total == 0:
        raise ValueError('series_r_max_ohm + tail_r_ohm must be positive')
    v_c = i * r_total
    if v0 <= v_c:
        cc_s, tail_from = 0.0, v0
    else:
        cc_s, tail_from = c * (max(v1, v_c) - v0) / -i, min(v0, v_c)
    tail_s = r_total * c * math.log(tail_from / v1) if v1 < tail_from else 0.0
    return {'compliance_boundary_v': v_c, 'constant_current_s': cc_s, 'tail_s': tail_s,
            'total_s': cc_s + tail_s, 'series_r_peak_power_w': i * i * rs,
            'phase_at_end': 'constant-current' if v1 >= v_c else 'resistive-tail',
            'basis': 'CONDITIONAL_ON_CALLER_BOUNDS'}
