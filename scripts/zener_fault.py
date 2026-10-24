"""Conditional detector/hold-up bounds, never automatic pass/fail or severity.

Caller establishes topology, applicability, tolerances and source provenance.
Fixed-temperature monotone zener I-V is required for trip_drive. A test-point
maximum cannot supply a below-test-current voltage minimum. Units are SI.
"""
from electrical_contract import finite


def _n(x, name, positive=False):
    if not finite(x):
        raise ValueError(name + ' must be finite')
    if x < 0 or (positive and x == 0):
        raise ValueError(name + ' must be ' + ('positive' if positive else 'nonnegative'))
    return float(x)


def trip_drive(*, zener_max_v, test_current_a, series_max_ohm,
               threshold_max_v, clamp_min_v, clamp_r_min_ohm,
               extra_sink_max_a, helpful_source_min_a):
    """Sufficient supply and charging current at the upper threshold.

No time bound if the net current is nonpositive. Source must remain available
through capacitor charging AND the receiver's subsequent detection interval.
"""
    vals = locals().copy()
    v, i, r, th, cl, cr, extra, help_i = [
        _n(x, k, k in ('test_current_a', 'clamp_r_min_ohm')) for k, x in vals.items()]
    sink = max(0.0, (th-cl)/cr) + extra
    return {'supply_sufficient_v': v+i*r+th,
            'charging_current_min_a': i+help_i-sink,
            'basis': 'CONDITIONAL_ON_CALLER_BOUNDS'}


def no_trip_budget(*, threshold_min_v, clamp_max_v, clamp_r_max_ohm,
                   other_source_max_a):
    """External injection must be strictly BELOW this steady current budget.

Negative budget means this sufficient static test cannot establish no-trip;
this does not assert actual triggering. Dynamics are a separate alternative.
"""
    th = _n(threshold_min_v, 'threshold_min_v')
    cl = _n(clamp_max_v, 'clamp_max_v')
    r = _n(clamp_r_max_ohm, 'clamp_r_max_ohm', True)
    source = _n(other_source_max_a, 'other_source_max_a')
    return {'external_current_budget_a': max(0.0, (th-cl)/r)-source,
            'basis': 'CONDITIONAL_ON_CALLER_BOUNDS'}


def hold_charge(*, capacitance_min_f, start_min_v, reset_max_v, deficit_charge_c):
    """Charge deficit includes supply gaps, switching delay and all loads.

A zero margin cannot guarantee avoiding reset; negative margin is not proof
of actual reset if inputs are conservative bounds rather than a trajectory.
"""
    c = _n(capacitance_min_f, 'capacitance_min_f', True)
    start = _n(start_min_v, 'start_min_v')
    reset = _n(reset_max_v, 'reset_max_v')
    deficit = _n(deficit_charge_c, 'deficit_charge_c')
    return {'voltage_lower_bound_v': start-deficit/c,
            'charge_margin_c': c*(start-reset)-deficit,
            'basis': 'CONDITIONAL_ON_CALLER_BOUNDS'}
