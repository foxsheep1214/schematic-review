#!/usr/bin/env python3
"""Verify reviewer-declared device kinds against the bound datasheet text.

The reviewer states the kind of every part whose kind only a datasheet settles (device_kinds.needs_datasheet) with the
datasheet page and a verbatim quote (intent.device_kinds). This module reads that page of the PDF the datasheet audit
bound to the ref and checks that the quote is really there, that the quote itself names the declared kind, and that the
datasheet's own title does not name another kind (a kind is what the part does at its pins, not what is inside it).
It also proposes candidates for undeclared parts and compares a bound datasheet's title with the classifier's guess.
It never turns extracted text into a conclusion: only a VERIFIED declaration is used as the 'datasheet' basis;
anything else stays a gap or a hint.
"""
import functools
import hashlib
import re
import shutil
import subprocess

import catalog
import device_kinds

# Cue words on ASCII-alphanumeric text with spaces removed (PDF extraction often drops spaces).
# Integrated-circuit roles come from the role registry (catalog.DEVICE_ROLES): the datasheet title names what the part does.
# Discrete kinds' cues come from the kind registry (device_kinds.KINDS), the IC roles' from catalog.DEVICE_ROLES.
KIND_CUES = device_kinds.cue_table() + tuple((name, role.cues) for name, role in catalog.DEVICE_ROLES.items() if role.cues)
IC_ROLE_CUES = {name for name, role in catalog.DEVICE_ROLES.items() if role.cues}
DISCRETE_CUES = {'mosfet', 'bjt', 'diode', 'zener', 'tvs', 'bridge_rectifier'}
# An IC role in the same text names these as its load or its function: "Industrial eFuse", "relay driver" (A4).
ROLE_LOADS = DISCRETE_CUES | {'fuse', 'relay'}
SPECIFIC_DIODES = {'tvs', 'zener', 'bridge_rectifier'}      # a quote naming these is not evidence for a plain diode
GENERIC_IC = catalog.GENERIC_IC_ROLE
STATUSES = ('VERIFIED', 'QUOTE_NOT_FOUND', 'QUOTE_LACKS_TYPE', 'QUOTE_CONFLICT', 'TITLE_MISMATCH', 'NO_DOCUMENT', 'NO_TEXT',
            'CLASSIFIED')
# Statuses of a part without a declaration: a datasheet kind waits for one, a part the classifier cannot read waits for
# the reviewer to place it (2026-10-27 A5).
OPEN_STATUSES = ('UNDECLARED', 'UNCLASSIFIED')
TITLE_LINES = 6          # C1: a datasheet's title area; page 1 when it names no kind, never page 2 (applications, loads)
# A reason for keeping a declaration its title contradicts may not be the part's internal make-up (C3): an eFuse with an
# internal N-channel MOSFET is a load switch.
COMPOSITION_REASON_RE = re.compile(r'内部|内置|集成|构成|internal|integrat|inside|built-?in|compos', re.I)


def squash(text):
    return re.sub(r'[^a-z0-9]', '', str(text or '').lower())


SHORT_CUE = 3   # squashed, "Supply Current vs" holds tvs and "Maximum Current" mcu: a cue this short is read as a word
WORD_CUES = ('fuse',)   # squashed, "Littelfuse" (a maker's name) holds fuse: read as a word too


def named_by(word, text, flat=None):
    """True when text names the cue: a long cue anywhere in the squashed text, a short cue as a word of its own (a
    lowercase-to-capital join counts as a space, "BidirectionalTVSDiode"; a plural s is allowed; the cue in capitals may
    run into a lowercase word, "TVSdiode")."""
    if len(word) > SHORT_CUE and word not in WORD_CUES:
        return word in (squash(text) if flat is None else flat)
    spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', str(text or ''))
    return re.search(r'(?<![A-Za-z0-9])(?:%s(?![0-9])|(?i:%s)s?(?![a-z0-9]))' % (word.upper(), word), spaced) is not None


