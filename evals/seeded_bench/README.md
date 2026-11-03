# Seeded Bench：真实电路植入缺陷的自动层快检

把盲审缺陷库里**能用网表表达**的缺陷类型（D-GND-PIN、D-RAIL-SPLIT、D-CAP-POL、D-TVS-STUB、
D-EN-FLOAT、D-FLY-MISS/REV、D-OPTO-R/PU、D-I2C-PU、D-LED-R、D-CAP-VR、D-REF-ANNO、D-BOM-WS）
程序化地植入多块真实公开电路的 db，逐位点跑 SR 冷跑（lint + 计划），统计：

| 列 | 含义 |
|---|---|
| 自动检出（目标规则） | 植入后新增、且点名该位点的目标规则发现 |
| 位点有任意新发现 | 目标规则或其他规则（如 NET-A01）点名该位点的新增发现 |
| 计划有逐对象检查指向 | 计划里有逐对象检查点名该位点，即专家审查至少会被引到这里 |

它只衡量**自动层**，不衡量专家审查，也不证明任何电路合格。语料是已在往轮校准中评过分的公开电路，
不能放入待盲审的电路。位点是“若这样改就是缺陷”的假设，个别位点在电气上可能不构成缺陷，
结论要回到具体发现核对。

## 在校准循环中的位置

盲审一轮要 3～10 小时，只能得到 2～3 个缺陷的检出信号；本基准一次几十秒，覆盖几十个位点。
建议每轮先跑本基准：

1. 改规则/检查器前后各跑一次（`--compare`），自动检出率只能升不能降，基线发现数的增量要逐条核对是否误报；
2. 本基准已稳定检出的缺陷类型，盲审出题时少植入，把名额留给需要判断的缺陷（D-FLOOR、计算、条款类）；
3. 盲审漏检的自动类缺陷，先在这里复现成位点，再修。

## 运行

```sh
python3 -B evals/seeded_bench/prepare.py --cache <缓存目录>
python3 -B evals/seeded_bench/run.py --cache <缓存目录> --out <输出目录> [--sut <另一个 SR 副本>] [--compare <旧 results.json>]
```

`prepare.py` 按 `corpus.json` 的固定 commit 拉取源仓库、用 kicad-cli 导出网表并解析；第三方文件只留在缓存目录。
`strict: false` 的板子按 `strict_note` 记录的原因用 `--no-strict` 解析。

## 语料扩充记录（2026-10-18）

语料加入 `evals/typical_circuits` 的 32 块开源单模块板（与原有继电器板重复的一块不重复收），共 39 块，
夹具直接用该基准随许可证保存的 KiCad XML（`fixture` 指向 `.xml` 时 `prepare.py` 直接解析）。
扩充后按同一缓存比较：修正前 SR（7c122a3）与当日修正后检出相同（209/247，漏检位点集合完全一致，无回退）；
补上 KiCad 极性电容 1 脚为正的库约定、正电源按来源追踪认定、I²C 段跨 ≤1 kΩ 串阻、`OSC` 关键字只匹配整词后，
自动检出 223/251（89%），极性电容反接 3→11/13，I²C 上拉缺失 11→13/17。其余漏检位点均有 NET-A01 等其他规则点名。


## 离线运行与基线闸门（2026-10-19）

语料中随仓库保存网表的板子（`evals/typical_circuits` 的 32 块）不需要拉取和 kicad-cli，可直接离线跑：

```sh
python3 -B evals/seeded_bench/run.py --offline --out <输出目录> --gate evals/seeded_bench/baseline-offline.json
```

`baseline-offline.json` 冻结每类缺陷的自动检出数（当日 203 个位点检出 179）。任一类低于基线或出现运行错误时退出 1。
规则修改可以提高检出；要降低某一类，须在同一提交里说明漏检原因并更新基线。
本闸门约 90 秒，不放进单元测试，在改规则或检查器前后各跑一次。


## 设计准则正反例扩充（2026-11-02）

本轮从 [Top 50报告](../../docs/proposals/criteria-top50-examples-2026-11-02.md) 加入8类种子，对应8条准则；另复用G03-037/038的极性/耐压操作器，共10条。这些是**自动层漏报探测**，不新增检查器，不修改BASIS；C/D规则可能只在计划中引导人工判断。

