"""The HTML copy of 审查报告.md: same text, pictures shown inline. Converts only what render_report writes
(headings, paragraphs, lists, tables, images, links, bold, code, <details>); no third-party package. Each error and
gap is a card, and its pictures (现状 / 改后) stand side by side (user 2026-10-27: 问题用图的形式来说明，这个要保留)."""

import html
import re

STYLE = """
:root{--fg:#1f1f1d;--muted:#5f5e5a;--bg:#fbfaf7;--line:#d3d1c7;--card:#f1efe8;--link:#185fa5}
@media (prefers-color-scheme: dark){:root{--fg:#e8e6df;--muted:#b4b2a9;--bg:#1e1e1c;--line:#444441;--card:#2c2c2a;--link:#85b7eb}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:960px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:26px}h2{font-size:21px;margin-top:2em;border-bottom:1px solid var(--line)}h3{font-size:17px;margin-top:1.6em}
table{border-collapse:collapse;display:block;overflow-x:auto;margin:12px 0}
th,td{border:1px solid var(--line);padding:4px 10px;text-align:left;vertical-align:top}th{background:var(--card)}
code{background:var(--card);padding:0 4px;border-radius:4px}a{color:var(--link)}
figure{margin:0}figure img{max-width:100%;border:1px solid var(--line);border-radius:6px;background:#fff}
figcaption{color:var(--muted);font-size:14px}
.figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin:12px 0}
.card{border:1px solid var(--line);border-radius:10px;padding:2px 16px 8px;margin:16px 0}.card h3{margin-top:.8em}
details{background:var(--card);border-radius:8px;padding:8px 14px;margin:12px 0}summary{cursor:pointer;color:var(--muted)}
"""

PASSTHROUGH = re.compile(r'^\s*</?(details|summary)\b.*$')
IMAGE = re.compile(r'^!\[([^\]]*)\]\(([^)]+)\)\s*$')
CAPTION = re.compile(r'^图：(.*)$')
CARD_SECTIONS = ('发现的错误', '待办')   # render_report's sections of error and gap cards
INLINE = re.compile(r'\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)')


def inline(text):
    out, pos = [], 0
    for m in INLINE.finditer(text):
        out.append(html.escape(text[pos:m.start()], quote=False))
        if m.group(1) is not None:
            out.append('<strong>%s</strong>' % inline(m.group(1)))
        elif m.group(2) is not None:
            out.append('<code>%s</code>' % html.escape(m.group(2), quote=False))
        else:
            out.append('<a href="%s">%s</a>' % (html.escape(m.group(4)), inline(m.group(3))))
        pos = m.end()
    out.append(html.escape(text[pos:], quote=False))
    return ''.join(out)


def cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def to_html(markdown):
    lines = markdown.splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith('# ')), '审查报告')
    body, i, section, card = [], 0, '', False

    def next_line(k):
        while k < len(lines) and not lines[k].strip():
            k += 1
        return k

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif PASSTHROUGH.match(line):
            body.append(line.strip()); i += 1
        elif re.match(r'^#{1,4} ', line):
            level = len(line) - len(line.lstrip('#'))
            name = line[level:].strip()
            if card and level <= 3:
                body.append('</section>'); card = False
            if level == 2:
                section = name
            elif level == 3 and section in CARD_SECTIONS:
                body.append('<section class="card">'); card = True
            body.append('<h%d>%s</h%d>' % (level, inline(name), level)); i += 1
        elif IMAGE.match(line):
            # Pictures in a row (only blank lines between) share one grid; a 图： line under one is its caption.
            figures = []
            while i < len(lines) and IMAGE.match(lines[i]):
                alt, src = IMAGE.match(lines[i]).groups()
                k = next_line(i + 1)
                caption = CAPTION.match(lines[k]) if k < len(lines) else None
                # a schematic crop side by side is small: the picture opens full size
                figures.append('<figure><a href="%s"><img src="%s" alt="%s"></a>%s</figure>' % (
                    html.escape(src), html.escape(src), html.escape(alt),
                    '<figcaption>%s</figcaption>' % inline(caption.group(1)) if caption else ''))
                i = next_line(k + 1) if caption else k
            body.append(figures[0] if len(figures) == 1 else '<div class="figs">\n%s\n</div>' % '\n'.join(figures))
        elif line.startswith('|') and i + 1 < len(lines) and re.match(r'^\|[\s:|-]+\|\s*$', lines[i + 1]):
            rows = ['<tr>%s</tr>' % ''.join('<th>%s</th>' % inline(c) for c in cells(line))]
            i += 2
            while i < len(lines) and lines[i].startswith('|'):
                rows.append('<tr>%s</tr>' % ''.join('<td>%s</td>' % inline(c) for c in cells(lines[i])))
                i += 1
            body.append('<table>\n%s\n</table>' % '\n'.join(rows))
        elif re.match(r'^(- |\d+\. )', line):
            tag = 'ul' if line.startswith('- ') else 'ol'
            marker = r'^- ' if tag == 'ul' else r'^\d+\. '
            items = []
            while i < len(lines) and re.match(marker, lines[i]):
                items.append('<li>%s</li>' % inline(re.sub(marker, '', lines[i]).strip()))
                i += 1
            body.append('<%s>\n%s\n</%s>' % (tag, '\n'.join(items), tag))
        else:
            # A line no other branch took starts a paragraph, so the loop always advances (a lone '|' line
            # that no separator row follows is text, not a table).
            para = [inline(line.strip())]
            i += 1
            while i < len(lines) and lines[i].strip() and not (
                    PASSTHROUGH.match(lines[i]) or re.match(r'^(#{1,4} |- |\d+\. |\|)', lines[i]) or IMAGE.match(lines[i])):
                para.append(inline(lines[i].strip()))
                i += 1
            body.append('<p>%s</p>' % '<br>\n'.join(para))
    if card:
        body.append('</section>')
    return ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n<main>\n%s\n</main>\n</body>\n</html>\n'
            % (html.escape(title), STYLE, '\n'.join(body)))
