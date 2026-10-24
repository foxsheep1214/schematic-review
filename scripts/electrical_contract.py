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


PLAN_SCHEMA_VERSION = 7  # 7 版起电路行只在网表有其机制时派（catalog.SUBJECT_REQUIRES），行带 requires，框架带 not_asked；行带 owner 与 check_key（电路行按 circuit_key），计划带 owners 所属表与 interfaces 接口（功能树）；5 版起行与框架带 circuit_type、question/function_id/aspect，计划带 functions


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
