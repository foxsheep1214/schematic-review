"""Independent geometric connectivity from KiCad 8+ schematics, compared with a KiCad XML netlist.
Usage: geo_netlist.py <root.kicad_sch> <export.xml>"""
import math, os, re, sys, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(__file__))
from conn_compare import parse, kids, val

class UF(dict):
    def find(self, a):
        self.setdefault(a, a)
        while self[a] != a:
            self[a] = self[self[a]]; a = self[a]
        return a
    def union(self, a, b):
        self[self.find(a)] = self.find(b)

uf = UF()
P = lambda x, y: (round(x, 2), round(y, 2))

def on_seg(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    if abs((x2-x1)*(y-y1) - (y2-y1)*(x-x1)) > 1e-3: return False
    return min(x1,x2)-1e-3 <= x <= max(x1,x2)+1e-3 and min(y1,y2)-1e-3 <= y <= max(y1,y2)+1e-3

def libpins(root):
    out = {}
    for ls in kids(kids(root, 'lib_symbols')[0], 'symbol'):
        pins, power = [], any(isinstance(c, list) and c and c[0] == 'power' for c in ls[1:])
        def walk(n, unit):
            for c in n[1:]:
                if isinstance(c, list) and c and c[0] == 'symbol':
                    m = re.search(r'_(\d+)_(\d+)$', c[1]); walk(c, int(m.group(1)) if m else 0)
                elif isinstance(c, list) and c and c[0] == 'pin':
                    at = val(c, 'at'); pins.append((unit, val(c, 'number')[0], float(at[0]), float(at[1]), c[1]))
        walk(ls, 0)
        out[ls[1]] = (pins, power)
    return out

pin_nodes = {}   # (ref, pin) -> uf key
def sheet(path, inst, base):
    root = parse(open(path, encoding='utf-8').read())
    lp = libpins(root)
    pts, segs = [], []
    for w in kids(root, 'wire'):
        xy = [P(float(p[1]), float(p[2])) for p in kids(kids(w, 'pts')[0], 'xy')]
        segs.append((xy[0], xy[1])); uf.union((inst, xy[0]), (inst, xy[1]))
    def attach(p):
        key = (inst, p); uf.find(key)
        for a, b in segs:
            if on_seg(p, a, b): uf.union(key, (inst, a))
        return key
    for a, b in segs:   # wire endpoints on other wires
        attach(a); attach(b)
    for name, scope in (('label', 'L'), ('global_label', 'G'), ('hierarchical_label', 'H')):
        for l in kids(root, name):
            at = val(l, 'at'); k = attach(P(float(at[0]), float(at[1])))
            tag = ('G', l[1]) if scope == 'G' else ((inst, 'H', l[1]) if scope == 'H' else (inst, 'L', l[1]))
            uf.union(k, tag)
    for sym in kids(root, 'symbol'):
        props = {p[1]: p[2] for p in kids(sym, 'property')}
        lib = val(sym, 'lib_id')[0]; pins, power = lp[lib]
        at = val(sym, 'at'); x0, y0, rot = float(at[0]), float(at[1]), float(at[2] if len(at) > 2 else 0)
        mirror = (val(sym, 'mirror') or [None])[0]; unit = int((val(sym, 'unit') or ['1'])[0])
        ref = props['Reference']
        for inst_list in kids(sym, 'instances'):
            for proj in kids(inst_list, 'project'):
                for pth in kids(proj, 'path'):
                    if pth[1] == base: ref = val(pth, 'reference')[0]
        for u, num, px, py, ptype in pins:
            if u not in (0, unit): continue
            x, y = px, -py
            if mirror == 'x': y = -y
            if mirror == 'y': x = -x
            t = math.radians(-rot); c, s = round(math.cos(t)), round(math.sin(t))
            k = attach(P(x0 + x*c - y*s, y0 + x*s + y*c))
            if power and ptype == 'power_in': uf.union(k, ('G', props['Value']))
            elif not ref.startswith('#'): pin_nodes[(ref, num)] = k; uf.find(k)
    for sh in kids(root, 'sheet'):
        props = {p[1]: p[2] for p in kids(sh, 'property')}
        child = os.path.join(os.path.dirname(path), props.get('Sheetfile') or props.get('Sheet file'))
        cuuid = val(sh, 'uuid')[0]; cinst = inst + '/' + cuuid
        for p in kids(sh, 'pin'):
            at = val(p, 'at'); k = attach(P(float(at[0]), float(at[1])))
            uf.union(k, (cinst, 'H', p[1]))
        sheet(child, cinst, base + '/' + cuuid)

rootfile = sys.argv[1]
r = parse(open(rootfile, encoding='utf-8').read())
sheet(rootfile, '', '/' + val(r, 'uuid')[0])
geo = {}
for node, k in pin_nodes.items():
    geo.setdefault(uf.find(k), set()).add(node)
geo = {frozenset(v) for v in geo.values() if len(v) > 1}
x = ET.parse(sys.argv[2]).getroot()
exp = {frozenset((n.get('ref'), n.get('pin')) for n in net.findall('node')) for net in x.findall('./nets/net')}
exp = {e for e in exp if len(e) > 1}
print('geometric nets', len(geo), 'exported nets', len(exp), 'identical' if geo == exp else 'DIFFER')
for e in sorted(map(sorted, geo - exp))[:5]: print('  geo-only', e)
for e in sorted(map(sorted, exp - geo))[:5]: print('  xml-only', e)
sys.exit(geo != exp)
