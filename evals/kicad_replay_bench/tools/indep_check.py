"""Independent answers from raw KiCad XML (no SR imports): counts, missing names, decoupling groups."""
import json, re, sys, xml.etree.ElementTree as ET
x = ET.parse(sys.argv[1]).getroot(); obs = json.load(open(sys.argv[2]))['observed'][sys.argv[3]]
comps = {c.get('ref'): c for c in x.findall('./components/comp')}
libpins = {}
for lp in x.findall('./libparts/libpart'):
    libpins[(lp.get('lib'), lp.get('part'))] = {p.get('num'): p.get('name') or '' for p in lp.findall('./pins/pin')}
nets = x.findall('./nets/net')
node_net, node_type, node_fn = {}, {}, {}
for n in nets:
    for nd in n.findall('node'):
        k = nd.get('ref') + '.' + nd.get('pin'); node_net[k] = n.get('name'); node_type[k] = nd.get('pintype'); node_fn[k] = nd.get('pinfunction') or ''
def libname(k):
    ref, pin = k.split('.', 1); src = comps[ref].find('libsource')
    return libpins.get((src.get('lib'), src.get('part')), {}).get(pin, '')
missing = sorted(k for k in node_net if node_type[k] not in ('passive', 'no_connect') and not node_fn[k].strip() and libname(k) in ('', '~'))
GND = lambda net: bool(re.match(r'^/?(.*/)?[A-Z]{0,2}GND', net or '', re.I))
RET_PIN = re.compile(r'^([AP]?GND\d*|[AD]?VSS\d*)$', re.I)
groups = {}
for ref in comps:
    if not re.match(r'^(U|Reg)\d', ref): continue
    pins = [k for k in node_net if k.split('.')[0] == ref]
    name = lambda k: (node_fn[k] or libname(k)).split('_')[0]
    rets = sorted({node_net[k] for k in pins if RET_PIN.match(name(k)) or GND(node_net[k])})
    for k in pins:
        if node_type[k] in ('power_in', 'power_out') and not GND(node_net[k]) and not RET_PIN.match(name(k)):
            net = node_net[k]
            caps = sorted(c for c in comps if c.startswith('C') and len(rets) == 1 and
                          sorted(node_net.get(c + '.' + p) for p in ('1', '2')) == sorted([net, rets[0]]))
            groups['candidate:%s:%s' % (ref, net)] = {'returns': rets, 'caps': caps}
print('parts', len(comps), obs['parse.parts'], '| nets', len(nets), obs['parse.nets'], '| missing', missing, obs['parse.missing_functional_pins'])
og = {k.split('/', 1)[1]: v for k, v in obs['decoupling.group_gaps'].items()}
print('group keys equal:', set(groups) == set(og), sorted(set(groups) ^ set(og)))
bad = 0
for g, v in sorted(groups.items()):
    gaps = og.get(g, [])
    pop = sorted(x.split(':', 1)[1] for x in gaps if x.startswith('population:C'))
    need = 'need-one-explicit-return-net' in gaps
    ok = (need == (len(v['returns']) != 1)) and (gaps and any(x.startswith('population:') for x in gaps) and pop == v['caps'] or not any(x.startswith('population:') for x in gaps))
    if not ok: bad += 1; print('  MISMATCH', g, v, gaps)
print('groups checked', len(groups), 'mismatches', bad)
