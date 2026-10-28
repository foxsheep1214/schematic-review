# 输入解析

> 读者：审查员。

把原理图网表和 PDF 读成 `db.json` 与可查的文本：各 EDA 的导出文件、字段映射、解析自检、PDF 提取与读图。
输入版本、覆盖与留档见[输入与覆盖](inputs-and-coverage.md)（2026-10-27 从那里拆出，内容未改）。

上游工具的 FAIL 要按具体对象与判据解释。若 SR 已独立验证同版原生源/XML、完整物理引脚、
缓存、实例身份与显式无脚角色，且自身解析自检通过，这些证据可关闭相应的窄输入资格判断；
不能仅因另一个工具的字段表示或几何误报再开同范围的待补证。保留上游原始 FAIL 和工具改进事项，
MPN/BOM资格、参数保证等仍各自审查。自身 self_check=false、缺脚、未解继承、身份或哈希不一致时
不能借此关闭 DOC-Q01 或准出阻断。

## 输入文件

| 文件 | 作用 | 获取方式 |
|---|---|---|
| 原理图 PDF | 页面结构、图形复核 | EDA 导出 |
| `pstxnet.dat` | 展开网表（核心数据源） | Cadence PSTWRITER 导出 allegro 网表 |
| `pstxprt.dat` | 器件实例清单（位号→原语） | 同上 |
| `pstchip.dat` | 原语库（型号/封装/参数值/引脚映射） | 同上 |
| `netlist.log` | **导出日志——免费证据，勿丢** | 同上，与三件套同目录 |

非 Cadence 工具链（PADS/Altium 等）提供等效网表导出即可，解析规则按格式改写；方法论其余部分不变。
KiCad 已随附解析器，见下文“KiCad 网表（kicadxml）”。

## 目标索引

- `parts`：位号 → {part（型号）, jedec（封装）, value（值）}
- `nets`：网络名 → [位号.引脚号, …]
- `pin2net`：位号.引脚号 → 网络名
- `pinname`：Uxxx.2A2 → "VCCIO2_VCC"（引脚功能名，藏在 `CDS_PINID` 字段，是识别 SoC 电源球/信号球身份的关键）

节点在第一个点处分开位号与完整源脚标识；例如 `RM1.1.2` 属于 `RM1`，脚标识为 `1.2`，不可截断或改名消除库存缺口。源脚标识含点不证明它就是厂商物理脚号；多单元/焊盘别名须有明确的原厂脚表对应，阵列内部支路仍按原件逐对取证。

## 格式要点

- `pstxnet.dat`：`NET_NAME` 行独占一行，下一行是带引号的网络名；随后 `NODE_NAME\t<refdes> <pin>` 逐节点；`CDS_PINID` 给出引脚功能名。
- `pstxprt.dat`：` <refdes> '<primitive>':;` 每实例一行；primitive 名或 VALUE 带 NC 标记 = 该实例不贴（实例级 NC 信息只在这里，库不含）。各家命名不同，`/NC` 与 `_NC` 后缀都在用（`0R/1%/NC`、`0R/1%_NC`），`is_not_populated()` 只在 NC 被 `/ _ - 空格` 或串首尾界定时才判为不贴——否则 `NCP1117` 这类型号会被误判成不贴。**该标志漏判会静默放大**：把不贴的 0R/上拉当成已贴，RST-E01/RST-E02 的默认态判定和 PWR-A02 的驱动判定都会跟着错。
- `pstchip.dat`：`primitive '<name>'; ... end_primitive;` 块内含 pin 名→PIN_NUMBER 映射（符号审计用）、PART_NAME/JEDEC_TYPE/VALUE。

## 解析实现

**直接运行脚本，不要照抄代码**：

```bash
python3 scripts/parse_netlist.py <allegro目录> -o db.json
```

### pinname 有两种布局——这是最容易踩的坑

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

### 伪网络自动识别

导出器会把"带 No-Connect 属性且无连线"的引脚汇集到一张名为 `NC` 的网。
它不是电气短路。脚本按 `C_SIGNAL` 是否带层次路径自动判别，结果放进
`pseudo_nets`（判别式详见 `automation.md`）。

### 输出索引

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


## PDF 处理

