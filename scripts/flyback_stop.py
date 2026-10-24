"""Phase-specific flyback calculations; callers qualify all physical bounds.

No controller timing, parasitic model, automatic SOA verdict or severity inference.
"""
import math
from electrical_contract import finite


def _finite(value, name, positive=False):
    if not finite(value):
        raise ValueError(name + ' needs an evidenced finite input; missing is not zero')
    if value < 0 or (positive and value == 0):
        raise ValueError(name + ' out of physical range')
    return float(value)


def post_stop_capacitor_bound(*, voltage_at_stop_v, capacitance_f, remaining_energy_j):
    """Capacitor stored-energy voltage after actual primary switching has stopped.

Remaining energy must bound ALL energy still able to reach the output, not just
one guessed magnetic packet. Assumes no subsequent source/restart/backfeed;
ignoring load and dissipative loss is conservative. ESR/ESL terminal spikes are
not included, nor is there a claim about rectifier blocking at another phase.
"""
    v = _finite(voltage_at_stop_v, 'voltage_at_stop_v')
    c = _finite(capacitance_f, 'capacitance_f', True)
    e = _finite(remaining_energy_j, 'remaining_energy_j')
    return {'capacitor_voltage_bound_v': math.sqrt(v*v + 2*e/c),
            'basis': 'CONDITIONAL_ON_CALLER_BOUNDS',
            'phase': 'AFTER_LAST_PRIMARY_SWITCHING', 'terminal_spikes_included': False}


def primary_on_sr_platform(*, output_v_at_event, primary_bus_v_at_event,
                           primary_secondary_ratio, phase):
    """Ideal low-side SR blocking platform, same primary-on event only.

A post-stop maximum output cannot be relabeled as this event's output. Ringing,
commutation overshoot and simultaneous-conduction behavior need separate models.
"""
    if phase != 'PRIMARY_ON':
        raise ValueError('Vout + Vbus/n applies only to a primary-on event')
    v = _finite(output_v_at_event, 'output_v_at_event')
    bus = _finite(primary_bus_v_at_event, 'primary_bus_v_at_event')
    n = _finite(primary_secondary_ratio, 'primary_secondary_ratio', True)
    return {'platform_v': v + bus/n, 'phase': phase,
            'basis': 'CONDITIONAL_ON_SAME_EVENT_INPUTS', 'spikes_included': False}
