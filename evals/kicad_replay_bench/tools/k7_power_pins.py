"""KiCad 7 joins power symbols by hidden pin name; KiCad 8+ by Value. Name each power
lib symbol's pin after the symbol (as KiCad 7's own power library does)."""
import re, sys
path = sys.argv[1]
s = open(path, encoding='utf-8').read()
values = {}
for m in re.finditer(r'\(symbol\s*\(lib_id "(power:[^"]+)"', s):
    v = re.search(r'\(property "Value" "([^"]*)"', s[m.end():m.end() + 2000]).group(1)
    values.setdefault(m.group(1).split(':', 1)[1], set()).add(v)
assert all(len(v) == 1 for v in values.values()), values  # one lib symbol cannot carry two K7 net names
out, pos, changed = [], 0, []
for m in re.finditer(r'\(symbol "power:([^"]+)"\s*\(power\)', s):
    if m.start() < pos:
        continue
    depth, i = 0, m.start()
    while True:
        c = s[i]
        depth += c == '('; depth -= c == ')'
        i += 1
        if depth == 0:
            break
    block = s[m.start():i]
    name = m.group(1)
    if name != 'PWR_FLAG':
        block, n = re.subn(r'(\(pin power_in \S+\s*\(at [^)]*\)\s*\(length [^)]*\)(?:\s*hide)?\s*\(name )"~"',
                           lambda x: x.group(1) + '"%s"' % next(iter(values[name])), block)
        changed.append((name, next(iter(values[name])), n))
    out.append(s[pos:m.start()] + block); pos = i
out.append(s[pos:])
open(path, 'w', encoding='utf-8').write(''.join(out))
print(changed)
