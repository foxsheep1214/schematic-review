# 电路原理图审查方法论（Netlist-Driven Schematic Review Methodology）

> 版本 V1.4（文件名为兼容既有引用保留） | 适用范围：以结构化网表为主数据源的
> **原理图准出审查**；结论只表示可冻结并进入 PCB Layout，不表示整板可投板。
> 本方法论由多个真实工程项目的多轮审查闭环沉淀，所有规则均有实证出处。

---

## 第 0 章 总览：方法论的骨架

### 0.1 核心思想

原理图的电气本质是**网络表**（netlist），图形只是它的可视化。审查不依赖 EDA 软件，而是把 Cadence 导出的文本网表解析成可查询的结构化数据，然后分两层执行：

- **AC0 Automated Check（自动检查）**：先发现检查适用性并生成逐项计划，再用脚本执行机械、无歧义、可穷举的规则。解决**范围与覆盖率**——数百个网络、数百个电源球一个不漏。
- **ER1–ER7 Expert Review（专家审查）**（按执行序）：datasheet 核实、供电建图、链路追踪、最坏情况分析、平台原理图规则、图形复核、器件身份与封装一致性。解决**正确性与风险**。

### 0.2 审查流程总图

**检查标识中的数字即执行顺序。** AC0 是唯一的自动检查层，ER1–ER7 是需要工程判断的专家审查层。流程步骤（0～10）、检查标识（AC0/ER1–ER7）和规则身份（Rule-NN）彼此独立。

```
0.  意图对齐（设计意图问卷）
1.  数据解析（三件套 → 结构化索引）
2.  AC0 适用性发现 + Lint 冷跑（生成逐项计划，再做纯网表规则全量扫描）
3.  ER1 datasheet 核实 —— Abs Max / 强制条款 / 公式常量 / 引脚语义
    └ 回补 AC0 热跑（Rule-08 / Rule-09 / Rule-12 / Rule-14 / Rule-16）
4.  ER2 供电系统审计（建电源树 = 后续一切的地图）
5.  ER3 关键链路逐条追踪（在图上走路径）
6.  ER4 参数与边界条件验算（WCA）
7.  ER5 平台原理图规则扫描
8.  ER6 图形化系统目检
9.  ER7 器件身份与封装一致性
10. 输出分级报告 + 修复-复验闭环

贯穿（不排队）：文本层不可靠时立即渲染目检
```

**顺序依据**：先有 datasheet 才谈得上"违反"（ER1 供给 Rule-16/ER5 的判定依据、
供给 ER4 的公式常量）；先有电源树才有地图可走链路（ER2 → ER3）；
先走通链路才知道该算哪些点（ER3 → ER4）。

### 0.2.1 检查标识迁移对照

早期版本把「分类」与「顺序」混为一谈，导致 datasheet 核实排在最后、
读图排在第 8 步，而两者实际都是前置或贯穿项。V1.1 先完成执行顺序重排；
V1.2 再把自动检查与专家审查分别命名为 AC（Automated Check）和 ER（Expert Review）：

| 早期职责/层号 | V1.1 层号 | V1.2 现行标识 | 变化 |
|---|---|---|---|
| L0 自动 Lint | **L0** | **AC0** | 明确为 Automated Check，按输入依赖分冷跑/冷跑·参数化/热跑三档 |
| L6 前半 datasheet 核实 | **L1** | **ER1** | 提到最前，作为一切判断的证据前置 |
| L2 供电审计 | **L2** | **ER2** | 顺序不变，归入 Expert Review |
| L1 链路追踪 | **L3** | **ER3** | 后移，先建电源树再走路径 |
| L3 参数验算 | **L4** | **ER4** | 顺延，归入 Expert Review |
| L4 平台规则 | **L5** | **ER5** | 顺延，归入 Expert Review |
| L5 后半 系统目检 | **L6** | **ER6** | 拆分为独立专家审查模块 |
| L5 前半 按需渲染 | **贯穿** | **贯穿** | 不再排队 |
| L6 后半 器件核实 | **L7** | **ER7** | V1.3 收窄为器件身份与封装一致性 |

V1.1 报告可直接按 `L0 → AC0`、`L1 → ER1` …… `L7 → ER7` 换算。一个迁移版本内允许并列写成 `AC0（原 L0）`、`ER1（原 L1）`；新报告只使用 AC0/ER1–ER7。

### 0.2.2 三个编号体系解耦

三个编号体系分别表达不同含义，不互相嵌套：

- **步骤 0～10**：工作流位置；例如 AC0 位于第 2 步，并不等于流程第 0 步。
- **AC0/ER1–ER7**：检查模块与执行顺序；AC 表示 Automated Check，ER 表示 Expert Review。
- **Rule-01～Rule-20**：规则身份；Rule-11 在 ER2，Rule-17 在改版 Diff，其他规则按输入依赖运行。

Rule-08/09/12/14/16 虽由 AC0 热跑执行，却需要 ER1 提供 datasheet 结论；这正是规则身份不能与检查模块绑定的原因。

### 0.3 置信度分级（所有结论必须标注）

