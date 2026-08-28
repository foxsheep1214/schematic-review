#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L3-WCA：稳压器反馈分压 / 监控分压 自动求解

用法:
    python3 solve_dividers.py db.json --vfb U1=0.815 U2=0.6 ...
    python3 solve_dividers.py db.json --net FB_NET --vfb 0.62      # 单点求解

为什么必须用脚本
----------------
高频错误模式第 15 条「**串联下臂被当成单电阻**」是分压算错的首要原因，
而它无法靠肉眼规避——一块板十几颗稳压器，只要有一颗的臂是两颗电阻串联，
手算就会得出完全错误的电压。真实案例：某 4G 模组供电按单颗 9.1K 下臂
算出 5.386V（模组 VBAT 上限 4.2V，看似要烧模组），追到底发现下臂是
9.1K + 4.7K 串联 = 13.8K，实际 3.829V —— 差点报出假致命项。

本脚本沿电阻串递归求和，正确处理任意长度的串联臂。

交叉校验
--------
求出的电压会与**轨名**对撞（VCC_3V3 -> 3.3V、VBAT_4G1_3V8 -> 3.8V）。
对不上先怀疑自己的工具，而不是先怀疑板子——本脚本开发时正是靠这个
校验抓出了一个递归终止 bug（入口网本身是电源轨时未立即终止，
把轨上其他电阻也算进了上臂）。
"""
import argparse
import io
import json
import re
import sys

GNDS = {'GND', 'PGND', 'AGND', 'DGND', 'EGND'}
RAIL_RE = re.compile(
    r'^(VCC|VBAT|VDD|VOUT|AVDD|DVDD|VIN|VBUS|3V3|5V|1V|2V|0V)', re.I)
FB_NAMES = ('FB', 'ADJ', 'VFB', 'FBX')


def r_kohm(value):
    """'4.7K/1%' -> 4.7 ; '0R/1%' -> 0.0 ; '2.49k' -> 2.49"""
    m = re.match(r'\s*([\d.]+)\s*([KkMmRr]?)', str(value))
    if not m:
        return None
    x = float(m.group(1))
    u = m.group(2).upper()
    return x * 1000 if u == 'M' else (x if u == 'K' else x / 1000.0)


def rail_hint(name):
    """从轨名推标称电压：VBAT_4G1_3V8 -> 3.8 ; VCC_3V3 -> 3.3 ; VDD_1V95 -> 1.95"""
    m = re.search(r'(\d+)V(\d*)', name or '')
    if not m:
        return None
    whole, frac = m.group(1), m.group(2)
    return float(f'{whole}.{frac}') if frac else float(whole)


class Solver:
    def __init__(self, db):
        self.nets = db['nets']
        self.parts = db['parts']
        self.pinname = db['pinname']
        self.pin2net = db['pin2net']
        self.page = db.get('ref2page', {})
        self._ends = {}

    def ends(self, ref):
        if ref not in self._ends:
            self._ends[ref] = sorted(
                {v for k, v in self.pin2net.items() if k.startswith(ref + '.')})
        return self._ends[ref]

    def walk(self, net, seen, acc, path, depth=0):
        """沿电阻串递归，返回 (终点, 累计kΩ, 路径)。终点为 'GND' 或电源轨名。"""
        if net in GNDS:
            return ('GND', acc, path)
        if RAIL_RE.match(net):
            return (net, acc, path)      # 入口即轨 -> 立即终止（此处曾有 bug）
        if depth > 6 or net in seen:
            return (None, acc, path)
        seen = seen | {net}
        for x in self.nets.get(net, []):
            ref = x.split('.')[0]
            if not ref.startswith('R'):
                continue
            v = self.parts.get(ref, {})
            if v.get('nc'):
                continue             # 未贴电阻不在通路上
            rv = r_kohm(v.get('value'))
            if rv is None:
                continue
            for e in self.ends(ref):
                if e == net:
                    continue
                t, a, p = self.walk(e, seen, acc + rv,
                                    path + [f'{ref}({rv}k)'], depth + 1)
                if t:
                    return (t, a, p)
        return (None, acc, path)

    def solve_net(self, fbnet):
        """给定反馈节点，解出 (上臂kΩ, 下臂kΩ, 上臂终点, 上臂路径, 下臂路径)"""
        up = lo = None
        for x in self.nets.get(fbnet, []):
            ref = x.split('.')[0]
            if not ref.startswith('R'):
                continue
            v = self.parts.get(ref, {})
            if v.get('nc'):
                continue
            rv = r_kohm(v.get('value'))
            if rv is None:
                continue
            for e in self.ends(ref):
                if e == fbnet:
                    continue
                t, a, p = self.walk(e, {fbnet}, rv, [f'{ref}({rv}k)'])
                if t == 'GND' and lo is None:
                    lo = (a, p)
                elif t and t != 'GND' and up is None:
                    up = (a, p, t)
        if not (up and lo):
            return None
        return {'r_up': up[0], 'r_lo': lo[0], 'src': up[2],
                'path_up': up[1], 'path_lo': lo[1]}

    def find_fb_nets(self):
        """自动找出所有带 FB/ADJ 引脚的器件及其反馈网"""
        out = []
        for node, pn in self.pinname.items():
            if pn in FB_NAMES:
                out.append((node.split('.')[0], self.pin2net.get(node)))
        return sorted(set(out))


def fmt_path(p):
    return ' + '.join(p) if len(p) > 1 else (p[0] if p else '-')


def main():
    ap = argparse.ArgumentParser(description='反馈/监控分压自动求解（含串联臂）')
    ap.add_argument('db')
    ap.add_argument('--vfb', nargs='*', default=[],
                    help='REF=电压，如 U1=0.815 U2=0.6；未列出的按 --default-vfb')
    ap.add_argument('--default-vfb', type=float, default=None,
                    help='未在 --vfb 中列出的器件使用的基准电压')
    ap.add_argument('--net', help='只解这一个反馈网（配合单个 --vfb 数值）')
    ap.add_argument('--tol', type=float, default=0.06,
                    help='与轨名标称值的允许偏差，默认 6%%')
    a = ap.parse_args()

    db = json.load(io.open(a.db, encoding='utf-8'))
    S = Solver(db)

    vfb = {}
    single = None
    for kv in a.vfb:
        if '=' in kv:
            k, v = kv.split('=', 1)
            vfb[k] = float(v)
        else:
            single = float(kv)

    if a.net:
        r = S.solve_net(a.net)
        if not r:
            sys.exit(f'[FATAL] {a.net} 上未找到完整的上/下臂')
        k = 1 + r['r_up'] / r['r_lo']
        print(f'  上臂 {r["r_up"]:.3f}k = {fmt_path(r["path_up"])}  -> {r["src"]}')
        print(f'  下臂 {r["r_lo"]:.3f}k = {fmt_path(r["path_lo"])}  -> GND')
        print(f'  系数 1+R1/R2 = {k:.4f}')
        if single:
            print(f'  Vout = {single} x {k:.4f} = {single * k:.3f} V')
        return

    rows = []
    for ref, fbnet in S.find_fb_nets():
        if not fbnet:
            continue
        r = S.solve_net(fbnet)
        if not r:
            print(f'  [跳过] {ref} 反馈网 {fbnet} 未解出完整上/下臂（可能为固定输出）')
            continue
        vref = vfb.get(ref, a.default_vfb)
        k = 1 + r['r_up'] / r['r_lo']
        v = vref * k if vref else None
        hint = rail_hint(r['src'])
        flag = ''
        if v is not None and hint:
            flag = 'OK' if abs(v - hint) / hint <= a.tol else '** 与轨名不符 **'
        rows.append((ref, r, k, vref, v, hint, flag))

    print(f'{"REF":8s}{"轨":22s}{"上臂k":>9s}{"下臂k":>9s}{"系数":>9s}'
          f'{"VFB":>7s}{"实算V":>9s}{"轨名":>8s}  校验')
    print('-' * 104)
    for ref, r, k, vref, v, hint, flag in rows:
        print(f'{ref:8s}{r["src"]:22s}{r["r_up"]:9.3f}{r["r_lo"]:9.3f}{k:9.4f}'
              f'{(f"{vref:.3f}" if vref else "-"):>7s}'
              f'{(f"{v:.3f}" if v else "-"):>9s}'
              f'{(f"{hint}" if hint else "-"):>8s}  {flag}')

    multi = [(ref, r) for ref, r, *_ in rows
             if len(r['path_up']) > 1 or len(r['path_lo']) > 1]
    if multi:
        print(f'\n  含串联臂的分压 {len(multi)} 处 —— 手算这些必错：')
        for ref, r in multi:
            print(f'    {ref}: 上臂={fmt_path(r["path_up"])} ／ '
                  f'下臂={fmt_path(r["path_lo"])}')

    bad = [x for x in rows if '不符' in x[6]]
    if bad:
        print(f'\n  [交叉校验] {len(bad)} 处实算值与轨名不符 —— '
              '先怀疑 VFB 取值或本脚本，再怀疑板子：')
        for ref, r, k, vref, v, hint, _ in bad:
            print(f'    {ref} {r["src"]}: 实算 {v:.3f}V vs 轨名暗示 {hint}V')


if __name__ == '__main__':
    main()
