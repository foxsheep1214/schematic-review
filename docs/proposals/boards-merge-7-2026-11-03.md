# 合并步 7：HOLD_UP 与 SIGNAL_PROTECTION 电路类型、层次网名叶名当词、穿串联电阻找被保护脚（2026-11-03）

用户 2026-11-03 “按建议执行”，落实合并步 6 提案第六节的 1–5 点。分支 `boards-merge7`，基于 main 18f5474。SKILL.md 和设计准则条款都没改。共用层只改了 `references/shared/vocabulary.json` 的 `circuit_types`，加了两项，准则库随之重建到 1.7.2；ASG 侧由主会话同步。

## 一、词表与准则库 1.7.2（ae0d5ba）

`circuit_types` 在 `ISOLATION` 之后、`DEBUG` 之前加了两项：`HOLD_UP`（掉电保持）和 `SIGNAL_PROTECTION`（信号端口保护）。重建命令：`guideline_criteria.py build --from HardwareWiki/原理图设计规范 --library-version 1.7.2`（HardwareWiki 只读），`check` 通过。

- 353 条准则与 1.7.1 逐条相同，变的只有 `library_version`、`vocabulary` 和指纹。
- 共用层指纹 `3e50da53d0b5` → `48c61bb3a5e7`。
- `guideline-criteria.json` sha256 `b12edc03…`，`vocabulary.json` sha256 `86c84fb5…`。
- 其余共用文件一个字节没改，`shared-layer.md` 也没改。

步 1 和步 2 合成了一次提交：词表对齐测试要求 catalog 与词表的电路类型一致，单改词表这条测试就红。

## 二、catalog 框架（同 ae0d5ba）

| 类型 | 域 | 挂的检查项（都是已有 ID） | 要点 |
|---|---|---|---|
| HOLD_UP 掉电保持 | PWR | PWR-C18、PWR-T05、PWR-C13 | 储能能否把下游保持到需求的中断时长（保持时间 vs 下游欠压门限）、充电浪涌、上下电时序 |
| SIGNAL_PROTECTION 信号端口保护 | PRO | PRO-C01、PRO-C05、PRO-C08 | 钳位窗口对被保护脚绝限、串联限流件的脉冲功率与压降、PTC/保险的 I²t |

**挂不上的要点。** 词表里没有直接对应的检查 ID，所以没挂；这些由所属器件的行承担：

- 保持二极管的反向电压和正向电流、储能电容的耐压和纹波电流：器件级 DEV-C01/DEV-C02 与降额行（被候选收为成员以后，这些行跟着该电路走）。
- 钳位窗口的逐器件比较：PRO-E02，见第四节。
- 保持期间与下游 UVLO 的配合：并在 PWR-C18、PWR-T05 的问法里，没有单独的 ID。

**PRO-C08 加了前提 `FUSE_PART`**：电路里没有保险丝或 PPTC 就不问。纯电阻限流的端口不问保险丝的 I²t。

**和任务书不同的一处。** 任务书写“状态表、描述表不加”，实际加了：

- `CANDIDATE_STATES`：HOLD_UP 是 startup/run/power-down，SIGNAL_PROTECTION 是 run/fault。
- `FRAME_QUESTIONS`：两类各一句描述。

原因是 `test_catalog` 要求描述表覆盖每个类型，lint 遇到状态为空的候选会报错。不加这两张表，测试就过不了。`EXTERNAL_INTERFACE_TYPES` 按任务书没有加。`catalog.BASIS` 没加映射：现行准则里没有条款点名这两个类型。

## 三、候选生成（9224568，RULES_VERSION 2026-11-03.7a）

### HOLD_UP 候选

1. 认法：两端二极管，阳极接电源网，阴极上有 ≥10 µF 储能，并有变换器把阴极当输入锚点。
2. 不认的情况：
   - 阴极另有二极管馈入（那是多源 OR 合）。
   - 有晶体管跨在 A–K 上（理想二极管或开关）。
   - 阳极经入口链接直通连接器（那是输入保护）。
