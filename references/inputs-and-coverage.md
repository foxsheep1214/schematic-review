# 输入、解析与覆盖

## 一、覆盖、版本与反漏检

### 输入基线

建立输入清单（相对路径、SHA-256、版本、导出来源/日期、用途、质量限制）：原理图 PDF、
原生设计/网表、导出日志、当前装配 BOM、选项表、需求/ICD、对端/线缆、datasheet/errata、
官方 pinout/平台 checklist、参考模板、历史报告、实测记录。输入只读，修复另存受控副本。
文件时间只作线索。原图/网表关键电路、修订号、MPN 与装配状态须交叉一致；缺一致性证据时
明确受影响项。导出错误或旧文件残留不得用于当前版本准出。

仅 PDF 可做逐页受限审查；把辨认的连接与不确定图形分开，不能伪造 db.json 并声称完成
机器全网覆盖。完整模式用受支持的 Cadence/OrCAD 三件套或 KiCad 解析器，其他格式做适配自检；没有适配器也不能拒绝可做的读图。

### 三条独立覆盖线

| 线 | 枚举来源 | 必须产出的证据 |
|---|---|---|
| 需求→电路 | 需求/方案/用户确认/接口规范的每个条款 | REQ ID、出处、约束类型、量化条件、实现对象、检查 ID、结果 |
| 电路→判据 | 全部器件/脚/网络/页面/装配表 | 每个模块功能、每轨源/负载、每路接口终点、器件应用条款及检查 ID |
| 工况→响应 | 允许运行方式、外部接入/故障/掉电条件 | 每个关键状态电源、使能、输入电平、保护动作、恢复路径及检查 ID |

`review-plan.json` 只提供初始集合。依据网表补充无关键词的网络、未使用引脚的处置、
漏列的器件与需求；不得只在发现清单附近审查。关键外围逐脚表至少含
物理脚号/官方名称/方向或电源域/实接网/外围值及贴装/适用条款/结果；官方引脚与网表
双向比较，解释多单元、EP、隐藏电源、保留脚、符号未声明的物理引脚。

不要用“库里有 698 脚且全部映射”替代“官方 720 脚全部处置”：缺的 22 脚必须逐脚解释。
同一类 IC 可复用同 MPN/封装/版本条款，但每个位号外围与贴装配置独立核验。

### 状态与组合

每个项目至少裁定：OFF、STARTUP/RESET、RUN、BROWNOUT/POWER_DOWN、EXTERNAL_POWER_ONLY/
HOTPLUG 的适用性；其余按需求加入待机、编程、备用源、短路/过载、反接、开路、通信丢失。
对“设计是否需要承受该故障”缺依据时先记证据不足，不把所有假设故障一律当成必需设计要求。

每个适用状态追：源/回路→开关方向/体二极管→受电域→EN/PG/RESET 默认态→外部 IO→
保护/恢复。查掉电域注入、锁存/自动重试、MCU 未启动时的默认安全状态、软件依赖及循环启动。
保护链应查故障产生、检测量、比较/决策、关断执行、反馈/复位全过程。

### DNP / 选项 / 模板

- 两套图：设计连线图与按装配配置裁出的有效通路图。NC 伪网不导电；DNP 元件两端原网
  各自仍存在，其跨元件边不导通。不能把所有 0Ω 选项同时接上。
- 装配不确定时按候选配置给条件结论；标明唯一供电/上拉/保护是否依赖某个 DNP。
- 模板一致仅证明未变；核对模板 MPN、封装、BOM、跳线、输入/负载、固件默认与本设计是否相同。
- 冻结区域也须审查依赖：修改上游电源或时钟后，“DDR 网未动”不足以证明 DDR 条件未变。
- diff 别只比网络名；查物理 pin→net 成员、参数/贴装、符号版本以及依赖链。重新标注位号时
  建旧新对象映射，缺映射不自动宣称闭环。

### 阅读、视觉与结束条件

datasheet 台账按“MPN/封装→文档修订→适用章节→提取限值/条件→检查 ID”填写，包含正常工作
条件、上掉电/复位/内部默认、应用公式和 errata。发现切换模式/固定档先回应用章节，
不能从通用分压模板推断内置反馈缺件。
每页留图面记录；文字错位/旋转坐标先用小裁图确认定位，再放大判读。图页名不等于 PDF 页号。