def cues(text, specific=True):
    """Kinds named in text; with specific=True a TVS/Zener word suppresses the generic 'diode'."""
    flat = squash(text)
    found = {kind for kind, words in KIND_CUES if any(named_by(w, text, flat) for w in words)}
    if specific and found & SPECIFIC_DIODES:
        found.discard('diode')
    if specific and 'opto' in found:
        # An optocoupler quote names its emitter diode and phototransistor too, and "optoisolator" is not a digital isolator.
        found -= {'diode', 'bjt', 'isolator'}
    if specific and found & IC_ROLE_CUES:
        # "MOSFET gate driver", "synchronous rectifier controller": the role is the kind, the discrete is its load.
        found -= ROLE_LOADS
    if specific and found & {'ntc', 'varistor'}:
        found.discard('fuse')            # a thermistor or varistor datasheet names its thermally fused (ThermoFuse) types
    if specific and 'relaydriver' in flat:
        found.discard('relay')           # a relay driver drives the coil; no IC role names generic load drivers
    if specific and 'supervisor' in found:
        found.discard('mcu')             # "microprocessor supervisor" watches an MCU, it is not one
    if specific and 'isolator' in found and 'gate_driver' in found:
        found.discard('gate_driver')     # an isolated gate driver is declared by its barrier
    if specific and 'regulator' in found and found & {'pwm_controller', 'sr_controller', 'pd_controller', 'charger'}:
        found.discard('regulator')       # "... controller for boost converters" names the controller
    if specific and 'motor_driver' in found:
        found.discard('gate_driver')     # "H-bridge motor driver" is the motor driver; a bare "gate driver" stays one
    if specific and 'mcu' in found:
        found -= {'oscillator', 'memory'}   # "MCU with 2 MB flash memory and internal oscillator" is the MCU
    return found


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_page_texts(source, page):
    """Reading-order and layout-order text of one PDF page (a quote may survive only one of them).

    `source` is a path or the PDF bytes. pdftotext (poppler) is used when installed, otherwise
    PyMuPDF; None when neither is available or the page cannot be read."""
    if shutil.which('pdftotext'):
        texts = []
        for mode in ([], ['-layout']):
            args = ['pdftotext', '-q', '-f', str(page), '-l', str(page), *mode]
            try:
                if isinstance(source, bytes):
                    out = subprocess.run(args + ['-', '-'], input=source, capture_output=True, timeout=60)
                else:
                    out = subprocess.run(args + [source, '-'], capture_output=True, timeout=60)
            except (OSError, subprocess.SubprocessError):
                return None
            if out.returncode != 0:
                return None
            texts.append(out.stdout.decode('utf-8', 'replace'))
        return texts
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None
    try:
        with (fitz.open(stream=source, filetype='pdf') if isinstance(source, bytes) else fitz.open(source)) as doc:
            if not 1 <= page <= doc.page_count:
                return None
            sheet = doc[page - 1]
            return [sheet.get_text(), sheet.get_text(sort=True)]
    except Exception:  # a damaged or encrypted PDF reads as no text, like a pdftotext failure
        return None


@functools.lru_cache(maxsize=512)
def _page_text(path, page, mtime_ns, size):
    texts = pdf_page_texts(path, page)
    joined = '\n'.join(texts or [])
    return joined if joined.strip() else None


def page_text(path, page):
    """Text of one PDF page, or None when no extractor is available or the page has no text layer."""
    import os
    try:
        st = os.stat(path)
    except OSError:
        return None
    return _page_text(path, int(page), st.st_mtime_ns, st.st_size)


GLYPH_OHM_AS_W_RE = re.compile(r'\d\s?[kM]W\b')   # kΩ / MΩ printed as kW / MW: the Symbol font did not survive extraction
MICRO_SIGNS = ('µ', 'μ')
UNIT_GLYPHS = ('SYMBOL_FALLBACK', 'OK', 'UNREAD')


