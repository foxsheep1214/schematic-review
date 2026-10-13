"""Source-bound execution consistency, v1; never electrical signoff.

The controlled execution basis belongs in plan.execution_inputs,
outside the contract. Bindings are JSON pointers into that input or the native
DB, not prose assertions. Expert review must establish the basis' completeness
and physical model applicability. This gate catches contradictions, omitted
declared cases and unsupported transfers; it cannot prove the controlled basis.
"""
import hashlib
import json
import math
from design_preflight import validate_calculations, evidence

VERSION = 1
SECTIONS = ('networks', 'power', 'aggregates', 'repairs', 'gaps', 'handoffs')
RESULTS = {'PASS', 'FAIL', 'INSUFFICIENT', 'NA'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode('utf-8')).hexdigest()


def text(value):
    return isinstance(value, str) and bool(value.strip())


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def pointer(root, path):
    if not text(path) or not path.startswith('/'):
        raise ValueError('absolute JSON pointer required')
    for token in path[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(root, list):
            if not token.isdecimal():
                raise ValueError('array pointer needs index')
            root = root[int(token)]
        elif isinstance(root, dict):
            root = root[token]
        else:
            raise ValueError('pointer traverses scalar')
    return root


def validate_execution_audit(plan, report, db=None, audit=None, required=False):
    try:
        return _validate_execution_audit(plan, report, db, audit, required)
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return {'enforced': True, 'scope': 'SOURCE_BOUND_EXECUTION_CONSISTENCY_ONLY',
            'electrical_approval': False, 'errors': ['MALFORMED_EXECUTION_AUDIT: ' + str(exc)],
            'checked': {s: 0 for s in SECTIONS}}


def _validate_execution_audit(plan, report, db=None, audit=None, required=False):
    errors = []
    output = {'enforced': bool(required or audit is not None or 'execution_contract' in plan),
        'scope': 'SOURCE_BOUND_EXECUTION_CONSISTENCY_ONLY', 'electrical_approval': False,
        'errors': errors, 'checked': {s: 0 for s in SECTIONS}}
    if not output['enforced']:
        return output

    def need(ok, code, label):
        if not ok:
            errors.append(code + ': ' + label)
        return ok

    def binding(value, label):
        if not isinstance(value, dict) or set(value) != {'root', 'pointer'}:
            need(False, 'SOURCE_BINDING', label + ' needs root/pointer'); return None
        root, path = value['root'], value['pointer']
        if not ((root == 'plan' and isinstance(path, str) and path.startswith('/execution_inputs/'))
                or (root == 'db' and isinstance(path, str) and path.startswith('/'))):
            need(False, 'SOURCE_BINDING', label + ' must bind controlled execution_inputs or native DB'); return None
        try:
            return pointer(plan if root == 'plan' else db, path)
        except (ValueError, KeyError, IndexError, TypeError):
            need(False, 'SOURCE_BINDING', label + ' source pointer absent'); return None

    def index(rows, label):
        out = {}
        if not need(isinstance(rows, list), 'SCHEMA', label + ' must be array'):
            return out
        for row in rows:
            if not need(isinstance(row, dict) and text(row.get('id')), 'SCHEMA', label + ' needs id'):
                continue
            need(row['id'] not in out, 'DUPLICATE', label + '/' + row['id'])
            out[row['id']] = row
        return out

    limited_inputs = []
    current_missing = set()
    current_allows_missing = False
    def interval(value, unit, label, positive=False):
        if value is None and current_allows_missing:
            # A real, source-bound missing input can leave a numeric parameter
            # unavailable. Do not force an estimate to make an honest INS valid.
            limited_inputs.append(label)
            return None
        ok = isinstance(value, dict) and value.get('unit') == unit and all(finite(value.get(k)) for k in ('min', 'max'))
        ok = ok and value['min'] <= value['max'] and (not positive or value['min'] > 0)
        need(ok, 'INTERVAL', label + ' needs finite ordered ' + unit + ' guarantee interval')
        if ok:
            # Reuse the shared condition machinery; neither a source locator nor
            # the word GUARANTEED waives operating-condition applicability.
            scalar = {k: value[k] for k in ('basis', 'evidence', 'conditions', 'operating_conditions',
                      'unconditional_basis', 'derivation') if k in value}
            scalar.update(value=value['min'], unit=unit)
            calculation = {'id':'bound','model':'Controlled interval applicability','output_unit':unit,
                'inputs':{'x':scalar}, 'expression':'x', 'assumptions':[],
                'acceptance':{'operator':'>=', 'value':value['min'], 'unit':unit},
                'claim':'SUPPORTED'}
            ce, cr = validate_calculations([calculation])
            # CONDITIONAL is a legitimate unresolved basis; do not reject it
            # just because the temporary applicability probe requested SUPPORTED.
            ce = [e for e in ce if 'claim disagrees' not in e and 'conditional calculation needs closure' not in e]
            errors.extend('INTERVAL_SOURCE: ' + label + ': ' + e for e in ce)
            if ce or cr.get('bound', {}).get('status') != 'SUPPORTED':
                limited_inputs.append(label)
        return value if ok else None

    contract = plan.get('execution_contract')
    if not need(isinstance(contract, dict) and type(contract.get('version')) is int and contract['version'] == VERSION,
                'CONTRACT_REQUIRED', 'execution_contract.version must be 1'):
        return output
    if not need(isinstance(audit, dict) and type(audit.get('version')) is int and audit['version'] == VERSION,
                'AUDIT_REQUIRED', 'execution-audit.json version 1 required'):
        return output
    need(audit.get('plan_digest') == digest(plan), 'STALE_AUDIT', 'plan_digest differs')
    need(audit.get('results_digest') == digest(report), 'STALE_AUDIT', 'results_digest differs')
    need(audit.get('db_digest') == (digest(db) if db is not None else None), 'STALE_AUDIT', 'db_digest differs')
    checks = index(plan.get('checks'), 'plan.checks')
    actual = index(report.get('checks'), 'results.checks')
    findings = index(report.get('findings'), 'findings')
    work_items = index(report.get('work_items', []), 'work_items')
    sections = {s: index(contract.get(s, [] if s == 'handoffs' else None), 'contract.' + s) for s in SECTIONS}
    records = {s: index(audit.get(s, [] if s == 'handoffs' else None), 'audit.' + s) for s in SECTIONS}
    for section in SECTIONS:
        need(set(sections[section]) == set(records[section]), 'SECTION_COVERAGE', section + ' ids differ')
    # These scopes are discoverable in the saved review, so empty contracts do
    # not silently evade aggregate, remediation or INSUFFICIENT reconciliation.
    need({k for k, x in checks.items() if x.get('rule') == 'REQ-Q07'}.issubset(
         {x.get('check_id') for x in sections['aggregates'].values()}),
         'AGGREGATE_SCOPE', 'all REQ-Q07 checks required')
    repair_targets = {('finding', k) for k, x in findings.items() if 'remediation' in x}
    repair_targets.update(('work_item', k) for k, x in work_items.items()
                          if isinstance(x.get('design_option'), dict) and 'remediation' in x['design_option'])
    need({(x.get('target_kind', 'finding'), x.get('target_id', x.get('finding_id')))
          for x in sections['repairs'].values()} == repair_targets,
          'REPAIR_SCOPE', 'all finding/work-item actionable instructions required')
    need({x.get('check_id') for x in sections['gaps'].values()} ==
         {k for k, x in actual.items() if x.get('review_result') == 'INSUFFICIENT'}, 'GAP_SCOPE', 'all INSUFFICIENT rows required')
    need({x.get('check_id') for x in sections['handoffs'].values()} ==
         {k for k, x in actual.items() if isinstance(x.get('handoff'), dict) and x['handoff'].get('required') is True},
         'HANDOFF_SCOPE', 'all actual required handoffs must bind objects/receivers/quantity')
    # Numeric scope is source-bound, independently of the mutable contract.
    numeric_scope = binding(contract.get('numeric_scope'), 'numeric_scope')
    need(isinstance(numeric_scope, dict) and set(numeric_scope) == {'networks', 'power'} and
         all(isinstance(numeric_scope[s], list) and all(text(k) for k in numeric_scope[s]) and
             len(numeric_scope[s]) == len(set(numeric_scope[s])) and set(numeric_scope[s]) == set(sections[s])
             for s in ('networks', 'power')), 'NUMERIC_SCOPE', 'controlled numerical obligation inventory differs')

    def scoped(entry, label):
        cid = entry.get('check_id')
        return cid if need(cid in checks and cid in actual, 'CHECK_BINDING', label + ' unknown check_id') else None

    for section in ('networks', 'power'):
        for key, entry in sections[section].items():
            label = section + '/' + key
            cid = scoped(entry, label)
            record = records[section].get(key, {})
            basis = binding(entry.get('basis'), label)
            if not isinstance(basis, dict) or cid is None:
                need(False, 'NUMERIC_BASIS', label); continue
            current_missing = set()
            for gap in sections['gaps'].values():
                if gap.get('check_id') != cid:
                    continue
                own = binding(gap.get('basis'), label + '/own_gap')
                if isinstance(own, dict) and all(isinstance(own.get(k), list) and
                        all(text(v) for v in own[k]) for k in ('required_inputs', 'available_inputs')):
                    current_missing.update(set(own['required_inputs']) - set(own['available_inputs']))
            current_allows_missing = bool(current_missing) and actual[cid].get('review_result') == 'INSUFFICIENT'
            cases = index(basis.get('cases'), label + '.cases')
            need(bool(cases), 'EMPTY_CASES', label)
            need(basis.get('criterion_kind') == 'GUARANTEE_REQUIRED', 'NUMERIC_CRITERION', label + ' only explicit guarantee-required criteria supported')
            cells = {}
            for cell in record.get('calculations', []) if isinstance(record.get('calculations'), list) else []:
                if not isinstance(cell, dict):
                    need(False, 'SCHEMA', label + ' calculation object required'); continue
                pair = (cell.get('receiver') if section == 'networks' else None, cell.get('case_id'))
                need(pair not in cells, 'DUPLICATE_CELL', label)
                cells[pair] = cell
            receivers = basis.get('receivers', {}) if section == 'networks' else {None: None}
            if section == 'networks':
                net = basis.get('net')
                obj = checks[cid].get('object', {})
                need(isinstance(obj, dict) and obj.get('net') == net, 'NET_BINDING', label + ' check object/net differs')
                pins = db.get('nets', {}).get(net, []) if isinstance(db, dict) else []
                native = db.get('native_pintype', {}) if isinstance(db, dict) else {}
                raw_types = db.get('pintype', {}) if isinstance(db, dict) else {}
                aliases = {'IN': 'input', 'OUT': 'output', 'BI': 'bidirectional',
                           'BIDI': 'bidirectional', 'BIDIR': 'bidirectional',
                           'POWER': 'power_in', 'GROUND': 'power_in', 'PASSIVE': 'passive'}
                types = {p: aliases.get(raw_types.get(p), raw_types.get(p)) for p in pins}
                types.update({p: native[p] for p in pins if p in native})
                drivers = basis.get('drivers', [])
                need(isinstance(pins, list) and bool(pins) and isinstance(drivers, list)
                     and set(drivers).issubset(pins), 'NET_BINDING', label + ' native endpoints/drivers required')
                need(all(db.get('pin2net', {}).get(p) == net for p in pins), 'NET_BINDING', label + ' nets/pin2net must reciprocate')
                output_roles = {'output', 'tri_state', 'open_collector', 'open_emitter'}
                need(all(types.get(p) in output_roles | {'bidirectional'} for p in drivers) and
                     {p for p in pins if types.get(p) in output_roles}.issubset(drivers),
                     'DRIVER_ROLE', label + ' source driver classification contradicts native roles')
                need(all(types.get(p) in ('output', 'tri_state', 'open_collector', 'open_emitter',
                     'bidirectional', 'power_out') for p in drivers),
                     'DRIVER_ROLE', label + ' an input/passive endpoint cannot hide a native receiver as a driver')
                derived = {p for p in pins if types.get(p) in ('input', 'bidirectional') and p not in drivers}
                ambiguous = {p for p in pins if types.get(p) not in ('input', 'bidirectional', 'output',
                             'tri_state', 'open_collector', 'open_emitter', 'passive', 'power_in', 'power_out')}
                need(not ambiguous, 'UNKNOWN_PIN_ROLE', label + ' native roles unresolved ' + str(sorted(ambiguous)))
                need(isinstance(receivers, dict) and bool(receivers) and set(receivers) == derived,
                     'RECEIVER_COVERAGE', label + ' actual native receiver set differs')
                receivers = receivers if isinstance(receivers, dict) else {}
                model = basis.get('model_support', {})
                model_ok = (isinstance(model, dict) and evidence(model.get('evidence')) and
                    isinstance(model.get('endpoint_roles'), dict) and set(model['endpoint_roles']) == set(pins) and
                    all(model['endpoint_roles'].get(p) == 'DRIVER' for p in drivers) and
                    all(model['endpoint_roles'].get(p) == 'HIGH_IMPEDANCE_RECEIVER' for p in receivers) and
                    all(model['endpoint_roles'][p] in ('DRIVER', 'HIGH_IMPEDANCE_RECEIVER', 'PASSIVE_RC') for p in pins) and
                    model.get('excluded_branches') == [])
                # Unknown active/clamp/parallel branches cannot receive a
                # numerical PASS from a simplified RC curve.
                source_path = bool(drivers)
                if isinstance(model, dict) and isinstance(db, dict):
                    pin2net = db.get('pin2net', {})
                    native_nets = db.get('nets', {})
                    all_types = {n: aliases.get(v, v) for n, v in raw_types.items()}
                    all_types.update(native)

                    def native_members(net_name):
                        members = native_nets.get(net_name, [])
                        ok = (isinstance(members, list) and all(text(n) and
                            pin2net.get(n) == net_name for n in members) and
                            set(members) == {n for n, v in pin2net.items() if v == net_name})
                        need(ok, 'SOURCE_NATIVE_INDEX', label + ' nonreciprocal native net ' + str(net_name))
                        return members if ok else []

                    native_members(net)
                    if not drivers:
                        external = model.get('external_source_nodes', [])
                        need(isinstance(external, list) and all(text(n) and n in pin2net for n in external),
                             'MODEL_SOURCE', label + ' external sources must be real native nodes')
                        external = external if isinstance(external, list) else []
                        branches = model.get('source_branches')
                        if branches is None:
                            # Preserve the existing directly evidenced single
                            # branch model. Multi-hop paths must name their
                            # conductive branches: passive connector/cap pins
                            # are not implicitly shorted by a source search.
                            branches = []
                            for pin in pins:
                                if model.get('endpoint_roles', {}).get(pin) != 'PASSIVE_RC' or types.get(pin) != 'passive':
                                    continue
                                for peer in pin2net:
                                    if peer != pin and peer.split('.', 1)[0] == pin.split('.', 1)[0] and all_types.get(peer) == 'passive':
                                        branches.append([pin, peer])
                        need(isinstance(branches, list), 'SOURCE_BRANCH', label + ' branch array required')
                        adjacency = {}
                        for pair in branches if isinstance(branches, list) else []:
                            ok = (isinstance(pair, list) and len(pair) == 2 and all(text(n) and n in pin2net for n in pair)
                                and pair[0] != pair[1] and pair[0].split('.', 1)[0] == pair[1].split('.', 1)[0]
                                and all(all_types.get(n) == 'passive' for n in pair))
                            if not need(ok, 'SOURCE_BRANCH', label + ' needs two real passive nodes on the same declared component'):
                                continue
                            n1, n2 = (pin2net[n] for n in pair)
                            # Check even unvisited declared edges before using
                            # them as an independently controlled source model.
                            native_members(n1); native_members(n2)
                            adjacency.setdefault(n1, set()).add(n2)
                            adjacency.setdefault(n2, set()).add(n1)
                        visited, pending = set(), [net]
                        while pending:
                            current = pending.pop()
                            if current in visited:
                                continue
                            visited.add(current)
                            members = native_members(current)
                            if any(all_types.get(n) in ('output', 'tri_state', 'open_collector',
                                    'open_emitter', 'power_out') or n in external for n in members):
                                source_path = True
                            pending.extend(adjacency.get(current, set()) - visited)
                        if model.get('qualification') == 'SUPPORTED':
                            need(source_path, 'MODEL_SOURCE', label + ' supported passive RC needs a native upstream source path')
                model_supported = model_ok and source_path and model.get('qualification') == 'SUPPORTED'
                need(isinstance(model, dict) and model.get('qualification') in ('SUPPORTED', 'UNRESOLVED'), 'MODEL_SUPPORT', label)
            else:
                model_supported = basis.get('model_support', {}).get('qualification') == 'SUPPORTED' and evidence(basis.get('model_support', {}).get('evidence'))
            expected_cells = {(receiver, case) for receiver in receivers for case in cases}
            need(set(cells) == expected_cells, 'CASE_COVERAGE', label + ' every receiver × actual operating case required')
            states = []
            for receiver, case_id in sorted(expected_cells, key=str):
                case = cases[case_id]
                cell = cells.get((receiver, case_id), {})
                previous_limitations = len(limited_inputs)
                voltage = interval(case.get('voltage'), 'V', label + '/' + case_id + '/voltage')
                resistance = interval(case.get('resistance'), 'ohm', label + '/' + case_id + '/resistance', True)
                value, unit, meets, limited = None, None, None, not model_supported
                if section == 'networks':
                    capacitance = interval(case.get('capacitance'), 'F', label + '/' + case_id + '/capacitance', True)
                    initial = interval(case.get('initial'), 'V', label + '/' + case_id + '/initial')
                    threshold = receivers[receiver]
                    threshold = threshold if isinstance(threshold, dict) else {}
                    bounds = interval(threshold.get('threshold'), 'V', label + '/' + str(receiver) + '/threshold')
                    need(threshold.get('basis') in ('GUARANTEED', 'TYPICAL', 'ASSUMED') or
                         (threshold.get('threshold') is None and current_allows_missing and threshold.get('basis') in (None, 'UNAVAILABLE')),
                         'THRESHOLD_BASIS', label)
                    limited = limited or threshold.get('basis') != 'GUARANTEED'
                    delay = case.get('required_delay_s')
                    need(finite(delay) and delay >= 0, 'DELAY_LIMIT', label)
                    if all(x is not None for x in (voltage, resistance, capacitance, initial, bounds)) and finite(delay):
                        # Single-pole monotone charge: earliest threshold crossing.
                        if initial['max'] >= bounds['min']:
                            value = 0.0
                        elif voltage['max'] <= bounds['min']:
                            need(False, 'UNREACHABLE_THRESHOLD', label + ' threshold cannot be guaranteed reached'); limited = True
                        else:
                            value = -resistance['min'] * capacitance['min'] * math.log(
                                (voltage['max'] - bounds['min']) / (voltage['max'] - initial['max']))
                        unit, meets = 's', value is not None and value >= delay
                    need(basis.get('model') == 'SINGLE_POLE_CHARGE', 'MODEL', label + ' bounded supported model required')
                else:
                    rating = interval(basis.get('power_rating'), 'W', label + '/power_rating', True)
                    limited = limited or basis.get('rating_basis') != 'GUARANTEED'
                    need(basis.get('rating_basis') in ('GUARANTEED', 'TYPICAL', 'ASSUMED') or
                         (basis.get('power_rating') is None and current_allows_missing and basis.get('rating_basis') in (None, 'UNAVAILABLE')),
                         'RATING_BASIS', label)
                    if voltage is not None and resistance is not None:
                        value = max(abs(voltage['min']), abs(voltage['max'])) ** 2 / resistance['min']
                        unit, meets = 'W', rating is not None and value <= rating['min']
                    limited = limited or rating is None
                    need(basis.get('model') == 'RESISTOR_DC_POWER', 'MODEL', label + ' bounded supported model required')
                limited = limited or len(limited_inputs) > previous_limitations
                state = 'INSUFFICIENT' if limited or value is None else ('PASS' if meets else 'FAIL')
                states.append(state)
                need(cell.get('claim') == state, 'NUMERIC_CLAIM', label + '/' + case_id + ' recomputed ' + state)
                expected_unit = 's' if section == 'networks' else 'W'
                no_estimate = (state == 'INSUFFICIENT' and cell.get('value') is None
                    and (value is None or (section == 'networks' and not model_supported)))
                numeric_equal = finite(cell.get('value')) and value is not None and math.isclose(
                    cell['value'], value, rel_tol=1e-9, abs_tol=1e-15)
                need((no_estimate or numeric_equal) and cell.get('unit') == expected_unit,
                     'NUMERIC_VALUE', label + '/' + case_id + ' corner value/unit differs')
            summary = 'FAIL' if 'FAIL' in states else ('INSUFFICIENT' if 'INSUFFICIENT' in states else 'PASS')
            need(actual[cid].get('review_result') == summary, 'NUMERIC_VERDICT', label + ' requires ' + summary)
            fid = entry.get('finding_id')
            if fid is not None:
                remediation = findings.get(fid, {}).get('remediation', {})
                need(cid in findings.get(fid, {}).get('check_ids', []), 'FINDING_BINDING', label)
                need(remediation.get('readiness') != 'READY' or summary == 'PASS', 'FALSE_READY', label)
            output['checked'][section] += 1

    for key, entry in sections['aggregates'].items():
        cid = scoped(entry, 'aggregates/' + key)
        scope = binding(entry.get('basis'), 'aggregates/' + key)
        row = records['aggregates'].get(key, {})
        if cid is None or not isinstance(scope, dict):
            need(False, 'AGGREGATE_BASIS', key); continue
        members = scope.get('members')
        kind = scope.get('kind')
        need(checks[cid].get('rule') != 'REQ-Q07' or kind == 'COVERAGE',
             'AGGREGATE_KIND', key + ' REQ-Q07 is coverage-only')
        applicability = scope.get('applicability', 'APPLICABLE')
        need(applicability in ('APPLICABLE', 'NOT_APPLICABLE', 'UNDETERMINED'),
             'AGGREGATE_APPLICABILITY', key)
        if applicability != 'APPLICABLE':
            # A package that is absent or not yet identified need not invent
            # members merely to satisfy the consistency contract.
            need(kind == 'COVERAGE' and members == [] and row.get('member_results') == {}
                 and evidence(scope.get('evidence')),
                 'AGGREGATE_APPLICABILITY', key + ' needs source-qualified empty coverage scope')
            need(checks[cid].get('applicability') == applicability,
                 'AGGREGATE_APPLICABILITY', key + ' source/plan applicability differs')
            expected = 'NA' if applicability == 'NOT_APPLICABLE' else 'INSUFFICIENT'
            need(actual[cid].get('review_result') == expected,
                 'AGGREGATE_VERDICT', key + ' applicability requires ' + expected)
            output['checked']['aggregates'] += 1
            continue
        ok = isinstance(members, list) and bool(members) and all(text(k) and k != cid and k in actual for k in members)
        ok = ok and len(members) == len(set(members)) and kind in ('ELECTRICAL', 'COVERAGE')
        if not need(ok, 'AGGREGATE_MEMBERS', key):
            continue
        claims = row.get('member_results')
        statuses = {k: actual[k].get('review_result') for k in members}
        need(claims == statuses, 'AGGREGATE_STATUS', key + ' actual required member results differ')
        excluded = scope.get('not_applicable', [])
        need(isinstance(excluded, list) and set(excluded) == {k for k, v in statuses.items() if v == 'NA'},
             'AGGREGATE_NA', key + ' NA requires controlled applicability scope')
        if kind == 'ELECTRICAL':
            expected = 'FAIL' if 'FAIL' in statuses.values() else ('INSUFFICIENT' if 'INSUFFICIENT' in statuses.values() else 'PASS')
            need(actual[cid].get('review_result') == expected, 'AGGREGATE_VERDICT', key + ' required ' + expected)
        else:
            # Complete coverage can PASS while an electrical child FAILs.
            need(set(statuses.values()).issubset(RESULTS), 'AGGREGATE_COVERAGE', key)
            incomplete = scope.get('review_incomplete')
            need(isinstance(incomplete, list) and set(incomplete).issubset(members), 'AGGREGATE_COVERAGE', key + ' controlled review-incomplete members required')
            if isinstance(incomplete, list):
                expected = 'INSUFFICIENT' if incomplete else 'PASS'
                need(actual[cid].get('review_result') == expected, 'AGGREGATE_VERDICT', key + ' coverage requires ' + expected)
        output['checked']['aggregates'] += 1

    for key, entry in sections['repairs'].items():
        kind = entry.get('target_kind', 'finding')
        target = entry.get('target_id', entry.get('finding_id'))
        owner = (findings if kind == 'finding' else work_items if kind == 'work_item' else {}).get(target, {})
        scope = binding(entry.get('basis'), 'repairs/' + key)
        repair = owner.get('remediation') if kind == 'finding' else owner.get('design_option', {}).get('remediation')
        record = records['repairs'].get(key, {})
        if not isinstance(scope, dict) or not isinstance(repair, dict):
            need(False, 'REPAIR_BINDING', key); continue
        allowed = scope.get('obligations')
        need(isinstance(allowed, list) and bool(allowed) and all(text(v) for v in allowed), 'REPAIR_OBLIGATIONS', key)
        allowed = allowed if isinstance(allowed, list) else []
        unresolved = scope.get('unresolved_obligations')
        decisions = scope.get('design_decision_obligations', [])
        ready_ok = (isinstance(unresolved, list) and isinstance(decisions, list) and
                    all(text(v) for v in unresolved + decisions) and
                    set(unresolved).issubset(allowed) and set(decisions).issubset(allowed))
        need(ready_ok, 'REPAIR_READINESS_SCOPE', key)
        if ready_ok:
            readiness = 'DESIGN_REQUIRED' if set(unresolved) & set(decisions) else ('CONDITIONAL' if unresolved else 'READY')
            need(repair.get('readiness') == readiness, 'REPAIR_READINESS', key + ' controlled obligations require ' + readiness)
        uses = index(record.get('dependencies'), 'repairs/' + key + '.dependencies')
        expected = {s + '/' + str(n) for s in ('prerequisites', 'parameters', 'steps', 'verification')
                    for n, _ in enumerate(repair.get(s, []))}
        need(set(uses) == expected, 'REPAIR_DEPENDENCY_COVERAGE', key)
        for locator, use in uses.items():
            obligation = use.get('obligation')
            origin = use.get('origin_check_id')
            dependency = binding(use.get('basis'), 'repairs/' + key + '/' + locator)
            need(isinstance(dependency, dict) and dependency.get('obligation') == obligation and
                 dependency.get('check_id') == origin and origin in checks and
                 obligation in allowed, 'UNRELATED_REPAIR_DEPENDENCY', key + '/' + locator)
            need(origin in owner.get('check_ids', []) or origin in scope.get('physical_dependencies', []),
                 'UNRELATED_REPAIR_DEPENDENCY', key + '/' + locator + ' no controlled original/physical dependency')
        output['checked']['repairs'] += 1

    for key, entry in sections['gaps'].items():
        cid = scoped(entry, 'gaps/' + key)
        scope = binding(entry.get('basis'), 'gaps/' + key)
        record = records['gaps'].get(key, {})
        if cid is None or not isinstance(scope, dict):
            need(False, 'GAP_BINDING', key); continue
        needed, available = scope.get('required_inputs'), scope.get('available_inputs')
        ok = all(isinstance(v, list) and all(text(k) for k in v) and len(v) == len(set(v)) for v in (needed, available))
        if not need(ok, 'GAP_INPUTS', key):
            continue
        missing = set(needed) - set(available)
        uses = record.get('missing_inputs')
        need(isinstance(uses, list) and bool(uses) and set(uses) == missing, 'UNRELATED_GAP', key + ' missing inputs must equal own required-minus-available')
        # IDs are machine-checkable; prose follows in the normal rationale.
        need(actual[cid].get('missing_inputs') == uses, 'GAP_RESULT_BINDING', key + ' result must name the same controlled input IDs')
        output['checked']['gaps'] += 1
    for key, entry in sections['handoffs'].items():
        cid = scoped(entry, 'handoffs/' + key)
        scope = binding(entry.get('basis'), 'handoffs/' + key)
        record = records['handoffs'].get(key, {})
        if cid is None or not isinstance(scope, dict):
            need(False, 'HANDOFF_BINDING', key); continue
        handoff = actual[cid].get('handoff', {})
        need(scope.get('object') == checks[cid].get('object') == record.get('object'), 'HANDOFF_OBJECT', key)
        need(isinstance(scope.get('receivers'), list) and bool(scope['receivers']) and
             scope['receivers'] == handoff.get('receivers') == record.get('receivers'), 'HANDOFF_RECEIVERS', key)
        if 'quantity' in scope:
            need(text(scope.get('quantity')) and scope['quantity'] == handoff.get('quantity') == record.get('quantity'),
                 'HANDOFF_QUANTITY', key + ' quantified constraint differs')
        need(scope.get('constraint') == handoff.get('constraint') and text(scope.get('constraint')),
             'HANDOFF_CONSTRAINT', key)
        need(scope.get('verification') == handoff.get('verification') and text(scope.get('verification')),
             'HANDOFF_VERIFICATION', key)
        output['checked']['handoffs'] += 1
    return output


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('results')
    parser.add_argument('audit')
    parser.add_argument('--db')
    parser.add_argument('--json')
    args = parser.parse_args()
    try:
        read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
        result = validate_execution_audit(read(args.plan), read(args.results),
            read(args.db) if args.db else None, read(args.audit), required=True)
    except (ValueError, OSError) as exc:
        result = {'enforced':True, 'electrical_approval':False, 'errors':[str(exc)]}
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
