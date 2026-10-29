#!/usr/bin/env python3
"""The project's derating level and the stress check of a margin that names a derating rule (stress spec, 2026-10-27).

The level (I/II/III) is part of the requirements: `intent.derating{level, source}`, where source is `req:<requirement
id>` or `clarification:<answered clarification id>`; the planner copies it into the plan. A margin that names
`basis.derating_rule` is checked against the rule's value at that level (references/derating-rules.json, shared with
ASG): over the rating it fails as any margin does; within the rating but over the derated value it passes with the
stress risk (`basis.risk.types` holds STRESS), listed in the risk list and not blocking (references/stress-spec.md,
user 2026-10-27: 将共用规范R6和ASG统一到现在的“应力”规范下来). Only margins the reviewer writes are checked; a stress
margin of a part whose kind has rules but names none is a hint (user: 统一到余量审核规则上来).
"""
import json
from pathlib import Path
import re

from electrical_contract import text

RULES_PATH = Path(__file__).resolve().parent.parent / 'references' / 'derating-rules.json'
LEVELS = ('I', 'II', 'III')
SOURCE_RE = re.compile(r'^(req|clarification):(\S+)$')
RECOMPUTED = ('ratio', 'pulse_ratio')   # stress / rating ≤ value: the gate redoes these from the margin and its limit
STRESS_ASPECTS = ('器件应力与降额',)      # the aspect a part's stress margin is written under (DEV-C01)
_RULES = None
# Whether a named rule fits the margin (SR-FIX-05, 2026-10-28, user: 按推荐修改): only what the record states is checked —
# the quantity's dimension (the margin's unit), the terminal pair the limit names, and the technology the part's identity
# names. Steady against transient, and a part whose identity names no technology, are hints, never refusals.
DIMENSIONS = (('I²t', re.compile(r'^A²?s$|^A\^?2\s?s$')), ('能量', re.compile(r'^[mµu]?J$')),
              ('功率', re.compile(r'^[mµuk]?W$')), ('功耗', re.compile(r'^[mµuk]?W$')),
              ('电流', re.compile(r'^[mµukn]?A$')), ('电压', re.compile(r'^[mµuk]?V$')), ('频率', re.compile(r'^[kMG]?Hz$')))
TERMINALS = (('漏-源', 'VDS'), ('栅-源', 'VGS'), ('集电极-发射极', 'VCE'), ('栅-发射极', 'VGE'), ('发射极-基极', 'VEB'))
TERMINAL_RE = re.compile(r'\bV_?\(?(DS|GS|CE|GE|EB|BE)\)?(?:\(?(?:max|MAX|off|on|th|S|T)\)?)?', re.I)
TECHNOLOGIES = {'gan': re.compile(r'\bGaN\b|氮化镓', re.I), 'sic': re.compile(r'\bSiC\b|碳化硅', re.I),
                'igbt': re.compile(r'\bIGBT\b', re.I), 'si': re.compile(r'\bSi\b(?!C)|硅(?!胶)')}
TRANSIENT_RE = re.compile(r'尖峰|瞬态|脉冲|浪涌|单次|spike|transient|pulse|surge|peak', re.I)
STEADY_RE = re.compile(r'稳态|连续|持续|直流|steady|continuous|\bDC\b', re.I)


def rules():
    """{rule id: rule} of the shared spec."""
    global _RULES
    if _RULES is None:
        _RULES = {r['id']: r for r in json.loads(RULES_PATH.read_text(encoding='utf-8'))['rules']}
    return _RULES


def engineering_value(name):
    """A value the spec's 工程取值 table holds where the standards give none (unset_level, soa_segment_share)."""
    return json.loads(RULES_PATH.read_text(encoding='utf-8'))['engineering_values'][name]['value']


def kinds_with_rules():
    return {k for r in rules().values() for k in r['kinds']}


def intent_errors(intent):
    """intent.derating: optional until a margin names a rule; when written, a level and where it was decided."""
    info = intent.get('derating') if isinstance(intent, dict) else None
    if info is None:
        return []
    if not isinstance(info, dict) or set(info) != {'level', 'source'}:
        return ['intent.derating 写 {level: I/II/III, source: req:<需求编号> 或 clarification:<已答复的澄清编号>}']
    errors = []
    if info['level'] not in LEVELS:
        errors.append('intent.derating.level 必须为 I、II 或 III')
    m = SOURCE_RE.match(str(info['source'] or ''))
    requirements = {r.get('id'): r for r in intent.get('requirements') or [] if isinstance(r, dict)}
    answered = {c.get('id') for c in intent.get('clarifications') or [] if isinstance(c, dict)
                and isinstance(c.get('answer'), dict) and c['answer'].get('decision') in ('DECIDED', 'ADOPTED_PROPOSAL')}
    if not m:
        errors.append('intent.derating.source 写 req:<需求编号> 或 clarification:<已答复的澄清编号>')
    elif m.group(1) == 'req' and m.group(2) not in requirements:
        errors.append('intent.derating.source %s 不是 intent.requirements 里的需求' % info['source'])
    elif m.group(1) == 'clarification' and m.group(2) not in answered:
        errors.append('intent.derating.source %s 不是已答复（DECIDED / ADOPTED_PROPOSAL）的需求澄清；没定的等级先问用户'
                      % info['source'])
    return errors


