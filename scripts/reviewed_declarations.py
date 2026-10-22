#!/usr/bin/env python3
"""Persist reviewer-derived pin roles and decoupling groups, not electrical verdicts.

Capture records an explicit reviewer's declaration and exact sources; it does not
infer correctness from a filename, pin hint or previous PASS. Every consumer checks
source bytes, board identity and review context again before using the declaration.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

KEY = 'reviewed_declarations'
VERSION = 1


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def context_digest(intent):
    # The audit-derived cache is recomputed by SR; it is not reviewer input.
    return digest({k: v for k, v in intent.items() if k not in (KEY, 'device_kinds_verified')})


def text(v):
    return isinstance(v, str) and bool(v.strip())


def record_errors(record, db, intent):
    from board_intent import input_fingerprint
    errors = []
    if not isinstance(record, dict):
        return [KEY + ': record must be an object']
    required = {'schema_version', 'reviewer', 'sources', 'input_sha256', 'context_sha256', 'declarations', 'digest'}
    if set(record) != required or type(record.get('schema_version')) is not int or record['schema_version'] != VERSION:
        errors.append(KEY + ': invalid schema/fields')
    try:
        if record.get('digest') != digest({k: v for k, v in record.items() if k != 'digest'}):
            errors.append(KEY + ': record was modified; review and capture again')
        if record.get('context_sha256') != context_digest(intent):
            errors.append(KEY + ': review context changed; recheck roles/groups, not just hashes')
        if db is not None and record.get('input_sha256') != input_fingerprint(db):
            errors.append(KEY + ': source input changed; recheck roles/groups, not just hashes')
    except (TypeError, ValueError):
        errors.append(KEY + ': non-serializable record/context')
    reviewer = record.get('reviewer')
    if not (isinstance(reviewer, dict) and set(reviewer) == {'kind', 'method'}
            and reviewer.get('kind') in ('AI', 'HUMAN') and text(reviewer.get('method'))):
        errors.append(KEY + ': reviewer needs kind AI/HUMAN and actual review method')
    sources = record.get('sources')
    if not isinstance(sources, list) or not sources:
        errors.append(KEY + ': exact source files and locators required')
        sources = []
    for i, src in enumerate(sources):
        try:
            if not (isinstance(src, dict) and set(src) == {'path', 'sha256', 'locator'} and text(src.get('locator'))):
                raise ValueError('file/hash/locator required')
            path = Path(src['path'])
            if not path.is_absolute() or not path.is_file():
                raise ValueError('absolute readable file required')
            if hashlib.sha256(path.read_bytes()).hexdigest() != src['sha256']:
                raise ValueError('source bytes changed; recheck declarations')
        except (KeyError, TypeError, OSError, ValueError) as e:
            errors.append(f'{KEY}.sources[{i}]: {e}')
    payload = record.get('declarations')
    if not (isinstance(payload, dict) and 'decoupling' in payload and set(payload) <= {'devices', 'decoupling'}
            and isinstance(payload['decoupling'], dict) and isinstance(payload.get('devices', {}), dict)):
        errors.append(KEY + ': declarations supports devices and decoupling only; no verdicts')
    return errors


def resolve(intent, db=None):
    """Return a validated effective intent; original data and cached records are never updated."""
    if not isinstance(intent, dict) or KEY not in intent:
        return intent
    record = intent[KEY]
    errors = record_errors(record, db, intent)
    if errors:
        raise ValueError('; '.join(errors))
    out = deepcopy({k: v for k, v in intent.items() if k != KEY})
    payload = record['declarations']
    devices = out.setdefault('devices', {})
    if not isinstance(devices, dict):
        raise ValueError(KEY + ': existing devices must be an object')
    for ref, spec in payload.get('devices', {}).items():
        if ref in devices and devices[ref] != spec:
            raise ValueError(KEY + ': conflicting official device declaration: ' + ref)
        devices[ref] = deepcopy(spec)
    import checkers  # noqa: F401 -- decoupling and the checkers import each other; the registry must load first
    from decoupling import SECTION_SCHEMA_VERSION   # decoupling imports this module
    cfg = out.setdefault('decoupling', {'schema_version': SECTION_SCHEMA_VERSION, 'groups': [], 'components': {}})
    extra = payload['decoupling']
    if not isinstance(cfg, dict) or extra.get('schema_version') != SECTION_SCHEMA_VERSION or set(extra) - {'schema_version', 'groups', 'components'}:
        raise ValueError(KEY + ': decoupling must use schema %d' % SECTION_SCHEMA_VERSION)
    groups, components = extra.get('groups', []), extra.get('components', {})
    if not (isinstance(groups, list) and isinstance(components, dict)
            and isinstance(cfg.get('groups', []), list) and isinstance(cfg.get('components', {}), dict)):
        raise ValueError(KEY + ': malformed groups/components')
    for g in groups:
        if not isinstance(g, dict) or not text(g.get('ref')) or not text(g.get('net')):
            raise ValueError(KEY + ': each group names its ref and supply net')
        same = lambda x: isinstance(x, dict) and (x.get('ref'), x.get('net')) == (g['ref'], g['net'])
        prior = [x for x in cfg.get('groups', []) if same(x)]
        if prior and any(x != g for x in prior):
            raise ValueError(KEY + ': conflicting group: %s:%s' % (g['ref'], g['net']))
        if not prior:
            cfg.setdefault('groups', []).append(deepcopy(g))
    for ref, spec in components.items():
        if ref in cfg.get('components', {}) and cfg['components'][ref] != spec:
            raise ValueError(KEY + ': conflicting component role: ' + ref)
        cfg.setdefault('components', {})[ref] = deepcopy(spec)
    # Normal pin-role, assembly and physical-node contracts still apply.
    from board_intent import validate
    from checkers.decoupling import validate_decoupling_intent
    errors = validate(out, db) + validate_decoupling_intent(out, db)
    if errors:
        raise ValueError('; '.join(errors))
    return out


def capture(db, intent, draft):
    """Persist an explicitly reviewed draft. This function does not perform the review."""
    from board_intent import input_fingerprint
    if not isinstance(intent, dict) or KEY in intent:
        raise ValueError('capture needs the base intent without an old reviewed_declarations record')
    if not isinstance(draft, dict) or set(draft) != {'reviewer', 'sources', 'declarations'}:
        raise ValueError('draft needs reviewer, sources and declarations')
    sources = []
    for src in draft.get('sources', []) if isinstance(draft.get('sources'), list) else []:
        if not isinstance(src, dict) or set(src) != {'path', 'locator'}:
            raise ValueError('draft sources need path and locator')
        path = Path(src['path']).resolve(strict=True)
        sources.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'locator': src['locator']})
    record = {'schema_version': VERSION, 'reviewer': deepcopy(draft['reviewer']), 'sources': sources,
              'input_sha256': input_fingerprint(db), 'context_sha256': context_digest(intent),
              'declarations': deepcopy(draft['declarations'])}
    record['digest'] = digest(record)
    resolve(dict(intent, **{KEY: record}), db)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('capture', 'apply', 'status'):
        p = sub.add_parser(name)
        p.add_argument('db'); p.add_argument('intent')
        if name != 'status':
            p.add_argument('declaration', help='reviewed draft for capture; captured record for apply')
            p.add_argument('-o', '--out', required=True)
    args = parser.parse_args(argv)
    load = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    try:
        db, intent = load(args.db), load(args.intent)
        if args.command == 'capture':
            result = capture(db, intent, load(args.declaration))
        elif args.command == 'apply':
            if KEY in intent:
                raise ValueError('apply needs base intent, never silently replace an existing review record')
            result = dict(intent, **{KEY: load(args.declaration)})
            resolve(result, db)
        else:
            if KEY not in intent:
                raise ValueError('no reviewed declarations to verify')
            resolve(intent, db)
            print('CURRENT: source and context unchanged; no electrical PASS implied')
            return 0
        output = Path(args.out).resolve()
        record = result if args.command == 'capture' else result[KEY]
        inputs = {Path(p).resolve() for p in (args.db, args.intent, args.declaration)}
        inputs.update(Path(s['path']).resolve() for s in record['sources'])
        if output in inputs:
            raise ValueError('output must not overwrite an input or cited source')
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print('saved', args.out)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as e:
        print('REVIEW_REQUIRED:', e)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
