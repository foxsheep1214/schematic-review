"""Conditional packet-energy bounds; callers establish the physical input bounds.

Time begins at the stated event (not automatically at fault onset). A pre-existing
magnetic energy packet is counted separately. No acceptance or severity is inferred.
"""
import math
from decimal import Decimal
from electrical_contract import finite


def _number(value, name, positive=False):
    if not finite(value):
        raise ValueError(name + ' must be finite')
    if value < 0 or (positive and value == 0):
        raise ValueError(name + (' must be positive' if positive else ' must be nonnegative'))
    return float(value)


def packet_bound(*, inductance_h, peak_current_a, frequency_hz, duration_s,
                 capacitance_f, initial_voltage_v, initial_stored_j):
    """Full per-cycle packets conservatively ignore load and conversion losses.

Applicable to a flyback with bounded primary turn-off current and event rate,
including CCM: each cycle's transferred magnetic energy is at most L*Ipk²/2.
The caller must separately include any already-stored energy at the time origin.
"""
    L = _number(inductance_h, 'inductance_h', True)
    I = _number(peak_current_a, 'peak_current_a')
    f = _number(frequency_hz, 'frequency_hz', True)
    t = _number(duration_s, 'duration_s')
    C = _number(capacitance_f, 'capacitance_f', True)
    v = _number(initial_voltage_v, 'initial_voltage_v')
    initial = _number(initial_stored_j, 'initial_stored_j')
    packet = .5 * L * I * I
    # Preserve decimal input boundaries (40 us * 150 kHz is six, not seven).
    cycles = math.ceil(Decimal(str(f)) * Decimal(str(t)))
    energy = cycles * packet + initial
    return {'cycles': cycles, 'packet_j': packet, 'energy_j': energy,
            'final_voltage_v': math.sqrt(v*v + 2*energy/C),
            'basis': 'CONDITIONAL_ON_CALLER_BOUNDS'}


def capacitor_energy_window(*, capacitance_f, initial_voltage_v, limit_voltage_v,
                            initial_stored_j, packet_j, frequency_hz):
    """Discrete remaining-event budget before a stated capacitor-voltage limit.

A zero/negative remaining energy margin never yields a positive time budget.
This is an energy budget, not proof the detector or switch meets it.
"""
    C = _number(capacitance_f, 'capacitance_f', True)
    v = _number(initial_voltage_v, 'initial_voltage_v')
    limit = _number(limit_voltage_v, 'limit_voltage_v')
    stored = _number(initial_stored_j, 'initial_stored_j')
    packet = _number(packet_j, 'packet_j', True)
    f = _number(frequency_hz, 'frequency_hz', True)
    remaining = .5*C*(limit*limit-v*v)-stored
    count = max(0, math.floor(remaining/packet))
    return {'remaining_energy_j': remaining, 'allowed_full_packets': count,
            'duration_budget_s': count/f, 'basis': 'CONDITIONAL_ON_CALLER_BOUNDS'}