def margin_errors(label, margin, conditions, level, kinds_of, identity_of=None):
    """A margin naming basis.derating_rule: the rule exists and fits the parts, the level is set, and for a ratio rule the
    stress risk is written exactly when the stress is over the derated value. `kinds_of(refs)` gives the parts' kinds."""
    basis = margin.get('basis') if isinstance(margin.get('basis'), dict) else {}
    rid = basis.get('derating_rule')
    if rid is None:
        return []
    rule = rules().get(rid)
    if rule is None:
        return ['%s: basis.derating_rule %s is not in references/derating-rules.json' % (label, rid)]
    limit = conditions.get(basis.get('limit')) or {}
    kinds = kinds_of(limit.get('refs') or [])
    errors = []
    if kinds and not set(kinds) & set(rule['kinds']):
        errors.append('%s: derating rule %s is for %s, the limit\'s parts are %s'
                      % (label, rid, '/'.join(rule['kinds']), '/'.join(sorted(kinds))))
    errors += fit_errors(label, rule, margin, limit, identity_of(limit.get('refs') or []) if identity_of else '')
    if level not in LEVELS:
        return errors + ['%s: names derating rule %s but the project has no derating level; write intent.derating '
                         '{level, source} from a requirement or an answered clarification' % (label, rid)]
    if rule['measure'] not in RECOMPUTED:
        return errors
    bound = limit.get('limit') or {}
    rating = bound.get('max')
    if not isinstance(rating, (int, float)) and isinstance(bound.get('min'), (int, float)) and bound['min'] < 0:
        rating = -bound['min']   # a negative rating (turn-off gate voltage) is compared by magnitude (R8)
    if not isinstance(rating, (int, float)) or not text(margin.get('unit')) or \
            str(bound.get('unit') or '').strip() != margin['unit'].strip():
        return errors + ['%s: a %s derating rule compares the stress with the limit\'s max (or a negative min, by '
                         'magnitude); the limit gives it in the margin\'s unit' % (label, rule['measure'])]
    stress = rating - margin['value']
    derated = rating * rule['values'][level]
    stressed = 'STRESS' in ((basis.get('risk') or {}).get('types') or [])
    if stress > derated and margin['value'] >= 0 and not stressed:
        errors.append('%s: stress %g %s is within the rating %g but over the level %s derated value %g (%s %s); '
                      'write basis.risk{types: [STRESS], corner, improvement} (stress spec)'
                      % (label, stress, margin['unit'], rating, level, derated, rid, rule['parameter']))
    elif stress <= derated and stressed:
        errors.append('%s: stress %g %s is within the level %s derated value %g (%s); no stress risk'
                      % (label, stress, margin['unit'], level, derated, rid))
    return errors


def _terminal(rule):
    return next((sym for word, sym in TERMINALS if word in rule['parameter']), None)


def _named_technologies(identity):
    return {t for t, pattern in TECHNOLOGIES.items() if pattern.search(identity or '')}


def fit_errors(label, rule, margin, limit, identity):
    """The rule's parameter is the quantity compared, and its technology is not one the part's identity rules out."""
    errors = []
    unit = str(margin.get('unit') or '').strip()
    dimension = next(((word, pattern) for word, pattern in DIMENSIONS if word in rule['parameter']), None)
    if rule['measure'] in RECOMPUTED and dimension and unit and not dimension[1].match(unit):
        errors.append('%s: derating rule %s rates %s, but the margin is in %s; name the rule for the quantity compared'
                      % (label, rule['id'], rule['parameter'], unit))
    expected = _terminal(rule)
    named = {('V' + m.group(1)).upper() for m in TERMINAL_RE.finditer(' '.join(
        str(x or '') for x in (limit.get('says'), margin.get('against'))))}
    if expected and named and expected not in named:
        errors.append('%s: derating rule %s is for %s (%s); the limit and margin name %s'
                      % (label, rule['id'], expected, rule['parameter'], '/'.join(sorted(named))))
    technology = rule.get('subtype')
    stated = _named_technologies(identity)
    if technology and stated and technology not in stated:
        errors.append('%s: derating rule %s is for %s parts (%s); the part\'s identity names %s'
                      % (label, rule['id'], technology, rule['type'], '/'.join(sorted(stated))))
    return errors


