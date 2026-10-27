# Typical Circuits：真实单模块开源板上的发现级基准

SR 要覆盖各种单模块原理图，而 `kicad_replay_bench` 只冻结计划结构（检查数、NA 数），不看 SR 实际报了什么。
本基准取 47 块 GitHub 上的开源 KiCad 6–10 板：33 块单功能小板（MCU 最小系统、USB-C 受电、
buck/buck-boost、LDO、锂电充电与保护、I²C 传感器、电平转换、电机/舵机驱动、继电器与光耦、RS-485/CAN、
运放前端、负载 ADC、音频功放、LED 恒流、以太网 PHY/控制器、USB-UART、定时电源开关），加 2026-10-19 补的
9 块功率/隔离/多页板（230 VAC 反激 ×2、LCC 谐振无线充电、DRV8323 三相桥、16S BMS、隔离 I²C、理想二极管、
PD 输入升压充电、I²S DAC），再加 2026-10-26 补的 5 块（推挽隔离电源 ×2、PD 受电 + 升降压充电、外部看门狗 ×2），冷跑 SR，
**逐条人工审读每个 FINDING 与 CANDIDATE**，按下面三类冻结在 `cases.json`：

| 类别 | 含义 | 运行时状态 |
|---|---|---|
| `expected` | 真实问题或有效审查线索（例如 LAN8720 板 PHY 复位脚标 `RST`、PMOD 脚标 `RSTn`，复位实际没接通） | 仍须报出，否则 MISSED |
| `known_false_alarms` | 现在仍报、但对本板是误报，`why` 写原因 | 跟踪；修好后变 FALSE_ALARM_GONE，需移到 `fixed_false_alarms` |
| `fixed_false_alarms` | 曾经误报、已修 | 不得再出现，否则 FALSE_ALARM_BACK |

SR 报出、却不在任何一类里的条目记为 UNCLASSIFIED，基准失败，所以每条新发现都会被人读一次。INFO 不判。
匹配按规则号加 detail 子串。

## 运行

```sh
python3 -B evals/typical_circuits/run.py [--case <id>] [--show] [--sut <另一个 SR 副本>] [--json out.json]
```

每例：`parse_kicad.py` 严格解析（失败时 `--no-strict`），再 `lint.py --log <空日志>`。约 30 秒。
`scripts/tests/test_typical_circuits.py` 在单元测试里跑同一基准。

## 建立过程（typical-circuits-v1，2026-10-18）

首次冷跑（SR @7c122a3）报 FINDING 89 条、CANDIDATE 65 条，并有 1 块板（CMoy）解析即被拒收。逐条审读后修正：
多单元运放共享电源脚被判重复归网；厂商库连接器（`OLIMEX_Connectors:`、USB-C、电源插座）和电池认不出，
经保险丝/二极管/开关/跳线/防反 MOS/滤波电阻进板的电源被报无驱动；`K` 位号的 16 脚 USB-C 座被当继电器；
光耦输出驱动三极管基极、无方向库的 IC 脚驱动栅极被报悬空；继电器线圈经电阻供电时续流二极管认不出；
手册 NC/DNC 脚、带下划线或斜杠的位号、输入型连接器触点、LDO 的 EN 接 IN 被报问题等。
修正后 FINDING 12 条，全部为真实线索（标签只落在一个脚上）；之后补上 KiCad 极性电容 1 脚为正的库约定，又在 LM386 功放板上查出一处真实缺陷：C4（100µF）正极接地、负极接 +9V，CANDIDATE 71 条均有审读理由，
已知误报 3 条（连接器 NC 豁免需要受控库身份）。

## 扩充（typical-circuits-v2，2026-10-19）

按固定 commit 拉取 9 块 KiCad 6+ 板，kicad-cli 10.0.6 导出，SR @a547907 冷跑后逐条审读。新报出 93 条：
45 条归 `expected`、48 条归 `known_false_alarms`、0 条 `fixed`；随后修正自动层，48 条全部转为 `fixed_false_alarms`，
并补上 VDD 接地漏检（见下）。要点：

