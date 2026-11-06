"""订货状态线索和库内候选。只给审查员任务，不作电气判定或替代批准。"""
import re
from pathlib import Path

import datasheet_kinds

TABLE = re.compile(r'orderable\s+part|ordering\s+(?:information|guide)|订货(?:表|信息)', re.I)
RISK = re.compile(r'pre[ -]?production|product\s+preview|preview|advance\s+information|NRND|'
                  r'not\s+recommended|obsolete|discontinued|last\s+time\s+buy|\bEOL\b', re.I)
ACTIVE = re.compile(r'\bactive\b|\bproduction\b|量产', re.I)


def _pages(path):
    if not path:
        return
    if str(path).lower().endswith('.pdf'):
        for page in range(1, 501):
            texts = datasheet_kinds.pdf_page_texts(str(path), page)
            if texts is None:
                break
            yield page, texts[-1]
    else:
        text = datasheet_kinds.document_text(str(path))
        for page, text in enumerate((text or '').split('\f'), 1):
            yield page, text


def scan_ordering(identity, path):
    """Match ordering rows, never the legend or another model's state. Preserve PDF page numbers.

    Family identities may match suffix variants; every matching row is retained and any risk wins.
    X/P is a risk hint only, never proof that an arbitrary manufacturer's prefix means preproduction.
    """
    result = dict(identity=identity, path=str(path or ''), status='INSUFFICIENT', evidence=[])
    token = re.compile(r'(?<![A-Za-z0-9])([XP]?' + re.escape(identity) + r'(?:[A-Za-z/+-][A-Za-z0-9/+-]*)?)(?![A-Za-z0-9])', re.I)
    for page, text in _pages(path):
        # A first-page prepublication banner applies to the named family, independently of row Active.
        banner = re.search(r'^\s*(ADVANCE INFORMATION|PRODUCT PREVIEW|PREVIEW)\s*$', text, re.I | re.M)
        if page == 1 and banner and token.search(text):
            result['evidence'].append(dict(page=page, orderable=identity, state=banner.group(1),
                                           quote=banner.group().strip(), risk=True, explicit=True))
        heading = TABLE.search(text)
        if not heading:
            continue
        # Tables of contents and footnote legends do not establish row status.
        for line in text[heading.end():].splitlines():
            match = token.search(line)
            if not match:
                continue
            code = match.group(1)
            tail = line[match.end():]
            risk, active = RISK.search(tail), ACTIVE.search(tail)
            prefixed = code.upper().startswith(('X'+identity.upper(), 'P'+identity.upper()))
            if not (risk or active or prefixed):
                continue
            state = risk.group() if risk else ('X/P 前缀待核实' if prefixed else active.group())
            result['evidence'].append(dict(page=page, orderable=code, state=state, quote=line.strip(),
                                           risk=bool(risk or prefixed), explicit=bool(risk or (active and not prefixed))))
    if result['evidence']:
        result['status'] = 'RISK' if any(e['risk'] for e in result['evidence']) else 'PRODUCTION'
    return result


def notice(scan, acceptance=None):
    """Acceptance metadata de-duplicates the task, never supplies manufacturer/electrical evidence."""
    if scan['status'] == 'PRODUCTION':
        return None
    a = acceptance or {}
    registered = (scan['status'] == 'RISK' and a.get('identity') == scan['identity']
                  and all(isinstance(a.get(k), str) and a[k].strip() for k in ('accepted_by', 'action', 'source'))
                  and re.search(r'投产前.*(?:换|替)|(?:换|替).*投产前', a['action']))
    kind = 'REGISTERED' if registered else scan['status']
    locations = '；'.join(f"{e['orderable']} {e['state']} p{e['page']}" for e in scan['evidence'])
    message = (f"{scan['identity']}：{locations or '订货表/状态读不到，资料不足'}；手册 {scan['path']}。"
               + (f"已登记投产前换料，接受人 {a['accepted_by']}（{a['source']}），不重复新建问题。" if registered
                  else '核原表并给待核替换建议；订货状态风险不判电路错误。'))
    return dict(kind=kind, message=message)


def candidate_pool(identity, catalog_path, selection=None):
    """Catalog's same second-level class + unselected candidates of the matching selection role.

    Selection contributes names only, never its numbers/reasons/verdicts. Every name must resolve
    to a real catalog document, including candidates outside the source's second-level class.
    """
    import json
    catalog_path = Path(catalog_path)
    rows = json.loads(catalog_path.read_text(encoding='utf-8'))['rows']
    def names(row):
        return row.get('model', '').upper()
    def matches(model, mpn):
        return bool(model and re.fullmatch(r'[XP]?' + re.escape(model) + r'(?:[A-Z/+-][A-Z0-9/+-]*)?', mpn.upper()))
    originals = [r for r in rows if matches(names(r), identity)]
    classes = {(r.get('category'), r.get('subcategory')) for r in originals}
    extra = set()
    for role in (selection or {}).get('roles', []):
        candidates = role.get('candidates', [])
        if any(c.get('mpn', '').upper() == identity.upper() or
               any(matches(names(r), c.get('mpn', '')) for r in originals) for c in candidates):
            extra.update(c.get('mpn', '').upper() for c in candidates if c.get('status') in ('rejected', 'alternate'))
    pool = []
    root = catalog_path.parent.resolve()
    for row in rows:
        if row in originals:
            continue
        same = (row.get('category'), row.get('subcategory')) in classes
        if not same and not any(matches(names(row), code) for code in extra):
            continue
        path = (root / row['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        pool.append(dict(model=row['model'], path=str(path), source='同二级类' if same else 'selection 候选线索',
                         ordering=scan_ordering(row['model'], path)))
    return pool


def recommend_candidates(pool, assessments):
    """Reviewer independently checks decisive function/voltage/package parameters before inclusion.

    Unknown states are excluded; known nonproduction candidates remain visibly flagged.
    Empty result means no verified candidate, not permission to invent a model.
    """
    result = []
    for candidate in pool:
        assessment = assessments.get(candidate['model'], {})
        scan = candidate['ordering']
        if (assessment.get('suitable') is not True or not assessment.get('why') or not assessment.get('pending')
                or scan['status'] == 'INSUFFICIENT' or not all(e['explicit'] for e in scan['evidence'])):
            continue
        result.append(dict(candidate, why=assessment['why'], pending=assessment['pending'], tentative=True))
    return sorted(result, key=lambda c: c['ordering']['status'] != 'PRODUCTION')[:3]