3. 成员：二极管加储能电容，网为 input/storage。

合并步 6 F20 加在 POWER_PROTECTION 里的裁剪特例删了：前提 `INTEGRATED_SWITCH`、`MULTI_SOURCE`，以及对应的 SUBJECT_REQUIRES 和 plan_circuits 分支。保持电路改由 HOLD_UP 框架承担，这个框架本来就不问 eFuse 和双源切换。

### SIGNAL_PROTECTION 候选

1. 认法：从连接器信号脚出发，过串联限流件（保险，或 >1 Ω 的电阻；读不出阻值的也算，零欧不算），沿途有对地钳位，最终到 IC 信号脚。
2. 二极管只按正向穿，搜索最多 3 跳。
3. 不认的情况：
   - USB 连接器。
   - 电源脚、急停脚和地脚。
   - 通道上的器件已被其他非跨电路候选持有。
4. 按连接器出一个跨电路候选 `SIGNAL_PROTECTION-<连接器>`，IC 本身不作成员。

### 78 块板上的变化（c3 对 before）

| 指标 | before | 之后 |
|---|---:|---:|
| 冷扫非 INFO 行 | 2271 | 2271 |
| 计划项 | 37572 | 37572 |
| 真缺陷定位 | 172/172 | 172/172 |
| 真缺陷自动检出 | 37 | 37 |
| 候选：新增 / 消失 / 变化 | — | +17 / 0 / 0 |
| 未归属器件 | 8090 | 7886 |

新增的 17 个候选：

- 公开板 15 个 SIGNAL_PROTECTION，分布在 7 块板上：
  - anthc J3
  - stm32h7 J7
  - zigbee J2
  - stm32-plc J1/J8/J14/J15/J16
  - hackrf P1/P2/P22
  - pionix cb-eval J4/J5/J7
  - satya J5
- 校准板 2 个：HOLD_UP-D201、SIGNAL_PROTECTION-J601。

公开板上没有出 HOLD_UP。stm32-plc 的 DI/AI 通道（PTC 加齐纳）就是合并步 6 第六节第 5 点说的那些通道，现在归入 SIGNAL_PROTECTION。全链路退出码逐板不变；完整合并成功的板，前后都是 19 块。

## 四、PRO-E02 穿串联电阻找被保护脚（89ccb35，F11）

**怎么找。** 钳位所在网没有 IC 脚时，从该网出发往外找：

- 可以穿正向二极管，最多 2 只；只能穿一颗电阻或 PTC/保险。
- 不跨地网，地名脚不算被保护脚。
- 找到的 IC 脚列为被保护对象，每只脚出一条核对行。

**核对行写什么。** 钳位器件和 IC 脚都在精确表里时，按电阻压降比较；不在表里就写“读手册”。精确表在 `protective_clamps.CLAMP_RATINGS` / `PIN_LIMITS`，出处都核过原件：

- SMAJ30CA 48.4 V@8.3 A、SMAJ33CA 53.3 V@7.5 A，10/1000 µs（ST DS1251 Rev 15 p2 Table 2）。
- SN65HVS883 IPx 和 V24 绝限 36 V（TI SLASEE6 p4 §6.1）；IIP-LIM 最大 4 mA（p5 §6.5）。

**校准板 F11 报出的核对行**（D611–D618 每只一条，以 D611 为例）：

> 核对：钳位 48.4 V（ST SMAJ DS1251 Rev 15 p2 Table 2：IPP 8.3 A，10/1000 µs）经 D621（二极管压降不计）、R611 1.2 kΩ 到 U601.3(IP0) 绝限 36 V（TI SLASEE6 …）：钳位高出脚绝限 12.4 V，需注入 ≥ 10.3 mA 才在电阻上降掉；手册输入限流 ≤ 4 mA 时电阻压降 ≤ 4.8 V，脚电压约 43.6 V，仍高于绝限