| 种子类型 | 准则 / BASIS 目标规则 | 操作及位点条件 | 自动 / 位点 | 任意 / 指向 |
|---|---|---|---|---|
| `D-USB-BULK` | G01-029 / SIG-C05 | 仅在命名VBUS/VUSB直连地的电容改1000µF/50V；不跨限流器找电容，Sink角色/外部限流仍须人工确认 | 0/4 | 0/0 |
| `D-LDO-COUT` | G03-003 / PWR-C04 | 对明确AMS1117/LM1117/AP2112/MCP1700/XC6206身份线索且OUT/VOUT脚匹配的器件移除全部直接对地输出电容；远端电容及准确变体最小Cout待人工核 | 0/1 | 0/1 |
| `D-I2C-PU-HIGH` | G04-017 / SIG-C01 | 保留真实上拉拓扑，将该段全部上拉改10MΩ；沿用i2c_pu候选，板级电容/速度及片内上拉仍须确认 | 0/13 | 0/12 |
| `D-I2C-PU-LOW` | G04-018 / SIG-C01 | 同一段全部上拉改1Ω；比对最弱器件IOL/VOL保证值 | 0/13 | 6/12 |
| `D-CAN-TERM-SHORT` | G04-032 / SIG-C03 | 在已装配IC的CANH/CANL物理脚网络间加导线短接，旁路含跳线的端接；无需假设端接跳线闭合 | 0/2 | 0/2 |
| `D-ISO-BRIDGE` | G04-040 / PRO-D02 | 对有两独立地的光耦或明确ADuM/ADM2483/ADM3251/CA-IS37身份线索器件合并两地；无身份的一般多地IC不入选 | 0/4 | 0/4 |
| `D-XTAL-LOAD` | G04-078 / CLK-C01 | 只改真实无源晶振两端的既有对地负载电容为1µF；不能凭OSC网名发明晶振 | 0/5 | 0/4 |
| `D-XTAL-SHARED` | G04-082 / CLK-C01 | 复制真实晶振驱动IC及全部脚/电源/配置，两个振荡器共享原晶振；复制也可能引入其他输出争用，旁报不计目标检出 | 0/2 | 2/2 |

以上全部目标自动检出为0，明确登记为“当前漏报”；任意新发现与计划指向按原运行器定义统计，不能替代本条检出。新增共44个位点；全部32板共247个位点、自动177、错误0。既有203个位点与修改前记录完全一致。

按上面的`--offline --out`用法运行，并将TMPDIR指向已创建的`/tmp/codex-work/<任务>/`；不需要下载新语料。每个操作器只选已贴装器件，每板每类最多4个位点。源码器件身份仅用于选位点，不代替人工核对准确MPN和工作模式。

[本轮受控摘要](criteria-examples-2026-11-02.json)保存全部类别汇总、输入哈希与10类的逐位点结果。旧离线闸门要求D-CAP-VR为17，本分支修改前后均为15，因此旧`--gate baseline-offline.json`仍失败；这是已有基线差异，本轮未调低基线，也没有引入既有类别退化。漏报数是种子位点的统计，不是现场失效率或人工SR检出率。

## 8 类种子的自动检出（2026-11-02）

上一节登记的 44 个漏报位点已全部由新的自动扫描规则报出，自动检出 177→221/247，既有 203 个位点逐条不变，32 块板未植入时的发现数不变。
C/D 规则由审查员判定，工具不下结论，所以新增的是 A 规则（`scripts/board_scans.py`），`BASIS` 映射到同一批准则，种子目标改为“新 A 规则或原 C 规则”。

