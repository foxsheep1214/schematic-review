#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""意图里随网表版本变化的共享声明：装配状态（assemblies）与器件脚表（devices）。

两者和各检查器段都按位号、网络或物理脚声明，统一由顶层 input_sha256 绑定网表；
检查器段只写本检查器的对象，装配状态只在 assemblies 写一次。
名称、nc=false、默认闭合都不是装配证据：未声明就保留缺口。
"""
import hashlib
import json
import re

from electrical_contract import db_fingerprint

ASSEMBLY_FIELDS = ('id', 'citation', 'population', 'jumpers')
JUMPER_POSITIONS = ('closed', 'open', 'unknown')
MAX_ASSEMBLIES = 32
DEVICE_FIELDS = ('mpn', 'package', 'identity_citation', 'citation', 'pinout_complete', 'pins')
PIN_ROLES = ('power', 'return', 'nc', 'other')
SHARED_KEYS = ('input_sha256', 'assemblies', 'devices')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def input_fingerprint(db):
    """网表指纹之外，再覆盖符号独有脚、伪网络与完整性记录。"""
    payload = {'db_sha256': db_fingerprint(db), **{k: db.get(k) for k in (
        'declared_pinname', 'declared_pintype', 'pseudo_nets', 'integrity', 'export_errors')}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_db_shape(db):
    """Reject malformed index containers before hashing or graph iteration."""
    if not isinstance(db, dict):
        return ['db must be an object']
    errors = []
    for field in ('parts', 'nets', 'pin2net', 'pinname', 'pintype', 'integrity'):
        if field in db and not isinstance(db[field], dict):
            errors.append('db.' + field + ' must be an object')
    if errors:
        return errors
    if not all(_text(ref) and isinstance(part, dict) for ref, part in db.get('parts', {}).items()):
        errors.append('db.parts requires named part objects')
    if not all(_text(net) and isinstance(nodes, list) and all(_text(n) for n in nodes)
               for net, nodes in db.get('nets', {}).items()):
        errors.append('db.nets requires named arrays of physical nodes')
    for field in ('pin2net', 'pinname', 'pintype'):
        if not all(_text(node) and isinstance(value, str) for node, value in db.get(field, {}).items()):
            errors.append('db.' + field + ' requires string node/value pairs')
    if 'pseudo_nets' in db and not (isinstance(db['pseudo_nets'], list) and all(_text(n) for n in db['pseudo_nets'])):
        errors.append('db.pseudo_nets must be a string array')
    return errors


def validate(intent, db=None):
    """校验 input_sha256、assemblies 与 devices；都未声明时不要求绑定。"""
    if not isinstance(intent, dict) or not any(key in intent for key in SHARED_KEYS):
        return []
    if db is not None:
        errors = validate_db_shape(db)
        if errors:
            return errors
    errors = []
    digest = intent.get('input_sha256')
    if not (isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest)):
        errors.append('input_sha256 is required when assemblies/devices/checker sections are declared')
    elif db is not None and digest != input_fingerprint(db):
        errors.append('stale input_sha256')
    if 'assemblies' in intent:
        errors.extend(assembly_errors(intent['assemblies'], db))
    if 'devices' in intent:
        errors.extend(device_errors(intent['devices'], db))
    return errors


def requires_assemblies(intent, label):
    """检查器段依赖共享装配状态与绑定；缺了就报一次。"""
    if isinstance(intent, dict) and label in intent and 'assemblies' not in intent:
        return [label + ': requires intent.assemblies (assembly states moved out of checker sections)']
    return []


def assembly_errors(assemblies, db):
    errors = []

    def require(ok, message):
        if not ok:
            errors.append('assemblies: ' + message)

    require(isinstance(assemblies, list) and 0 < len(assemblies) <= MAX_ASSEMBLIES,
            'must contain 1..%d assembly states' % MAX_ASSEMBLIES)
    seen = set()
    for state in assemblies if isinstance(assemblies, list) else []:
        if not isinstance(state, dict):
            require(False, 'state must be an object')
            continue
        require(not set(state) - set(ASSEMBLY_FIELDS), 'state has unsupported fields')
        sid = state.get('id')
        require(_text(sid) and sid not in seen, 'state id missing/duplicate')
        if _text(sid):
            seen.add(sid)
        require(_text(state.get('citation')), 'state needs assembly/configuration citation')
        for key in ('population', 'jumpers'):
            entries = state.get(key, {})
            require(isinstance(entries, dict), key + ' must be an object')
            for ref, value in entries.items() if isinstance(entries, dict) else []:
                require(_text(ref) and (db is None or ref in db.get('parts', {})),
                        key + ': unknown ref ' + str(ref))
                ok = (type(value) is bool if key == 'population'
                      else isinstance(value, str) and value in JUMPER_POSITIONS)
                require(ok, key + ': invalid value for ' + str(ref))
    return errors


def device_errors(devices, db):
    errors = []

    def require(ok, message):
        if not ok:
            errors.append('devices: ' + message)

    require(isinstance(devices, dict), 'must be an object keyed by refdes')
    for ref, device in devices.items() if isinstance(devices, dict) else []:
        require(_text(ref) and (db is None or ref in db.get('parts', {})), 'unknown device ' + str(ref))
        if not isinstance(device, dict):
            require(False, 'device must be an object')
            continue
        require(not set(device) - set(DEVICE_FIELDS), 'device has unsupported fields')
        for key in ('mpn', 'package', 'identity_citation', 'citation'):
            require(_text(device.get(key)), 'device ' + str(ref) + ' needs ' + key)
        require(type(device.get('pinout_complete')) is bool, 'pinout_complete must be boolean')
        pins = device.get('pins')
        require(isinstance(pins, dict) and bool(pins), 'device needs full physical pin map')
        for pin, spec in pins.items() if isinstance(pins, dict) else []:
            require(_text(pin) and '.' not in pin and not any(c.isspace() for c in pin),
                    'invalid physical pin number')
            if not isinstance(spec, dict):
                require(False, 'pin must be an object')
                continue
            require(not set(spec) - {'name', 'role'}, 'pin has unsupported fields')
            require(_text(spec.get('name')), 'pin name missing')
            require(isinstance(spec.get('role'), str) and spec['role'] in PIN_ROLES, 'unsupported pin role')
    return errors


def context(intent, key, extra=()):
    """检查器清单的重建上下文：共享声明加本检查器段，未声明的键不写。"""
    source = intent if isinstance(intent, dict) else {}
    return {k: source[k] for k in ('input_sha256', 'assemblies') + tuple(extra) + (key,) if k in source}


def pin_sets(db, ref, device):
    """官方脚表与网表/符号实有脚的双向差集。"""
    official = {ref + '.' + pin for pin in device['pins']}
    observed = set()
    for field in ('pin2net', 'pinname', 'pintype', 'declared_pinname', 'declared_pintype'):
        observed.update(n for n in db.get(field, {}) if n.rpartition('.')[0] == ref)
    return sorted(official - observed), sorted(observed - official)


def pin_disposition(db, ref, device):
    """官方脚中未接入真实网络的脚（无网、单节点网或 No-Connect 汇集网），以及脚表标 nc 却接了网的脚。"""
    nets, pin2net = db.get('nets', {}), db.get('pin2net', {})
    pseudo = set(db.get('pseudo_nets', []))
    unconnected, nc_connected = [], []
    for pin, spec in sorted(device['pins'].items()):
        node = ref + '.' + pin
        net = pin2net.get(node)
        if not net or net in pseudo or len(nets.get(net, [])) < 2:
            unconnected.append(node)
        elif spec['role'] == 'nc':
            nc_connected.append(node)
    return unconnected, nc_connected