- `pdftotext -layout sch.pdf out.txt`（没有 pdftotext 时用 PyMuPDF：`python3 -c "import fitz,sys;print('\\f'.join(p.get_text(sort=True) for p in fitz.open(sys.argv[1])))" sch.pdf`），按 `\f` 换页符分页；每页抓 `File:` 字段得页面标题 → 实际页面清单（目录页常过期，不可信）。
- 单页渲染读图：`pdftoppm -png -r 150 -f N -l N sch.pdf page`（引脚图/表格细节用 `-r 200` 以上并裁剪局部）。
- 扫描件 datasheet（无文本层）必须渲染目检。
- **硬规则：提取出的表格出现列错位，必须渲染目检后才允许下结论。** 判别信号——同一行里出现本属不同列的值、
  水印文字插进数据行、单元格合并处的值漂到相邻行（常见于订购信息表的变体档位和电源时序表）。
- **旋转页坐标换算**（`Page rot: 90` 的图纸/datasheet 很常见）：用 `pdftotext -bbox` 拿到目标文字的
  `(x, y)`，注意该坐标已在旋转后的横向坐标系里（宽=页面 height）。映射到 `pdftoppm` 输出的像素：
  `px = x / page_h * img_w`，`py = y / page_w * img_h`。先按此裁一小块验证命中，再放大读图。
- 比对 PDF 生成时间与网表导出时间，防止拿旧图审新版。

## 其他 EDA 适配

本 skill 随附 Cadence/OrCAD 三件套与 KiCad 网表（见下文“KiCad 网表（kicadxml）”）解析器；下列是其他格式的适配路线，
不代表仓内已有对应脚本。适配后必须生成同一 db.json 约定并建立格式 fixture/覆盖自检。

- Altium：导出 EDIF/Protel 网表，按 `(` 分组解析。
- PADS：ASCII 网表 `*SIGNAL*` 段。
- 适配后按每条规则输入依赖确定覆盖范围，缺引脚名/类型/页映射不能宣称完整适配。

## 完整性与适用范围

解析器保留 `declared_pinname` / `declared_pintype`：来自符号 primitive 的完整脚表（含未连接脚），
不是官方封装定义。必须与 `pin2net` 及官方 pinout 双向差集，解析过的引脚覆盖率不等于物理脚覆盖率。
自检拒绝跨网重复物理脚、索引不互反、网络引用缺失器件、缺失 primitive 及导出日志 ERROR/中止。
严格模式自检失败时仍写出 `db.json`（`integrity.self_check_passed=false`）并以退出码 2 结束，可直接用它定位缺口；`--no-strict` 只把退出码改为 0。self_check_passed=false 的数据不能准出，`validate_review.py` 会将其列为阻断项。
缺日志仍需在输入一致性项记录，不能假定导出成功；确认是历史追加日志时分离本次导出记录另行留证。

严格失败先区分编号/归网丢失、功能名/类型覆盖不足、官方库存差集与导出中止；缺功能名不等于硬件断路，
官方未用脚允许浮空也不等于库存完整。逐物理对象用原生编号、官方角色、装配状态及实际路径记录局部事实，
全量 DOC-Q01/库存缺口独立保留。去耦和 I²C 清单的原生 PASS 仍遵守各检查器的完整缺口约定：已有局部
观察不能靠编辑清单、删完整性缺口、假报完整脚表或另设窄项绕过。仍被约定阻断时保留 INSUFFICIENT，
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

## KiCad 网表（kicadxml）

    python3 scripts/parse_kicad.py 板子.kicad_sch -o db.json      # 自动调 kicad-cli 导出
    python3 scripts/parse_kicad.py 已导出.xml -o db.json          # 或用手工导出的 kicadxml

导出命令等价于 `kicad-cli sch export netlist --format kicadxml`；`kicad-cli` 路径可用
`KICAD_CLI` 指定。导出失败时把 kicad-cli 原文抛出，不吞错继续。

- **版本**：kicad-cli 只能读不新于自身版本的原理图。KiCad 8/9 工程（文件头 `(version …)` 大于 20230121）
  在只有 KiCad 7 的环境里，用 `python3 scripts/install_kicad_cli.py --prefix <目录>` 从 Ubuntu 新版仓库
  解出一份私有的 KiCad 9 kicad-cli（不改系统、不需要 root 或 Docker），再 `export KICAD_CLI=<目录>/kicad-cli`。
- **KiCad 5 旧格式（`.sch`）**：各版 kicad-cli 读入后都没有器件，不能用。改用工程里 KiCad 5 导出的网表
  `.net`（s-expression），`parse_kicad.py` 直接解析，并按 libparts 补全引脚类型；先核对 `.net` 的位号集合
  与 `.sch` 的 `$Comp` 一致，不一致说明网表过期，须让设计方重新导出。kicad-cli 用 `--format kicadsexpr`
  导出的网表同样可读，与 kicadxml 解析结果一致。