下列反漏检与反证工作在相应检查中完成，交付前仅核对有无遗漏；已完成且输入/判据未变的项不另起一轮全量审查：

1. 建计划时从完整需求、器件清单、端口和物理脚表枚举，交付前通过覆盖对账查未入计划对象。
2. 判定时对每个 PASS 问“是否只因没报错/沿用模板/典型值/样机调通”；对每个 P0/P1 检查
   身份、贴装、方向、工况、计算与独立保护，收窄过度结论但保留已证实的偏离。
3. 形成修改建议时验算额定/全角/启动/接口，记录可能引入的新问题；实际修改后按依赖范围复验。
4. 冷/热所有候选逐条关联最终检查和处置；各规则的 planned/executed/pending 分对象统计。
5. 统计唯一缺陷 ID 与逐项结果两个口径；标题数字、正文、需求矩阵和闭环列表一致。

覆盖维度不能混成单个漂亮百分比。在附录台账保留需求、页面、器件、物理引脚、轨、链路、状态、
文档章节和历史意见的总数/完成/NA/不足/未执行。未知总数写 UNKNOWN，不能写 100%。
自动校验可核对象遗漏与记录矛盾，工程上遗漏了哪些判据仍由审查负责。

### 留档

项目审查目录保留 `input-manifest.json`、`intent.json`、`db.json`、冷跑计划快照及合并后的最终计划、
`evidence.json`、lint、`review-results.json`、`review-gate.json`、计算、关键图形证据及复审 Diff。
临时 OCR/大图放任务临时目录（例如 /tmp/codex-work/<任务>/）；最终结论的唯一证据不能随临时目录消失。不要把客户原图、BOM、
私有手册、人员姓名或项目路径复制到公开 skill 仓库，用最小脱敏 fixture 做回归。

封存审查证据时，先完成报告、逐行复核、校验、格式说明与命令记录，再生成清单并逐文件复核。
清单注明相对路径基准，保存原始清单字节及 SHA-256；不能只保留文件名和 `OK`，否则无法证明后来未改。
记录与清单避免循环哈希：内容清单排除自身和封存记录，封存记录绑定内容清单的哈希，另一个清单可绑定
封存记录。最后的只读校验日志另作明确排除的旁证。上述内容齐备并验证后，才宣告“已冻结”；
审查证据冻结与硬件准出结论分别记录，NO_GO 也可完整封存。

冻结后补格式、日志或说明要另存补充版本并保留旧清单与旧文件原字节，不能重写旧冻结记录/清单后
凭“只改元数据”宣称历史内容未变。接收对照答案或新增证据后，原主审保持不变，复核另存版本。
旧清单或原字节不可取得时明确写历史哈希闭环 UNKNOWN，不按当前文件重建后冒充首次封存。

### 重绘后的复审证据

- 版面重排、标签转换、短线清理和符号笔画修补都可能改变连接；对最终保存目录重新导出网表/ERC，绑定全层级源文件哈希。不得沿用最后一次后处理之前的通过结果。
- 纯重绘复审至少比较物理 pin→net 分组、位号/值/MPN/封装/DNP、NC 和 ERC 项的器件/引脚身份。相同 ERC 数量不能证明没有新增问题。
- ASG 路由日志、几何通过、完整页数和图面美观不构成 SR 电气 PASS。原有 P1、证据不足项与全工况缺口继续保留稳定 ID；没有新证据不得随重绘关闭。
- 若只做连接保持与历史意见继承，明确写“重绘差异复验”，不能写成重新完成了整板电气审查。几何误报按具体对象、原生图和网络证据处置，保留原始 FAIL/INSUFFICIENT。

## 二、网表解析（Cadence/OrCAD 三件套、KiCad 及其他 EDA 适配）

上游工具的 FAIL 要按具体对象与判据解释。若 SR 已独立验证同版原生源/XML、完整物理引脚、
缓存、实例身份与显式无脚角色，且自身解析自检通过，这些证据可关闭相应的窄输入资格判断；
不能仅因另一个工具的字段表示或几何误报再开同范围的待补证。保留上游原始 FAIL 和工具改进事项，
MPN/BOM资格、参数保证等仍各自审查。自身 self_check=false、缺脚、未解继承、身份或哈希不一致时
不能借此关闭 DOC-Q01 或准出阻断。

### 一、输入文件

