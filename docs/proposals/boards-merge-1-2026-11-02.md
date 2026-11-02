# 四块板合并步 1：解析、装配、供电与计划误报源（2026-11-02）

生产代码截止 `ce9d7a6`，基线 `0c4b52a6173cf2b92739268ab0744acfac772e10`；分支 `boards-program`。只修改本工作树，未 push。四条 lane 的发现、报告、原 XML/缓存均只读。`SKILL.md`、`references/shared/`、`scripts/guideline_criteria.py`、`scripts/stress_check.py` 无改动；未改另一会话的六条检查器数值判据，CLK-C01 只扩展选对象/所有权。

## 修法和归因

1. **原生字段和值**：解析器保留 fields、original_value、value_provenance，大小写无关的 Val 优先，记录字段、原文、literal-RKM/封装名解码及欧姆值。支持 0R、0R01、0R001、4K7、10R、1M 及 `R_0R_22.4A_0603`；识别限定封装后缀，无法解码为 unknown，不推作零欧或断路。未带字段的普通符号维持旧表示，避免无意义改变冻结输入。
2. **直流供电来源**：沿已装配 ≤1 Ω 电阻、电感、磁珠、保险丝、网桥追到稳压器实际输出或连接器，证据保存位号路径。未知阻值保留待核路径；有片内源时避免连接器掩盖来源，但未确认跳线选路仍保守处理。纠正 SiC437 VOUT sense/SW 与 TPS65295 VDDQSNS 造成的源识别，不能把 sense 当输出或升压输入。
3. **DNP**：读 KiCad 属性及 DNP/不贴字段，尊重 false；不把 excluded_from_bom 当 DNP。实际装配视图排除其网络参与、浮空脚、上拉/钳位路径，DB 保留原图。计划记录 UNFITTED_PARTS，报告单列“未贴装器件 N 个，已排除”。移除 DNP 后暴露的真实单端网仍提示，因此 NET-A01 不保证单调减少。
4. **默认工作态**：接口等候选类型补 idle/active 默认集；计划诊断明确“默认状态，未经需求确认”，不把推断当产品需求。
5. **晶体对象**：每只已装配无源晶体均有 CLK-C01，独立于 USB/CLOCK 所有权；已有逐对象项去重，供电有源振荡器不套无源补项。RDIMM 的 Y2 在 USB-J9 所有权下仍生成 `CLK-C01.Y2`；没有增加 CL 数值判法。
6. **反复出现的其余误报**：保留总线索引语义，排除真实串联分段/DNP 备选、TDI/TDO/BCLK/LRCLK/PS/PL 等合法不同网；拉电阻只向实际电源方向取电压，不把 `20V_EN` 当20V供电；EN 默认态穿低阻/网桥核实实际驱动；避免矩阵 B01/C01/E01 被当 BJT、理想二极管控制器被当分立管、RESET 驱动控制输入被当复位断路。同一器件同功能并脚、确知开漏告警脚与桥输出不笼统判多驱动。保留 KiCad 原始脚名，另外解 `P_{GOOD}`/`V_{IN}` 等标记。对准确型号的 MAX3421 GPIN、TPS2372 AUTCLS、TXU0204BQAR 允许不用输入、93LC66B ORG、KSZ9031 外部供电 LDO_O 采用有边界的许可条件；普通输入（含 U36.13）不豁免。FT4232H MPSSE 经 TXU0204/0304 的名字线索降为 INFO，明确声明 I²C 时照常检查。PoE/二极管返回域留待核 CANDIDATE，不要求跨隔离短接。

根因按独立机制计数，非按发现行数：`rule_not_enforced 5`（字段取值、低阻供电、DNP装配、工作态完整性、晶体逐对象覆盖）；`knowledge_wrong 10`（封装阻值、sense/源优先级、格式化脚名、近似网名、偏置电源身份、驱动与器件分类、输出类型、型号限定NC许可、条件回流/复位去向、合法非传统位号）。新增种子基础设施不另算电气根因。

## before / after

口径为同一板原 XML、冷扫 `findings` 的所有非 INFO 行，含 FINDING/CANDIDATE，不是缺陷数。before 使用原 DB；after 重新解析同一 XML，以检验字段/DNP 修复。未对物理接线作修改。Antmicro库继续沿用原取板时的 `--no-strict` 导入（原生符号信息缺口保存在DB中），不把容错导入当完整原生校验通过。输入 XML、DB 和计划指纹及逐规则数保存在同名 JSON。