- **VIPer22A 反激板有 3 处真实缺陷**：U1.4 VDD 与 VDD 储能电容 C10.1 同在 GND1（VDD 短接到源极地）、
  C10.2 悬空（NET-A01 报出）；`+12V_1`、`+12V_2` 两个电源标签只各挂一个输出电容和光耦偏置/TL431 分压，
  没接到输出网 `Net-(J2-Pin_1)`，反馈环开路（PWR-A01 报出两条）。VDD 接地冷跑原本没有规则报出，现由 PWR-A02
  “电源脚落在地网”报出：非地名的原生 `power_in` 脚落在地网为 FINDING（VDD/VCC/V* 名）或 CANDIDATE（REGIN 等按手册
  可接地的脚，bms-c1 U4.36 即为此类）；地名脚、负端脚（VSS/VEE/-Vin）、散热焊盘和 power_out/passive 脚不报。
- **新发现的误报模式**（已修，记为 fixed）：NET-A02 对 `+/-` 差分对、字母序兄弟（GHA/GHB/GHC、AUX_A…E）、
  RX/TX 收发对、同名双路稳压器（FB_12V/FB_5V）报“疑似分裂”，moteus 18 条、bms-c1 2 条、resonare 7 条、pd-liion 1 条；
  修正：只比较叶名（层次路径不构成相似证据），并豁免 `+/-` 差分对、序号/字母序兄弟、RX/TX、MISO/MOSI、SCL/SDA
  等收发对与同名双路；seeded_bench 的 D-RAIL-SPLIT（`VCC_3V3` ↔ `VCC_3V3_1`）仍报。
  DRV-A03 不穿过串联栅极电阻找驱动与下拉（bms-c1 并联 MOS ×8）；修正：栅极网上只有栅极和一颗 ≤1 kΩ 串联电阻时，
  穿一级到另一端找上/下拉。DRV-A04 把 BMS 静态开关管、理想二极管的 PNP 对+PMOS 当成半桥开关节点
  （bms-c1 ×8、ideal-diode ×4）；修正：半桥证据要求对管是 MOSFET、源极在该节点、漏极接电源轨或储能母线，
  本管不是高边；resonare/moteus/pd-liion 的真实开关节点候选保留。
- 第 10 块候选 Unicamp-Odhin/PatchLogic（ECP5 + DRAM + HDMI）在固定 commit 上 627 个网里 477 个是单节点、
  DRAM 电源脚挂在自动命名网上，原图未布完，673 条报出无法审读，未收。
- 仍缺：带 PFC/QR 控制器 + 同步整流控制器的离线电源（公开 KiCad 里没有）、独立看门狗板、SN6501 隔离 DC-DC；
  ULX3S、LibreSolar MPPT、etherkit Si5351 等好板是 KiCad 5 `.sch`，kicad-cli 10 仍打不开，需 GUI 转换后再收。

## 扩充（typical-circuits-v3，2026-10-26）

补 v2 记下的缺口。检索范围：GitHub 仓库与代码搜索（KiCad 文件 + 器件型号），以及 GitHub 之外的厂商参考设计与
技术文章（Power Integrations DER 报告、ST SRK1001 评估板、SN6501 应用文章、MAX6369 看门狗应用笔记），只收许可证
明确且不含 NC 条款、能用 kicad-cli 10 导出网表的板。按固定 commit 收 5 块，SR @5fa41d3 冷跑后逐条审读，
新报出 83 条全部归 `expected`，另有 5 条误报修正后记为 `fixed`（suntastic 的跳线供电 3 条改报 CANDIDATE 后仍归 `expected`）：

- **kxkm-bmu-v2**（GPL-3.0）：VPS8505 推挽隔离电源 + 隔离 I²C + INA237 电池监测。
- **zenn-main-controller**（MIT）：SN6501 推挽隔离电源 + AMC1311 隔离放大器。真实断线 12 条：子页的层次标签
  `HV_IN_+`、`OUTN/OUTP` 和踏板信号在根页没有接上。