D602（F10，FIELD+）也找到了 U601.14(V24)，并给出数字。F10 是否适用线-线浪涌仍需人判，本步没有改它的结论。

**78 块板（c4 对 c3）。** 非 INFO 2271 → 2271，计划 37572 → 37572，真缺陷 172/172。PRO-E02 行 336 → 336，其中 47 行文字有变化：

| 变化 | 行数 | 说明 |
|---|---:|---|
| 改写 | 34 | 同一对象，换成新的核对文字 |
| 新找到被保护脚 | 5 | cellkeeper |
| 去掉误列的地脚 | 8 | jetson-nano D12、switch-v4 ×6、copperpilot D12 |

## 五、名称线索：层次网名的叶名当词（b183b97）

**边界取法。** 不是任何 `/` 都当词边界，只认网名最后一个 `/` 之后的叶名：`_LEAF = r'(^|[:_-]|^NET:.*/(?=[^/]*$))'`。不把所有 `/` 都放开，原因有两个：

- 路径里的图纸名会误中，例如 `/Debugger/…`、`/CSI/…`、`/ADC/…`。
- 脚的复用功能名会误中，例如 `PB2/BOOT1`、`P7/SCL/D5`。

变异 M1430（任何 `/` 都当边界）和 M1431（叶名不当边界）都被杀。

逐类型结果：在 before 的 78 块板加校准板上，比较新旧正则命中的名称，新增命中逐条看过。

| 类型 | 新增命中的板 / 名称 | 由无到有的板（新 REQ-Q07） | 处理 |
|---|---:|---|---|
| POWER_CONVERTER | 8 / 14 | — | 放开（/VOUT、/Power/FB 等，都真） |
| POWER_PROTECTION | 4 / 8 | — | 放开（/Power/ILIM、/OVP） |
| ANALOG | 8 / 24 | — | 放开（/AIN1、/Microcontroller/ADC0_x、VREF） |
| STARTUP | 4 / 5 | — | 放开（/BOOT0、ESP0/BOOT） |
| I2C | 17 / 45 | crazyflie、zigbee、feather-rak3172（另 m2-smart-iot、faderbuddy 已有 REQ-Q07.I2C） | 放开（/SCL、/SDA） |
| RF | 5 / 6 | nabucasa yellow | 放开；greenmobi 的 /MCU/Ant_CLC 存疑，没有翻转计划项 |
| AV | 10 / 93 | — | 放开（/CSI/CSI2_*，叶名是真的 CSI 信号） |
| DEBUG | 10 / 28 | faderbuddy（DBG_LED，调试灯） | **不放开**，维持原式 |
| INDUSTRIAL_DI | — | — | 维持合并步 6 的 `[:_/-]` |
| DC_48V、DC_24V、AC_MAINS、POE_PD、VEHICLE_28V、SHIP_AC | 0 | — | 统一用叶名式，无变化 |
| HOLD_UP、SIGNAL_PROTECTION | — | — | 新类型直接用叶名式 |

HOLD_UP 的线索只认 `HOLD_UP` 或 `24V_HOLD` 这类电压加 HOLD 的名字，不认 SPI flash 的 HOLD 脚（M1402 守着）。

实测（c5 对 c4）：

- 78 块板：非 INFO 2271 → 2271，计划 37572 → 37576（+4 行 REQ-Q07：crazyflie、zigbee、feather-rak3172 各一行 I2C，nabucasa 一行 RF），真缺陷 172/172，候选文件逐板字节相同。
- 校准板：没有变化。
- 回放：rh-ad8495 三例的 `/02_tc_amp/VREF_2V5` 命中 ANALOG，各多一行 REQ-Q07.ANALOG（67→68、67→68、63→64），新建约定 `boards-merge7-v1`，195/195。

## 六、校准板 before/after

**输入冻结。** 本步进行中，设计记录被另一会话改过：

- 05:45 改了需求输入，需求 sha 对不上缓存 intent。
- 06:47 起重画原理图，schematic.pdf 暂缺。

