#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查器注册表。

加一个检查器 = 加一个模块并登记到 REGISTRY；计划、lint 与校验都按注册表遍历，
不需要再改主流程。检查器的规则编号、名称与判据都登记在 scripts/catalog.py，
检查器只引用编号。
"""
from .base import Checker, validate_inventories
from .powertree import PowerTree
from .decoupling import DecouplingChecker
from .diff_levels import DiffLevelsChecker
from .i2c import I2CTopologyChecker
from .inductive_load import InductiveLoadChecker
from .input_filter import InputFilterChecker
from .optocoupler import OptocouplerChecker
from .power_switch import PowerSwitchChecker
from .power_up import PowerUpChecker
from .supervision import SupervisionChecker

REGISTRY = (
    I2CTopologyChecker(),
    DecouplingChecker(),
    InductiveLoadChecker(),
    PowerSwitchChecker(),
    InputFilterChecker(),
    PowerUpChecker(),
    SupervisionChecker(),
    DiffLevelsChecker(),
    OptocouplerChecker(),
)

REGISTRY_BY_ID = {checker.id: checker for checker in REGISTRY}


def registry_cold_rules():
    """自动扫描规则编号 -> (名称, 检查器)。"""
    table = {}
    for checker in REGISTRY:
        for rule, name in checker.cold_rules.items():
            table[rule] = (name, checker)
    return table


def registry_hot_rules():
    """证据计算规则编号 -> (名称, 检查器)。"""
    table = {}
    for checker in REGISTRY:
        for rule, name in checker.hot_rules.items():
            table[rule] = (name, checker)
    return table


__all__ = ['Checker', 'PowerTree', 'REGISTRY', 'REGISTRY_BY_ID', 'registry_cold_rules',
           'registry_hot_rules', 'validate_inventories']
