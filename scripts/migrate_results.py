#!/usr/bin/env python3
"""Bring an older review-results.json to the current results format where the change was only a renaming.

The results format number counts changes of structure (2026-10-27, user: 按照你推荐的三种方式进行修改). A change that only
renames words — a vocabulary moved into the catalog, a field given another name with the same meaning — is a rename
here: the gate refuses the old word and names this script, and the script rewrites it. Renames are found by the old
word itself, so they apply to a file of any format and running the script twice changes nothing. A structural step
(an open-item kind removed, a field split by meaning) needs the reviewer and is not migrated: the script says which step
and what to redo.

    python3 scripts/migrate_results.py review-results.json            # rewrites the file in place
    python3 scripts/migrate_results.py review-results.json -o new.json
"""
import argparse
import json
import sys

from results_model import SCHEMA_VERSION

# results 15: basis.derivation and worst_case.bound.basis became the bounding table's method
METHOD_OF = {'GUARANTEED_LIMIT': 'G1', 'ADJACENT_TEST_POINT': 'G2', 'MONOTONIC': 'G2', 'TEMPCO': 'G4',
             'PUBLISHED_TABLE': 'G5', 'TYPICAL_CURVE': 'G8', 'APPLICATION_NOTE': 'G11'}
# format reached → what that step changed; the steps needing the reviewer are not migrated
STEPS = {
    7: 'a datasheet or BOM condition names the parts it is about (conditions[].refs)',
    8: 'REQUIREMENT open items removed: requirement questions are answered in intent.clarifications',
    9: 'an estimate that passes names basis.risk{types, corner, improvement}',
    10: 'DESIGN_VALUE open items removed: a value the schematic should state is a fail item',
    11: 'DELIVERABLE_PENDING open items removed: what another stage owes is a DESIGN_CONSTRAINT handed on',
    12: 'USER_DEFERRED open items removed: a deferred check is NA with na_reason USER_DEFERRED',
    13: 'a pass whose stress is only a handed-on DESIGN_CONSTRAINT is a judgements entry, not a zero margin',
    14: 'a finding says root_cause, consequence and fix once; the older finding texts are retired',
    15: None,   # renames only (METHOD_OF)
}


def _method(basis):
    """A margin basis: derivation → method; a method the cell already names wins."""
    word = basis.pop('derivation')
    if 'method' not in basis and word in METHOD_OF:
        basis['method'] = METHOD_OF[word]
    return 'basis.derivation %s → method %s' % (word, basis.get('method'))


def _bound(bound):
    word = bound.pop('basis')
    if 'method' not in bound and word in METHOD_OF:
        bound['method'] = METHOD_OF[word]
    return 'worst_case.bound.basis %s → method %s' % (word, bound.get('method'))


def rename(node, done):
    """Every old word in the tree, rewritten in place; `done` collects what was changed."""
    if isinstance(node, dict):
        if 'derivation' in node and 'kind' in node and 'comparison' in node:
            done.append(_method(node))
        bound = node.get('bound')
        if isinstance(bound, dict) and 'condition' in bound and 'basis' in bound:
            done.append(_bound(bound))
        for value in node.values():
            rename(value, done)
    elif isinstance(node, list):
        for value in node:
            rename(value, done)
    return done


def migrate(report):
    """(report at the current format, [what was changed]); ValueError names a step that needs the reviewer."""
    version = report.get('schema_version') if isinstance(report, dict) else None
    if not isinstance(version, int) or version > SCHEMA_VERSION:
        raise ValueError('results.schema_version %r is not a format this SR knows (current %d)' % (version, SCHEMA_VERSION))
    needs_review = ['%d: %s' % (v, STEPS.get(v, 'a step before format 7')) for v in range(version + 1, SCHEMA_VERSION + 1)
                    if v not in STEPS or STEPS[v]]
    if needs_review:
        raise ValueError('results format %d cannot be carried to %d by renaming; the steps that need the reviewer: %s; '
                         'review again with this SR' % (version, SCHEMA_VERSION, '; '.join(needs_review)))
    done = rename(report, [])
    if version != SCHEMA_VERSION:
        report['schema_version'] = SCHEMA_VERSION
        done.append('schema_version %d → %d' % (version, SCHEMA_VERSION))
    return report, done


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('results')
    parser.add_argument('-o', '--output', help='write here instead of rewriting the file in place')
    args = parser.parse_args(argv)
    with open(args.results, encoding='utf-8') as f:
        report = json.load(f)
    try:
        report, done = migrate(report)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    with open(args.output or args.results, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('\n'.join(done) or 'nothing to rename')
    return 0


if __name__ == '__main__':
    sys.exit(main())
