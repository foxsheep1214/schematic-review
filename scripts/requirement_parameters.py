#!/usr/bin/env python3
"""A requirement's numbers as fixed parameters (fixed requirements, step 3).

The reviewer reads each requirement's numbers into `requirements[].parameters` [{name, min, max, unit, condition}]:
the name and its units come from catalog.REQUIREMENT_PARAMETERS, every number must appear in that requirement's
original text (a ± number gives both signs), and a condition must be a piece of that text. The plan uses them: a rail
window `power_rails.<net>.voltage_v: {"requirement": <id>}` takes that requirement's voltage range, the input range
reaches the power-tree frame and the ambient temperature reaches the part stress rows.
"""
import copy
import math
import re

import catalog

NUMBER_RE = re.compile(r'(±|[-−+])?(\d+(?:\.\d+)?)')
RAIL_PARAMETERS = ('input_voltage', 'output_voltage')
INPUT_PARAMETERS = ('input_voltage', 'input_frequency')
# The requirement numbers a part stress row is judged under.
STRESS_CONDITIONS = {'DEV-C01': ('ambient_temperature',), 'DEV-C02': ('ambient_temperature', 'lifetime'),
                     'DEV-C05': ('ambient_temperature',)}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _squeeze(text):
    return re.sub(r'\s', '', text or '')


def numbers(text):
    """Every number the text states, signed as written; a sign right after a digit is a range dash, not a minus."""
    out = set()
    for match in NUMBER_RE.finditer(text or ''):
        sign, value = match.group(1), float(match.group(2))
        if sign and sign != '±' and match.start() > 0 and text[match.start() - 1].isdigit():
            sign = None
        if sign == '±':
            out.update((value, -value))
        else:
            out.add(-value if sign in ('-', '−') else value)
    return out


def errors(rid, parameters, original):
    """Errors of one requirement's parameters against its original text (None when the text is not known)."""
    label = 'requirement.%s.parameters' % rid
    if not isinstance(parameters, list):
        return [label + ' 须为数组']
    out, stated = [], numbers(original) if original is not None else None
    for n, item in enumerate(parameters, 1):
        at = '%s[%d]' % (label, n)
        if not isinstance(item, dict):
            out.append(at + ' 须为 object')
            continue
        entry = catalog.REQUIREMENT_PARAMETERS.get(item.get('name'))
        if entry is None:
            out.append('%s.name 不支持: %r（取规则总表需求参数表）' % (at, item.get('name')))
            continue
        if item.get('unit') not in entry.units:
            out.append('%s.unit %r 不是 %s 的单位（%s）' % (at, item.get('unit'), item['name'], '、'.join(entry.units)))
        bounds = [k for k in ('min', 'max') if k in item]
        if not bounds:
            out.append(at + ' 至少给 min 或 max')
        for key in bounds:
            if not _number(item[key]):
                out.append('%s.%s 须为有限数' % (at, key))
            elif stated is not None and not any(abs(item[key] - v) < 1e-9 for v in stated):
                out.append('%s.%s %g 不在该条需求原文里；数字只从原文读' % (at, key, item[key]))
        if len(bounds) == 2 and all(_number(item[k]) for k in bounds) and item['min'] > item['max']:
            out.append(at + '.min 大于 max')
        if 'condition' in item and (not isinstance(item['condition'], str) or not item['condition'].strip()
                                    or (original is not None and _squeeze(item['condition']) not in _squeeze(original))):
            out.append(at + '.condition 须是该条需求原文里的一段')
    return out


def normalized(item):
    """A parameter in its canonical unit, with what was written."""
    entry = catalog.REQUIREMENT_PARAMETERS[item['name']]
    scale = entry.units[item['unit']]
    value = lambda key: round(item[key] * scale, 9) if key in item else None
    return {'name': item['name'], 'min': value('min'), 'max': value('max'), 'unit': entry.unit,
            'condition': item.get('condition'),
            'written': {'min': item.get('min'), 'max': item.get('max'), 'unit': item['unit']}}