| 文件 | 作用 | 获取方式 |
|---|---|---|
| 原理图 PDF | 页面结构、图形复核 | EDA 导出 |
| `pstxnet.dat` | 展开网表（核心数据源） | Cadence PSTWRITER 导出 allegro 网表 |
| `pstxprt.dat` | 器件实例清单（位号→原语） | 同上 |
| `pstchip.dat` | 原语库（型号/封装/参数值/引脚映射） | 同上 |
| `netlist.log` | **导出日志——免费证据，勿丢** | 同上，与三件套同目录 |

非 Cadence 工具链（PADS/Altium 等）提供等效网表导出即可，解析规则按格式改写；方法论其余部分不变。
KiCad 已随附解析器，见下文第六节。

### 二、目标索引

- `parts`：位号 → {part（型号）, jedec（封装）, value（值）}
- `nets`：网络名 → [位号.引脚号, …]
- `pin2net`：位号.引脚号 → 网络名
- `pinname`：Uxxx.2A2 → "VCCIO2_VCC"（引脚功能名，藏在 `CDS_PINID` 字段，是识别 SoC 电源球/信号球身份的关键）

节点在第一个点处分开位号与完整源脚标识；例如 `RM1.1.2` 属于 `RM1`，脚标识为 `1.2`，不可截断或改名消除库存缺口。源脚标识含点不证明它就是厂商物理脚号；多单元/焊盘别名须有明确的原厂脚表对应，阵列内部支路仍按原件逐对取证。

### 三、格式要点

- `pstxnet.dat`：`NET_NAME` 行独占一行，下一行是带引号的网络名；随后 `NODE_NAME\t<refdes> <pin>` 逐节点；`CDS_PINID` 给出引脚功能名。
- `pstxprt.dat`：` <refdes> '<primitive>':;` 每实例一行；primitive 名或 VALUE 带 NC 标记 = 该实例不贴（实例级 NC 信息只在这里，库不含）。各家命名不同，`/NC` 与 `_NC` 后缀都在用（`0R/1%/NC`、`0R/1%_NC`），`is_not_populated()` 只在 NC 被 `/ _ - 空格` 或串首尾界定时才判为不贴——否则 `NCP1117` 这类型号会被误判成不贴。**该标志漏判会静默放大**：把不贴的 0R/上拉当成已贴，RST-E01/RST-E02 的默认态判定和 PWR-A02 的驱动判定都会跟着错。
- `pstchip.dat`：`primitive '<name>'; ... end_primitive;` 块内含 pin 名→PIN_NUMBER 映射（符号审计用）、PART_NAME/JEDEC_TYPE/VALUE。

### 四、解析实现

**直接运行脚本，不要照抄代码**：

```bash
python3 scripts/parse_netlist.py <allegro目录> -o db.json
```

#### 4.1 pinname 有两种布局——这是最容易踩的坑

引脚功能名（`Uxxx.2A2 -> "VCCIO2_VCC"`）随 PSTWRITER 版本有两种放法：

| 变体 | 形态 |
|---|---|
| A | `NODE_NAME` 之后的属性行里带 `'\NAME\':CDS_PINID` |
| B | `NODE_NAME` → 实例行 → **紧接一行 `'NAME':;`** |

只处理其中一种，另一种会得到**空的 pinname 索引**。后果是静默的：
PWR-A02（电源脚无驱动）与 PWR-A03（地脚未入地）依赖 pinname，会扫出 0 条命中，
报告写成"数百个电源球全扫通过"而实际一个都没查过。

**实测**：某板 `pstxnet.dat` 中 `CDS_PINID` 出现 0 次，只按变体 A 解析得到
pinname = 0 条（应为 6047 条）。

`scripts/parse_netlist.py` 两种都试，**并在覆盖率低于 50% 时报错退出**——
宁可中断，也不交出一份静默残缺的索引。

#### 4.2 伪网络自动识别

导出器会把"带 No-Connect 属性且无连线"的引脚汇集到一张名为 `NC` 的网。
它不是电气短路。脚本按 `C_SIGNAL` 是否带层次路径自动判别，结果放进
`pseudo_nets`（判别式详见 `automation.md`）。

#### 4.3 输出索引

| 键 | 含义 |
|---|---|
| `nets` | 网络名 → [refdes.pin, …] |
| `pin2net` | refdes.pin → 网络名 |
| `pinname` | refdes.pin → 引脚功能名（识别 SoC 电源球/信号球身份的关键） |
| `pintype` | refdes.pin → PINUSE（POWER/GROUND/…） |
| `parts` | refdes → {prim, part, jedec, value, **nc**}；`nc=True` 表示该实例不贴 |
| `ref2page` | refdes → 页号 |
| `pseudo_nets` | 工具生成的伪网络名 |

