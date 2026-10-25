#!/usr/bin/env python3
"""A requirement's numbers as fixed parameters (fixed requirements, step 3).

The reviewer reads each requirement's numbers into `requirements[].parameters` [{name, min, max, unit, condition}]:
the name and its units come from catalog.REQUIREMENT_PARAMETERS, every number must appear in that requirement's
original text (a ± number gives both signs), and a condition must be a piece of that text. The plan uses them: a rail
window `power_rails.<net>.voltage_v: {"requirement": <id>}` takes that requirement's voltage range, the input range
reaches the power-tree frame and the ambient temperature reaches the part stress rows.
"""
import copy
import re

import catalog
from electrical_contract import finite, squeeze

NUMBER_RE = re.compile(r'(±|[-−+])?(\d+(?:\.\d+)?)')
RAIL_PARAMETERS = ('input_voltage', 'output_voltage')
INPUT_PARAMETERS = ('input_voltage', 'input_frequency')
# The requirement numbers a part stress row is judged under.
STRESS_CONDITIONS = {'DEV-C01': ('ambient_temperature',), 'DEV-C02': ('ambient_temperature', 'lifetime'),
                     'DEV-C05': ('ambient_temperature',)}


_number = finite


_squeeze = squeeze


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


def _unit_pattern():
    units = sorted({u for entry in catalog.REQUIREMENT_PARAMETERS.values() for u in entry.units}, key=len, reverse=True)
    return '|'.join(re.escape(u) for u in units)


UNIT_NUMBER_RE = None


def unread_numbers(original, parameters):
    """The unit-bearing numbers of a requirement's text that no parameter states, as written ('264 Vac'); a range
    '85–264 Vac' gives both ends. Numbers without a unit (ids, counts) are not listed: a parameter needs a unit."""
    global UNIT_NUMBER_RE
    if UNIT_NUMBER_RE is None:
        UNIT_NUMBER_RE = re.compile(r'(±|[-−+])?(\d+(?:\.\d+)?)(?:\s*[-–~～至到/]\s*(±|[-−+])?(\d+(?:\.\d+)?))?\s*(%s)(?![A-Za-z])'
                                    % _unit_pattern())
    stated = set()
    for item in parameters or ():
        if isinstance(item, dict):
            for key in ('min', 'max'):
                if _number(item.get(key)):
                    stated.add(round(float(item[key]), 9))
    out = []
    for match in UNIT_NUMBER_RE.finditer(original or ''):
        unit = match.group(5)
        for sign, digits in ((match.group(1), match.group(2)), (match.group(3), match.group(4))):
            if digits is None:
                continue
            value = float(digits)
            values = {value, -value} if sign == '±' else {-value if sign in ('-', '−') else value}
            if not any(round(v, 9) in stated for v in values):
                out.append('%s%s %s' % (sign or '', digits, unit))
    return out


def parameter_homes(values, categories):
    """{number as written: [parameter names]} — the catalog parameters whose units take the number's unit and whose aspects
    belong to the requirement's categories; [] when no parameter can take it (the reviewer explains it in the
    interpretation or registers a rule gap)."""
    aspects = {a for c in categories for a in (catalog.REQUIREMENT_CATEGORIES.get(c).aspects
                                                if catalog.REQUIREMENT_CATEGORIES.get(c) else ())}
    homes = {}
    for value in values:
        unit = value.rsplit(' ', 1)[-1]
        homes[value] = sorted(name for name, param in catalog.REQUIREMENT_PARAMETERS.items()
                              if unit in param.units and set(catalog.PARAMETER_ASPECTS.get(name, ())) & aspects)
    return homes


def home_text(value, homes):
    names = homes.get(value) or []
    if not names:
        return value + '（没有参数能收这个数：在 interpretation 里说明，或登记 rule_gaps）'
    return value + '（可写进 ' + ' / '.join('%s %s' % (n, catalog.REQUIREMENT_PARAMETERS[n].title) for n in names) + '）'


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


# The mission profile (consistency proposals of 2026-10-23, item 6d): one profile in the intent that every life row is
# planned on — the phases of the design life with their share of the time, the load as a fraction of the rated load
# and the ambient, and the counts (catalog.LIFE_EVENTS, over the design life); each cites a piece of its requirement.
PROFILE_FIELDS = ('requirement', 'phases', 'events')
PHASE_FIELDS = ('name', 'share', 'load', 'ambient_c', 'citation', 'requirement')
EVENT_FIELDS = ('event', 'count', 'refs', 'citation', 'requirement')
SHARE_TOLERANCE = 0.01


def _cited(label, item, default, ids, originals):
    rid = item.get('requirement', default)
    if rid not in ids:
        return ['%s.requirement %r 不是 intent.requirements 里的需求' % (label, rid)]
    citation, original = item.get('citation'), originals.get(rid)
    if not (isinstance(citation, str) and citation.strip()):
        return [label + '.citation 须是需求原文里的一段']
    if original is not None and _squeeze(citation) not in _squeeze(original):
        return ['%s.citation 须是需求 %s 原文里的一段' % (label, rid)]
    return []