字段映射：

| db 字段 | 来源 | 说明 |
|---|---|---|
| `nets` / `pin2net` | `<nets><net name><node ref pin>` | 网名保持 KiCad 原样（含 `Net-(...)`、层次路径） |
| `pinname` | node 的 `pinfunction`，缺失回落 libpart 引脚名 | `~` 是 KiCad 的"无名"标记，按空处理，不伪造 |
| `pintype` | node 的 `pintype` 基础类型 | input→IN、output→OUT、bidirectional→BI、tri_state→TRISTATE、power_in/out→POWER、passive/free→UNSPEC、open_collector→OCL、open_emitter→OCA；未知类型保留原文大写，不静默当 UNSPEC |
| `parts[].prim` | `libsource` 的 `lib:part` | 相当于 Cadence 的 primitive 名 |
| `parts[].part` | MPN 类字段（MPN/Manufacturer Part Number/Order Code…），否则 libsource 的 part | 符号名不是订货码，仍需 DEV-D01 核身份 |
| `parts[].jedec` | `<footprint>` | KiCad 的封装库项 |
| `parts[].datasheet` | 实例 `<comp><datasheet>` | 空、缺失或 `~` 记空字符串；不借 libpart 缓存链接，不按 URL/文件名推定型号或用途，链接与实际身份另核 DEV-D04；链接变更/删除进入复审 Diff |
| `parts[].nc` | `<property name="dnp"/>` 或 VALUE 带 NC 标记 | `exclude_from_bom` 是 BOM 卫生标记，不作装配证据 |
| `ref2page` | 组件 `sheetpath.names` 对应 `design/sheet` 的明确编号 | 不按顺序重编号，不从路径前缀推导页面 |
| `page_inventory` | 全部原生 `design/sheet` 的 number/name/tstamps，v1 | 包括没有功能器件的根页；页号可不连续，页面身份按真实编号和路径绑定 |
| `declared_pinname` / `declared_pintype` | libpart 的全部引脚 | 含网表里没出现的脚，用于官方脚表双向差集 |
| `export_meta` | `design` 的 source/tool/date | 用于核对导出版本与 PDF 是否同版 |
| `bom` | `read_bom.py db.json BOM.csv` 读入的装配 BOM：每个位号除位号、值以外的非空列（`parts`），每行都相同的列（`uniform_columns`），两边对不上的位号（`not_in_netlist` / `not_in_bom`），文件哈希 | 器件规格照用；BOM 里写的设计方计算值不用；位号对不上时按 DOC-Q01 核 |

`page_inventory.scope=native_declared_sheets` 时，DOC-V01 对库存每页唯一展开，
`coverage.pages` 必须全量列出并链接本页的 DOC-V01；空根页只要求图面目检，
不据此伪造电气对象或执行。没有原生 sheet 元数据的 XML，以及没有此字段的旧
Cadence/受限 db，只能声明 `component_pages_only`：按已有 `ref2page` 目检，
未知空页/根页须另核原图，不能猜页 1、补连续空页或以路径前缀建立虚构页。
声明存在但缺明确页号/路径、重复编号/路径/非空 tstamps，或组件路径超出声明范围时拒绝解析。
库存与定位进入新原生 db 的计划指纹；重建当前计划并逐页审查，不能迁移旧结果。

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

库中 `JUMPER...NC_TRACE` 的 NC 指 normally closed 铜桥，不是“不装配”；解析只排除此限定词，独立 /NC、DNP、DNI、DNF 及原生 dnp 属性仍有效。型号不证明实际装配/导通。

检查器侧还有一层引脚名归一化（上划线、脚号装饰、序号、多功能合写），所以即使某个库
把引脚名写成 `EN_12`、`G1`，识别也不依赖解析器单点修正；低有效标记一律保留。

自检与 Cadence 解析器共用：重复归网、索引互反、缺失 libpart、引脚名覆盖率过低都会
失败退出。KiCad 的无源件引脚名多为 `~`，覆盖率天然偏低，核对时按 IC 引脚看，
不要用整体百分比代替逐脚核对。

### KiCad 无名称引脚与原生类型

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
原生类型约定时保留原有名称覆盖率检查。使用 `parse_kicad.py` 默认严格检查；严格失败后的 `db.json` 用来定位缺口，不用 `--no-strict` 掩盖缺口。
