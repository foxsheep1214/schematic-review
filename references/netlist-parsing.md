# 网表解析规范（Cadence allegro 三件套 + 其他 EDA 适配）

## 一、输入文件

| 文件 | 作用 | 获取方式 |
|---|---|---|
| 原理图 PDF | 页面结构、图形复核 | EDA 导出 |
| `pstxnet.dat` | 展开网表（核心数据源） | Cadence PSTWRITER 导出 allegro 网表 |
| `pstxprt.dat` | 器件实例清单（位号→原语） | 同上 |
| `pstchip.dat` | 原语库（型号/封装/参数值/引脚映射） | 同上 |

非 Cadence 工具链（PADS/Altium/KiCad）提供等效网表导出即可，解析规则按格式改写；方法论其余部分不变。

## 二、目标索引

- `parts`：位号 → {part（型号）, jedec（封装）, value（值）}
- `nets`：网络名 → [位号.引脚号, …]
- `pin2net`：位号.引脚号 → 网络名
- `pinname`：Uxxx.2A2 → "VCCIO2_VCC"（引脚功能名，藏在 `CDS_PINID` 字段，是识别 SoC 电源球/信号球身份的关键）

## 三、格式要点

- `pstxnet.dat`：`NET_NAME` 行独占一行，下一行是带引号的网络名；随后 `NODE_NAME\t<refdes> <pin>` 逐节点；`CDS_PINID` 给出引脚功能名。
- `pstxprt.dat`：` <refdes> '<primitive>':;` 每实例一行；VALUE 带 `/NC` 后缀 = 该实例不贴（实例级 NC 信息只在这里，库不含）。
- `pstchip.dat`：`primitive '<name>'; ... end_primitive;` 块内含 pin 名→PIN_NUMBER 映射（符号审计用）、PART_NAME/JEDEC_TYPE/VALUE。

## 四、参考实现（Python）

```python
import re

def parse_allegro(dirpath):
    nets, pinname = {}, {}
    cur, last = None, None
    for line in open(f'{dirpath}/pstxnet.dat', encoding='utf-8', errors='replace'):
        line = line.rstrip('\n')
        if line.startswith('NET_NAME'):
            cur = 'EXPECT'; continue
        if cur == 'EXPECT' and line.startswith("'"):
            cur = line.strip().strip("'"); nets[cur] = []; continue
        m = re.match(r"^NODE_NAME\t(\S+)\s+(\S+)", line)
        if m and cur and cur != 'EXPECT':
            last = f"{m.group(1)}.{m.group(2)}"
            nets[cur].append(last); continue
        mm = re.search(r"'\\([^\\]+)\\':CDS_PINID", line)
        if mm and last:
            pinname[last] = mm.group(1)

    xprt = open(f'{dirpath}/pstxprt.dat', encoding='utf-8', errors='replace').read()
    ref2prim = dict(re.findall(r"^ ([A-Za-z0-9]+) '(.*?)':;", xprt, re.M))

    chip = open(f'{dirpath}/pstchip.dat', encoding='utf-8', errors='replace').read()
    prim = {}
    for m in re.finditer(r"primitive '(.*?)';(.*?)end_primitive;", chip, re.S):
        body = m.group(2)
        g = lambda k: (re.search(k + r"='(.*?)'", body).group(1)
                       if re.search(k + r"='(.*?)'", body) else '')
        prim[m.group(1)] = dict(part=g('PART_NAME'), jedec=g('JEDEC_TYPE'), value=g('VALUE'))
    parts = {r: prim.get(p, {}) for r, p in ref2prim.items()}

    pin2net = {}
    for n, nds in nets.items():
        for x in nds:
            pin2net[x] = n
    return dict(nets=nets, parts=parts, pinname=pinname, pin2net=pin2net)
```

简化版（只取 NET/NODE，够大多数查询用）：

```python
import re
lines = open("allegro/pstxnet.dat", errors="ignore").read().splitlines()
nets, cur, i = {}, None, 0
while i < len(lines):
    if lines[i].strip() == "NET_NAME":
        cur = re.match(r"\s*'([^']+)'", lines[i+1]).group(1)
        nets[cur] = []; i += 2; continue
    m = re.match(r"NODE_NAME\s+(\S+)\s+(\S+)", lines[i])
    if m and cur: nets[cur].append((m.group(1), m.group(2)))
    i += 1
# 用法：按 ref 反查所在网络；按网络列出全部节点；追踪分压链路时沿节点逐跳展开
```

符号审计（库符号引脚映射提取）：从 pstchip.dat 目标 primitive 块中取 `'<PINNAME>': PIN_NUMBER='(<num>)'`，与官方 datasheet 引脚表逐脚比对。

## 五、PDF 处理

- `pdftotext -layout sch.pdf out.txt`，按 `\f` 换页符分页；每页抓 `File:` 字段得页面标题 → 实际页面清单（目录页常过期，不可信）。
- 单页渲染读图：`pdftoppm -png -r 150 -f N -l N sch.pdf page`（引脚图/表格细节用 `-r 200` 以上并裁剪局部）。
- 扫描件 datasheet（无文本层）必须渲染目检；文本层表格错乱（pdftotext 拆散行列）时同样以渲染图为准。
- 比对 PDF 生成时间与网表导出时间，防止拿旧图审新版。

## 六、其他 EDA 适配

- KiCad：`.kicad_sch` 本身即文本（S 表达式），可直接解析；或用 `kicad-cli sch export netlist`。
- Altium：导出 EDIF/Protel 网表，按 `(` 分组解析。
- PADS：ASCII 网表 `*SIGNAL*` 段。
- 只要能得到 {nets, parts, pin2net} 三个索引，L0~L6 全部流程原样适用。