def _parameters(intent):
    """{requirement id: [normalized parameters]} for the well-formed parameters of the intent."""
    out = {}
    requirements = intent.get('requirements') if isinstance(intent, dict) else None
    for req in requirements if isinstance(requirements, list) else []:
        if not isinstance(req, dict) or not isinstance(req.get('id'), str):
            continue
        items = req.get('parameters') if isinstance(req.get('parameters'), list) else []
        out[req['id']] = [normalized(p) for p in items
                          if isinstance(p, dict) and not errors(req['id'], [p], None)]
    return out


def windows(intent, name):
    """Every requirement window of one parameter: [{name, requirement, min, max, unit, condition}]."""
    return [{'name': name, 'requirement': rid, 'min': p['min'], 'max': p['max'], 'unit': p['unit'],
             'condition': p['condition']}
            for rid, items in sorted(_parameters(intent).items()) for p in items if p['name'] == name]


def envelope(items):
    lows = [w['min'] for w in items if w['min'] is not None]
    highs = [w['max'] for w in items if w['max'] is not None]
    return {'min': min(lows) if lows else None, 'max': max(highs) if highs else None, 'unit': items[0]['unit'],
            'requirements': sorted({w['requirement'] for w in items})}


def _rail_window(parameters, ref):
    """(window, error) for a rail window {requirement, parameter?}."""
    rid = ref.get('requirement')
    if rid not in parameters:
        return None, '不是 intent.requirements 里的需求'
    named = ref.get('parameter')
    candidates = [p for p in parameters[rid] if p['name'] in RAIL_PARAMETERS and (named is None or p['name'] == named)]
    if not candidates:
        return None, '没有 %s 参数' % '/'.join([named] if named else RAIL_PARAMETERS)
    if len({p['name'] for p in candidates}) > 1:
        return None, '同时有 %s，写 parameter 指定取哪一个' % '、'.join(sorted({p['name'] for p in candidates}))
    lows = [p['min'] for p in candidates if p['min'] is not None]
    highs = [p['max'] for p in candidates if p['max'] is not None]
    if not lows or not highs:
        return None, '的电压参数没有给出上下限'
    return dict({'min': min(lows), 'max': max(highs), 'requirement': rid},
                **({'parameter': named} if named else {})), None


def _rail_refs(intent):
    rails = intent.get('power_rails') if isinstance(intent, dict) else None
    for net, budget in (rails.items() if isinstance(rails, dict) else ()):
        window = budget.get('voltage_v') if isinstance(budget, dict) else None
        if isinstance(window, dict) and 'requirement' in window:
            yield net, window


def rail_errors(intent):
    parameters, out = _parameters(intent), []
    for net, ref in _rail_refs(intent):
        if set(ref) - {'requirement', 'parameter'}:
            out.append('power_rails.%s.voltage_v 引用需求时只写 requirement（和 parameter），数值由需求参数给出' % net)
            continue
        _, error = _rail_window(parameters, ref)
        if error:
            out.append('power_rails.%s.voltage_v.requirement %s %s' % (net, ref.get('requirement'), error))
    return out


def resolve(intent):
    """The intent with every rail window that names a requirement filled from that requirement's parameters."""
    refs = list(_rail_refs(intent))
    if not refs:
        return intent
    out, parameters = copy.deepcopy(intent), _parameters(intent)
    for net, ref in refs:
        window, _ = _rail_window(parameters, ref)
        if window:
            out['power_rails'][net]['voltage_v'] = window
    return out


def text(window):
    """'9–36 V（REQ-IN-01）' for a frame question."""
    fmt = lambda v: '%g' % v
    lo, hi = window['min'], window['max']
    span = ('%s–%s' % (fmt(lo), fmt(hi)) if lo is not None and hi is not None
            else ('≥' + fmt(lo)) if lo is not None else ('≤' + fmt(hi)))
    return '%s %s（%s）' % (span, window['unit'], window['requirement'])