| 级别 | 含义 | 处置 |
|---|---|---|
| **A 网表实证** | 由网表数据直接证明（如网络断裂、参数不符） | 可直接整改 |
| **B datasheet 已核** | 经官方 datasheet/规范核实（如引脚耐压、公式） | 可直接整改 |
| **C 证据不足** | 来源未核实或可靠性不足 | 只写入 `evidence_confidence`，**严禁臆测** |

> 教训（真实案例）：某浪涌器件仅凭库符号名即判定为普通 TVS 并给出替代型号，后被原厂规格书证伪（其为 MOSFET 结构低钳位器件，常规 TVS 无法替代）。规则：**器件类别必须 ≥2 个独立证据源才允许定级为 A/B。**

> **C 级证据隔离（全自动流程强制）**：证据置信度 C 不得作为推导 A/B 级证据结论的依据。信息补齐前，依赖它的所有下游证据置信度一并保持 C；对应适用检查项的结果为 `INSUFFICIENT`，不得被逐级洗白成 PASS。全流程无人在场时，这是防止 agent 用臆测填补缺口的结构性约束。

报告必须分开记录 `review_result` 与 `evidence_confidence`。材料不足统一写
`review_result=INSUFFICIENT`；A/B/C 只属于证据置信度，不再存在“状态 C”。

### 0.4 原理图准出边界与状态

每个检查项独立落到 PASS / FAIL / INSUFFICIENT / NA；NA 只表示有依据证明不适用。
HANDOFF 是独立下游动作，不是第五种结果，可与 PASS/FAIL/INSUFFICIENT 并存；它用于
阻抗、布局、回流、实测、结构和生产约束，不能被写成对应下游活动已经通过。完整矩阵
见 references/scope-boundary.md。逐项记录完成后再聚合，报告结论只能是原理图准出、
有条件准出或不准出。

---

## 第 1 章 输入数据要求（设计数据包）

### 1.1 必需项

| 文件 | 作用 | 获取方式 |
|---|---|---|
| 原理图 PDF | 页面结构、图形复核 | EDA 导出 |
| `pstxnet.dat` | 展开网表（核心数据源） | Cadence PSTWRITER 导出 allegro 网表 |
| `pstxprt.dat` | 器件实例清单（位号→原语） | 同上 |
| `pstchip.dat` | 原语库（型号/封装/参数值） | 同上 |

非 Cadence 工具链（PADS/Altium/KiCad）提供等效网表导出即可，解析规则按格式改写。

### 1.2 强烈建议项

| 文件 | 作用 |
|---|---|
| 基线/参考设计（含其网表） | 逐引脚 diff 审查（裁剪类项目杀伤力强） |
| 关键器件 datasheet 包 | 冷门料、定制料兜底（平台查不到时必须有） |
| 平台设计规范（HDG/Checklist/PinOut） | ER5 规则扫描依据 |

### 1.3 设计意图问卷（审查前必须对齐，第 0 步）

```
1. 板卡功能一句话：____（例：某无人机平台负载，SDK 运行于主控 SoC，经 45P 连接器接入，对外仅 4 路接口）
2. 电源链路：输入电压范围/来源 → 各中间轨 → 各负载及功耗预算
3. 必须保留的接口清单与各自角色（Host/Device、电压、协议）
4. 必须删除的内容清单
5. 环境约束：温度范围、振动、防护等级、EMC 合规（平台方规定的频段与 EIRP 限值）
6. 降额与可靠性策略：电容/电阻/MOSFET 的降额标准
7. 特殊约束：认证/绑定芯片、不可更改项（如 SoC 原厂强制的电源控制脚、平台方的握手信号规则）
```

---

## 第 2 章 数据解析规范

### 2.1 三个文件的格式与索引

**目标索引**：
- `parts`：位号 → {part（型号）, jedec（封装）, value（值）}
- `nets`：网络名 → [位号.引脚号, …]
- `pin2net`：位号.引脚号 → 网络名
- `pinname`：Uxxx.2A2 → "VCCIO2_VCC"（引脚功能名，藏在 `CDS_PINID` 字段里，是识别 SoC 电源球/信号球身份的关键）

### 2.2 参考实现（Python，可直接在 ChatGPT Code Interpreter 运行）