| 种子类型 | 新规则 | 判据与出处 | 自动 / 位点 | 仍须人工确认 |
|---|---|---|---|---|
| `D-USB-BULK` | SIG-A05 候选 | 有 USB 证据的板上，VBUS/VUSB 网直挂电容合计 >100 µF（USB PD 表 4.7 注 1、Type-C 表 4-3） | 4/4 | 端口角色（Source 按表 4-2）、前级限浪涌、非附着态 10 µF（SIG-C05/PWR-C13） |
| `D-LDO-COUT` | PWR-A07 候选 | 线性稳压器输出网没有接地电容，经磁珠/电感也到不了（TI SLVA115A） | 1/1 | 手册是否允许无电容；容量、ESR、有效值（PWR-C04） |
| `D-I2C-PU-HIGH` | SIG-A04 候选 | 并联上拉 >118 kΩ：标准模式 1 µs、Cb 只算 10 pF（UM10204 §7.1 式 (1)、表 11） | 13/13 | 实际模式与总线电容（SIG-C01）；此上限内的偏大仍靠人工 |
| `D-I2C-PU-LOW` | SIG-A04 候选 | 并联上拉 <(V−0.4 V)/20 mA（§7.1 式 (2)、表 10）；轨压读不出按 1.8 V | 13/13 | 最弱器件 IOL（SIG-C01）；此下限内的偏小仍靠人工 |
| `D-CAN-TERM-SHORT` | SIG-A06 疑点 | CANH/CANL 同网或被 ≤1 Ω 电阻跨接（TI TCAN1042 §10.2.2.1、SLLA270 §4） | 2/2 | 端接位置与总等效负载（SIG-C03） |
| `D-ISO-BRIDGE` | PRO-A05 候选 | 型号或已核验角色为数字隔离器，两侧地同网或被 ≤1 Ω 电阻、磁珠、电感连通（TI SLLA284G §1） | 4/4 | 是否确有隔离需求、工作资格（PRO-C03）；光耦没有地脚名，归 PRO-D01 的计划项，本语料无光耦位点 |
| `D-XTAL-LOAD` | CLK-A01 候选 | 两端负载电容串联等效 >100 pF（ST AN2867 §3.3 的公式；100 pF 是外包络，TI SNLA290 §7 建议 8–20 pF） | 5/5 | 与准确料号 CL 相符、Cs、ESR、起振裕量（CLK-C01） |
| `D-XTAL-SHARED` | CLK-A02 疑点 | 无源晶体两端都接两颗以上 IC 的振荡脚（TI SNLA387 Clock Source） | 2/2 | 手册是否明确允许共用；外部时钟模式（CLK-D01） |

这些判据是外包络：超出才报，落在包络内的不等于合格，具体数值仍由审查员按对应 C 规则算。
`resonare-lcc` 的 `VBUS` 是逆变器直流母线，直挂 249.6 µF，曾被 SIG-A05 误报，因此要求板上有 USB 证据；已有单元测试和变异锁住。

## 四板合并 1 的配对种子（2026-11-02）

登记 **5 个新类型、7 个位点**，其中 `D-XTAL-LOAD` 复用已有类型。来源为已完成归因的四块板，
元数据见 `boards-merge1.json`；第三方 XML 只读用户缓存，不进入仓库。
原板已有错误时，`Mutation.baseline` 保存仅修正目标缺陷的合成参数合同，比较相同电压合同下的正确/错误两侧；
不把有缺陷的原板当干净负例，也不伪造可订购物料。`contract` 记录准确 MPN、厂家条款或额定出处。

```sh
TMPDIR=/tmp/codex-work/boards-merge-1 python3 -B evals/seeded_bench/run.py --offline \
  --boards-cache ~/.cache/sr-boards --compare <before/results.json> --out <after目录>
```

先创建上述临时目录。除目标轨的明确电压合同外，其余新发现供电网只登记拓扑身份，电压保持未知。
基线或变异运行错误退出非零；错误不能算漏报或命中。

| 类型 | 来源位点 | 合同与操作 | 自动目标提示 / 位点 |
|---|---|---|---:|
| D-TVS-VRWM | Thor D54；STM32 D22 | 合成合格 VRWM 合同换为 TPD1E0B04DPYR 的 3.6 V、PTVS9V0S1UR 的 9 V；分别固定 5 V、15 V 工作合同。统一收纳原归因的 D-TVS-VRWM-BELOW-PD 别名 | 2/2 |
| D-MLCC-RATING-BELOW-PD | STM32 C139/C140 | 合成 25 V MLCC 换准确 TDK C1005X6S1A105K050BC（10 V），保留 15 V 合同和 TDK 资格记录，两颗作为一个位点 | 0/1 |
| D-SHUNT-MPN-CONFLICT | RDIMM R199 | 合成 5 mΩ 合同仅把 MPN 换为 CR1206-J/-000ELF；保留 5 mΩ 值及 Kelvin 连线 | 0/1 |
| D-I2C-ADDRESS-COLLISION | RDIMM U19/U20 | 同一 SCL/SDA、准确 PAC1954 身份下，U20 ADDRSEL.6 从 GND（0x10）移到 VDD（0x1F），U19 保持 0x1F | 0/1 |
| D-CMOS-UNUSED-IN-FLOAT | Kria U36.13 | 由 GND 改 NC，只改未用输入，输出和 DAP 的 NC 保持 | 1/1 |
| D-XTAL-LOAD（已有） | RDIMM Y2/C190/C193 | 将既有 18 pF 电容改 1 µF，记录 ABM8G 的 CL=18 pF；不新造晶体 | 0/1 |

