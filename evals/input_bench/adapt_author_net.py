#!/usr/bin/env python3
"""Read-only syntax conversion of KiCad author .net to XML for import tests.

Preserves names, values and nodes. Does not reconstruct NC markers, fix library
pin types, qualify a schematic or claim native current KiCad acceptance.
"""
import argparse
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

TOKEN = re.compile(r'\s+|;[^\n]*|\(|\)|"(?:\\.|[^"\\])*"|[^\s();"]+')
ATTRS = {'comp': {'ref'}, 'net': {'code', 'name'}, 'node': {'ref', 'pin'},
         'libpart': {'lib', 'part'}, 'pin': {'num', 'name', 'type'},
         'libsource': {'lib', 'part'}, 'sheetpath': {'names', 'tstamps'},
         'sheet': {'number', 'name', 'tstamps'}, 'field': {'name'},
         'comment': {'number'}}


def read(text):
    stack, root, end = [], None, 0
    for match in TOKEN.finditer(text):
        if match.start() != end:
            raise ValueError('Invalid author S-expression')
        end = match.end(); token = match.group()
        if token.isspace() or token.startswith(';'):
            continue
        if token == '(':
            node = []
            if stack: stack[-1].append(node)
            elif root is not None: raise ValueError('Multiple roots')
            else: root = node
            stack.append(node)
        elif token == ')':
            if not stack: raise ValueError('Unexpected close')
            stack.pop()
        else:
            if not stack: raise ValueError('Atom outside root')
            if token.startswith('"'):
                token = re.sub(r'\\([\\"nr])', lambda m: {'n': '\n', 'r': '\r'}.get(m[1], m[1]), token[1:-1])
            stack[-1].append(token)
    if stack or root is None or text[end:].strip():
        raise ValueError('Incomplete author netlist')
    return root


def element(node):
    if not node or not isinstance(node[0], str): raise ValueError('Missing XML element name')
    result = ET.Element(node[0]); attributes = ATTRS.get(node[0], set())
    for item in node[1:]:
        if isinstance(item, list):
            if item and item[0] in attributes:
                if len(item) != 2 or item[0] in result.attrib: raise ValueError('Malformed/duplicate attribute')
                result.set(item[0], item[1])
            else: result.append(element(item))
        else:
            if result.text is not None: raise ValueError('Multiple text values')
            result.text = item
    return result


def adapt(raw):
    tree = read(raw.decode('utf-8'))
    if tree[0] != 'export': raise ValueError('Not an author KiCad export')
    root = element(tree)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('input', type=Path); cli.add_argument('--expected-sha256', required=True)
    cli.add_argument('--out', type=Path, required=True); args = cli.parse_args()
    raw = args.input.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.expected_sha256: cli.exit(2, 'Author input hash mismatch\n')
    with args.out.open('xb') as handle: handle.write(adapt(raw))