```python
import re, json

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

### 2.3 PDF 处理

- `pdftotext -layout sch.pdf out.txt`，按 `\f`（换页符）分页；每页抓 `File:` 字段得页面标题 → **实际页面清单**（目录页常常过期，不可信）。
- 图形复核（第 7 章）：`pdftoppm -png -r 150 -f N -l N sch.pdf page` 渲染单页后读图。

---

## 第 3 章 AC0 Automated Check（自动检查）

### 3.1 定位

把结论**算得出来**的规则交给确定性代码执行。**判据不是「能不能自动化」，而是「结论是算出来的还是推出来的」**：算出来的（可复现、零幻觉、可穷举）走 AC0 脚本；推出来的（需语义理解或外部证据）走 ER1–ER7 由 agent 完成。

全流程由 agent 驱动时这条分界线**更要紧而非更宽松**——AC0 的价值不是「省人力」，而是**把 LLM 不可靠的地方交给代码**：Rule-05 逐个核对 357 个电源球的驱动，脚本零漏检；让 agent 读网表自己数，必漏。**因此 AC0 规则一律用 `scripts/` 执行，不得改由 agent 逐条推演。**

**AC0 的输出是「疑似问题清单」，不是判决**——合法结构（如 Bob-Smith 终端、补偿网络、DNP 选项）由执行 agent 逐条排除，排除依据写入报告附录。

### 3.2 首轮适用性发现与执行计划

解析完成后先运行：

    python3 scripts/plan_review.py db.json --intent intent.json --json review-plan.json

脚本同时从网表实例化具体检查对象（网络、位号、引脚、页面、功能包），并把每项写成
独立记录：`applicability`、`readiness`、执行阶段、缺失输入、触发证据和独立 handoff。
输入输出契约见 `references/review-plan-schema.md`。

- `APPLICABLE + READY`：本轮执行。
- `APPLICABLE + WAITING_EVIDENCE`：必须执行但缺材料；未补齐时结果为 INSUFFICIENT。
- `UNDETERMINED`：先补设计意图或消除冲突，不能偷换成 NA。
- `NOT_APPLICABLE`：必须有设计意图/范围 citation，最终才可写 NA。

网表未检出 DDR、RF 等关键词只能说明“未发现特征”，不能证明“不适用”。反过来，
设计意图明确要求某功能而网表未检出特征时，应新增功能存在性检查并优先复核。

### 3.3 规则库（每条含真实出处）

| 规则 ID | 名称 | 检查逻辑 | 真实案例 |
|---|---|---|---|
| Rule-01 | 单节点悬空网 | 网络节点数=1 且不在白名单（被删外设的 SoC 引脚、自动中间网） | `EFUSE2_EN_L` 只有 Rxxx.2 → 24V 输出永远无法开通 |
| Rule-02 | 双胞胎网络名 | 两网络名相似度>90%（差下划线/后缀）→ 疑似拼写分裂 | `FLT_0` vs `FLT0`、`VCC_5V0_SYS` vs `VCC5V0_SYS`（5V 主轨分裂，PMIC 无电） |
| Rule-03 | 自动命名孤岛 | N 开头自动编号网中只挂无源件（无 U/J/Q/Y/M） | 中间节点悬空筛查 |
| Rule-04 | 电源轨无驱动 | 轨名（VCC/VDD/VDDA/VCCA…）网络中无 PMIC/电感/开关类驱动 | |
| Rule-05 | 电源球无驱动 | SoC 每个含 VDD/VCC/AVDD 功能名的球，所在网络无驱动源 | 357 球全扫；`MIPI_DCPHY_AVDD→NC` 即由此暴露（后经规范裁定合法） |
| Rule-06 | VSS 未入地 | 功能名含 VSS/AVSS 的球不在 GND 网 | 268 球只抓 1 例外且与参考设计一致 |
| Rule-07 | 关键器件计数 | 按设计意图核对器件存在性（该删=0，该有≥N） | TPS16530 应×2 实×1 → 输入保护缺失 |
| Rule-08 | 参数验算不符 | 见第 5 章公式库，代入实际阻值验算 | FB 分压、限流、门限 |
| Rule-09 | 必需上拉/串阻缺失 | I2C 上拉（2.2K）、eMMC CMD 上拉（10K）、复位链、REXT（200R/8.2K）等 | 按平台规则表核对 |
| Rule-10 | ESD 挂残网 | ESD 器件所在网络节点数<2 或不含真实信号端点 | Dxx1/Dxx2 挂在废弃 USB_DP/DM 空网，活线无防护 |
| Rule-12 | 使能逻辑极性 | EN 有效电平 vs 上/下拉方向冲突；EN 脚耐压 vs 所接电源 | TPS16530 EN 低有效却被上拉至 24V VIN（耐压 5.5V，会烧） |
| Rule-13 | 钳位器件直连电源 | 稳压管/TVS 直接跨接在超过其 Vz/Vrwm 的电源轨上 | BZT52B3V0（3V）误并在 24V VBUS 上（上电即烧毁） |
| Rule-14 | 新增符号引脚映射 | 见 3.5 符号审计 | 新建连接器/IC 符号引脚号与实物不符 |
| Rule-15 | 电气 NC | 区分设计短接的 NC 网与工具 No-Connect 伪网络 | 避免把 357 个伪 NC 引脚误判短接 |
| Rule-16 | strap 强制条款 | ER1 证据给出 high/low/float 强制态后热跑 | must be pulled down |
| Rule-17 | 假闭环 | diff_netlists.py 按旧/新网表和历史断言核验 | 回复已改但字段/换网未变化 |
| Rule-18 | 同基名多轨 | 相似电源域是否张冠李戴 | VCC_3V3 与 VCC_3V3_SOM |
| Rule-19 | PINUSE/ERC | OUT-OUT 直连；输入-only/GROUND 异常出候选 | 利用 pstchip PINUSE |
| Rule-20 | BOM 字段卫生 | VALUE 首尾空白等影响 BOM/Diff | 与 Rule-17 解耦 |

### 3.4 参考实现（核心部分，可直接运行）

下方代码仅保留方法演化背景；现行实现以 scripts/lint.py 为准，它还包含伪网络、
PINUSE/ERC、证据热跑和覆盖输出，不得复制下方摘录替代正式脚本。

```python
def lint(db, DRIVER_PREFIX=('U230.', 'L23', 'Q240'), SOC_REF='U100.'):
    nets, parts, pinname, pin2net = db['nets'], db['parts'], db['pinname'], db['pin2net']
    import difflib
    F = []
    # Rule-01 单节点网络
    for n, nds in nets.items():
        if len(nds) == 1 and not n.startswith(('N37', 'N31')):
            F.append(('Rule-01', '悬空网络', f'{n}: {nds[0]}'))
    # Rule-02 双胞胎网络名
    names = sorted(nets)
    for a, b in zip(names, names[1:]):
        if a != b and difflib.SequenceMatcher(None, a, b).ratio() > 0.9:
            F.append(('Rule-02', '疑似网络名分裂', f'{a} <-> {b}'))
    # Rule-03 自动命名孤岛
    for n, nds in nets.items():
        if n.startswith(('N37', 'N31')):
            refs = {x.split('.')[0] for x in nds}
            if not any(r[0] in 'UJQYM' for r in refs):
                F.append(('Rule-03', '孤岛中间节点', f'{n}: {refs}'))
    # Rule-04/05 电源审计（DRIVER 列表按项目 PMIC/电源芯片位号调整）
    # 示例：把本项目所有电源器件（PMIC/DCDC/LDO/电感/负载开关）的位号前缀填进来
    DRIVER_PREFIX = ('U230.', 'U240.', 'L23', 'L24', 'Q240')
    for n, nds in nets.items():
        if re.match(r'(VCC|VDD|VDDA|VCCA|VOUT)', n):
            if not any(x.startswith(DRIVER_PREFIX) for x in nds):
                F.append(('Rule-04', '电源轨疑似无驱动', f'{n} ({len(nds)} 节点)'))
    for node, pn in pinname.items():
        if node.startswith(SOC_REF) and any(k in pn.upper() for k in ('VDD', 'VCC', 'AVDD')):
            n = pin2net.get(node)
            if n is None:
                F.append(('Rule-05', '电源球无网络', f'{node}({pn})'))
            elif not any(x.startswith(DRIVER_PREFIX) for x in nets[n]):
                F.append(('Rule-05', '电源球所在轨无驱动', f'{node}({pn}) <- {n}'))
    # Rule-06 VSS 未入地
    for node, pn in pinname.items():
        if 'VSS' in pn.upper() and pin2net.get(node) != 'GND':
            F.append(('Rule-06', 'VSS 未入 GND', f'{node}({pn}) <- {pin2net.get(node)}'))
    return F
