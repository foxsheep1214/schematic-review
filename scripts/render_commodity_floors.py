#!/usr/bin/env python3
"""从知识框架的常规件最弱档.json 渲染最弱档数值表；解释、非数值行及 MLCC 介质注释仍人工维护。"""
import argparse
from fractions import Fraction
from pathlib import Path
import re

import guideline_criteria


def number(value):
    return '%g' % value


def render_doc(text, floors=None):
    floors = guideline_criteria.commodity_floors() if floors is None else floors
    packages = floors['chip_resistor']['packages']
    resistor = []
    for package, row in packages.items():
        power = str(Fraction(str(row['power_w_70c'])).limit_denominator(10000))
        resistor.append('| %s | %s W | %s V |' % (package, power, number(row['voltage_v'])))
    text, count = re.subn(r'(?m)^\| (?:0\d{3}|1\d{3}|2\d{3}) \| \S+ W \| \d+(?:\.\d+)? V \|(?:\n|$)', '', text)
    if count == 0:
        raise ValueError('missing resistor table')
    header = '| 封装 | 最弱档功率（70 ℃） | 最弱档最高工作电压 |\n|---|---|---|\n'
    if text.count(header) != 1:
        raise ValueError('missing resistor header')
    text = text.replace(header, header + '\n'.join(resistor) + '\n')
    # Preserve human dielectric annotations by part number; numeric columns and part identity come from JSON.
    pattern = r'(?m)^\| 0\d{3} \| \d+(?:\.\d+)? [pnµum]?F \| \d+(?:\.\d+)? V \| ([^（\n]+)([^\n]*) \|(?:\n|$)'
    annotations = dict(re.findall(pattern, text))
    text, count = re.subn(pattern, '', text)
    if count == 0:
        raise ValueError('missing MLCC table')
    mlcc = []
    for row in floors['mlcc_orderable']['rows']:
        scale, unit = (1e9, 'nF') if row['max_f'] < 1e-6 else (1e6, 'µF')
        mlcc.append('| %s | %s %s | %s V | %s%s |' % (
            row['package'], number(row['max_f'] * scale), unit, number(row['voltage_v']),
            row['part'], annotations.get(row['part'], '')))
    header = '| MLCC 可订购档 | 最大容值 | 耐压 | 依据料号（分销商在售，核对日期 %s） |\n|---|---|---|---|\n' % floors['mlcc_orderable']['checked']
    # The date is data too; recognize the existing date without using it as the output value.
    text, count = re.subn(r'\| MLCC 可订购档 \| 最大容值 \| 耐压 \| 依据料号（分销商在售，核对日期 [^）]+） \|\n\|---\|---\|---\|---\|\n',
                          lambda _: header + '\n'.join(mlcc) + '\n', text)
    if count != 1:
        raise ValueError('missing MLCC header')
    contacts = {r['category']: r for r in floors['contacts']['rows']}
    seen = set()
    def contact(match):
        category = match[1]
        if category not in contacts:
            return match[0]  # nonnumeric rows remain human explanations
        row = contacts[category]
        seen.add(category)
        if row['current_a'] < 1:
            rating = '%s mA / %s VDC（阻性）' % (number(row['current_a'] * 1000), number(row['voltage_v']))
        else:
            current = str(float(row['current_a'])) if category.startswith('JST ') and row['current_a'] == 1 else number(row['current_a'])
            rating = current + ' A / 触点'
        return '| %s | %s | %s |' % (category, rating, row['basis'])
    text = re.sub(r'(?m)^\| ([^|\n]+?) \| [^\n]+ \|$', contact, text)
    if seen != set(contacts):
        raise ValueError('contact categories need explicit table positions')
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    text = args.document.read_text(encoding='utf-8')
    rendered = render_doc(text)
    if args.check:
        if text != rendered:
            raise SystemExit('最弱档表与知识框架的常规件最弱档.json 不一致')
        print('PASS')
    else:
        args.document.write_text(rendered, encoding='utf-8')


if __name__ == '__main__':
    main()
