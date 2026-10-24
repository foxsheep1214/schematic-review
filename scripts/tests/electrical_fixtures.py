"""Synthetic, explicitly bounded source documents for electrical regression tests."""
from board_intent import input_fingerprint


def bound_intent(db, sections=None, populated=True, state='run', **extra):
    """新约定下的意图骨架：共享绑定 + 一个装配状态 + 各检查器段。"""
    intent = {'input_sha256': input_fingerprint(db),
              'assemblies': [{'id': state, 'citation': 'synthetic BOM option A',
                              'population': {ref: True for ref in db['parts']} if populated else {}}]}
    intent.update(sections or {})
    intent.update(extra)
    return intent


def pin_analysis(low, high, time_low=0, time_high=1):
    return {'voltage_v': {'min': low, 'max': high},
            'sample_window_s': {'min': time_low, 'max': time_high},
            'method': 'synthetic circuit corner calculation',
            'calculation': 'Voltage bounds follow the explicitly supplied synthetic circuit conditions',
            'loading': 'Synthetic test specifies all loading; no additional unmodelled leakage',
            'conditions': 'Synthetic test specifies rails, initial conditions, sample times and tolerances'}
