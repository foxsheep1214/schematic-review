#!/usr/bin/env python3
"""Verify reviewer-declared device kinds against the bound datasheet text.

The reviewer states each discrete semiconductor's kind with the datasheet page and a verbatim
quote (intent.device_kinds). This module reads that page of the PDF the datasheet audit bound to
the ref and checks that the quote is really there and that the quote itself names the declared kind.
It also proposes candidates for undeclared parts. It never turns extracted text into a conclusion:
only a VERIFIED declaration is used as the 'datasheet' basis; anything else stays a gap.
"""
import functools
import hashlib
import re
import shutil
import subprocess

# Cue words on ASCII-alphanumeric text with spaces removed (PDF extraction often drops spaces).
KIND_CUES = (
    ('bjt', ('npn', 'pnp', 'bipolar')),
    ('mosfet', ('mosfet', 'nchannel', 'pchannel', 'superjunction')),
    ('tvs', ('tvs', 'esdprotection', 'transientvoltagesuppress', 'transientsuppress')),
    ('zener', ('zener',)),
    ('diode', ('rectifier', 'diode', 'schottky')),
)
SPECIFIC_DIODES = {'tvs', 'zener'}      # a quote naming these is not evidence for a plain diode
SEMICONDUCTOR_REF = re.compile(r'^(Q|D|ZD|TVS)\d', re.I)
STATUSES = ('VERIFIED', 'QUOTE_NOT_FOUND', 'QUOTE_LACKS_TYPE', 'QUOTE_CONFLICT', 'NO_DOCUMENT', 'NO_TEXT')


def squash(text):
    return re.sub(r'[^a-z0-9]', '', str(text or '').lower())


def cues(text, specific=True):
    """Kinds named in text; with specific=True a TVS/Zener word suppresses the generic 'diode'."""
    flat = squash(text)
    found = {kind for kind, words in KIND_CUES if any(w in flat for w in words)}
    if specific and found & SPECIFIC_DIODES:
        found.discard('diode')
    return found


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


@functools.lru_cache(maxsize=512)
def _page_text(path, page, mtime_ns, size):
    if not shutil.which('pdftotext'):
        return None
    texts = []
    for mode in ([], ['-layout']):            # reading order and layout order: a quote may survive only one
        try:
            out = subprocess.run(['pdftotext', '-q', '-f', str(page), '-l', str(page), *mode, path, '-'],
                                 capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        texts.append(out.stdout.decode('utf-8', 'replace'))
    joined = '\n'.join(texts)
    return joined if joined.strip() else None


def page_text(path, page):
    """Text of one PDF page, or None when no extractor is available or the page has no text layer."""
    import os
    try:
        st = os.stat(path)
    except OSError:
        return None
    return _page_text(path, int(page), st.st_mtime_ns, st.st_size)


def verify(declaration, document_path, read_page=None):
    """Check one declaration {kind, page, quote} against the bound datasheet."""
    read_page = read_page or page_text
    kind, page, quote = declaration.get('kind'), declaration.get('page'), declaration.get('quote')
    result = {'kind': kind, 'page': page, 'quote': quote, 'document': document_path}
    if not document_path:
        return dict(result, status='NO_DOCUMENT', detail='datasheet audit has no AVAILABLE document for this ref')
    text = read_page(document_path, page)
    if text is None:
        return dict(result, status='NO_TEXT', detail='page text unavailable (no pdftotext or image-only page)')
    if not squash(quote) or squash(quote) not in squash(text):
        return dict(result, status='QUOTE_NOT_FOUND', detail=f'quote not found on page {page}')
    named = cues(quote)
    if kind not in cues(quote, specific=False):
        return dict(result, status='QUOTE_LACKS_TYPE', detail=f'quote names {sorted(named) or "no device type"}')
    if named - {kind}:
        return dict(result, status='QUOTE_CONFLICT', detail=f'quote also names {sorted(named - {kind})}')
    return dict(result, status='VERIFIED')


def candidates(document_path, pages=(1, 2), read_page=None):
    """Kinds named on the first pages, with a short context snippet; suggestions only."""
    read_page = read_page or page_text
    out = []
    for page in pages:
        text = read_page(document_path, page) if document_path else None
        if not text:
            continue
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for kind in sorted(cues(text)):
            words = dict(KIND_CUES)[kind]
            line = next((ln for ln in lines if any(w in squash(ln) for w in words)), '')
            out.append({'kind': kind, 'page': page, 'snippet': line[:120]})
        if out:
            break
    return out


def audit_kinds(materials, declared):
    """device_kinds section of the datasheet audit: every semiconductor ref and every declared ref."""
    docs, refs = {}, set(declared)
    for material in materials:
        path = (material.get('document') or {}).get('path') if material.get('status') == 'AVAILABLE' else None
        for ref in material.get('refdes', []):
            docs[ref] = path
            if SEMICONDUCTOR_REF.match(ref):
                refs.add(ref)
    section = {}
    for ref in sorted(refs):
        path = docs.get(ref)
        if ref in declared:
            entry = verify(declared[ref], path)
            if entry['status'] == 'VERIFIED':
                entry['document_sha256'] = file_sha256(path)
        else:
            entry = {'status': 'UNDECLARED', 'document': path,
                     'candidates': candidates(path) if path else []}
        section[ref] = entry
    return section