```

### 3.5 符号审计（新增短板补全）

**问题**：审查默认"库里符号引脚号 = 物理封装引脚号"。新建/定制符号（连接器、新 IC）若引脚映射画错，网表自洽但物理错误，全部结论失效。

**执行**：从 `pstchip.dat` 提取每个**新符号**的 pin 名/号映射，与该器件官方 datasheet 引脚定义逐一比对（如 45 针连接器的 pin1-45 vs 官方引脚表）。只查新符号；沿用成熟库的符号可免检。

---

## 第 4 章 ER1 datasheet 核实（一切判断的前置）

Abs Max、强制条款、公式常量、引脚语义全部来自 datasheet；没有它们，Rule-16 判不了
"什么叫违反"、ER4 算不出任何电压、ER5 无规可对。**因此本层排在所有判断之前。**

但**不必在 AC0 之前**：AC0 的纯网表规则先跑一遍，它会指出哪些器件有异常，
据此决定优先读谁的 datasheet，避免盲读几十份。

### 4.1 核实协议

1. **先读 Absolute Maximum Ratings**（任何新 IC 介入前的第一步），列出每个引脚耐压，再谈接法（真实案例：EN/SHDN 脚耐压 5.5V 却设计上拉 24V）。
2. 核实选型公式常量（Vref、ILIM/频率/软启动公式、min on-time 等）后再出参数。
3. 查不到 datasheet 的器件：证据置信度标 C，对应适用检查项标 INSUFFICIENT，列入报告待索取清单，**严禁凭印象补参数**。

### 4.1.1 覆盖审计与 Agent 联网补取

解析 db.json 后先运行 audit_datasheets.py，把 U/M/Q/D 等非 NC 有源物料按 value
归并，并与资料包 PDF 对照。文件名命中只产生 NEEDS_VERIFICATION；只有 agent 打开
PDF 并核实完整型号、后缀、封装和版本后，才能写 FOUND/AVAILABLE。

资料包确实缺失时，执行 agent 必须自行联网补取，先查 LCSC/立创商城，再查原厂官网；
不得一开始就把搜索工作转交设计者。Agent 将每颗物料的 FOUND 或 NOT_FOUND 写入
datasheet-resolution.json，重跑 audit_datasheets.py，并把 datasheet-audit.json
传入 plan_review.py/lint.py。完整契约见 references/datasheet-resolution-schema.md。

只有上述白名单渠道都检索过且仍无有效文档时，才能写 NOT_FOUND。此时逐颗提示：
「找不到这颗物料的 datasheet：<完整型号>（位号：<refs>）。请提供该物料的原厂
datasheet。」并保持 INSUFFICIENT/C。单个 URL 失败、Cache miss 或网络受限不构成
NOT_FOUND 证据。


### 4.2 四类信息与去向

| 取什么 | 供给哪一层 |
|---|---|
| Absolute Maximum Ratings | ER2 电平域匹配、ER7 选型复核 |
| **强制条款原文**（`must be pulled down` / `must be left floating` / 内部默认态） | Rule-16、ER5 —— **原文用词必须保留**，它是定级 BLOCKER 的唯一依据 |
| 公式常量（VFB、Vref、限流/频率系数）、**可调档 vs 工厂固定档** | ER4 全部验算 |
| 引脚语义表（方向敏感信号、多封装变体） | ER3 链路追踪、Rule-14 符号审计 |

### 4.3 回补 AC0

AC0 中依赖 datasheet 的规则——Rule-08（参数验算）、Rule-09（必需上拉）、Rule-12（EN 极性/耐压）、
Rule-14（符号引脚映射）、Rule-16（strap 强制条款）——在本层完成后回头补跑。
AC0 因此**不是一趟跑完**，而是按输入依赖分三档：**冷跑**（只吃 `db.json`）→ **冷跑·参数化**（加第 0 步意图清单 `--intent`，供 Rule-07）→ ER1 → **热跑**（加结构化 `evidence.json`，执行 Rule-08/09/12/14/16）。

证据格式见 references/datasheet-evidence-schema.md。热跑命令：

    python3 scripts/lint.py db.json --evidence evidence.json --json lint-hot.json

没有对应 evidence check 的规则保持 hot_pending；文字报告中“已经阅读 datasheet”不等于
规则已机器执行。

冷跑的产物有两类：`FINDING`（疑似缺陷）与 `CANDIDATE`（待 ER1 定夺的优先级清单）。后者是冷跑排在 ER1 之前的真正理由——**它直接决定 ER1 优先读哪几份 datasheet**，而不是让 agent 盲读几十份烧掉上下文预算。

`lint.py` 每趟末尾显式列出本趟未执行的规则及原因。**扫出 0 条与根本没扫必须长得不一样**——这正是 `parse_netlist.py` 自检闸门要防的同一类静默失败。

### 4.4 取值前先确认文本层可信

表格列错位时先渲染目检再取值。**工厂固定档被误读成可调档会直接产出假缺陷**
（实测：某监控芯片按"可调 0.62V"算出 1.09V 动作点、险些定为重大缺陷，
渲染订购信息表后确认该变体为固定 2.5V 档，实际 4.40V，属正常设计）。

---

## 第 5 章 ER2 供电系统审计

### 5.1 电源轨三问（每轨必答）

1. **谁驱动？**（PMIC 引脚/电感/负载开关/0R 跳线——注意 Rockchip 常用 0R 做电源选项，须追 0R 另一端找真实源）
2. **谁负载？**（SoC 球/DRAM/外设）
3. **电平对不对？**（对照设计要求的电压值与 FB 验算）

### 5.2 电源球覆盖

- 全部 SoC 电源球（功能名含 VDD/VCC/AVDD）：所在网络必须有驱动（Rule-05）。
- 全部 VSS/AVSS 球：必须在 GND 网（Rule-06）。例外需与基线参考设计比对确认。

### 5.3 电平域匹配（短板补全）

- 列出 SoC 各 IO 电源域（VCCIOx/PMUIOx）的实际供电电压（从网表反查域电源球所在轨）。
- 核对**相连两端**的域电平一致性：SoC GPIO 域 vs 外设 IO 供电（例：PMIC 控制 IO 属 1.8V ↔ SoC 侧必须是 1.8V 域；认证芯片 3.3V ↔ I2C 域 3.3V）。
- 复用功能引脚的域归属以 PinOut/HDG 为准。

### 5.4 每轨功率预算

输入轨能力 vs（板载自耗 + 对外输出）峰值合计，留 ≥20-30% 裕量；逐轨列出（5V 系统、3.3V、1.8V、输出轨）。

### 5.5 反灌/漏电审计（新增）

- 上拉电阻的供电轨 vs 信号两端器件的上电时序：上拉不得把电倒进未上电的器件（平台规范常见条款）。
- 不同电源域之间的信号连接，确认弱侧先上电或做隔离。

**可执行判据**：对每颗上拉（含上拉性通路），取「上拉源轨」与「被拉信号所属 IC 的供电轨」两者比较——
**跨轨即候选**。再判两轨是否同时上电（同一稳压器输出、或存在明确使能时序）。跨轨且无时序保证，
即该 IC 未上电时被上拉倒灌。隔离域之间的任何跨轨上拉一律列为发现项。
判定所需数据全在 `db.json` 里：`pin2net` 定位信号所属 IC，再取该 IC 的电源脚所在轨。

### 5.6 热与浪涌

- 电阻功耗：高压分压（>20V）每颗算 P=U²/R；泄放/放电电阻按满载功耗封装。
- 开关类器件（eFuse/负载开关）：I²Rds(on) 耗散与结温裕量。
- 热插拔浪涌：输入电容总量 vs 源端限制（平台方通常规定上限）；软启动时间常数与浪涌电流 I=C·dV/dt 验算。

这里只定判原理图和外部规格能够确定的电气应力。PCB 压降、PDN、布局寄生、铜皮和
实际结温另记 HANDOFF；原理图范围内缺输入则标 INSUFFICIENT，二者可以并存。

---

### 5.7 检测点取样侧（Rule-11）

判压/检测类分压必须取**源**侧，而不是**保护后内部轨**侧（实例：VBUS 判压分压错接到输出侧 `VOUT_24V`——保护动作后判压电路跟着失效，永远测不到真实输入）。

**为什么在 ER2 判而不在 AC0**：判定要回答「这条轨是源还是保护后」，答案只存在于电源树里，而电源树是本层的产物。AC0 阶段只有网表，写不出不高误报的判别式。

**执行**：建完电源树后，对每个检测/反馈分压回答三问——① 中点接的是谁的哪个脚（ADC/OV/UV/SENSE/MON）；② 上臂另一端挂在电源树的哪个节点；③ 该节点相对被测对象是源侧还是保护后。三问中出现「保护后」即为发现项。


## 第 6 章 ER3 关键链路逐条追踪

### 6.1 方法

对设计意图中的每一个"连接对"（A 必须连到 B），从 A 出发逐跳走到 B，路径上每一跳（网络 → 元件 → 网络）都列出。任何一跳缺失即断裂，断裂点即 bug 位置。

```
例：Uxxx.AK9 → [N312422630] → Ryyy.1/Ryyy.2(2.2R) → [USB2_DP] → Jxxx.12 ✓ 通
```

### 6.2 方向敏感信号协议（短板补全）

TX/RX/主从方向信号，**必须回到官方引脚语义表逐字确认**，并做"发射端 → 接收端"复述：

- 官方文档写"三方设备的 RX"= 我方接收 → 接 SoC 的 RX（直连），不得想当然交叉。
- 差分对同时核对 P/N 极性对应关系。
- 接口视角（Host/Device、Source/Sink）在链路复述中写明。

### 6.3 必查链路清单（按项目裁剪）

1. 电源输入 → 保护 → 各级电源 → 各负载
2. 每一路数据链路（USB/网口/串口/自定义接口）的双向连通
3. 复位链（RC/按键/PMIC → SoC nPOR）
4. 时钟链（晶振/RTC → SoC）
5. 启动配置（启动模式电阻、Recovery/Maskrom 键）
6. 检测/反馈链（电压检测、电流检测、温度检测）的取样点与终点（ADC/GPIO/比较器）
7. 使能链（上电时序相关的 EN 信号：谁产生、谁接收、极性、电平域）

---

## 第 7 章 ER4 参数与边界条件验算（WCA）

先用 scripts/solve_dividers.py 对反馈/监控分压做路径穷举和公差计算。脚本支持串联臂、
互不共享电阻的并联支路、VALUE 内公差和 Vref 公差窗口；多源或共享支路标未判定，
不允许采用第一条路径生成确定结论。

### 7.1 公式库（代入网表实际阻容值验算）

| 电路 | 公式/规则 | 验收标准 |
|---|---|---|
| 可调电源 FB 分压 | Vout=Vref×(1+Rtop/Rbot) | 与目标电压误差 <1-2%（用 E96 实际值） |
| UVLO/OVLO 门限 | Vth_in = Vth_pin×(1+Rtop/Rbot)，含迟滞 | 门限窗口落在设计"无人区"，公差叠加后仍有裕量 |
| 限流/恒流 | 按器件公式（如 IOL=18/R） | 限流点与系统保护线之间留裕量 |
| 软启动 | 按器件公式（如 t=k×VIN×C） | 浪涌 I=C·dV/dt 低于源端限制 |
| 稳压管钳位 | 脚压=min（分压值， Vz) | 宽输入范围下端高于检测门限、上端低于引脚耐压；低流拐点（knee）要计入 |
| ADC 检测分压 | Vadc=Vin×R2/(R1+R2) | 满量程不超 ADC 上限；各判定档位间隔 ≫LSB 与误差之和 |
| RC 复位 | τ=RC | 满足器件最小复位脉宽 |
| I2C 上拉 | 总线上拉等效 1-4.7K，电源=总线域电源 | 多器件地址不冲突；上拉电源与 GPIO 域一致 |
| MLCC 直流偏压 | 有效容量 = 标称 × 偏压系数 | 偏压系数取 40-70%（查厂家曲线），不得低于功能需求 |
| 电阻功耗 | P=U²/R、P=I²R | 不超过封装额定（建议 ≤50-70% 降额） |

### 7.2 边界条件清单（每个关键电路必过）

最高/最低输入电压、满载/空载、启动/热插拔、输出短路、负载瞬态、温度范围、器件公差叠加（电阻 1% + IC 阈值 ±2% + 基准温漂）。

只有输入材料给出相应工况时才可判定；PCB 热阻、寄生和实测工况属于 HANDOFF。

### 7.3 选型复核

- 对照平台 checklist 的硬性参数（如"Buck 电感 Isat≥X、DCR<Y"）。
- **封装兼容性**：替换料的封装/端子尺寸与 PCB 焊盘（JEDEC_TYPE 或实物测量）必须一致——电气可换≠物理可焊（真实案例：201610 ↔ 252012 不可直换）。

---

## 第 8 章 ER5 平台原理图规则库

### 8.1 使用方法

把平台官方 checklist/设计指南中**可判定的条目**转为检查表，逐条核对。下方为本项目沉淀的两套规则库示例；新项目应在其上增删。

### 8.2 规则库构建方法

平台规则库不通用——它必须由**你自己的项目所用平台的官方文档**生成。生成步骤：

1. **收齐来源**：SoC/模组原厂的 Hardware Design Guide、Schematic Review Checklist、Pinout 表；平台方的接口与功耗规范。
2. **只提取可判定条目**。判据：这条规则能否**仅凭网表或图纸就判定真/假**。
   - 可判定 →「XIN/XOUT 之间必须并联反馈电阻」「ZQ 校准电阻必须接 VDDQ 而非地」「某 IO 域仅支持 1.8V」
   - 不可判定（属 Layout/软件，另行归档）→「去耦电容须靠近引脚」「DTS 需 disable 未用功能」
3. **逐条写成三元组**：`条件 → 期望值 → 判定方法（查哪张网/哪个位号/哪个字段）`。没有判定方法的条目不入库。
4. **标注强制等级**：区分 datasheet 里的 `must / shall`（强制，违反即 BLOCKER 候选）与 `recommended / typical`（建议）。**原文用词必须保留**，这是后续定级的唯一依据。
5. **下游分流**：布局、SI/PI、EMC 实测、软件、结构和生产条目生成独立 HANDOFF，
   不得伪造其 PASS/FAIL；若同一条还有原理图可判部分，该部分仍保留自己的结果。
6. **随项目演进**：每轮审查中被证伪或被补充的条目，回写规则库并注明出处。

### 8.3 平台规则库模板

按下表逐条填写；每个平台一份，随项目替换。

| # | 域 | 规则（含原文强制词） | 期望值 | 判定方法 | 来源（文档/版本/页号） | 强制等级 |
|---|---|---|---|---|---|---|
| 1 | 电源输入 | | | | | must / rec |
| 2 | 时钟 | | | | | |
| 3 | 复位 | | | | | |
| 4 | DDR | | | | | |
| 5 | 存储（eMMC/SD） | | | | | |
| 6 | USB | | | | | |
| 7 | 网口/PHY | | | | | |
| 8 | ADC/模拟 | | | | | |
| 9 | strap/启动配置 | | | | | |
| 10 | 未用外设处置 | | | | | |
| 11 | 接口连接器 | | | | | |
| 12 | EMC/认证 | | | | | |
| 13 | 热/结构 | | | | | |

**填写要点**

- 「未用外设处置」一栏最容易出事：原厂对未用模块的电源常有**互不相同**的要求（有的可悬空、有的必须接地、有的必须照常供电），逐个查，不要按同一条规律套。
- strap 类条目务必记录**内部上/下拉默认态**，它决定了"不贴电阻"时芯片的实际行为。
- 认证类（EMC 频段、EIRP、温升）条目通常只能判"是否已在图纸上做出声明"，真值需实测，判定方法一栏写明"待测"。

> 本节刻意不附任何具体厂商的规则库内容——各原厂/平台方的设计指南通常受其自身授权条款约束，且版本更新频繁。请以你手上的官方文档版本为准自行生成。

---

## 第 9 章 ER6 图形化复核（短板补全）

网表覆盖不了的信息在图形里，必须补一轮读图：

1. **渲染关键页读图**（`pdftoppm` 150dpi）：新增页全读；重点看 Option/NC 贴装表、strap/CFG 配置表、注释框、方向标记、测试点。
2. **目检清单**（作为标准交付物输出）：
   - 二极管/稳压管/TVS 阴极方向（如钳位管阴极朝信号节点）
   - LED 方向、电解/聚合物电容极性
   - 连接器 pin1 朝向、变压器同名端
   - 新增符号实物对版（封装 vs 器件实物）
3. **PDF 文本层与网表版本一致性**：比对 PDF 生成时间与网表导出时间，防止拿旧图审新版。

---

## 第 10 章 ER7 器件身份与封装一致性

### 10.1 选型与 BOM 收口

- 封装兼容性：**电气可换 ≠ 物理可焊**，替代料必须核封装。
- BOM 二义在此收口：同一器件的 PART_NAME 与 VALUE 不一致、页面标注与库不一致，
  均须唯一化后方可原理图准出。
- 器件类别判定必须 **≥2 个独立证据源**才允许定级 A/B
  （实例：浪涌器件凭库名误判为 TVS，原厂规格书证伪其为 MOSFET 结构件）。

生命周期、单一来源、采购与国产替代属于独立供应链质量门；只有其提出的原理图整改
要求回到本流程做网表复验。

---

## 第 11 章 输出规范与闭环

### 11.1 严重度分级

| 级别 | 定义 | 处置 |
|---|---|---|
| 致命 | 板上电不工作/会损坏器件或上游设备 | 必须修复后原理图准出 |
| 严重 | 功能失效风险高、违反平台强制规范、可靠性硬伤 | 必须修复或书面风险接受 |
| 建议 | 提升可靠性/合规性的改进 | 评估后决定 |
| 观察 | 需设计方确认的决策项 | 列入报告「待确认」节并跟踪 |

### 11.2 发现项格式（可直接当 ECO 单执行）

```
[ID] [级别] 标题
位置：位号/网络/页码
证据：网表节点数据或 datasheet 条目（置信度 A/B/C）
根因：为什么会错
改法：具体到位号、阻值、网络名的修改动作
验证：改完后如何确认（网表复扫/bench 实测点）
```

### 11.3 修复-复验闭环

1. 修复后重新导出网表 → 复跑 AC0 冷跑/热跑 + 修复项专项验证。
2. 用 scripts/diff_netlists.py 自动列出 BOM/引脚/网络变化，并按
   references/diff-claims-schema.md 核验历史意见；断言失败即 Rule-17。
3. BLOCKER 清零、Warning 关闭或书面接受、阻断级 INSUFFICIENT 补齐/接受、HANDOFF 形成可执行约束
   后，输出“原理图可进入 PCB Layout”。

---

## 第 12 章 常见错误模式库（模式驱动检查）

| 模式 | 形态 | 检查规则 |
|---|---|---|
| 跨页标签错字 | 两个相似名网络互不相通 | Rule-02 |
| 自动后缀孤岛 | `NETNAME_37816262` 类后缀网 | Rule-02/03 |
| 检测点接错侧 | 判压接在负载侧/保护后 | Rule-11（ER2 §5.7） |
| ESD 挂残网 | 防护在空网，活线裸奔 | Rule-10 |
| EN 脚超耐压 | 逻辑脚上拉高压轨 | Rule-12 + abs-max 表 |
| 极性搞反 | 低有效当上拉、高有效当下拉 | Rule-12 |
| 钳位管并电源 | TVS/稳压管直接跨超压轨 | Rule-13 |
| 缺上拉/串阻 | I2C、CMD、复位链、REXT | Rule-09 |
| 电源轨改名分裂 | 同一轨两个名字互不相通 | Rule-02 |
| 方向信号交叉错 | RX/TX 凭感觉交叉 | 4.2 协议 |
| 电容只算标称 | 忽略 MLCC 直流偏压衰减 | 6.1 偏压规则 |
| 参数够、封装错 | 电气可换物理焊不上 | 6.3 封装核查 |

---

## 第 13 章 ChatGPT 迁移指南

### 13.1 使用方式

1. 上传：原理图 PDF、三个网表文件、（可选）基线网表与 datasheet 包。
2. 粘贴本方法论（或压缩版：第 0/1/2/3/10/11 章 + 项目规则库）。
3. 让 ChatGPT 用 Code Interpreter 先运行 datasheet 覆盖审计并处理 agent_requests，
   再运行第 2 章解析代码与第 3 章计划/lint 代码，输出 AC0 逐项计划与疑似清单。
4. 再逐章指令执行 ER1–ER7（链路追踪、供电审计、WCA、规则扫描、读图、器件核实）。
5. 按第 10 章格式产出报告，修复后重新上传网表做闭环 diff。

### 13.2 迁移注意

- Code Interpreter 有文件大小与会话持久性限制：大网表建议先本地拆分（按字母/位号段）或只上传解析后的 JSON。
- 图形复核需要模型具备读图能力：逐页渲染 PNG 后上传。
- datasheet 核实同样遵循第 9 章协议；查不到的适用项显式标为 INSUFFICIENT 并索要，不允许编造。
- 平台规则库（第 7 章）应按项目替换为对应平台的官方 checklist。

---

## 附：本方法论验证记录

本方法论在一个真实工程项目中完成四轮闭环：R1 抓出 7 致命+5 严重（5V 轨分裂、USB×2 断裂、PPS 断裂、EN 悬空、I2C 孤岛、判压错侧、输入无保护、GND 孤岛、TVS 挂残网、VBUSDET 缺失、复位缺失）；R2 验证 11 项修复并新抓 1 处（ESD 挂错网）；R3 验证修复并新抓 1 致命（稳压管误并 24V）+1 断网；终审全量核查（26 电源轨、357 电源球、268 VSS 球）+ 官方 Checklist 逐条核对，原理图审查通过并移交 PCB 阶段。期间方法论自身的 5 处失误（器件类别误判、方向写反、EN 超压、min on-time、TVS 替代误判）均已转化为本版规则。

---