TVS 的目标命中是原有 PRO-E02 **窗口复核提示**，不是自动完成 VRWM 违规的电气判定。
MLCC 额定、分流电阻 MPN、地址冲突与晶体负载仍有自动层缺口；其位点/合同已保存，不能把其他规则指向当目标检出。
现有 247 个位点逐位点比较无退化，仍为 177 个目标提示；新增 7 个位点有 3 个目标提示、0 个运行错误。
受控结果见 `boards-merge1-results.json`，包含逐位点自动提示、其他提示和计划指向。

## 合并 2B：外部端点、ADC 与 PMIC 输出覆盖种子（2026-11-02）

`boards-merge2b.json` 登记4块已归因板的来源，第三方网表仍只读缓存。`--boards-cache` 同时加载 merge1 与 merge2b。
新4类各1个位点，均使用显式配对基线：

| 类型 | 真实物理位点 | 网表变换 / 目标规则 |
|---|---|---|
| D-EXTERNAL-INJECTION-BYPASS | Amalthea J1.28/U1.43 `/PICO` | 去掉合成10kΩ串阻，恢复原直连；SIG-C08 |
| D-POWER-BRANCH-BYPASS | connect-programmer K1 VBUS/F1 | 0Ω跨接真实保险丝；PRO-C04/C01/C05 |
| D-ADC-SHUNT-RANGE | bq27441 U1.SRP/SRN、R6 | 10mΩ改1Ω；ANA-C03 |
| D-PMIC-OUTPUT-COUT | kimchi U4.55 MUXSW、C113/C54 | 合成22.22µF名义基线换原1.22µF；PWR-C04/C09 |

这些C规则仍由审查员计算判定，**计划指向不算自动检出**。运行器新增 `planned_targets`，只列点名位点的目标规则；
原 `auto` 仍只计算新扫描发现，`pointed` 仍为任意规则指向。注入源5V/关机钳位0.3V/1mA、ADC的1A/20mV
均明确是合成测试合同，不冒充AT86RF215或BQ27441的保证值；保险丝动作能量和22.22µF全环境有效值仍需独立核验。
PMIC的11–33µF窗口来自ROHM BD71847AMWV Rev003 p110 Table5-36，原1.22µF名义点已低于下限。

2B 最终固定版实测：既有 254 位点逐点保留、目标自动 225→225，新增 4 类/4 位点均有目标 C 计划（自动 0），合计 258 位点/225 自动/0 错误。数据见 `boards-merge2b-results.json`；不把计划覆盖算自动检出。首轮曾暴露自定义 `Oscillator_SMD` 的无源晶体误识别与 PMIC `-E2` 种子漏选，修正后全量重跑，未改原种子来隐藏丢失位点。


## 合并步 3 的四个受控位点

`boards-merge3.json` 只登记已归因公开板的来源、commit 和许可证，原始电路不复制进仓库。`--boards-cache` 会把这四个位点加入既有语料：