| 板 | 冷扫总行数 before → after | 已归因误报行数 before → after | DNP 器件数 |
|---|---:|---:|---:|
| Thor | 168 → 150 | 61 → 1 | 109 |
| STM32H7 HDMI | 81 → 64 | 58 → 3 | 57 |
| RDIMM DDR4 | 145 → 28 | 132 → 8 | 41 |
| Kria K26 | 244 → 72 | 191 → 6 | 27 |
| 合计 | 638 → 314 | 442 → 18 | 234 |

误报计数依据四个 findings.json 的 false_alarm，以同规则、物理脚/网络/位号对应原错误内容；不是将所有剩余行认定为正确。原归因文件共451条 false_alarm，其中9条未落在本次冷扫口径。after 的简单身份重叠为26行，经内容复核排除8行：Thor F116 错误20V上拉已消失；STM F51–F54 的DNP限流路径已消失，实际TVS窗口线索保留；STM F32与Kria F200/F201/F202（后两条同一行）已改为明确的条件回流核查，不再断言失地。上述条件回流仍未完成厂商模型验证，不能据消除旧误报宣称回路合格。

| 规则 | Thor | STM32H7 HDMI | RDIMM DDR4 | Kria K26 |
|---|---:|---:|---:|---:|
| DOC-A04 | 0 → 0 | 0 → 0 | 7 → 0 | 0 → 0 |
| DRV-A03 | 3 → 0 | 3 → 0 | 0 → 0 | 6 → 3 |
| NET-A01 | 0 → 23 | 0 → 19 | 5 → 10 | 185 → 34 |
| NET-A02 | 6 → 0 | 8 → 0 | 1 → 0 | 3 → 0 |
| NET-A04 | 0 → 0 | 0 → 0 | 1 → 1 | 0 → 0 |
| NET-A06 | 3 → 3 | 2 → 4 | 3 → 3 | 1 → 0 |
| NET-A07 | 32 → 35 | 25 → 7 | 2 → 1 | 15 → 14 |
| PRO-E02 | 21 → 21 | 11 → 11 | 1 → 1 | 1 → 1 |
| PWR-A01 | 7 → 13 | 7 → 9 | 12 → 2 | 5 → 2 |
| PWR-A02 | 38 → 0 | 11 → 3 | 100 → 2 | 11 → 3 |
| PWR-A03 | 0 → 0 | 1 → 1 | 1 → 1 | 3 → 2 |
| PWR-A06 | 1 → 1 | 0 → 0 | 1 → 1 | 0 → 0 |
| RST-A01 | 16 → 13 | 9 → 8 | 6 → 6 | 4 → 5 |
| RST-A02 | 1 → 1 | 0 → 0 | 0 → 0 | 0 → 0 |
| RST-A04 | 1 → 0 | 0 → 0 | 4 → 0 | 7 → 5 |
| RST-A06 | 1 → 0 | 0 → 0 | 1 → 0 | 0 → 0 |
| SIG-A02 | 30 → 30 | 0 → 0 | 0 → 0 | 2 → 2 |
| SIG-A03 | 8 → 10 | 4 → 2 | 0 → 0 | 1 → 1 |

部分计数上升来自正确解析 DNP 后实际单端网、完整值/脚名识别后新增对象；未逐条裁决的新行保持未归因。DOC-A04 消除的是 RDIMM 的 0V6/1V0/…等合法测试位号误判。带已核实资料的完整计划扫描 after 分别为150/61/28/70（合计309），另列以免和冷扫比较混用。

输出：`~/.cache/sr-boards/_merge1/before/<id>/` 与 `after/<id>/`。`before-original/`、`after-v2/` 为本次冻结副本；所有临时脚本、日志、回归中间件在 `/tmp/codex-work/boards-merge-1/`。after 四板 parse/audit/cold/candidates/decisions/candidate-scan/merge 全部退出0，空状态候选均为0。before Thor候选扫描失败，STM/Kria决定与候选扫描失败，RDIMM通过；before 的 merge fallback 不冒充完整候选计划通过。

## 回放输入与计划可生成的边界

