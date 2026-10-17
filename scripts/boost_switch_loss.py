"""Conditional triangular boost cycles. Inputs must be qualified by the reviewer.

No controller mode prediction, parasitic switching model, SOA verdict or grading.
DCM dead time changes peak current to preserve the specified average input current.
"""
import math


def boost_cycle(vin, vbus, inductance, input_current, dead_time=0.0):
    values = (vin, vbus, inductance, input_current, dead_time)
    if not all(math.isfinite(x) for x in values):
        raise ValueError('finite inputs required')
    if not 0 < vin < vbus or inductance <= 0 or input_current <= 0 or dead_time < 0:
        raise ValueError('require 0 < Vin < Vbus, L and Iavg > 0, dead time >= 0')
    a = inductance * (1 / vin + 1 / (vbus - vin))
    peak = input_current + math.sqrt(input_current ** 2 + 2 * input_current * dead_time / a)
    ton = inductance * peak / vin
    toff = inductance * peak / (vbus - vin)
    period = ton + toff + dead_time
    return dict(peak_A=peak, ton_s=ton, toff_s=toff, period_s=period,
                frequency_Hz=1 / period, switch_mean_square_A2=peak ** 2 * ton / (3 * period),
                input_mean_A=peak * (ton + toff) / (2 * period),
                input_energy_J=vin * peak * (ton + toff) / 2,
                output_energy_J=vbus * peak * toff / 2)


def conditional_losses(cycle, vbus, rds, overlap_time, residual_eoss=0.0):
    """Linear overlap + separately budgeted turn-on Eoss, not measured Eoff.

Do not add stored Coss a second time if using measured total switching energy.
Other turn-on current, diode capacitance, ringing and avalanche are excluded.
"""
    if not all(math.isfinite(x) and x >= 0 for x in (vbus, rds, overlap_time, residual_eoss)) or vbus == 0:
        raise ValueError('positive voltage and finite nonnegative loss inputs required')
    return dict(conduction_W=rds * cycle['switch_mean_square_A2'],
                overlap_W=0.5 * vbus * cycle['peak_A'] * overlap_time * cycle['frequency_Hz'],
                residual_eoss_W=residual_eoss * cycle['frequency_Hz'])
