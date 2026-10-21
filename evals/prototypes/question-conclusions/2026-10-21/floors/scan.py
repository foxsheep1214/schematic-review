"""Rows with min/typ/max or typ/max numbers in datasheet text: spread of the guarantee around the typical, by quantity."""
import re, sys, glob, json, collections
CLASSES = [
    ('recovery_charge', r'\bQrr\b|recovery charge|\bQRR\b'),
    ('gate_charge', r'gate charge|\bQg\b|Qgd|Qgs|Q\s?G\b'),
    ('capacitance', r'capacitance|\bCiss\b|\bCoss\b|\bCrss\b|\bCd\b'),
    ('on_resistance', r'on.?state resistance|RDS\(on\)|on.?resistance|rdif|dynamic resistance'),
    ('threshold_voltage', r'threshold|VGS\(th\)|plateau|VBE|turn.?on voltage|turn.?off voltage'),
    ('forward_voltage', r'forward voltage|\bVF\b|VFM|saturation voltage|VCE\(?sat'),
    ('leakage_current', r'leakage|reverse current|\bIR\b|\bIRM\b|ICEO|IDSS|IGSS|dark current'),
    ('supply_current', r'supply current|operating current|quiescent|\bICC\d?\b|\bIQ\b|bias current|standby current'),
    ('time', r'time|delay|\btd\b|\btr\b|\btf\b'),
]
num = r'(-?\d+(?:\.\d+)?)'
rows = collections.defaultdict(list)
for path in glob.glob(sys.argv[1] + '/*.txt'):
    for line in open(path, errors='replace'):
        if 'USB_' in path or 'IEC' in path or 'GB' in path:
            continue
        m = re.search(r'(?:\s|^)' + num + r'\s{2,}' + num + r'\s{2,}' + num + r'\s+(\S+)\s*(?:\S.*)?$', line)
        if m:
            lo, ty, hi = map(float, m.groups()[:3])
            if not (lo < ty < hi) or ty <= 0:
                continue
        else:
            m = re.search(r'[-–]\s{2,}' + num + r'\s{2,}' + num + r'\s+\S+', line)
            if not m:
                continue
            lo, ty, hi = None, float(m.group(1)), float(m.group(2))
            if not (0 < ty < hi):
                continue
        for cls, pat in CLASSES:
            if re.search(pat, line, re.I):
                rows[cls].append((path.split('/')[-1][:22], ty, hi, lo, line.strip()[:90]))
                break
out = {}
for cls, r in rows.items():
    up = sorted(h / t for _, t, h, _, _ in r)
    down = sorted(t / l for _, t, _, l, _ in r if l and l > 0)
    q = lambda v, p: v[min(len(v) - 1, int(p * len(v)))] if v else None
    out[cls] = {'n': len(r), 'max/typ median': q(up, .5), 'p90': q(up, .9), 'worst': up[-1],
                'typ/min median': q(down, .5), 'typ/min worst': down[-1] if down else None}
print(json.dumps(out, indent=1))
for cls in ('gate_charge', 'capacitance', 'on_resistance', 'supply_current', 'forward_voltage'):
    for r in sorted(rows[cls], key=lambda r: -r[2] / r[1])[:4]:
        print(cls, r)