严格输入门仍保留。重新解析后，对旧 intent 补的是发现到的供电轨**身份**，无新增电压范围；原需求电压不改。重新用原PDF核验资料文件；复用旧 resolution 中确已核实的准确料号、页引文、文件哈希，Thor五种标题分类歧义经实际标题核对补 kind_reason，没有改通用分类器。

修复后候选ID/成员变化，回放决策去掉退休候选与已归属/DNP手加项，新增候选按原图拓扑接纳，附未确认说明。Thor补原图中EEPROM、PD OR/VCONN及模块控制的覆盖归属，RDIMM把Q12并入既有启动电路；均为拓扑推断，功能边界/状态未经需求确认。Thor五个共享USB支持器件的端口候选合为USB-PORT-SUBSYSTEM（C120/C121/C136共享证据），连接器接口仍分别保留，没有放宽生产代码所有权门。逐板 `decision-replay-notes.json`、`rail-identity-replay.json` 记录调整。完整计划生成只证明工具可达，不等于需求已确认或逐项电气审查通过。

复现主链（四个id替换，真实资料审计/决策路径取各板输出目录；所有临时文件仍应放 /tmp/codex-work）：

```sh
python3 scripts/parse_kicad.py <source/netlist.xml> --no-strict -o <after/id/db.json>
python3 scripts/lint.py <db> --intent <intent-cold.json> --plan-json <plan-cold.json> --json <lint-cold.json>
python3 scripts/circuit_candidates.py <db> --intent <intent-cold.json> --datasheet-audit <datasheet-audit.json> --json <candidates.json>
python3 scripts/circuit_decisions.py <intent.json> <candidates.json> --db <db> --write
python3 scripts/lint.py <db> --intent <intent.json> --datasheet-audit <datasheet-audit.json> --candidates <candidates.json> --plan-json <plan-candidates.json> --json <lint-candidates.json>
python3 scripts/lint.py <db> --intent <intent.json> --datasheet-audit <datasheet-audit.json> --candidates <candidates.json> --merge-plan <plan-candidates.json> --plan-json <plan.json> --json <lint.json>
```

## 题列真缺陷保留

| 原归因 | after证据 | 自动判定边界 |
|---|---|---|
| lane1 F058 D54 3.6V TVS用于5V线上 | D54准确料号TPD1E0B04DPYR、PWR_BTN网络、PRO-E02仍在，5条逐对象项 | 提醒核窗口，未自动算5V/3.6V违规 |
| lane2 F49 D22 9V TVS用于15V PD | D22 PTVS9V0S1UR,115、USB_VBUS、PRO-E02仍在 | 同上；15V取已有审查/受控模式，不由网名猜测 |
| lane2 F91 C139/C140 10V MLCC用于该PD轨 | Val=1u、MPN=C1005X6S1A105K050BC保留；D22证据点名两电容；各24条逐对象项 | 10V准确料号额定依原厂证据，自动耐压冲突尚未实现 |
| lane3 F146 R199 5mΩ值与0Ω料号冲突 | Val=0R005→0.005Ω与CR1206-J/-000ELF并存，未归零；供电路径与2条逐对象项保留 | 保留事实冲突，未自动解料号阻值并判缺陷 |
| lane3 F147 U19/U20 PAC1954同地址 | 两者.4=SCL_3V3、.5=SDA_3V3、.6=3V3_SYS；各11条逐对象项 | 网表定位完整，地址表解码冲突仍人工核 |
| lane4 F219 U36.13 CMOS输入NC | NET-A07明确点名U36.13，11条逐对象项 | 没有被允许不用输入型号策略豁免 |

上述六个器件组全部保留或可定位。额外 miss：Y2的CLK-C01逐对象项已补，计算/实测负载与起振裕量仍未自动闭环。检查项数量表示可定位，不能替代真缺陷检出。

## 新增种子与剩余缺口

`mutators.py` 新增5类型、7位点，登记在 `boards-merge1.json`/README，受控运行记录见 `boards-merge1-results.json`：TVS工作电压2处、MLCC耐压1组、分流电阻MPN冲突1处、I²C地址冲突1组、CMOS不用输入悬空1处，以及复用D-XTAL-LOAD的Y2负载1处。已坏原板采用显式合格参数合同的配对基线，合同不是虚构可订购MPN；Y2基线保留原电容，变异为1uF。位点真实存在且拓扑保持，可用 `--boards-cache` 重跑，不入库第三方大网表。