def glyph_fallback(text):
    """True when a text layer lost its Symbol-font glyphs: kΩ and MΩ read as kW and MW and no µ survives, so a µs
    or µA on the same pages reads as ms or mA (one controller datasheet: tdelay(OVP) 22.5–37.5 "ms", IFMAX 9–11 "mA")."""
    return (isinstance(text, str) and len(GLYPH_OHM_AS_W_RE.findall(text)) >= 2
            and not any(sign in text for sign in MICRO_SIGNS))


@functools.lru_cache(maxsize=256)
def _document_text(path, mtime_ns, size):
    if not path.lower().endswith('.pdf'):
        try:
            with open(path, encoding='utf-8', errors='replace') as stream:
                return stream.read()
        except OSError:
            return None
    if shutil.which('pdftotext'):
        try:
            out = subprocess.run(['pdftotext', '-q', '-layout', path, '-'], capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.decode('utf-8', 'replace') if out.returncode == 0 else None
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None
    try:
        with fitz.open(path) as doc:
            return '\n'.join(sheet.get_text() for sheet in doc)
    except Exception:
        return None


def document_text(path):
    """Whole text of a datasheet file: a text extract as it is, a PDF through its text layer; None when unreadable."""
    import os
    try:
        st = os.stat(path)
    except (OSError, TypeError):
        return None
    return _document_text(path, st.st_mtime_ns, st.st_size)


def unit_glyphs(path):
    """SYMBOL_FALLBACK when the file's text lost Ω and µ (see glyph_fallback), OK when it reads them, UNREAD when the
    file has no text to judge."""
    text_ = document_text(path)
    if not text_ or not text_.strip():
        return 'UNREAD'
    return 'SYMBOL_FALLBACK' if glyph_fallback(text_) else 'OK'


def verify(declaration, document_path, read_page=None):
    """Check one declaration {kind, page, quote} against the bound datasheet."""
    read_page = read_page or page_text
    kind, page, quote = declaration.get('kind'), declaration.get('page'), declaration.get('quote')
    result = {'kind': kind, 'page': page, 'quote': quote, 'document': document_path}
    if not document_path:
        return dict(result, status='NO_DOCUMENT', detail='datasheet audit has no AVAILABLE document for this ref')
    text = read_page(document_path, page)
    if text is None:
        return dict(result, status='NO_TEXT', detail='page text unavailable (neither pdftotext nor PyMuPDF installed, or image-only page)')
    if not squash(quote) or squash(quote) not in squash(text):
        return dict(result, status='QUOTE_NOT_FOUND', detail=f'quote not found on page {page}')
    named = cues(quote)
    if kind == GENERIC_IC:
        if named:
            return dict(result, status='QUOTE_CONFLICT', detail=f'quote names {sorted(named)}; declare that kind, not ic')
        return title_check(result, declaration, document_path, read_page)
    if kind not in cues(quote, specific=False):
        return dict(result, status='QUOTE_LACKS_TYPE', detail=f'quote names {sorted(named) or "no device type"}')
    if named - {kind}:
        return dict(result, status='QUOTE_CONFLICT', detail=f'quote also names {sorted(named - {kind})}')
    return title_check(result, declaration, document_path, read_page)


def title_check(result, declaration, document_path, read_page):
    """C3 (2026-10-27): a quote from any page may name what is inside the part; the datasheet's title says what it is.
    A declaration the title contradicts takes effect only with a kind_reason that is not the part's make-up."""
    titled = cues(title_text(document_path, read_page))
    if not titled or agrees(declaration.get('kind'), titled):
        return dict(result, status='VERIFIED')
    reason = declaration.get('kind_reason')
    mismatch = {'title_kinds': sorted(titled)}
    if not (isinstance(reason, str) and reason.strip()):
        return dict(result, status='TITLE_MISMATCH', title_mismatch=mismatch,
                    detail=f'the datasheet title names {sorted(titled)}: quote the title, or give kind_reason')
    if COMPOSITION_REASON_RE.search(reason):
        return dict(result, status='TITLE_MISMATCH', title_mismatch=mismatch,
                    detail='kind_reason rests on what is inside the part; its kind is what it does at its pins')
    return dict(result, status='VERIFIED', title_mismatch=dict(mismatch, kind_reason=reason))


def title_text(document_path, read_page=None):
    """The datasheet's own title (C1): the first lines of page 1, or the whole page 1 when they name no kind."""
    read_page = read_page or page_text
    text = read_page(document_path, 1) if document_path else None
    if not text:
        return ''
    title = ' '.join([ln.strip() for ln in text.splitlines() if ln.strip()][:TITLE_LINES])
    return title if cues(title) else text


def agrees(kind, named):
    """Whether kind is among the kinds a text names; the generic ic agrees with any IC role."""
    return kind in named or (kind == GENERIC_IC and bool(named & IC_ROLE_CUES))


def kind_conflict(kind, document_path, read_page=None):
    """C2 (2026-10-27): the classifier's kind against a bound datasheet's title, as a hint; None when they agree or the
    title names no kind."""
    text = title_text(document_path, read_page) if document_path else ''
    titled = cues(text)
    if not titled or not kind or agrees(kind, titled):
        return None
    return {'code': 'KIND_CONFLICT', 'classifier_kind': kind, 'title_kinds': sorted(titled),
            'title': ' '.join(text.split())[:160]}


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
            line = next((ln for ln in lines if any(named_by(w, ln) for w in words)), '')
            out.append({'kind': kind, 'page': page, 'snippet': line[:120]})
        if out:
            break
    return out


def audit_kinds(materials, declared, heuristic, read_page=None):
    """device_kinds section of the datasheet audit (2026-10-27 A2/A5/C2/C3/B3). heuristic is {ref: {kind, basis,
    settlement}} as the classifier reads the netlist without declarations. Every part whose kind only a datasheet settles
    and every part the classifier cannot read that sits on two or more nets gets an entry, and so does every declared
    ref; a bound datasheet whose title contradicts the classifier carries a KIND_CONFLICT hint."""
    docs, refs = {}, set(declared)
    for material in materials:
        path = (material.get('document') or {}).get('path') if material.get('status') == 'AVAILABLE' else None
        for ref in material.get('refdes', []):
            docs[ref] = path
    refs |= {ref for ref, seen in heuristic.items() if seen.get('settlement')}
    section = {}
    for ref in sorted(refs):
        path, seen = docs.get(ref), heuristic.get(ref) or {}
        item = declared.get(ref)
        if isinstance(item, dict) and 'reason' in item:
            entry = {'status': 'CLASSIFIED', 'kind': item.get('kind'), 'reason': item.get('reason')}
        elif ref in declared:
            entry = verify(item, path, read_page)
            if entry['status'] == 'VERIFIED':
                entry['document_sha256'] = file_sha256(path)
                if seen.get('basis') == 'part-keyword' and not agrees(seen.get('kind'), {item['kind']}) \
                        and not agrees(item['kind'], {seen.get('kind')}):
                    # B3: the datasheet wins; the words that said otherwise are an SR capability gap
                    entry['keyword_conflict'] = {'keyword_kind': seen.get('kind')}
        else:
            entry = {'status': 'UNCLASSIFIED' if seen.get('settlement') == 'classify' else 'UNDECLARED', 'document': path,
                     'candidates': candidates(path, read_page=read_page) if path else []}
            conflict = kind_conflict(seen.get('kind'), path, read_page) if seen.get('kind') != 'unknown' else None
            if conflict:
                entry['kind_conflict'] = conflict
        section[ref] = entry
    return section


def kind_conflicts(materials, heuristic, read_page=None):
    """C2 over every bound datasheet, whether or not its part needs a declaration: {ref: KIND_CONFLICT hint}."""
    out = {}
    for material in materials:
        path = (material.get('document') or {}).get('path') if material.get('status') == 'AVAILABLE' else None
        for ref in material.get('refdes', []):
            kind = (heuristic.get(ref) or {}).get('kind')
            conflict = kind_conflict(kind, path, read_page) if path and kind not in (None, 'unknown') else None
            if conflict:
                out[ref] = conflict
    return out