Cadence 的 `PIN_NUMBER` 可能是 BGA 字母数字脚号，且 `PINUSE` 与 `PIN_NUMBER` 之间
可能夹有其他属性；随附解析器按完整 pin block 提取，不依赖两行相邻。`pintype` 缺失或
覆盖不足时，NET-A06 必须报告 SKIPPED/部分执行，不能把 0 命中写成通过。

最小索引只支持部分拓扑检查；完整审查还需要 pinname/物理脚/页映射、BOM 和官方条款；
改写 `parse_*` 函数即可，其余脚本无需改动。


### 五、PDF 处理

- `pdftotext -layout sch.pdf out.txt`，按 `\f` 换页符分页；每页抓 `File:` 字段得页面标题 → 实际页面清单（目录页常过期，不可信）。
- 单页渲染读图：`pdftoppm -png -r 150 -f N -l N sch.pdf page`（引脚图/表格细节用 `-r 200` 以上并裁剪局部）。
- 扫描件 datasheet（无文本层）必须渲染目检。
- **硬规则：提取出的表格出现列错位，必须渲染目检后才允许下结论。** 判别信号——同一行里出现本属不同列的值、
  水印文字插进数据行、单元格合并处的值漂到相邻行。实测两次栽在这上面（订购信息表读错变体档位、
  电源时序表读不出参数），两次都是渲染后才改对结论。
- **旋转页坐标换算**（`Page rot: 90` 的图纸/datasheet 很常见）：用 `pdftotext -bbox` 拿到目标文字的
  `(x, y)`，注意该坐标已在旋转后的横向坐标系里（宽=页面 height）。映射到 `pdftoppm` 输出的像素：
  `px = x / page_h * img_w`，`py = y / page_w * img_h`。先按此裁一小块验证命中，再放大读图。
- 比对 PDF 生成时间与网表导出时间，防止拿旧图审新版。

### 六、其他 EDA 适配

本 skill 当前只随附 Cadence/OrCAD 三件套解析器；下列是适配输入路线，不代表仓内已有
对应脚本。适配后必须生成同一 db.json 契约并建立格式 fixture/覆盖自检。

- KiCad：`.kicad_sch` 本身即文本（S 表达式），可直接解析；或用 `kicad-cli sch export netlist`。
- Altium：导出 EDIF/Protel 网表，按 `(` 分组解析。
- PADS：ASCII 网表 `*SIGNAL*` 段。
- 适配后按每条规则输入依赖确定覆盖范围，缺引脚名/类型/页映射不能宣称完整适配。

### 完整性与适用范围

解析器保留 `declared_pinname` / `declared_pintype`：来自符号 primitive 的完整脚表（含未连接脚），
不是官方封装定义。必须与 `pin2net` 及官方 pinout 双向差集，解析过的引脚覆盖率不等于物理脚覆盖率。
自检拒绝跨网重复物理脚、索引不互反、网络引用缺失器件、缺失 primitive 及导出日志 ERROR/中止。
严格模式自检失败时仍写出 `db.json`（`integrity.self_check_passed=false`）并以退出码 2 结束，可直接用它定位缺口；`--no-strict` 只把退出码改为 0。self_check_passed=false 的数据不能准出，`validate_review.py` 会将其列为阻断项。
缺日志仍需在输入一致性项记录，不能假定导出成功；确认是历史追加日志时分离本次导出记录另行留证。

严格失败先区分编号/归网丢失、功能名/类型覆盖不足、官方库存差集与导出中止；缺功能名不等于硬件断路，
官方未用脚允许浮空也不等于库存完整。逐物理对象用原生编号、官方角色、装配状态及实际路径记录局部事实，
全量 DOC-Q01/库存缺口独立保留。去耦和 I²C 清单的原生 PASS 仍遵守各检查器的完整缺口合同：已有局部
观察不能靠编辑清单、删完整性缺口、假报完整脚表或另设窄项绕过。仍被合同阻断时保留 INSUFFICIENT，
明确局部已证实范围与剩余输入/建模缺口；不把这种工具覆盖缺口改写为电气 FAIL 或要求改受保护符号来过门禁。