新7位点目标自动层3处（两TVS均是检索/审查线索，另1处NET-A07），另4处只可计划定位；没有把any/pointed算目标检出。数值耐压、料号冲突、地址冲突、晶体CL等检测仍是后续缺口。lane3 M02 PAC1954被归ADC/ANA-C03的功能归类意见不具确定的网表电气故障变换，未伪造seed。

剩余18条已归因误报：Thor 1条MAX16013使能时序；STM 3条LAN8742A内部VDDCR/STM32H7 LDO-only的VDDSMPS/PMOD互斥使能输出；RDIMM 8条涉及隔离PoE源返回、桥符号输出、TPS2372并联RTN与外部供电LDO_O；Kria 6条涉及PoE源返回、PCA9306 EN/VREF2大阻偏置、Q8/Q9资料驱动识别（带审核资料的hot扫描后二者消失）。这些需要准确模式、片内回流或功能事实，不能按网名/二极管/NC全局豁免。单次且未确认的PCA9306偏置、MAX16013时序、PMOD动态OE，以及监测型PWR-A06、特定去耦/隔离/自举角色留在本报告；不凭单例扩大知识规则。

## 门禁与提交

各项均有测试和变异，逐项全套pytest/changed变异通过后提交：

| 项 | commit | pytest通过 | changed变异全杀 |
|---|---|---:|---:|
| 字段/阻值 | ad1f674 | 2444 | 9 |
| 低阻供电 | bbc8cae | 2452 | 22 |
| DNP | c9ff22b | 2460 | 94 |
| 默认状态 | 685d163 | 2474 | 98 |
| 晶体对象 | 7c1c75e | 2476 | 66 |
| 重复语义/拓扑误报 | 345529f | 2500 | 49 |
| 真实板种子 | 8fe4775 | 2506 | 4 |
| 脚名与限定许可/条件回流 | ce9d7a6 | 2516 | 37 |

每轮另2 skipped。共新增29个代码变异；379是含重复选择的执行次数，不是独立变异数。unit列全部KILLED，contract列非门禁。最终典型电路203 DETECTED/185 FIXED/14 KNOWN_FALSE_ALARM，无运行错误/未分类/新增漏报；KiCad当前合同195/195字段一致。历史冻结合同保留，解析事实改变通过native-fields-v1/boards-merge1-v1登记新合同；r03真实DNP单端网、逐晶体项及实际EN默认态导致检查项386→414，其余来源不重写旧答案。

外部已安装ASG共用层与本SR原本不匹配（基线pytest即1 failed），本轮禁止改共用层。为可重复集成校验，测试增加可选 `SR_ASG_SHARED_ROOT`，默认仍检已安装ASG；全绿使用ASG真实历史提交5e7c969的共用文件（git show提取到临时目录，不从SR复制），共享SHA256为 `73d8d1474702a3ede4bdb38763f5c1e777ac713585e0a370bd37d0afa3064523`。这是匹配版本集成通过，不能声称当前已安装ASG已同步。

```sh
TMPDIR=/tmp/codex-work/boards-merge-1 PYTHONDONTWRITEBYTECODE=1 SR_ASG_SHARED_ROOT=/tmp/codex-work/boards-merge-1/asg-5e7c969 python3 -m pytest scripts/tests -q -p no:cacheprovider
TMPDIR=/tmp/codex-work/boards-merge-1 python3 evals/mutation/run.py --changed --tier unit
TMPDIR=/tmp/codex-work/boards-merge-1 python3 -B evals/seeded_bench/run.py --offline --boards-cache /Users/skyfend/.cache/sr-boards --compare /tmp/codex-work/boards-merge-1/seeded-before/results.json --out /tmp/codex-work/boards-merge-1/seeded-final
TMPDIR=/tmp/codex-work/boards-merge-1 python3 -B evals/detection/run.py
python3 scripts/check_ledger.py
```

种子最终254位点/180目标自动线索/0运行错误；原247逐位点目标集合检查无退化，原177自动检出不变。`--compare`本身仅展示按类型增减，另按board/defect/site验证未丢目标；没有拿聚合总数掩盖位点退化。历史D-CAP-VR=15/17低于既有绝对门限的基线问题仍在，未挪门限。detection先执行默认完整命令，再复用同一最终生产代码的seeded-final、typical-8、replay-8结果生成RESULTS.md（包含新增7位点，保留输入SHA）。结果只是检出度量，未签署设计准出。
