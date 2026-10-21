#!/usr/bin/env python3
"""Prototype: the machine checks over conclusions (docs/2026-10-20-question-conclusion-design.md §4).

    python3 conclusions_check.py questions.json clauses.json conclusions.json --db db.json [--evidence-root DIR] [-o out.json]

COVERAGE     every question (every state of it) has exactly one conclusion — conclusions may split a question
             by state when their outcomes differ; every tool observation is answered once per question.
CONSISTENCY  a numeric outcome is the one its input ranges give (worst corner passes → PASS, most favourable
             corner fails → FAIL, otherwise UNDECIDED); an undecided conclusion names one missing thing, from
             whom and how it closes; a fail carries its fix; graded conclusions name a consequence class.
TRACE        clauses resolve to evidence files and say what kind of source they are; facts hold on the
             netlist; inputs taken from the schematic equal the netlist; every result is recomputed in SI at the
             corners of its inputs and returned in the criterion's unit; the expression's dimension is the
             criterion's; interior points are sampled and a result leaving the corner range is refused.
STRICTNESS   no fail the favourable corner would pass, none against a limit the reviewer assumed or on an
             assumed point value; one change is one defect; severity no higher than its consequence class;
             a requirement nobody has set is neither graded nor blocking.

What no check here proves: that a clause says what the conclusion claims, that the model fits, that an
expression is monotone between the sampled points, or that the reasoning in `means` is right — those go to
sampling review (design §5). calc.py functions are recomputed in SI but not dimension-checked. Exit 0 valid, 1 errors, 2 malformed input. This never touches the main review path.
"""
import argparse
import ast
import itertools
import json
import math
import operator
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
import calc
import checkers  # noqa: F401  (imported before decoupling, which it imports back)
from decoupling import parse_capacitance
from solve_dividers import parse_resistor
from review_summary import IMPACT_CLASSES
from validate_remediation import READINESS

OUTCOMES = ('PASS', 'FAIL', 'UNDECIDED', 'NA')
FROM = ('DESIGN', 'VENDOR', 'REQUIREMENT', 'OTHER_STAGE', 'USER')
LEVELS = ('P0', 'P1', 'P2', 'P3')
DIRECTIONS = ('value_above_limit', 'value_below_limit')
CLAUSE_KINDS = ('DATASHEET', 'STANDARD', 'REQUIREMENT', 'PRACTICE', 'ASSUMPTION')
REL_TOL = 0.01
PREFIX = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'μ': 1e-6, 'm': 1e-3, '': 1.0, 'k': 1e3, 'K': 1e3,
          'M': 1e6, 'G': 1e9}
# Dimension of each base unit as powers of (V, A, s).
BASE_DIMS = {'ohm': (1, -1, 0), 'Ω': (1, -1, 0), 'R': (1, -1, 0), 'F': (-1, 1, 1), 'V': (1, 0, 0), 'A': (0, 1, 0),
             'W': (1, 1, 0), 'Hz': (0, 0, -1), 's': (0, 0, 1), 'J': (1, 1, 1), '': (0, 0, 0)}
BASE_UNITS = tuple(u for u in BASE_DIMS if u)
SAMPLES = (0.25, 0.5, 0.75)   # interior fractions of a range sampled for monotonicity
FUNCTIONS = {'min': min, 'max': max, 'abs': abs, 'sqrt': math.sqrt}
OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
             ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}


def evaluate(expr, names):
    """A restricted arithmetic expression: numbers, input names, + - * / **, min/max/abs/sqrt. Anything else raises."""
    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in names:
                raise ValueError('unknown name ' + node.id)
            return names[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](walk(node.operand))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS
                and not node.keywords):
            return FUNCTIONS[node.func.id](*[walk(a) for a in node.args])
        raise ValueError('not allowed in a conclusion expression: ' + type(node).__name__)
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as error:
        raise ValueError('syntax: %s' % error)
    return walk(tree)


def dims(base):
    return BASE_DIMS[base]


def parse_unit(unit):
    """(factor to SI, dimension) of `unit` (kΩ → 1e3, Ω); None when the unit is not known."""
    unit = (unit or '').strip()
    if unit == '':
        return 1.0, BASE_DIMS['']
    for base in sorted(BASE_UNITS, key=len, reverse=True):
        if unit.endswith(base) and unit[:-len(base)] in PREFIX:
            return PREFIX[unit[:-len(base)]], BASE_DIMS[base]
    return None


