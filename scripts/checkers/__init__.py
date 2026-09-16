#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查器注册表。

加一个检查器 = 加一个模块并登记到 REGISTRY；计划、lint 与校验都按注册表遍历，
不需要再改主流程。顺序固定，保证既有检查 ID 不变。
"""
from .base import Checker, validate_inventories
from .decoupling import DecouplingChecker
from .i2c import I2CTopologyChecker
from .inductive_load import InductiveLoadChecker

REGISTRY = (
    I2CTopologyChecker(),
    DecouplingChecker(),
    InductiveLoadChecker(),
)

REGISTRY_BY_ID = {checker.id: checker for checker in REGISTRY}


def registry_cold_rules():
    """规则号 -> (名称, 检查器)。"""
    table = {}
    for checker in REGISTRY:
        for rule, name in checker.cold_rules.items():
            table[rule] = (name, checker)
    return table


def registry_hot_rules():
    table = {}
    for checker in REGISTRY:
        for rule, name in checker.hot_rules.items():
            table[rule] = (name, checker)
    return table


__all__ = ['Checker', 'REGISTRY', 'REGISTRY_BY_ID', 'registry_cold_rules',
           'registry_hot_rules', 'validate_inventories']
