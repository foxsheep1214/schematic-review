# Typical Circuits：真实单模块开源板上的发现级基准

SR 要覆盖各种单模块原理图，而 `kicad_replay_bench` 只冻结计划结构（检查数、NA 数），不看 SR 实际报了什么。
本基准取 33 块 GitHub 上的开源 KiCad 6/7 小板，每块基本只有一个功能（MCU 最小系统、USB-C 受电、
buck/buck-boost、LDO、锂电充电与保护、I²C 传感器、电平转换、电机/舵机驱动、继电器与光耦、RS-485/CAN、
运放前端、负载 ADC、音频功放、LED 恒流、以太网 PHY/控制器、USB-UART、定时电源开关），冷跑 SR，
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
修正后 FINDING 12 条，全部为真实线索（标签只落在一个脚上），CANDIDATE 71 条均有审读理由，
已知误报 3 条（连接器 NC 豁免需要受控库身份）。

## 覆盖与局限

- 只测自动冷跑层的发现，不测计划、证据计算、专家审查或报告。
- 这些板是能工作的公开设计，`expected` 多是审查线索而不是确认缺陷；缺陷检出率见 `evals/seeded_bench`
  （同一批板子按缺陷类型程序化植入）。
- 缺独立数字隔离器和多节 BMS 前端；KiCad 5 旧格式与 KiCad 8+ 新格式的板子因 kicad-cli 7 不能导出而未收。

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
