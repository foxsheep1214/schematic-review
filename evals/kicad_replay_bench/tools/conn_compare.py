"""Compare connectivity-relevant content of two KiCad schematic files (any s-expr version)."""
import re, sys

def parse(text):
    tok = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack, cur = [], []
    for t in tok:
        if t == '(':
            stack.append(cur); cur = []
        elif t == ')':
            node, cur = cur, stack.pop(); cur.append(node)
        else:
            cur.append(t.strip('"') if t.startswith('"') else t)
    return cur[0]

def kids(n, name):
    return [c for c in n[1:] if isinstance(c, list) and c and c[0] == name]

def val(n, name, default=None):
    k = kids(n, name)
    return k[0][1:] if k else default

def num(xs):
    return tuple(round(float(x), 4) for x in xs)

def facts(root):
    out = set()
    for w in kids(root, 'wire') + kids(root, 'bus'):
        out.add((w[0], tuple(sorted(num(p[1:3]) for p in kids(kids(w, 'pts')[0], 'xy')))))
    for name in ('junction', 'no_connect', 'bus_entry'):
        for j in kids(root, name):
            out.add((name, num(val(j, 'at')[:2])))
    for name in ('label', 'global_label', 'hierarchical_label'):
        for l in kids(root, name):
            out.add((name, l[1], num(val(l, 'at')[:3])))
    for sym in kids(root, 'symbol'):
        props = {p[1]: p[2] for p in kids(sym, 'property')}
        mirror = val(sym, 'mirror')
        out.add(('symbol', val(sym, 'lib_id')[0], props.get('Reference'), props.get('Value'),
                 num(val(sym, 'at')[:3]), tuple(mirror or ()), tuple(val(sym, 'unit') or ('1',)),
                 tuple(val(sym, 'dnp') or ('no',)), tuple(val(sym, 'in_bom') or ('yes',))))
    for sh in kids(root, 'sheet'):
        props = {p[1]: p[2] for p in kids(sh, 'property')}
        out.add(('sheet', props.get('Sheetfile') or props.get('Sheet file'), num(val(sh, 'at')[:2])))
        for p in kids(sh, 'pin'):
            out.add(('sheetpin', p[1], p[2], num(val(p, 'at')[:2])))
    libs = kids(root, 'lib_symbols')
    for ls in (kids(libs[0], 'symbol') if libs else []):
        def walk(n, unit):
            for c in n[1:]:
                if isinstance(c, list) and c and c[0] == 'symbol':
                    walk(c, c[1])
                elif isinstance(c, list) and c and c[0] == 'pin':
                    numb = val(c, 'number')[0]; name = val(c, 'name')[0]
                    out.add(('libpin', ls[1], unit, numb, name, c[1], num(val(c, 'at')[:3]), num(val(c, 'length') or ['0'])))
        walk(ls, ls[1])
        pw = [c for c in ls[1:] if isinstance(c, list) and c and c[0] == 'power']
        if pw: out.add(('power', ls[1]))
    return out

if __name__ == '__main__':
    a, b = (facts(parse(open(p, encoding='utf-8').read())) for p in sys.argv[1:3])
    print(sys.argv[1].rsplit('/', 1)[-1], 'facts', len(a), 'only-orig', len(a - b), 'only-down', len(b - a))
    for x in sorted(map(str, a - b))[:8]: print('  -', x)
    for x in sorted(map(str, b - a))[:8]: print('  +', x)
    sys.exit(1 if a != b else 0)
