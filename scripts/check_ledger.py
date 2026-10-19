#!/usr/bin/env python3
"""The newest entry of docs/improvement-ledger.md names its event, its causes and its files.

A skill change happens because of an event (a review comment, a datasheet
page, a test result, a user correction), is attributed to a cause class, and
touches files that exist. Older entries are history and are not checked.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / 'docs' / 'improvement-ledger.md'
CAUSES = ('rule_missing', 'rule_not_enforced', 'knowledge_missing', 'knowledge_wrong', 'judgment')
SOURCE = re.compile(r'(review:[^\s/,;]+/[^\s,;]+|datasheet:[^\s,;]+#p\d+|test:[^\s,;]+|user:\d{4}-\d{2}-\d{2})')


def latest_entry(text):
    parts = re.split(r'^## ', text, flags=re.M)
    return parts[1] if len(parts) > 1 else ''


def field(entry, name):
    m = re.search(r'^[-*\s]*%s:\s*(.+?)(?=^\S|^[-*]\s+\w+:|\Z)' % name, entry, flags=re.M | re.S)
    return ' '.join(m.group(1).split()) if m else ''


def check_entry(entry, root=ROOT):
    problems = []
    title = entry.splitlines()[0].strip() if entry.strip() else ''
    event, causes, changed = field(entry, 'Event'), field(entry, 'Causes'), field(entry, 'Changed')
    if not SOURCE.search(event):
        problems.append('%s: Event: must cite review:<dir>/<item>, datasheet:<path>#p<n>, test:<record> or user:<date>' % title)
    if not any(re.search(r'%s\s+\d+' % c, causes) for c in CAUSES):
        problems.append('%s: Causes: must count the cause classes (%s)' % (title, ', '.join(CAUSES)))
    paths = [p.strip('`') for p in re.split(r'[\s,;]+', changed) if p.strip('`')]
    if not paths:
        problems.append('%s: Changed: must list the files changed' % title)
    for p in paths:
        if not (root / p).exists():
            problems.append('%s: Changed: %s does not exist' % (title, p))
    return problems


def main(argv=None):
    path = Path(argv[0]) if argv else LEDGER
    problems = check_entry(latest_entry(path.read_text(encoding='utf-8')))
    for p in problems:
        print('PROBLEM:', p)
    print('FAIL' if problems else 'PASS')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