去耦清单只有一个由工具判定的收窄：自检失败的**唯一**原因是功能脚缺名，且每个缺名脚都在
`intent.devices` 中 `pinout_complete: true` 的官方脚表里声明了角色时，去耦按官方角色识别电源/回路脚，
缺名不改变清单，因此不加整网完整性缺口；这些脚列在 `pin_names_resolved_by_official_pinout`。
典型情况是 KiCad 运放符号（LM358、AD8494）的输出脚按库惯例不写名字。导出错误、归网/索引问题、
缺失 primitive 等任何其他自检问题，或缺名脚不在完整官方脚表中，仍保留整网缺口。DOC-Q01 照常报告缺名，
`self_check_passed=false` 的数据照常不能准出；I²C 清单不适用这一收窄。

普通无层次 C_SIGNAL 不再被当伪网；仅已支持 PSTWRITER 格式的 NC 名称可被候选识别。
没有告警或告警不在该网只能作辅助线索，不能独立证明 NC 一定不短路；遇陌生导出格式须
对真实 NC 标签与 No-connect 属性构建小样本/读图交叉验证，再允许依赖 pseudo_nets 排除。
DNP/DNI/DNF/NC 只按分隔词识别为不贴，不能误判 NCP1117 型号。实际装配 BOM 优先核实，
命名未标识也不证明一定贴装。

### 七、KiCad 网表（kicadxml）

    python3 scripts/parse_kicad.py 板子.kicad_sch -o db.json      # 自动调 kicad-cli 导出
    python3 scripts/parse_kicad.py 已导出.xml -o db.json          # 或用手工导出的 kicadxml

导出命令等价于 `kicad-cli sch export netlist --format kicadxml`；`kicad-cli` 路径可用
`KICAD_CLI` 指定。导出失败时把 kicad-cli 原文抛出，不吞错继续。

字段映射：

| db 字段 | 来源 | 说明 |
|---|---|---|
| `nets` / `pin2net` | `<nets><net name><node ref pin>` | 网名保持 KiCad 原样（含 `Net-(...)`、层次路径） |
| `pinname` | node 的 `pinfunction`，缺失回落 libpart 引脚名 | `~` 是 KiCad 的"无名"标记，按空处理，不伪造 |
| `pintype` | node 的 `pintype` 基础类型 | input→IN、output→OUT、bidirectional→BI、tri_state→TRISTATE、power_in/out→POWER、passive/free→UNSPEC、open_collector→OCL、open_emitter→OCA；未知类型保留原文大写，不静默当 UNSPEC |
| `parts[].prim` | `libsource` 的 `lib:part` | 相当于 Cadence 的 primitive 名 |
| `parts[].part` | MPN 类字段（MPN/Manufacturer Part Number/Order Code…），否则 libsource 的 part | 符号名不是订货码，仍需 DEV-D01 核身份 |
| `parts[].jedec` | `<footprint>` | KiCad 的封装库项 |
| `parts[].nc` | `<property name="dnp"/>` 或 VALUE 带 NC 标记 | `exclude_from_bom` 是 BOM 卫生标记，不作装配证据 |
| `ref2page` | 组件 `sheetpath.names` 对应 `design/sheet` 的编号 | 层次页按导出顺序编号 |
| `declared_pinname` / `declared_pintype` | libpart 的全部引脚 | 含网表里没出现的脚，用于官方脚表双向差集 |
| `export_meta` | `design` 的 source/tool/date | 用于核对导出版本与 PDF 是否同版 |

`libsource.lib` 为空而 `part` 已含完整 `lib:part` 时，仅在该完整身份精确命中非空
libpart 引脚声明、且原始身份未被声明时归一化，并在 `export_meta.libsource_normalizations`
留原值；不跨库猜同名符号。冲突的同身份/同脚声明拒绝导入。

**三件事必须分清**（与 Cadence 流程一致）：

1. KiCad 把带 No-connect 标记的引脚写成 `pintype="passive+no_connect"` 并单独放进
   `unconnected-(...)` 网。这类网登记为 `pseudo_nets`，引脚另列 `no_connect_nodes`——
   它是"图上声明不接"，仍需逐处核实该脚确实允许悬空。
2. 没有 NC 标记却落在 `unconnected-(...)` 网里的引脚是**真悬空**，保持真实单节点网，
   NET-A01 照常扫出，不被伪网络掩盖。