def unit_scale(unit):
    parsed = parse_unit(unit)
    return parsed[0] if parsed else None


def dimension(expr, names):
    """Dimension of a restricted expression whose names carry dimensions; ValueError when terms do not agree.
    Numbers are dimensionless, except a literal 0, which takes the dimension of what it meets (max(0, v))."""
    def same(a, b, what):
        if a is None or b is None:
            return b if a is None else a
        if a != b:
            raise ValueError('%s mixes %s and %s' % (what, _dim_text(a), _dim_text(b)))
        return a

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            return None if node.value == 0 else BASE_DIMS['']
        if isinstance(node, ast.Name):
            return names[node.id]
        if isinstance(node, ast.UnaryOp):
            return walk(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                return same(left, right, 'a sum')
            if left is None or right is None:
                return None
            if isinstance(node.op, ast.Mult):
                return tuple(a + b for a, b in zip(left, right))
            if isinstance(node.op, ast.Div):
                return tuple(a - b for a, b in zip(left, right))
            if not (isinstance(node.right, ast.Constant) and right == BASE_DIMS['']):
                raise ValueError('a power takes a number as exponent')
            if left != BASE_DIMS[''] and float(node.right.value) != int(node.right.value):
                raise ValueError('a fractional power of %s' % _dim_text(left))
            return tuple(int(a * node.right.value) for a in left)
        if isinstance(node, ast.Call):
            args = [walk(a) for a in node.args]
            if node.func.id == 'sqrt':
                if args[0] is not None and any(a % 2 for a in args[0]):
                    raise ValueError('the square root of %s' % _dim_text(args[0]))
                return None if args[0] is None else tuple(a // 2 for a in args[0])
            out = None
            for a in args:
                out = same(out, a, node.func.id + '()')
            return out
        raise ValueError('not allowed: ' + type(node).__name__)
    evaluate(expr, {n: 1.0 for n in names})   # same whitelist as the evaluator
    return walk(ast.parse(expr, mode='eval'))


def _dim_text(d):
    text = '·'.join('%s%s' % (u, '' if n == 1 else '^%d' % n) for u, n in zip(('V', 'A', 's'), d) if n)
    return text or 'a number'


def db_value(part_value, parse):
    """SI value of a netlist part field; None when it cannot be read without guessing."""
    text = str(part_value or '').strip()
    if parse == 'resistance':
        parsed = parse_resistor(text.split('/')[0].strip())
        return parsed['kohm'] * 1e3 if parsed else None
    if parse == 'capacitance':
        return parse_capacitance(text)
    if parse == 'number':
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _close(a, b, scale):
    return abs(a - b) <= REL_TOL * max(abs(scale), 1e-12)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


class Checker:
    def __init__(self, questions, clauses, conclusions, db, evidence_root):
        self.questions = {q['id']: q for q in questions if isinstance(q, dict) and q.get('id')}
        self.clauses = {k['id']: k for k in clauses if isinstance(k, dict) and k.get('id')}
        self.conclusions = [c for c in conclusions if isinstance(c, dict)]
        self.db = db or {}
        self.root = Path(evidence_root)
        self.errors = []
        self.recomputed = 0
        self.facts_checked = 0
        self.derived = {}   # id(conclusion) -> what its input ranges give

    def error(self, check, code, question, message):
        self.errors.append({'check': check, 'code': code, 'question': question, 'message': message})

    # COVERAGE ---------------------------------------------------------------------------------------
    def coverage(self):
        by_question = {}
        for conclusion in self.conclusions:
            qid = conclusion.get('question')
            if qid not in self.questions:
                self.error('COVERAGE', 'UNKNOWN_QUESTION', qid, 'the conclusion answers no question of the plan')
                continue
            by_question.setdefault(qid, []).append(conclusion)
        for qid, question in self.questions.items():
            conclusions = by_question.get(qid, [])
            if not conclusions:
                self.error('COVERAGE', 'UNANSWERED', qid, 'no conclusion answers this question')
                continue
            self._states(qid, question, conclusions)
            self._observations(qid, question, conclusions)

    def _states(self, qid, question, conclusions):
        """One conclusion answers every state; conclusions split by state when their conclusions differ, each state once."""
        states = list((question.get('conditions') or {}).get('states') or [])
        taken = Counter()
        for conclusion in conclusions:
            own = conclusion.get('states')
            if own is None:
                taken.update(states or [None])
                continue
            unknown = [s for s in own or [None] if s not in states]
            if unknown:
                self.error('COVERAGE', 'UNKNOWN_STATE', qid,
                           'states %s are not states of this question (%s)' % (unknown, states or 'none'))
            taken.update(s for s in own if s in states)
        twice = sorted(str(s) for s, n in taken.items() if n > 1)
        if twice:
            self.error('COVERAGE', 'DUPLICATE_CONCLUSION', qid, '%d conclusions answer %s' % (len(conclusions), '/'.join(twice)))
        left = [s for s in states if not taken[s]]
        if left:
            self.error('COVERAGE', 'UNANSWERED', qid, 'no conclusion answers state(s) ' + '/'.join(left))

    def _observations(self, qid, question, conclusions):
        observations = {o['id']: o for o in question.get('observations') or []}
        answered = set()
        for conclusion in conclusions:
            for d in conclusion.get('disagrees') or []:
                if not (isinstance(d, dict) and d.get('observation') in observations and str(d.get('why') or '').strip()):
                    self.error('COVERAGE', 'UNKNOWN_OBSERVATION', qid,
                               'disagrees names an observation of this question and why')
                    continue
                answered.add(d['observation'])
        fails = any(c.get('outcome') == 'FAIL' for c in conclusions)
        for oid, obs in observations.items():
            if oid in answered:
                continue
            if obs.get('kind') == 'SUSPECT' and not fails:
                self.error('COVERAGE', 'SUSPECT_UNANSWERED', qid,
                           '%s (%s): fail the question or say in disagrees why the tool is wrong' % (oid, obs.get('says')))
            if obs.get('kind') == 'MISSING_INPUT' and any(c.get('outcome') in ('PASS', 'NA') for c in conclusions):
                self.error('COVERAGE', 'MISSING_INPUT_UNDER_PASS', qid,
                           '%s (%s): the tool lacked an input; a pass says in disagrees why it does not matter'
                           % (oid, obs.get('says')))

    # CONSISTENCY ------------------------------------------------------------------------------------
    def consistency(self, conclusion):
        qid, outcome = conclusion.get('question'), conclusion.get('outcome')
        question = self.questions.get(qid) or {}
        basis = conclusion.get('basis') if isinstance(conclusion.get('basis'), dict) else {}
        derived = (self.derived.get(id(conclusion)) or {}).get('outcome')
        if outcome not in OUTCOMES:
            self.error('CONSISTENCY', 'BAD_OUTCOME', qid, 'outcome is PASS, FAIL or UNDECIDED')
            return
        if basis.get('kind') == 'UNSPECIFIED' and outcome != 'FAIL':
            self.error('CONSISTENCY', 'UNSPECIFIED_NOT_FAIL', qid,
                       'the datasheet does not specify the part where the design runs it: that is a fail with a fix')
        if outcome == 'NA':
            if not question.get('undetermined'):
                self.error('CONSISTENCY', 'NA_NOT_OPEN', qid, 'NA only where the plan left applicability open')
            if basis.get('kind') != 'FACT':
                self.error('CONSISTENCY', 'NA_WITHOUT_FACT', qid, 'NA shows the netlist fact that makes it so')
        if outcome == 'PASS':
            if basis.get('kind') == 'NUMERIC':
                if derived and derived != 'PASS':
                    self.error('CONSISTENCY', 'PASS_NOT_PROVEN', qid,
                               'the worst corner of the inputs does not pass (%s): the inputs give %s'
                               % (self._margins(conclusion), derived))
            elif basis.get('kind') != 'FACT':
                self.error('CONSISTENCY', 'PASS_WITHOUT_BASIS', qid, 'a pass rests on a NUMERIC or FACT basis')
        if outcome == 'FAIL':
            fix = conclusion.get('fix')
            if not (isinstance(fix, dict) and (fix.get('same_as') or (
                    str(fix.get('change') or '').strip() and fix.get('readiness') in READINESS))):
                self.error('CONSISTENCY', 'FAIL_WITHOUT_FIX', qid,
                           'a fail carries fix {change, readiness %s} or {same_as: the question whose fix clears it}'
                           % '/'.join(READINESS))
            if basis.get('kind') not in ('NUMERIC', 'FACT', 'UNSPECIFIED'):
                self.error('CONSISTENCY', 'FAIL_WITHOUT_BASIS', qid, 'a fail rests on a NUMERIC, FACT or UNSPECIFIED basis')
        if outcome == 'UNDECIDED':
            self._undecided(conclusion, qid, basis, derived)
        if outcome in ('FAIL', 'UNDECIDED') and not self._requirement_open(conclusion):
            severity = conclusion.get('severity')
            if not (isinstance(severity, dict) and severity.get('level') in LEVELS
                    and severity.get('class') in IMPACT_CLASSES and str(severity.get('consequence') or '').strip()):
                self.error('CONSISTENCY', 'SEVERITY_MISSING', qid,
                           'severity {level P0–P3, class %s, consequence}' % '/'.join(IMPACT_CLASSES))

    def _requirement_open(self, conclusion):
        return conclusion.get('outcome') == 'UNDECIDED' and (conclusion.get('missing') or {}).get('from') == 'REQUIREMENT'

    def _undecided(self, conclusion, qid, basis, derived):
        missing = conclusion.get('missing')
        if not (isinstance(missing, dict) and all(str(missing.get(f) or '').strip() for f in ('what', 'closes_when'))
                and missing.get('from') in FROM):
            self.error('CONSISTENCY', 'MISSING_INCOMPLETE', qid,
                       'missing {what, from %s, closes_when}' % '/'.join(FROM))
            missing = missing if isinstance(missing, dict) else {}
        if missing.get('from') == 'USER' and not conclusion.get('instruction'):
            self.error('CONSISTENCY', 'USER_WITHOUT_INSTRUCTION', qid, 'a deferral cites the user instruction')
        if not basis:
            if missing.get('from') == 'VENDOR' and not _locators(conclusion.get('searched')):
                self.error('CONSISTENCY', 'NO_BOUND_NOT_SEARCHED', qid,
                           'no public bound: searched lists the curves, tables and notes looked at (source, locator)')
            return
        if basis.get('kind') != 'NUMERIC':
            self.error('CONSISTENCY', 'BOUND_NOT_NUMERIC', qid, 'an undecided conclusion\'s basis is the NUMERIC public bound, or none')
            return
        if derived in ('PASS', 'FAIL'):
            self.error('CONSISTENCY', 'ALREADY_DECIDED', qid,
                       'the public bounds already give %s (%s); split by state if they cover only part'
                       % (derived, self._margins(conclusion)))
        loose = (basis.get('inputs') or {}).get(conclusion.get('loose_input'))
        if not (isinstance(loose, dict) and _range(loose) and _range(loose)[0] < _range(loose)[1]):
            self.error('CONSISTENCY', 'LOOSE_INPUT_UNKNOWN', qid,
                       'loose_input names the ranged input whose width keeps the outcome open')

    def _margins(self, conclusion):
        d = self.derived.get(id(conclusion)) or {}
        return 'worst-corner margin %.4g, favourable-corner margin %.4g' % (d.get('worst_margin'), d.get('best_margin'))

    # STRICTNESS -------------------------------------------------------------------------------------
    def strictness(self, conclusion):
        qid, outcome = conclusion.get('question'), conclusion.get('outcome')
        basis = conclusion.get('basis') if isinstance(conclusion.get('basis'), dict) else {}
        derived = (self.derived.get(id(conclusion)) or {}).get('outcome')
        if outcome == 'FAIL':
            if basis.get('kind') == 'NUMERIC':
                if derived and derived != 'FAIL':
                    self.error('STRICTNESS', 'FAIL_NOT_PROVEN', qid,
                               'the most favourable corner of the inputs still passes (%s): this is %s, not a fail'
                               % (self._margins(conclusion), derived))
                if self._clause_kind((basis.get('criterion') or {}).get('clause')) == 'ASSUMPTION':
                    self.error('STRICTNESS', 'FAIL_ON_ASSUMED_LIMIT', qid,
                               'the limit comes from a reviewer assumption; a fail needs a datasheet, standard, '
                               'requirement or practice limit')
                for name, item in (basis.get('inputs') or {}).items():
                    source = (item.get('from') or {}) if isinstance(item, dict) else {}
                    rng = _range(item)
                    if self._clause_kind(source.get('clause')) == 'ASSUMPTION' and rng and rng[0] == rng[1]:
                        self.error('STRICTNESS', 'FAIL_ON_ASSUMED_POINT', qid,
                                   'input %s is an assumed point value; give the range the assumption allows' % name)
            elif basis.get('kind') == 'FACT':
                kinds = [self._clause_kind(c) for c in basis.get('clauses') or []]
                if not [k for k in kinds if k and k != 'ASSUMPTION']:
                    self.error('STRICTNESS', 'FAIL_ON_ASSUMED_LIMIT', qid,
                               'the fact breaks no datasheet, standard, requirement or practice clause')
            elif basis.get('kind') == 'UNSPECIFIED' and self._clause_kind(basis.get('clause')) != 'DATASHEET':
                self.error('STRICTNESS', 'FAIL_ON_ASSUMED_LIMIT', qid, 'an unspecified operating point cites the datasheet')
        severity = conclusion.get('severity') if isinstance(conclusion.get('severity'), dict) else {}
        if self._requirement_open(conclusion) and severity:
            self.error('STRICTNESS', 'REQUIREMENT_GRADED', qid,
                       'nobody has set this requirement yet; it is not graded and does not block')
        cap = IMPACT_CLASSES.get(severity.get('class'))
        if cap and severity.get('level') in LEVELS and LEVELS.index(severity['level']) < LEVELS.index(cap):
            self.error('STRICTNESS', 'SEVERITY_ABOVE_CLASS', qid, '%s is above %s for %s'
                       % (severity['level'], cap, severity['class']))

    def defects(self):
        """One change is one defect: a second fail cleared by the same change says fix.same_as."""
        fails = [c for c in self.conclusions if c.get('outcome') == 'FAIL' and isinstance(c.get('fix'), dict)]
        owners = {}
        for c in fails:
            change = ' '.join(str(c['fix'].get('change') or '').split())
            if not change or c['fix'].get('same_as'):
                continue
            if change in owners:
                self.error('STRICTNESS', 'DUPLICATE_DEFECT', c.get('question'),
                           'the same change already clears %s: write fix {same_as: "%s"} so it counts once'
                           % (owners[change], owners[change]))
            else:
                owners[change] = c.get('question')
        standalone = set(owners.values())
        for c in fails:
            target = c['fix'].get('same_as')
            if target and target not in standalone:
                self.error('CONSISTENCY', 'FIX_SAME_AS_UNKNOWN', c.get('question'),
                           'same_as names a question whose fail carries its own fix')
        return len(owners)

    # TRACE ------------------------------------------------------------------------------------------
    def clause_ok(self, qid, clause_id):
        clause = self.clauses.get(clause_id)
        if clause is None:
            self.error('TRACE', 'UNKNOWN_CLAUSE', qid, 'clause %s is not in clauses.json' % clause_id)
            return False
        return True

    def trace_clauses(self):
        for cid, clause in self.clauses.items():
            if not (all(str(clause.get(f) or '').strip() for f in ('source', 'locator', 'says'))
                    and clause.get('kind') in CLAUSE_KINDS):
                self.error('TRACE', 'CLAUSE_INCOMPLETE', None, '%s needs source, locator, says and kind %s'
                           % (cid, '/'.join(CLAUSE_KINDS)))
            elif not (self.root / clause['source']).is_file():
                self.error('TRACE', 'CLAUSE_SOURCE_MISSING', None, '%s: %s not found under the evidence root'
                           % (cid, clause['source']))

    def _clause_kind(self, clause_id):
        return (self.clauses.get(clause_id) or {}).get('kind')

    def trace_numeric(self, qid, basis, conclusion):
        criterion = basis.get('criterion') if isinstance(basis.get('criterion'), dict) else {}
        limits = _range({'value': criterion['limit']} if _number(criterion.get('limit')) else criterion.get('limit'))
        if not (limits and criterion.get('direction') in DIRECTIONS):
            self.error('TRACE', 'CRITERION_INCOMPLETE', qid, 'criterion {limit: number or {min, max}, unit, direction, clause}')
            return
        self.clause_ok(qid, criterion.get('clause'))
        target = parse_unit(criterion.get('unit'))
        if target is None:
            self.error('TRACE', 'UNIT_UNKNOWN', qid, 'criterion unit %r is not known' % criterion.get('unit'))
        inputs = basis.get('inputs') if isinstance(basis.get('inputs'), dict) else {}
        ranges, units = {}, {}
        for name, item in inputs.items():
            rng = _range(item)
            if rng is None:
                self.error('TRACE', 'INPUT_INCOMPLETE', qid, 'input %s needs a numeric value or min ≤ max' % name)
                continue
            unit = parse_unit(item.get('unit'))
            if unit is None:
                self.error('TRACE', 'UNIT_UNKNOWN', qid, 'input %s: unit %r is not known' % (name, item.get('unit')))
                continue
            ranges[name], units[name] = (rng[0] * unit[0], rng[1] * unit[0]), unit[1]
            source = item.get('from') if isinstance(item.get('from'), dict) else {}
            if 'clause' in source:
                self.clause_ok(qid, source['clause'])
            elif isinstance(source.get('db'), dict):
                self._db_input(qid, name, rng, item.get('unit'), source['db'])
            else:
                self.error('TRACE', 'INPUT_UNSOURCED', qid, 'input %s comes from a clause or the netlist' % name)
        stated = _range(basis.get('result'))
        if stated is None:
            self.error('TRACE', 'RESULT_INCOMPLETE', qid, 'result {min, max} in the criterion\'s unit')
        if len(ranges) != len(inputs) or stated is None or target is None:
            return
        if (basis.get('calc') or '') not in calc.FUNCTIONS:   # calc.py functions take SI inputs by name
            try:
                got = dimension(basis.get('calc') or '', units)
                if got is not None and got != target[1]:
                    raise ValueError('the expression gives %s, the criterion is in %s (%s)'
                                     % (_dim_text(got), _dim_text(target[1]), criterion.get('unit')))
            except ValueError as error:
                self.error('TRACE', 'DIMENSION_MISMATCH', qid, str(error))
                return
        try:
            values = [self._compute(basis, dict(zip(ranges, corner))) / target[0]
                      for corner in itertools.product(*[sorted(set(r)) for r in ranges.values()])]
            lo, hi = min(values), max(values)
            turned = self._turning_point(basis, ranges, lo, hi, target[0], inputs)
        except (ValueError, TypeError, ZeroDivisionError, OverflowError) as error:
            self.error('TRACE', 'RECOMPUTE_FAILED', qid, 'calc: %s' % error)
            return
        self.recomputed += 1
        if turned:
            self.error('TRACE', 'NON_MONOTONIC', qid,
                       'at %s the result is %.6g, outside the corner range %.6g…%.6g: the expression turns inside '
                       'the ranges; split the range at the turning point' % (turned[0], turned[1], lo, hi))
            return
        if not (_close(lo, stated[0], max(abs(lo), abs(hi))) and _close(hi, stated[1], max(abs(lo), abs(hi)))):
            self.error('TRACE', 'RECOMPUTE_MISMATCH', qid,
                       'the inputs give %.6g…%.6g, the conclusion says %.6g…%.6g' % (lo, hi, stated[0], stated[1]))
            return
        if criterion['direction'] == 'value_below_limit':
            worst, best = limits[0] - hi, limits[1] - lo
        else:
            worst, best = lo - limits[1], hi - limits[0]
        self.derived[id(conclusion)] = {
            'question': qid, 'states': conclusion.get('states'), 'stated': conclusion.get('outcome'),
            'outcome': 'PASS' if worst > 0 else 'FAIL' if best <= 0 else 'UNDECIDED',
            'min': lo, 'max': hi, 'worst_margin': worst, 'best_margin': best, 'unit': criterion.get('unit')}

    def _turning_point(self, basis, ranges, lo, hi, scale, inputs):
        """Vary one ranged input through interior points with the others at each corner; return the first point
        whose result leaves [lo, hi] (the corners then do not bound the result)."""
        spread = max(abs(lo), abs(hi), 1e-12) * REL_TOL
        names = list(ranges)
        for name in names:
            low, high = ranges[name]
            if low == high:
                continue
            others = [n for n in names if n != name]
            for corner in itertools.product(*[sorted(set(ranges[n])) for n in others]):
                point = dict(zip(others, corner))
                for f in SAMPLES:
                    point[name] = low + f * (high - low)
                    value = self._compute(basis, point) / scale
                    if value < lo - spread or value > hi + spread:
                        return ', '.join('%s=%.4g %s' % (n, v / unit_scale(inputs[n].get('unit')), inputs[n].get('unit') or '')
                                         for n, v in sorted(point.items())), value
        return None

    def _compute(self, basis, values):
        name = basis.get('calc') or ''
        if name in calc.FUNCTIONS:
            result = calc.FUNCTIONS[name](**values)
            value = result.get(basis.get('output')) if isinstance(result, dict) else None
            if not _number(value):
                raise ValueError('output %r is not a number of %s' % (basis.get('output'), name))
            return value
        return evaluate(name, values)

    def _db_input(self, qid, name, rng, unit, ref):
        part = (self.db.get('parts') or {}).get(ref.get('ref'))
        if part is None:
            self.error('TRACE', 'UNKNOWN_REF', qid, 'input %s: %s is not in the netlist' % (name, ref.get('ref')))
            return
        actual = db_value(part.get(ref.get('field') or 'value'), ref.get('parse'))
        scale = unit_scale(unit)
        if actual is None or scale is None:
            self.error('TRACE', 'DB_VALUE_UNREADABLE', qid,
                       'input %s: netlist value %r or unit %r cannot be read; cite a clause instead'
                       % (name, part.get('value'), unit))
            return
        if not (rng[0] * scale <= actual * (1 + REL_TOL) and actual * (1 - REL_TOL) <= rng[1] * scale):
            self.error('TRACE', 'DB_VALUE_MISMATCH', qid, 'input %s = %s %s but the netlist has %s %r'
                       % (name, rng[0] if rng[0] == rng[1] else '%s…%s' % rng, unit, ref.get('ref'), part.get('value')))

    def trace_facts(self, qid, basis):
        for c in basis.get('clauses') or []:
            self.clause_ok(qid, c)
        facts = basis.get('facts')
        if not (isinstance(facts, list) and facts):
            self.error('TRACE', 'FACTS_MISSING', qid, 'a FACT basis lists netlist facts')
            return
        pin2net = self.db.get('pin2net') or {}
        parts = self.db.get('parts') or {}
        for fact in facts:
            node = fact.get('node') if isinstance(fact, dict) else None
            ref = fact.get('ref') if isinstance(fact, dict) else None
            if node is not None and node not in pin2net and node not in (self.db.get('no_connect_nodes') or []):
                self.error('TRACE', 'UNKNOWN_NODE', qid, '%s is not a pin of the netlist' % node)
                continue
            if ref is not None and ref not in parts:
                self.error('TRACE', 'UNKNOWN_REF', qid, '%s is not in the netlist' % ref)
                continue
            held = self._holds(fact, pin2net, parts)
            if held is None:
                self.error('TRACE', 'BAD_FACT', qid, 'a fact uses one netlist predicate: ' + ', '.join(PREDICATES))
                continue
            self.facts_checked += 1
            if not held:
                self.error('TRACE', 'FACT_FALSE', qid, 'the netlist contradicts %s' % json.dumps(
                    {k: v for k, v in fact.items() if k != 'means'}, ensure_ascii=False))

    def _holds(self, fact, pin2net, parts):
        node, ref = fact.get('node'), fact.get('ref')
        if 'net_same_as' in fact:
            other = fact['net_same_as']
            return node in pin2net and other in pin2net and pin2net[node] == pin2net[other]
        if 'net_is' in fact:
            return pin2net.get(node) == fact['net_is']
        if 'pin_unconnected' in fact:
            unconnected = (node not in pin2net or pin2net[node] in (self.db.get('pseudo_nets') or [])
                           or node in (self.db.get('no_connect_nodes') or []))
            return unconnected == bool(fact['pin_unconnected'])
        if 'ref_value_is' in fact:
            return (parts.get(ref) or {}).get('value') == fact['ref_value_is']
        if 'ref_part_is' in fact:
            return (parts.get(ref) or {}).get('part') == fact['ref_part_is']
        if 'dnp_is' in fact:
            return bool((parts.get(ref) or {}).get('nc')) == bool(fact['dnp_is'])
        return None

    def trace(self, conclusion):
        qid = conclusion.get('question')
        basis = conclusion.get('basis')
        if isinstance(basis, dict):
            if basis.get('kind') == 'NUMERIC':
                self.trace_numeric(qid, basis, conclusion)
            elif basis.get('kind') == 'FACT':
                self.trace_facts(qid, basis)
            elif basis.get('kind') == 'UNSPECIFIED':
                self.clause_ok(qid, basis.get('clause'))
        if conclusion.get('outcome') in ('PASS', 'FAIL', 'NA') and not isinstance(basis, dict):
            self.error('TRACE', 'BASIS_MISSING', qid, 'the conclusion states its basis')

    def run(self):
        self.coverage()
        self.trace_clauses()
        for conclusion in self.conclusions:
            self.trace(conclusion)
            self.consistency(conclusion)
            self.strictness(conclusion)
        defects = self.defects()
        outcomes = Counter(c.get('outcome') for c in self.conclusions)
        blocked = any((c.get('outcome') == 'FAIL' and (c.get('severity') or {}).get('level') in ('P0', 'P1'))
                      or (c.get('outcome') == 'UNDECIDED' and (c.get('severity') or {}).get('level') == 'P0')
                      for c in self.conclusions)
        return {'valid': not self.errors, 'errors': self.errors,
                'derived': [self.derived[id(c)] for c in self.conclusions if id(c) in self.derived],
                'summary': {'questions': len(self.questions), 'conclusions': len(self.conclusions),
                            'outcomes': {k: outcomes[k] for k in OUTCOMES if outcomes[k]}, 'defects': defects,
                            'recomputed': self.recomputed, 'facts_checked': self.facts_checked,
                            'release': 'CANNOT_FREEZE' if blocked else 'CAN_FREEZE',
                            'errors_by_check': dict(Counter(e['check'] for e in self.errors))}}


PREDICATES = ('net_same_as', 'net_is', 'pin_unconnected', 'ref_value_is', 'ref_part_is', 'dnp_is')


def _range(item):
    """(min, max) of {value} or {min, max}; None when neither is given as numbers with min ≤ max."""
    if not isinstance(item, dict):
        return None
    if _number(item.get('value')) and 'min' not in item and 'max' not in item:
        return (item['value'], item['value'])
    if _number(item.get('min')) and _number(item.get('max')) and item['min'] <= item['max'] and 'value' not in item:
        return (item['min'], item['max'])
    return None


def _locators(value):
    return isinstance(value, list) and bool(value) and all(
        isinstance(x, dict) and str(x.get('source') or '').strip() and str(x.get('locator') or '').strip() for x in value)


def check(questions, clauses, conclusions, db, evidence_root):
    qs = questions.get('questions') if isinstance(questions, dict) else questions
    return Checker(qs or [], clauses or [], conclusions or [], db, evidence_root).run()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('questions')
    parser.add_argument('clauses')
    parser.add_argument('conclusions')
    parser.add_argument('--db', required=True)
    parser.add_argument('--evidence-root', help='directory clause sources are relative to (default: clauses.json\'s)')
    parser.add_argument('-o', '--out')
    args = parser.parse_args(argv)
    try:
        loaded = [json.loads(Path(p).read_text(encoding='utf-8'))
                  for p in (args.questions, args.clauses, args.conclusions, args.db)]
    except (OSError, ValueError) as error:
        print('malformed input: %s' % error, file=sys.stderr)
        return 2
    root = args.evidence_root or str(Path(args.clauses).resolve().parent)
    out = check(*loaded, root)
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if args.out:
        Path(args.out).write_text(text + '\n', encoding='utf-8')
    print(json.dumps(out['summary'], ensure_ascii=False))
    return 0 if out['valid'] else 1


if __name__ == '__main__':
    sys.exit(main())
