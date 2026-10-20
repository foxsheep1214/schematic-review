"""Small, typed closure contracts for easily lost schematic obligations.

These contracts prove coverage and request ownership, not electrical correctness.
Names/requirements are controlled by the rule, never inferred from prose.
"""
CONTRACTS = {
    'PRO-C03': ('isolation_qualification', {
        'working_stress': '实际工作电压、重复峰值与频率',
        'qualification_match': '各跨隔离器件的资格与实际条件匹配',
    }),
    'PWR-C15': ('loop_stability', {
        'loop_model': '实际拓扑、工作点及反馈模型',
        'compensation_configuration': '实际补偿配置与适用条件',
        'stability_limits': '规定角点的稳定性与动态边界',
    }),
}


def contract(rule):
    """Plan-side only until the planner emits function frames (design §6); results no longer carry obligations."""
    if rule not in CONTRACTS:
        return None
    domain, obligations = CONTRACTS[rule]
    return {'closure_domain': domain, 'obligations': dict(obligations)}
