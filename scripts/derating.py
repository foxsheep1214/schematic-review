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


def rules():
    """{rule id: rule} of the shared spec."""
    global _RULES
    if _RULES is None:
        _RULES = {r['id']: r for r in json.loads(RULES_PATH.read_text(encoding='utf-8'))['rules']}
    return _RULES


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


def margin_errors(label, margin, conditions, level, kinds_of):
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


def rule_hint(margin, conditions, kinds_of):
    """A part-stress margin on a guaranteed rating of a kind the spec has rules for, naming none: the kinds, else None."""
    basis = margin.get('basis') if isinstance(margin.get('basis'), dict) else {}
    if basis.get('derating_rule') or margin.get('aspect') not in STRESS_ASPECTS \
            or basis.get('derivation') != 'GUARANTEED_LIMIT':
        return None
    kinds = set(kinds_of((conditions.get(basis.get('limit')) or {}).get('refs') or [])) & kinds_with_rules()
    return sorted(kinds) or None
