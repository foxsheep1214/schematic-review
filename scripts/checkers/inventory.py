#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清单打包：逐装配状态扫描、输入指纹绑定与内容摘要。

摘要覆盖全部清单内容，计划项据此绑定；输入或状态一变，旧绑定立即过期。
"""
import hashlib
import json

import board_intent
from electrical_contract import db_fingerprint

from . import states as state_lib


def digest(payload):
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def build(db, intent, section, key, scanner, discovery_gaps=(), extra=None):
    """按 intent.assemblies 的装配状态逐一扫描；未声明时用按图状态并保留缺口。

    extra(state) 返回同一状态下的附加清单字段，避免为第二类对象重复解析状态。
    """
    source = intent if isinstance(intent, dict) else {}
    states = []
    for state in state_lib.resolve(db, source.get('assemblies')):
        entry = {'id': state['id'], 'citation': state['citation'],
                 'declared': state['declared'], 'gaps': state['gaps'],
                 key: scanner(state)}
        entry.update(extra(state) if extra else {})
        states.append(entry)
    inventory = {
        'schema_version': 1,
        'input_sha256': db_fingerprint(db),
        'context': board_intent.context(source, section),
        'discovery_gaps': sorted(discovery_gaps),
        'states': states,
    }
    inventory['digest'] = digest(inventory)
    return inventory


def walk(inventory, key):
    """遍历 (状态, 对象)。"""
    for state in inventory.get('states', []):
        for item in state.get(key, []):
            yield state, item


def walk_distinct(inventory, key):
    """遍历 (首个状态, 对象, 同结果状态列表)。

    同一对象在多个装配状态下扫描结果逐字段相同（拓扑、连接、缺口都一样）时，检查结论不可能随状态不同，
    只生成一项并记下全部适用状态；任何字段不同的状态仍各自成项。
    """
    groups, order = {}, []
    for state in inventory.get('states', []):
        for item in state.get(key, []):
            sig = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if sig in groups:
                groups[sig][2].append(state['id'])
            else:
                groups[sig] = (state, item, [state['id']])
                order.append(sig)
    for sig in order:
        yield groups[sig]


def state_fields(state_ids):
    """计划对象里的状态字段：单一状态只写 state；合并时另写 states。"""
    fields = {'state': state_ids[0]}
    if len(state_ids) > 1:
        fields['states'] = list(state_ids)
    return fields