3. `nc` 是装配状态，与上面两件事无关；逐装配变体仍需 intent 声明。

检查器侧还有一层引脚名归一化（上划线、脚号装饰、序号、多功能合写），所以即使某个库
把引脚名写成 `EN_12`、`G1`，识别也不依赖解析器单点修正；低有效标记一律保留。

自检与 Cadence 解析器共用：重复归网、索引互反、缺失 libpart、引脚名覆盖率过低都会
失败退出。KiCad 的无源件引脚名多为 `~`，覆盖率天然偏低，核对时按 IC 引脚看，
不要用整体百分比代替逐脚核对。

#### KiCad 无名称引脚与原生类型

KiCad 解析另存 `native_pintype`，保留 passive/free/no_connect 等原始电气类型。
通过两个 CLI 共用的 `parse_netlist.self_check()` 检查时，只有原生 passive/free/no_connect 可无功能名；
其余引脚仍须命名。类型须覆盖全部 pin2net 节点且属于已知类型，未知/缺类型不能豁免。
纯 no_connect 类型也进入类型索引，不因剥离属性而丢失。
`pin_name_coverage` 分别列 required、named、missing_functional_pins、unnamed_connector_pins、legitimately_unnamed。
连接器（位号 J/P/CN 或库/型号关键字识别为端子、排针、JST 等）的触点按编号识别，库把它们定为 input 等类型却不命名时，列入 unnamed_connector_pins，不判解析完整性失败、不阻断去耦等下游清单；图面目检（DOC-V02）时引用该清单逐个记录。

符号名明确为 JUMPER、完整声明和导出同一组 2/3 个无名接点，且声明/原生类型均仅为
input/passive/free/no_connect 时，另列 `unnamed_jumper_contact_pins`，按接点编号识别。
声明原始类型保留在 `declared_native_pintype`；缺声明、具名功能脚、输出/电源脚及仅靠
位号推断的器件不豁免。此清单不证明铜桥实际导通；晶振/有源时钟的无名功能脚仍须核实。

不为无名称电阻/电容等补造 pinname，不将 passive 强行转成信号或电源脚。此处理仅修正
解析完整性判据；不替代原厂 pinout、极性、额定值和实际连接审查。Cadence/旧适配器没有
原生类型契约时保留原有名称覆盖率检查。使用 `parse_kicad.py` 默认严格检查；严格失败后的 `db.json` 用来定位缺口，不用 `--no-strict` 掩盖缺口。


### I²C外部端口与局部判据

`external-port:*`保持在拓扑清单、required_inputs和WAITING_EVIDENCE中，不伪装已建模endpoint。SIG-T02连接覆盖、SIG-D01地址/选件和SIG-C08掉电路径可依据已绑定原图、端口定义、适用工况和约束人工判局部PASS，不能仅因未建模整个外部系统强制判证据不足；如果这些局部判据自身仍无证据就保持INSUFFICIENT。此处理不自动给PASS、不证明外端电气合格，也不允许未审掉电源/地址冲突或隐藏连接通过。SIG-C01数量/上升窗口与SIG-C07电平/驱动仍对外端缺口阻止PASS；装配未知、未辨器件/角色/rail、跨SDA/SCL短接、搜索截断等其它拓扑gap在全部判据保持阻止PASS。


### 默认闭合铜桥与多焊盘跳线

库中 `JUMPER...NC_TRACE` 的 NC 指 normally closed 铜桥，不是“不装配”；解析只排除此限定词，独立 /NC、DNP、DNI、DNF 及原生 dnp 属性仍有效。型号不证明实际装配/导通。

`i2c_topology.components.<ref>.links` 可给多焊盘 jumper 的实际两脚连接对，例如 `[["JP7.1","JP7.2"],["JP7.2","JP7.3"]]`，须引用实际封装铜桥/原件。节点必须属于该器件，全部物理脚覆盖且连接对不重复。每对只在该装配明确 fitted=true、jumpers[ref]=closed 时导通；open 控制全部对断开，不表示独立切桥变体，后者需另建可表达其实际连接的输入/模型。未声明多脚模型仍有 gap，不根据 NC_TRACE 猜铜桥。