def mission_profile_errors(intent, originals, refs=None):
    """Errors of intent.mission_profile; `originals` {requirement id: original text}, `refs` the board's designators."""
    profile = intent.get('mission_profile') if isinstance(intent, dict) else None
    if profile is None:
        return []
    if not isinstance(profile, dict) or set(profile) - set(PROFILE_FIELDS):
        return ['mission_profile 是 {requirement, phases[, events]}']
    ids = {r.get('id') for r in intent.get('requirements') or [] if isinstance(r, dict)}
    rid, out = profile.get('requirement'), []
    if rid not in ids:
        out.append('mission_profile.requirement %r 不是 intent.requirements 里的需求' % (rid,))
    elif not [w for w in windows(intent, 'lifetime') if w['requirement'] == rid]:
        out.append('mission_profile.requirement %s 没有 lifetime 参数；剖面写在给出设计寿命的需求下' % rid)
    phases = profile.get('phases')
    if not (isinstance(phases, list) and phases):
        return out + ['mission_profile.phases 须为非空数组']
    names, total = set(), 0.0
    for n, phase in enumerate(phases, 1):
        label = 'mission_profile.phases[%d]' % n
        if not isinstance(phase, dict) or set(phase) - set(PHASE_FIELDS):
            out.append(label + ' 是 {name, share, load, ambient_c, citation[, requirement]}')
            continue
        name = phase.get('name')
        if not (isinstance(name, str) and name.strip()) or name in names:
            out.append(label + '.name 缺失或重复')
        names.add(name)
        share = phase.get('share')
        if not (_number(share) and 0 < share <= 1):
            out.append(label + '.share 是这一段占设计寿命时间的比例（0–1）')
        else:
            total += share
        if not (_number(phase.get('load')) and 0 <= phase['load'] <= 1):
            out.append(label + '.load 是负载占额定负载的比例（0–1）')
        if not _number(phase.get('ambient_c')):
            out.append(label + '.ambient_c 是这一段的环境温度（°C）')
        out.extend(_cited(label, phase, rid, ids, originals))
    if abs(total - 1) > SHARE_TOLERANCE and not any('share' in e for e in out):
        out.append('mission_profile.phases 各段 share 合计 %.3f，须为 1（覆盖整个设计寿命）' % total)
    events = profile.get('events', [])
    if not isinstance(events, list):
        return out + ['mission_profile.events 须为数组']
    for n, event in enumerate(events, 1):
        label = 'mission_profile.events[%d]' % n
        if not isinstance(event, dict) or set(event) - set(EVENT_FIELDS):
            out.append(label + ' 是 {event, count, citation[, refs, requirement]}')
            continue
        if event.get('event') not in catalog.LIFE_EVENTS:
            out.append('%s.event 取 %s' % (label, '/'.join(catalog.LIFE_EVENTS)))
        if not (_number(event.get('count')) and event['count'] > 0):
            out.append(label + '.count 是设计寿命内的总次数（正数）')
        if 'refs' in event and not (isinstance(event['refs'], list) and event['refs']
                                    and all(isinstance(r, str) and (refs is None or r in refs) for r in event['refs'])):
            out.append(label + '.refs 是本板位号的非空数组')
        out.extend(_cited(label, event, rid, ids, originals))
    return out


def mission_profile(intent):
    """The well-formed mission profile in hours: {requirement, years, hours, phases[{name, share, load, ambient_c,
    hours}], events[{event, count, refs}]}; None without one or with errors."""
    profile = intent.get('mission_profile') if isinstance(intent, dict) else None
    if profile is None or mission_profile_errors(intent, {}):
        return None
    lives = [w for w in windows(intent, 'lifetime') if w['requirement'] == profile['requirement']]
    years = max(v for w in lives for v in (w['min'], w['max']) if v is not None)
    hours = round(years * 8760, 6)
    return {'requirement': profile['requirement'], 'years': years, 'hours': hours,
            'phases': [dict({k: p[k] for k in ('name', 'share', 'load', 'ambient_c')}, hours=p['share'] * hours)
                       for p in profile['phases']],
            'events': [{'event': e['event'], 'count': e['count'], 'refs': e.get('refs')}
                       for e in profile.get('events') or []]}


def profile_text(profile):
    """'任务剖面（REQ-LIFE-1，10 年共 87600 h）：充电 33.3%（29200 h，负载 100%，40 °C）；…' for a life row."""
    return '任务剖面（%s，%g 年共 %g h）：%s' % (profile['requirement'], profile['years'], profile['hours'], '；'.join(
        '%s %.1f%%（%g h，负载 %g%%，%g °C）' % (p['name'], p['share'] * 100, round(p['hours']), round(p['load'] * 100, 1),
                                           p['ambient_c']) for p in profile['phases']))


def profile_criterion_text(profile):
    """The profile as a life row's criterion reads it: the same numbers as profile_text without the phase names, in
    (share, load, ambient) order, so two reviewers who named the phases differently plan the same check (R6 acceptance
    2026-10-24: 17 life rows per pair unpaired on names alone)."""
    phases = sorted(profile['phases'], key=lambda p: (-p['share'], p['load'], p['ambient_c']))
    return '任务剖面（%s，%g 年共 %g h）：%s' % (profile['requirement'], profile['years'], profile['hours'], '；'.join(
        '%.1f%%（%g h，负载 %g%%，%g °C）' % (p['share'] * 100, round(p['hours']), round(p['load'] * 100, 1), p['ambient_c'])
        for p in phases))


def profile_count(profile, event, ref):
    """The count the profile gives `event` for part `ref`, or None."""
    counts = [e['count'] for e in (profile or {}).get('events') or []
              if e['event'] == event and (not e.get('refs') or ref in e['refs'])]
    return max(counts) if counts else None
