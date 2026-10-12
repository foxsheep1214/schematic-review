"""Document pages are native sheet declarations, not component membership.

Legacy databases expose only observed component pages. That fallback cannot
establish that an empty root or any other unrepresented page exists.
"""
from copy import deepcopy
import re


SOURCE = 'kicadxml.design/sheet'
NATIVE = 'native_declared_sheets'
LIMITED = 'component_pages_only'


def _path(value):
    return (isinstance(value, str) and value.startswith('/') and value.endswith('/')
            and not any(x in ('.', '..', '') for x in value.split('/')[1:-1])
            and not any(ord(c) < 32 for c in value))


def native_inventory(sheets):
    """Retain explicit identifiers; reject ambiguity rather than renumbering."""
    rows, numbers, paths, stamps = [], set(), set(), set()
    for sheet in sheets:
        number, path, stamp = sheet.get('number'), sheet.get('name'), sheet.get('tstamps', '')
        if not isinstance(number, str) or not re.fullmatch(r'[0-9]+', number) or int(number) <= 0:
            raise ValueError('native sheet missing/invalid explicit page number')
        number = int(number)
        if not _path(path):
            raise ValueError('native sheet missing/invalid absolute sheet path')
        if number in numbers or path in paths or (stamp and stamp in stamps):
            raise ValueError('duplicate native sheet page/path/tstamps')
        numbers.add(number)
        paths.add(path)
        if stamp:
            stamps.add(stamp)
        rows.append({'page': number, 'sheet_path': path, 'tstamps': stamp})
    return {'schema_version': 1, 'source': SOURCE,
            'scope': NATIVE if rows else LIMITED,
            'pages': sorted(rows, key=lambda x: x['page'])}


def inventory(db):
    """One checked source for planner and validator, with explicit old scope."""
    native = db.get('page_inventory')
    if not isinstance(db.get('ref2page', {}), dict):
        raise ValueError('ref2page must be an object for page inventory')
    if 'page_inventory' not in db:
        pages = sorted({p for p in db.get('ref2page', {}).values() if p not in (None, '')}, key=str)
        return {'schema_version': 1, 'source': 'ref2page', 'scope': LIMITED,
                'pages': [{'page': p} for p in pages]}
    if not isinstance(native, dict) or set(native) != {'schema_version', 'source', 'scope', 'pages'}:
        raise ValueError('invalid page_inventory structure')
    if type(native.get('schema_version')) is not int or native['schema_version'] != 1 or native['source'] != SOURCE:
        raise ValueError('invalid page_inventory schema/source')
    rows = native.get('pages')
    if not isinstance(rows, list):
        raise ValueError('page_inventory.pages must be array')
    sheets = []
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'page', 'sheet_path', 'tstamps'}
                or type(row.get('page')) is not int or not isinstance(row.get('tstamps'), str)):
            raise ValueError('invalid page_inventory page record')
        sheets.append({'number': str(row['page']), 'name': row['sheet_path'], 'tstamps': row['tstamps']})
    checked = native_inventory(sheets)
    if checked != native:
        raise ValueError('page_inventory scope/order does not match native declarations')
    numbers = {row['page'] for row in rows}
    if any(type(p) is not int or p not in numbers for p in db.get('ref2page', {}).values()):
        raise ValueError('ref2page outside native page_inventory scope')
    return deepcopy(checked)


def validate_document_pages(plan, expected, db, require):
    """A page ledger cannot substitute an unrelated electrical PASS for a view."""
    checked = inventory(db)
    if 'page_inventory' not in db:
        if 'page_inventory' in plan:
            require(plan['page_inventory'] == checked, 'plan.page_inventory mismatch; regenerate current plan')
        return checked, {}  # Historical limited-format ledger remains bounded.
    require(plan.get('page_inventory') == checked, 'plan.page_inventory mismatch; regenerate current plan')
    docs = [x for x in expected.values() if x.get('rule') == 'DOC-V01']
    by_page = {}
    for row in checked['pages']:
        key = str(row['page'])
        matches = [x for x in docs if isinstance(x.get('object'), dict)
                   and str(x['object'].get('page')) == key]
        require(len(matches) == 1, 'DOC-V01 page ' + key + ': missing/duplicate native page view')
        if len(matches) == 1:
            check = matches[0]
            obj = {'page': row['page']}
            if 'sheet_path' in row:
                obj['sheet_path'] = row['sheet_path']
            require(check.get('object') == obj and check.get('applicability') == 'APPLICABLE',
                    'DOC-V01 page ' + key + ': changed page identity/scope')
            by_page[key] = check['id']
    require(len(docs) == len(checked['pages']), 'DOC-V01 must contain exactly one view per inventory page')
    return checked, by_page