清单给每对唯一 edge_id，保留实际 ref/节点/边界，不跨供电轨把 SDA/SCL 合并。经铜桥到轨的偏置仍须沿实际 R→铜桥→轨人工复算；此扩展不自动给上拉等效值/电气 PASS。整链 C01/C07 未指定外端时按模块范围判适用性，不能把单个接收器自己的 VOL 与 VIL 比较当完整双端匹配；窄本体能力记录另绑明确判据/状态，保留 INT。

### 实例身份与符号缓存来源

实例 MPN/Value、BOM/采购字段、Datasheet 和官方订货信息证明实际物料；libsource、缓存 primitive 与库 ID
说明符号来源，不能仅因来源名称旧而自动认定采购型号冲突。复用符号须按实际 MPN 核完整物理脚、脚义、
封装字段与适用参数，记录兼容映射；不兼容仍判对应身份/引脚缺陷。实际实例采购字段与 Value/公差/额定
组合冲突保持 DEV-D04 FAIL，并按身份分支复核电气；来源名兼容不消除这些实际冲突。

### 阵列与多单元器件的内部通道

追踪信号跨越电阻/电容阵列、分体或多单元器件前，先从完整原生缓存的各 unit 引脚定义与
原厂内部连接图确认物理 pin 的配对、元件类型和该装配的导通条件，再与每个外部 pin/net
逐端对账。保存各通道的两端物理 pin、所属 unit、数值/公差、实际源端与接收端和引用位置。
网表只列各引脚的外部网络，网络邻居不证明器件内部通道；编号相邻或图上排布也不证明配对。
缺内部映射时保留具体路径 INSUFFICIENT，不凭编号顺序推断跨阵列的端到端连接。

按确认的通道核正常态、启动与单域掉电的源/接收端供电和应力；整改方案、影响分析、条件
计算及下游移交必须指向同一真实通道。发现配对错误时保留旧记录，逐条修正受影响路径与
任务，重新对账父子结果；不把记录修正当作硬件已改动或新增已发生故障。硬件可实现某个
方向/PIO功能不证明实际固件 pinmux 或模式，配置与默认高阻/恢复顺序仍需独立受控证据。

### 逐电源轨的监控要求与来源身份

PWR-T04 按需求决定哪些域必须监控。`supervision.schema_version=2` 可增加
`rail_requirements` 数组；每项只绑定一个实际 `net` 和一个 `intent.assemblies` 的 `state`，
写 `required`（真布尔）、`criterion`（明确监控要求或不要求的范围依据）、`citation`（受控出处），
以及 `identity`：

- `source_node`：该轨实际来源的物理节点；`source_role` 为 `external_supply` 或 `rail_driver`。
- `part`：实际来源器件的 `part`、`prim`、`value`、`jedec` 四字段快照（空字段保留空字符串）。
- `pin_name`：该来源脚的实际名称；`native_pintypes`：来源器件全部原生节点/类型的快照，无此原生索引时写空对象。
- `citation`：该来源角色与物理身份的定位出处。

声明须绑定当前 `input_sha256`，来源须在本装配实际已贴、位于该真实电源轨，名称与身份快照吻合。
外供源须有已核连接器类型/连接器触点身份，或明确书面外供角色加完整的原生 passive 触点结构；
有原生类型时，声明与导出节点/类型须完整一致且全部 passive。只靠 J 位号或把 IC 的 power_in/input
声明成外供源不成立。板内 `rail_driver` 必须匹配 PowerTree 实际回溯的来源节点；已有原生类型时须为输出。
这些资格只证明书面声明与原生结构相符，不证明出处语义真实、精确机械变体、额定值、阈值、动作或 UVLO；
原厂资料与受控需求仍须人工逐项核实，其他身份 OPEN 不因本声明关闭。

清单保留 `observation_gaps` 原始发现，另存 `scope_qualified` 与有效 `requirement`，按新上下文重建
清单摘要与计划。有效 `required=false` 只解除该轨×装配状态的未监测阻断；有效来源身份只解除该轨的
名称线索身份缺口。`required=true` 无监测、数组模式下未声明/UNKNOWN、缺出处、来源不存在/DNP、
身份不完整/错配、过期绑定或其他装配缺口仍阻止 PASS。重复声明不能任选一条，其他轨和状态不继承。
PWR-T04 仍适用且等待人工审查，声明不自动产生 PASS；已有监控器不豁免其他轨，内部 UVLO 不伪装为
SENSE/RESET 拓扑。没有 `rail_requirements` 的旧配置保持原扫描与阻断行为，`exclusions` 不排除轨覆盖。