def fit_hints(margin, conditions, identity_of):
    """What the record does not state: a steady rule on a limit worded as a transient (or the reverse), and a
    technology-specific rule on a part whose identity names no technology. Messages, never refusals."""
    basis = margin.get('basis') if isinstance(margin.get('basis'), dict) else {}
    rule = rules().get(basis.get('derating_rule'))
    if rule is None:
        return []
    limit = conditions.get(basis.get('limit')) or {}
    words = ' '.join(str(limit.get(k) or '') for k in ('says', 'regime')) + ' ' + str(margin.get('against') or '')
    hints = []
    if rule.get('condition') == 'steady' and TRANSIENT_RE.search(words) and not STEADY_RE.search(words):
        hints.append('derating rule %s is for steady operation, the limit reads as a transient; a transient compares '
                     'with the transient rule (…-T) or the pulse rating' % rule['id'])
    if rule.get('condition') in ('transient', 'pulse') and STEADY_RE.search(words) and not TRANSIENT_RE.search(words):
        hints.append('derating rule %s is for %s stress, the limit reads as steady; a steady stress takes the steady '
                     'rule (…-S)' % (rule['id'], rule['condition']))
    if rule.get('subtype') and not _named_technologies(identity_of((limit.get('refs') or [])) if identity_of else ''):
        hints.append('derating rule %s is for %s parts and the part\'s identity does not say which technology it is; '
                     'check the datasheet' % (rule['id'], rule['type']))
    return hints


DIMENSION_WORDS = {'current': ('电流',), 'voltage': ('电压',), 'power': ('功率', '功耗')}
# rules of one kind told apart by the part's identity; the "其他…" rule takes a part none of them names
TYPE_WORDS = {'USB 母座': re.compile(r'USB', re.I),
              '器具耦合器': re.compile(r'耦合器|IEC ?60320|appliance coupler|\bC(?:5|6|7|8|13|14|15|16)\b', re.I)}


def implied_ratio(margin, conditions, level, kinds_of, dimension, identity_of=None):
    """(rule, stress, derated) for a margin on a guaranteed rating that names no rule, when exactly one steady or
    worst-case ratio rule fits the limit's part kinds and the margin's dimension and the stress is over the derated
    value; else None. R8 (2026-10-28): VBUS 5 A against the connector's 5 A rating passed with zero margin and no
    stress risk, CONN-I allowing 85 % at level III. `dimension` is the margin unit's (units.parse, current/voltage/…)."""
    basis = margin.get('basis') if isinstance(margin.get('basis'), dict) else {}
    if level not in LEVELS or basis.get('derating_rule') or basis.get('method') != 'G1':
        return None
    limit = conditions.get(basis.get('limit')) or {}
    bound = limit.get('limit') or {}
    rating, unit = bound.get('max'), str(margin.get('unit') or '').strip()
    if not (isinstance(rating, (int, float)) and rating > 0 and isinstance(margin.get('value'), (int, float))
            and margin['value'] >= 0 and dimension and str(bound.get('unit') or '').strip() == unit):
        return None
    kinds = set(kinds_of(limit.get('refs') or []))
    words = DIMENSION_WORDS.get(dimension, ())
    fits = [r for r in rules().values() if r['measure'] == 'ratio' and r['condition'] in ('worst', 'steady')
            and kinds & set(r['kinds']) and any(w in r['parameter'] for w in words)]
    if len(fits) > 1:
        identity = identity_of(limit.get('refs') or []) if identity_of else ''
        named = [r for r in fits if TYPE_WORDS.get(r['type']) and TYPE_WORDS[r['type']].search(identity)]
        fits = named or [r for r in fits if r['type'].startswith('其他') and not any(
            TYPE_WORDS.get(o['type']) and TYPE_WORDS[o['type']].search(identity) for o in fits)]
    if len(fits) != 1:
        return None
    stress, derated = rating - margin['value'], rating * fits[0]['values'][level]
    return (fits[0], stress, derated) if stress > derated else None


def rule_hint(margin, conditions, kinds_of):
    """A part-stress margin on a guaranteed rating of a kind the spec has rules for, naming none: the kinds, else None."""
    basis = margin.get('basis') if isinstance(margin.get('basis'), dict) else {}
    if basis.get('derating_rule') or margin.get('aspect') not in STRESS_ASPECTS \
            or basis.get('method') != 'G1':
        return None
    kinds = set(kinds_of((conditions.get(basis.get('limit')) or {}).get('refs') or [])) & kinds_with_rules()
    return sorted(kinds) or None