为了前后用同一份输入，before（18f5474）和 after 都用缓存里的冻结副本 `review/intent-*-frozen.json`：需求 sha 改为当前 `c7728e55…`，去掉 materials.schematic_pdf。设计记录本身没碰。

| 项目 | 18f5474 | 终版 |
|---|---:|---:|
| 冷扫非 INFO 行 | 19 | 19 |
| 合并后非 INFO 行 | 19 | 19 |
| 计划检查项 | 808 | 826 |
| 候选电路 / 未归属器件 | 15 / 70 | 17 / 45 |

**计划项按规则的变化：**

| 规则 | 变化 | 原因 |
|---|---|---|
| PWR-C18、PWR-C13 | 各 +3 | 来自 HOLD_UP |
| PWR-T05 | +1 | 来自 HOLD_UP，对象 C201 |
| PRO-C01 | +2 | 来自 SIGNAL_PROTECTION |
| PRO-C05 | +1 | 来自 SIGNAL_PROTECTION |
| PRO-C08 | 不问 | DI-PORT 没有保险，FUSE_PART 前提不满足 |
| PWR-C23 | 3 → 9 | F20 裁剪特例删除后，DI-FIELD-PWR、DO-HS 两个 POWER_PROTECTION 电路重新问到 |
| PRO-C07 | 2 → 3 | 同上 |

PWR-C23 与 PRO-C07 回到合并步 6 之前的问法。D201 本身已经不在 POWER_PROTECTION 里，F20 不复现。

**条目状态：**

- F11：8 只 DI 钳位都报出核对行。
- F20：POWER_PROTECTION 里不再有 D201，HOLD_UP-D201 成立。
- M02：仍为 0。
- 其余条目与合并步 6 终版相同。

## 七、门禁

| 提交 | pytest | mutation --changed 18f5474 | 回放 | seeded | 78 板 |
|---|---:|---|---|---|---|
| ae0d5ba | 2787 | 128 全杀 | 195/195 | 274/231，0 退化 | 2271/37572/172 |
| 9224568 | 2791 | 168 全杀 | 195/195 | 同上 | 2271/37572/172 |
| 89ccb35 | 2795 | 220 全杀（M888 锚点随代码改写重锚） | 195/195 | 同上 | 2271/37572/172 |
| b183b97 | 2797 | 222 全杀 | 195/195（boards-merge7-v1） | 同上 | 2271/37576/172 |

- pytest 都在 `SR_ASG_SHARED_ROOT` 指向本树共用层快照（`~/.cache/sr-boards/_merge7/asg-shared`）下运行。ASG 还是 1.7.1，所以 `test_asg_holds_the_same_shared_layer` 指向真实 ASG 时预期失败，要等主会话同步。
- 每次提交前都跑了 `evals/detection/run.py` 和 check_ledger。

## 八、没做的和原因

- **F05**：按用户决定，不加 intent 的 TVS 字段，继续由审查者在结果里关闭。
- **F10**：FIELD+ 是否适用线-线浪涌是需求问题，needs_human，本步只让它多了 V24 的数字。
- **DEBUG 的名称线索不放开**：唯一新增的“由无到有”是调试灯。
- **精确表只收了读过手册的三种器件**（SMAJ30CA、SMAJ33CA、SN65HVS883）。其余器件的核对行写“读手册”，不臆造数字。
- **公开板上没有 HOLD_UP 实例**，形状判断只由校准板和单元测试守着。
- **PRO-E02 只穿一颗电阻或 PTC**，不穿 RC 网络或两级限流，任务书要求只穿一级。

## 九、提交

ae0d5ba（词表、准则库 1.7.2、catalog）、9224568（候选）、89ccb35（PRO-E02）、b183b97（叶名词边界）、5b5d06c（F05 决定）、23b8a97（校准板登记），以及本文档、台账和架构表所在的收尾提交。都没有 push。