- **usb-pd-power-manager**（CERN-OHL-P-2.0）：HUSB238 PD 受电 + BQ25672 升降压充电 + TPS63070。
- **rt-ihu**（BSD-2-Clause）：双 MCU 飞控，STWD100 外部看门狗 + 仲裁。`+1V2_SEC` 只由 U38 FPF2001 供电而 U38 值为 DNI；
  `ARB_BATT` 是自定义电源符号，板上和连接器都没有来源，U11–U20、MAX14930 的 VDDA 脚和 U39 因此无供电。
- **suntastic**（Apache-2.0）：TPL5010 看门狗定时器 + 负载开关的低功耗电源管理板。`GPIO_DONE` 全局标签只出现一次，
  U9 ON 脚无驱动。

修正的扫描误报（单元测试 `test_typical_circuits_v3.py`，变异 M722–M725）：

- 三脚选择焊盘跳线（公共端 C，选 A/B）：馈电追溯只穿两端件，供电脚被报“所在轨无驱动”（FINDING）；
  现在两路都算上游，改报“经跳线供电”的 CANDIDATE，核装配状态（suntastic JP16）。
- NET-A02 网络名分裂：同一晶体管的端子名对（G/S、G/D、D/S、B/E、B/C、C/E，usb-pd `VLDO_VIN2_EN_G/_S`）和嵌在
  一个词里的收发对（rt-ihu `PRI_DCAN1RX/TX`）不再算拼写分裂；`MOTOR_ENABLE/ENABEL` 这类真分裂仍报。
- NET-A06 网络只有输入：RF 扼流圈等无源连接件（磁珠、保险丝、电感、跳线、NTC、电阻）的库脚类型为 input 时，
  同样视作该网的馈入（rt-ihu PA 的 VCC1 经 L6/L24 供电）。

未收：
- 带 PFC/QR 控制器 + 同步整流控制器的离线电源仍没有许可证明确的 KiCad 源文件：TSAC-DCDC（UCC28740 + UCC24610）
  仓库无许可证；DER 报告、SRK1001 评估板等厂商参考设计只有 PDF，且不授予再分发许可。
- ULX3S、LibreSolar mppt-2420-hc 等 KiCad 5 `.sch` 板仍需 GUI 转换后再收。

## 覆盖与局限

- 只测自动冷跑层的发现，不测计划、保证值核对、专家审查或报告。
- 这些板是能工作的公开设计，`expected` 多是审查线索而不是确认缺陷；缺陷检出率见 `evals/seeded_bench`
  （同一批板子按缺陷类型程序化植入）。
- KiCad 5 旧格式 `.sch` 的板子 kicad-cli 7/10 都不能导出，未收；KiCad 8+ 新格式自 v2 起用 kicad-cli 10 导出。