- Xerxes U7：同物理脚表的 5.5 V 四通道 TVS 换成 3.3 V TVS，正常窗固定为合成的 4.75–5.25 V；要求四个独立 PRO-E02 对象。自动计数只代表逐通道取证提示，工作窗/残压仍须专家判定。
- MP2 QA1：原生脚名在两侧均为空，完整 CRST030N10N 官方 G/D/S 表是唯一脚义输入；仅变异侧将真实栅极断开，目标 DRV-A03。
- flyback-ac-dc U3：完整 EL817 A/K/E/C 表贯通后断开 R4 LED 供电；要求仍有 FEEDBACK-OPEN 的逐对象单故障问题，不能冒充自动判坏。
- isolated-flyback C12：额定 16 V 改为 4 V，分析侧刻意不提供 VIN/VCC 窗；合同外部真值取 TI SNVSA03E p6 的 VIN=24 V、ICC=20 mA、VCC=6.47–8.52 V 条件。装配状态显式锁定，避免因装配未核先覆盖成 unknown 而掩盖零伏预判；分析必须保留 unknown 和电源依赖，不能给零伏/PASS。

`contract_guards` 单独记录通道对象、反馈故障问题及未知应力预判，不计为自动发现。`--compare` 同时按 `(board, defect, site)` 拒绝任一既有自动目标丢失，新增位点不能抵消旧位点退化。原始板本身的其他缺陷保留，配对基线不表示整板正确。


## 合并步 4 的四个受控位点（2026-11-02）

`boards-merge4.json` 只登记来源、commit 和许可证。四个位点分别对应合并步 4 的第 1、2、3、7 项：

- pslab R29（D-FRACTION-POWER-NO-PASS）：47Ω 跨合成 5 V 窗（约 0.59 W），配对基线额定 2W，变异侧改为 `1/16W 5%`。新 guard `guard_no_pass` 要求 DEV-C01 行存在且不预判 PASS；不计自动检出，过载结论仍由审查员给出。
- openrefmic R21（D-MIDPOINT-GROUND-NO-PASS）：配对基线把 R20/R21 分压中点命名为 VMID，变异侧用原名 VGND。沿用 `guard_no_proposal_pass`：中点不得当 0 V，必须保留 AMP_VDD 依赖。
- gnssdo U19/R63（D-BIAS-FEED-REMOVED）：删去 PCA9306 VREF2/EN 的 200k 偏置电阻，弱驱动由 INFO 变为无驱动，目标 PWR-A02 自动报出。
- hdmi-mipi J6.38（D-NC-FLAG-REMOVED）：去掉 FFC 空脚的原生 no-connect 标记，目标 NET-A01 重新报出；配对基线里该脚只有 INFO。

实测：旧 262 位点逐点保留、自动目标 227→229（新增 bias/NC 两位点），合计 266 位点/229 自动/0 错误；两个 no-PASS 位点只算 guard 通过，不算自动检出。


## 合并步 5：224 条漏问核对后仍漏的六个位点（2026-11-02）

`boards-merge5.json` 登记六块已归因板的来源。合并步 5 在当前 SR 上把 224 条漏问逐条重跑，仍漏且能用网表表达的挑出六类各落一个位点，全部用原板作配对基线，登记为**当前漏报**（目标规则自动 0）：

| 类型 | 位点 | 网表变换 / 目标规则 |
|---|---|---|
| D-HBRIDGE-RESET-UNSAFE | faderbuddy U2 DRV8837 | nSLEEP、IN1 接 VCC，IN2 接地：MCU 复位期间 H 桥仍驱动电机；RST-T04 |
| D-ISO-BRIDGE | kicad-pmod_rs485 U1 ADM2582E | 已贴 0R 跨 GND 与隔离侧 /GND3；PRO-D02、PRO-A05 |
| D-ISO-BRIDGE | 12v-1a-isolated-flyback U1 变压器 | 已贴 0R 跨次级 GND 与初级返回 /E；PRO-D02 |
| D-MCU-ADC-DIVIDER | esp32-industrial-io R18 | 0–10 V 输入分压下臂 10K→100K；ANA-C03 |
| D-REVERSE-PMOS-DS | leviathanext Q1 | 防反接 PMOS 漏源对调；PWR-T05 |
| D-LDO-STARTUP-COVERAGE | capacitive-soil-sensor C6/U2 | SE5218 输出电容 2.2µF→1000µF；PWR-D03 |

实测：旧 266 位点逐点保留，合计 272 位点/229 自动/0 错误；六个新位点自动目标均为 0。ADM2582E 位点只旁报 PWR-A03，PRO-A05 的隔离器型号表不含隔离 RS-485 收发器，记为后续修法。其余仍漏项多数要合成合同（源窗、器件保证值、需求），见合并步 5 报告的漏问表。
