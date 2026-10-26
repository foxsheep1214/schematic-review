#!/usr/bin/env python3
"""Shared input gates: netlist and document fingerprints, strict JSON loading, finite bounds.

The hashes bind reviewed inputs, not the truth of a datasheet interpretation.
"""
import argparse
import hashlib
import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path

from skill_identity import engineering_identity


def db_fingerprint(db):
    data = {key: db.get(key, {}) for key in
            ('parts', 'pin2net', 'pinname', 'pintype')}
    data['nets'] = {net: sorted(nodes) for net, nodes in db.get('nets', {}).items()}
    if 'page_inventory' in db:
        # Native document inventory and component locations bind a new plan;
        # an electrically unchanged empty page is still a review obligation.
        data['page_inventory'] = db['page_inventory']
        data['ref2page'] = db.get('ref2page', {})
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=128)
def _file_hash(path, size, mtime_ns):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def document_fingerprint(path):
    stat = os.stat(path)
    return _file_hash(os.path.abspath(path), stat.st_size, stat.st_mtime_ns)


WORD_PUNCTUATION_RE = re.compile(r'[\s，。；;,.、：:（）()]')


def squeeze(text):
    """Text compared without spacing; the Greek mu and the micro sign are one letter (µ, U+00B5)."""
    return re.sub(r'\s+', '', str(text or '')).replace('\u03bc', '\u00b5')


def squeeze_words(text):
    """Text compared as words: without spacing and punctuation."""
    return WORD_PUNCTUATION_RE.sub('', squeeze(text))


def finite(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'JSON 重复字段: {key}')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f'JSON 不接受非有限常量: {value}')


def load_json(path):
    """Shared raw-input gate: ambiguity must not disappear before hashing."""
    with open(path, encoding='utf-8') as stream:
        return json.load(stream, object_pairs_hook=_unique_object,
                         parse_constant=_invalid_constant)


def bounded(value, positive=False):
    return (isinstance(value, dict) and finite(value.get('min'))
            and finite(value.get('max')) and value['min'] <= value['max']
            and (not positive or value['min'] > 0))


PLAN_SCHEMA_VERSION = 7  # 7 版起电路检查项只在网表有其机制时派（catalog.SUBJECT_REQUIRES），检查项带 requires，框架带 not_asked；检查项带 owner 与 check_key（电路检查项按 circuit_key），计划带 owners 所属表与 interfaces 接口（功能树）；5 版起检查项与框架带 circuit_type、question/function_id/aspect，计划带 functions


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='生成证据绑定指纹，不生成审查结论')
    parser.add_argument('db')
    parser.add_argument('--document', action='append', default=[])
    args = parser.parse_args()
    try:
        result = {'db_sha256': db_fingerprint(load_json(args.db))}
    except (OSError, ValueError) as error:
        parser.error(str(error))
    result['documents'] = {p: document_fingerprint(p) for p in args.document}
    print(json.dumps(result, ensure_ascii=False, indent=2))

# Format agreements every ring reads (SR self-check 5.8, user: 并进 contract): the review phases, a non-empty text,
# what locates a condition, the consequence classes and the SR rule fingerprint. They lived in the gate's modules and
# the plan and the row derivation imported them from there.
PHASES = ('design_iteration', 'schematic_freeze', 'prototype_verification')


def text(value):
    return isinstance(value, str) and bool(value.strip())


# A located condition names a place in its source a reader can open: a page, table, figure, section or chapter,
# a datasheet section title, a requirement or record id, a designator, or named nets/pins. "相关位号所有物理脚"
# and "## BIAS" locate nothing. Words are matched without case, ids with it.
LOCATOR_WORDS_RE = re.compile(
    r'(?<![a-z])pp?\.?\s*\d|第\s*\d+\s*[页节条章]'
    r'|\b(?:table|tab|fig(?:ure)?|section|sec|chapter|clause|note|eq(?:uation)?)\.?\s*[a-z]?\d'
    r'|[表图]\s*\d|§\s*\d'
    r'|电气特性|绝对最大|推荐工作|引脚说明|引脚定义|订货|功能框图|特性曲线|热阻|应用说明|典型应用|电气参数'
    r'|electrical characteristics|absolute maximum|recommended operating|pin description|pin assignment|ordering'
    r'|block diagram|typical (?:characteristics|application)|thermal'
    r'|(?:\bnets?\b|\bpins?\b|\bnodes?\b|网络|引脚|位号|节点)\s*[:：]?\s*/?[a-z][a-z0-9_/.-]+', re.I)
LOCATOR_IDS_RE = re.compile(r'\b[A-Z]{1,4}\d{1,4}\b|\b[A-Z]+(?:-[A-Z0-9]+)*-[A-Z]*\d[A-Z0-9]*\b')

# Consequence class -> potential level (verdicts-and-release.md 等级边界). A damage/hazard or
# core-link class drops to P1 only with a written independent exclusion of that path.
# impact_class_version 2 separates COMPONENT_DAMAGE (a part may be destroyed, nothing else
# follows: P1) from DAMAGE_OR_HAZARD, which then must name the hazard path it opens.
IMPACT_CLASSES = {'DAMAGE_OR_HAZARD': 'P0', 'CORE_LINK_LOSS': 'P0',
                  'COMPONENT_DAMAGE': 'P1',
                  'REQUIRED_FUNCTION': 'P1', 'PERFORMANCE_OR_LIFE': 'P1',
                  'LOCAL_OR_DATA': 'P2', 'OPTIMIZATION': 'P3'}
HAZARD_PATHS = ('FIRE', 'SHOCK', 'INSULATION', 'HAZARDOUS_ENERGY', 'PORT_OVERVOLTAGE', 'PROTECTION_LOSS')


def engine_identity(root=None):
    """The SR rule fingerprint the plan records and the gate compares (skill_identity.engineering_identity)."""
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    return engineering_identity(root)