| 用例 | 类别 | expected | known | fixed |
|---|---|---:|---:|---:|
| rp2040-stamp | MCU minimal system (RP2040) | 1 | 0 | 3 |
| esp32-c3-devkit-lipo | MCU + LiPo charger + buck | 2 | 0 | 13 |
| rvpc | MCU (CH32V003) retro PC | 0 | 1 | 7 |
| fusb302-breakout | USB-C PD sink | 4 | 0 | 7 |
| powercb-usbc-ldo | USB-C input + LDO | 0 | 0 | 1 |
| tps5430 | Buck converter | 2 | 0 | 2 |
| stepbubodc01 | Buck-boost converter | 0 | 0 | 1 |
| soldered-liion-charger | Li-ion charger (TP4056) | 7 | 0 | 8 |
| soldered-bq24295-charger | Li-ion charger + 5V boost (BQ24295) | 5 | 0 | 5 |
| soldered-liion-charger-protection | Battery protection (DW01 + FS8205A) | 11 | 0 | 13 |
| piicodev-tmp117 | I2C sensor (TMP117) | 0 | 0 | 1 |
| piicodev-ens160 | I2C sensor (ENS160) | 0 | 0 | 1 |
| bme280-dspace | I2C sensor (BME280) | 0 | 0 | 1 |
| pmod-bme280 | I2C sensor PMOD (BME280) | 0 | 0 | 1 |
| soldered-txb0104-level-shifter | Level shifter (TXB0104) | 0 | 0 | 1 |
| makerverse-motor-driver-2ch | Motor driver H-bridge (TC78H660) | 0 | 0 | 2 |
| piicodev-servo-driver | Servo/PWM driver (PCA9685) | 2 | 0 | 3 |
| soldered-relay-1ch | Relay + opto + flyback diode | 0 | 0 | 4 |
| esp32-4ch-relays | 4 relays + ESP32 + USB-C | 10 | 2 | 0 |
| isolated-serial-adapter | Isolated RS-485/RS-232 (ADM2483) | 23 | 0 | 19 |
| han-to-rs485 | RS-485 transceiver | 2 | 0 | 3 |
| mcp25625-breakout | CAN controller + transceiver (MCP25625) | 3 | 0 | 0 |
| soldered-can-mcp2518 | CAN-FD (MCP2518FD + ATA6561) | 0 | 0 | 3 |
| bioamp-exg-pill | Op-amp biopotential front-end | 0 | 0 | 1 |
| makerverse-loadcell-hx710c | Load-cell ADC front-end (HX710C) | 0 | 0 | 0 |
| lm386-amp | Audio amplifier (LM386) | 0 | 0 | 1 |
| cmoy-headphone-amp | Headphone amp (op-amp CMoy) | 0 | 0 | 0 |
| led-al8860 | LED driver (AL8860) | 0 | 0 | 1 |
| led-lm3404 | LED driver (LM3404) | 0 | 0 | 2 |
| ethernet-pmod-lan8720 | Ethernet PHY (LAN8720A) | 4 | 0 | 2 |
| soldered-w5500 | Ethernet controller (W5500) | 3 | 0 | 19 |
| makerverse-nano-power-timer | Power timer (TPL5110-type) | 1 | 0 | 2 |
| usb232r02 | USB-UART (FT232) | 0 | 0 | 5 |
| flyback-viper22a | AC-DC flyback (VIPer22A, 230 VAC to 12 V) | 4 | 0 | 0 |
| flyback-uc3844 | AC-DC flyback (UC3844 + discrete MOSFET) | 2 | 0 | 0 |
| resonare-lcc | LCC-S resonant wireless charger TX+RX (120 W) | 7 | 0 | 7 |
| moteus-c1 | BLDC controller (DRV8323 + 3-phase bridge) | 23 | 0 | 18 |
| bms-c1 | 16S battery management (BQ76952) | 5 | 0 | 18 |
| easyiso | Isolated I2C/Qwiic (ISO1640 + isolated DC-DC) | 1 | 0 | 0 |
| ideal-diode | Ideal diode / reverse protection (4 ch) | 0 | 0 | 4 |
| pd-liion-charger | USB-C PD input + boost + Li-ion charger (LTC3769 + LTC4000) | 5 | 0 | 1 |
| pcm5102a-dac | I2S DAC (PCM5102A) | 0 | 0 | 0 |
| kxkm-bmu-v2 | Isolated push-pull DC-DC (VPS8505) + isolated I2C + battery monitor (INA237) | 4 | 0 | 0 |
| zenn-main-controller | Motor controller main board (SN6501 isolated supply + AMC1311) | 12 | 0 | 0 |
| usb-pd-power-manager | USB-C PD sink + buck-boost charger (HUSB238 + BQ25672 + TPS63070) | 4 | 0 | 1 |
| rt-ihu | Dual-MCU flight computer with external watchdog (STWD100) | 52 | 0 | 4 |
| suntastic | Low-power board with watchdog timer (TPL5010) and load switches | 11 | 0 | 0 |
