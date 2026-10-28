# 审查词表：功能电路、器件角色、需求类别

> 读者：审查员。

这三张表是审查员在 `intent.json` 里要写的名字：`circuit_decisions` 推出的电路类型、`device_kinds` 的器件角色、`requirements[].categories` 的需求类别与 `parameters` 的参数名。表由 [`scripts/catalog.py`](../scripts/catalog.py) 生成（`python3 scripts/catalog.py --write-doc references/review-vocabulary.md`），与 [检查规则总表](check-catalog.md) 同源，测试拒绝两者不一致；规则编号、判据和每项检查的盲区在那边，审查员不用翻。

<!-- vocabulary:begin（由 scripts/catalog.py --write-doc 生成，勿手改） -->

## 功能电路

电路由电路候选与 `intent.circuit_decisions` 推出；名称命中只生成 UNDETERMINED 候选。推出的电路或已确认拓扑使功能电路适用，再生成 REQ-Q07 覆盖项与电路检查项，逐项再核实际用途。未检出的功能电路汇总到一项 REQ-Q08 确认；`features` 里的 NOT_APPLICABLE 声明不生成检查项，只作 REQ-Q08 那一项的依据。分立 MOSFET 电平转换器没有名称线索，候选没检出时写 add 决定（在 I²C 等总线上则并入该总线电路），转换管在 `intent.power_switches` 中声明为 `role: "level_shifter"`，见 [计划格式](plan-format.md)。

| 功能电路 | 名称 | 内容域 | 电路检查项 | 必需资料 | 检出特征（正则） |
|---|---|---|---|---|---|
| POWER_CONVERTER | 变换器与稳压器 | PWR | PWR-C02、PWR-C03、PWR-C04、PWR-C05、PWR-C15 | requirements、datasheets | `(^\|[:_-])(FB\|VFB\|LX\d*\|PGOOD\|PWRGD\|VOUT\d*)([:_-]\|$)\|LDO\|BUCK\|BOOST\|DC-?DC\|PMIC` |
| POWER_PROTECTION | 电源输入保护 | PWR | PWR-C06、DRV-C02、PRO-C01、PWR-C13、PWR-T05、ANA-T01 | requirements、datasheets | `FUSE\|HOT-?SWAP\|SURGE\|PART:F\d+:\|(^\|[:_-])(OVP\|UVP\|OCP\|ILIM)([:_-]\|$)\|SMBJ\|SMAJ\|SMCJ` |
| ANALOG | 模拟前端与监测 | ANA | ANA-C01、ANA-C02、ANA-C03、ANA-T01、ANA-D01 | requirements、datasheets | `(^\|[:_-])(AIN\d*\|ADC\w*\|VREF\w*\|REFIN\|REFOUT\|OPA\w*\|INA\d*\|ISENSE\w*\|CSP\|CSN\|NTC\w*\|THERM\w*)([:_-]\|$)` |
| STARTUP | 上电、复位与启动 | RST | RST-C01、RST-C02、RST-T04、RST-D01 | requirements、datasheets | `RESET\|(^\|_)RST\|POR(_\|$)\|(^\|[:_-])(BOOT\w*\|STRAP\w*\|PWRON\w*)([:_-]\|$)` |
| CLOCK | 时钟 | CLK | CLK-C01、CLK-D01、CLK-D03 | datasheets | `CLK\|CLOCK\|OSC\|XTAL\|XIN\|XOUT\|32K` |
| I2C | I²C | SIG | SIG-C01、SIG-C07、SIG-C08、SIG-D01 | requirements、datasheets | `(^\|[:_-])(I2C\w*\|SCL\d*\|SDA\d*)([:_-]\|$)` |
| LEVEL_SHIFT | 电平转换与跨电压域互连 | SIG | SIG-C07、SIG-C08、SIG-C09、SIG-T04 | requirements、datasheets | `TXS0\d{3}\|TXB0\d{3}\|TXU0\d{3}\|PCA9306\|NVT20\d\d\|LSF0\d{3}\|GTL2003\|FXMA\d+\|FXLA\d+\|NLSX\d+\|(SN)?74(LVC\|AVC\|AXC\|ALVC)\d*T\d+\|LEVEL_?SHIFT\|LVL_?SHIFT\|TRANSLAT\|NET:\w*_(LV\|HV)(_\|$)` |
| SPI | SPI | SIG | SIG-D09、SIG-C07、SIG-C09 | requirements、datasheets | `\bSPI\w*\|MOSI\|MISO\|SCLK` |
| UART | UART/RS232 | SIG | SIG-D08、SIG-T04、SIG-C07 | requirements、datasheets | `UART\|\bTXD\w*\|\bRXD\w*` |
| CAN | CAN | SIG | SIG-C03、SIG-C04、SIG-D08、PRO-C01 | requirements、datasheets | `CANH\|CANL\|CAN_TX\|CAN_RX\|\bCAN\d*\b` |
| RS485 | RS485 | SIG | SIG-C03、SIG-C04、SIG-D08、SIG-T04、PRO-C01 | requirements、datasheets | `RS485\|485_TX\|485_RX\|485_A\|485_B` |
| USB | USB/Type-C | SIG | SIG-D07、SIG-D04、SIG-C05、SIG-T04 | requirements、datasheets | `USB\|VBUS\|TYPEC\|TYPE_C` |
| ETHERNET | 以太网 | SIG | SIG-D11、SIG-C09、PRO-C01 | requirements、datasheets、platform_checklist | `ETH\|RGMII\|RMII\|SGMII\|MDIO\|\bMDI\d\|PHY` |
| DDR | DDR | SIG | SIG-D02、SIG-D03、SIG-C09 | requirements、datasheets、platform_checklist | `LPDDR\|DDR[2345]?\|SDRAM\|DQS\|\bZQ\b` |
| STORAGE | eMMC/SD | SIG | SIG-D10、SIG-C07、SIG-C09 | requirements、datasheets、platform_checklist | `EMMC\|SDIO\|SDMMC\|MICROSD\|TF_CARD` |
| RF | 射频与模组 | SIG | SIG-D12 | requirements、datasheets | `(^\|[:_-])(RF\|ANT\|WIFI\|WLAN\|LTE\|GNSS\|SIM)([:_-]\|$)` |
| HSSERIAL | 高速串行 | SIG | SIG-D14、SIG-T01 | requirements、datasheets、platform_checklist | `PCIE\|PCI_E\|SATA\|SERDES\|USB3\|SSTX\|SSRX\|PERST\|CLKREQ` |
| AV | 音视频接口 | SIG | SIG-D15、SIG-C07 | requirements、datasheets | `HDMI\|MIPI\|(^\|[:_-])(CSI\|DSI\|EDP\|LCD)\w*\|(^\|[:_-])I2S\|MCLK\|LRCK\|BCLK\|CODEC\|(^\|[:_-])(SPK\|MIC)([:_-]\|\d\|$)` |
| ISOLATION | 隔离 | PRO | PRO-D02、PRO-C01、PRO-C03 | requirements、datasheets | `ISOLAT\|(^\|_)ISO(_\|$)\|DIGITAL_ISO` |
| DEBUG | 调试与烧录 | SIG | SIG-D06 | datasheets | `JTAG\|SWDIO\|SWCLK\|(^\|[:_-])(SWD\|TCK\|TMS\|TDI\|TDO\|TRST\w*)([:_-]\|$)\|(^\|[:_-])(DEBUG\|DBG)` |

下表的电路检查项只在网表上有它问的机制时生成，检查项对象取前提找到的器件；前提不成立的规则记在功能框架的 `not_asked`，报告在功能下列“未问”。网表说不清（器件类别未知、IC 没有脚名）时照问；漏问的可经 `intent.rule_gaps` 补回。

| 功能电路 | 电路检查项 | 前提 | 不成立时 |
|---|---|---|---|
| POWER_CONVERTER | PWR-C04 | SWITCH_PIN | 电路里没有受控开关：电路和与它相接的 IC 都没有驱动/开关脚（GATE、DRV、OUT、SW、LX）或稳压输出脚 |
| POWER_CONVERTER | PWR-C15 | FEEDBACK_PIN | 电路里没有反馈环：电路和与它相接的 IC 都没有反馈/补偿脚（FB、VFB、COMP、VCTRL、ITH、ADJ）或稳压输出脚，也没有分压或光耦把输出送到 IC |
| POWER_PROTECTION | PWR-C06 | PROTECTION_PART | 电路里没有保险、压敏电阻、NTC、TVS、稳压管，也没有带 UV/OV/ILIM/EN 脚的 IC |
| POWER_PROTECTION | DRV-C02 | POWER_SWITCH | 电路里没有 MOSFET 或 BJT |
| POWER_PROTECTION | PRO-C01 | PROTECTION_PART | 电路里没有保险、压敏电阻、NTC、TVS、稳压管，也没有带 UV/OV/ILIM/EN 脚的 IC |
| POWER_PROTECTION | PWR-C13 | CONNECTOR_INPUT | 电路里没有连接器，也不在连接器的输入路径上 |
| POWER_PROTECTION | PWR-T05 | SUPPLY_SWITCH | 电路里没有 D、S 都不接地的 MOSFET |
| POWER_PROTECTION | ANA-T01 | SENSE_ELEMENT | 电路里没有采样电阻（<1 Ω）、NTC 或接到 IC 检测脚的分压 |
| ANALOG | ANA-C01 | ANALOG_PIN | 电路里没有放大器、ADC 或温度传感器的脚 |
| ANALOG | ANA-C02 | ANALOG_PIN | 电路里没有放大器、ADC 或温度传感器的脚 |
| ANALOG | ANA-C03 | ANALOG_PIN | 电路里没有放大器、ADC 或温度传感器的脚 |
| ANALOG | ANA-T01 | SENSE_ELEMENT | 电路里没有采样电阻（<1 Ω）、NTC 或接到 IC 检测脚的分压 |
| ANALOG | ANA-D01 | ANALOG_PIN | 电路里没有放大器、ADC 或温度传感器的脚 |
| STARTUP | RST-C01 | START_PIN | 电路里没有带复位、使能或启动配置脚（RESET、EN、BOOT、strap）的 IC |
| STARTUP | RST-C02 | START_PIN | 电路里没有带复位、使能或启动配置脚（RESET、EN、BOOT、strap）的 IC |
| STARTUP | RST-T04 | START_PIN | 电路里没有带复位、使能或启动配置脚（RESET、EN、BOOT、strap）的 IC |
| STARTUP | RST-D01 | START_PIN | 电路里没有带复位、使能或启动配置脚（RESET、EN、BOOT、strap）的 IC |

## 器件角色

集成电路在 `intent.device_kinds` 声明手册标题给出的角色（`audit_datasheets.py --intent` 用标题词核验原文），角色决定它作核心器件时生成哪些电路候选；泛称 `ic` 只在标题不含任何角色词时可写，计划把每个 `ic` 列成 `DEVICE_KIND_GENERIC` 诊断（不生成电路候选），这张清单是下一批角色的来源。加角色只改 `catalog.DEVICE_ROLES` 一行：标题词、靶的电路类型、走哪些脚。

| 角色 | 名称 | 手册标题词（去空格小写的子串，3 个字母以内按整词） | 作核心器件生成的电路 | ANALOG 走线从哪些脚出发 |
|---|---|---|---|---|
| `pwm_controller` | 开关电源控制器 | pwmcontroller、pfccontroller、flybackcontroller、currentmodecontroller、voltagemodecontroller、switchingcontroller、offlinecontroller、quasiresonantcontroller、boostcontroller、buckcontroller、powerfactorcorrectioncontroller、powerfactorcontroller、resonantcontroller、llccontroller、switchmodecontroller、pwmcontrol | POWER_CONVERTER | — |
| `gate_driver` | 栅极驱动器 | gatedriver、mosfetdriver、igbtdriver、bridgedriver、fetdriver | POWER_CONVERTER | — |
| `sr_controller` | 同步整流控制器 | synchronousrectif、srcontroller | POWER_CONVERTER | — |
| `pd_controller` | USB PD 控制器 | pdcontroller、powerdelivery、usbpd、typeccontroller、usbccontroller | USB、ANALOG | 检测脚 |
| `regulator` | 稳压器与变换器 | voltageregulator、linearregulator、lowdropout、ldoregulator、dcdcconverter、buckconverter、boostconverter、switchingregulator、stepdownconverter、stepupconverter、powermanagementic、pmic、chargepump | POWER_CONVERTER | — |
| `supervisor` | 电压监控与复位 | supervisor、supervisory、voltagemonitor、resetcircuit、resetic、watchdog | ANALOG | 检测脚 |
| `opamp_comparator` | 运放、比较器与放大器 | operationalamplifier、opamp、comparator、erroramplifier、instrumentationamplifier、currentsenseamplifier、currentshuntmonitor、differenceamplifier、audioamplifier | ANALOG | 全部信号脚 |
| `shunt_reference` | 并联基准 | shuntregulator、voltagereference、shuntreference | ANALOG | 全部信号脚 |
| `mcu` | 微控制器与处理器 | microcontroller、microprocessor、systemonchip、mcu | ANALOG | 检测脚 |
| `transceiver` | 总线收发器与 PHY | transceiver、ethernetphy、linedriver、busdriver | ANALOG、CAN、RS485、UART、ETHERNET、HSSERIAL | 检测脚 |
| `isolator` | 数字隔离器 | digitalisolator、isolatedgatedriver、isolator | 不作核心器件 | — |
| `load_switch` | 负载开关与热插拔保护 | loadswitch、hotswap、efuse、idealdiode、powerdistributionswitch、currentlimitswitch、highsideswitch | POWER_PROTECTION | — |
| `charger` | 电池充电器 | batterycharger、chargecontroller、chargemanagement、switchingcharger、linearcharger、chargeric | POWER_CONVERTER | — |
| `adc_dac` | ADC 与 DAC | analogtodigital、digitaltoanalog、bitadc、bitdac、channeladc、channeldac、audiodac、audioadc、sigmadeltaadc、deltasigmaadc | ANALOG | 全部信号脚 |
| `oscillator` | 时钟源 | crystaloscillator、clockgenerator、clockbuffer、clocksynthesizer、jittercleaner、oscillator、clockdistribution、realtimeclock、clockmultiplier | CLOCK | — |
| `memory` | 存储器 | flashmemory、serialflash、spiflash、eeprom、sdram、lpddr、ddr2、ddr3、ddr4、ddr5、nandflash、norflash、sram、emmc | SPI、I2C、DDR、STORAGE | — |
| `level_shifter` | 电平转换器 | leveltranslat、levelshifter、voltagetranslat、voltageleveltranslat | LEVEL_SHIFT | — |
| `motor_driver` | 电机驱动器 | motordriver、steppermotor、brushlessdc、bldc、brusheddc、hbridgedriver、fullbridgedriver、halfbridgedriver | POWER_CONVERTER | — |
| `ic` | 泛称：手册标题没有登记的角色 | — | 不作核心器件 | — |

接口电路（POWER_PROTECTION、CLOCK、I2C、LEVEL_SHIFT、SPI、UART、CAN、RS485、ETHERNET、DDR、STORAGE、RF、HSSERIAL、AV）的走线总是从核心器件的全部信号脚出发走两跳，到达的网上的连接器作成员。

一个角色能靶多种接口电路（上表 transceiver、memory）时，按下表从手册标题挑第一个命中的类型，都不命中记候选缺口 `role-bus`，由审查员写 `circuit_decisions` add。

| 接口电路 | 标题里的词（正则） |
|---|---|
| CAN | `\bCAN(?:[ -]?FD)?\b` |
| RS485 | `RS[- ]?4(?:85\|22)\b\|\bPROFIBUS\b` |
| UART | `RS[- ]?232\b\|\bUART\b\|\bLIN\b` |
| ETHERNET | `\bETHERNET\b\|\bPHY\b\|\b(?:RG\|R\|SG)?MII\b` |
| HSSERIAL | `\bLVDS\b\|\bSERDES\b\|\bPCIE?\b\|PCI EXPRESS\|\bSATA\b\|\bUSB ?3` |
| I2C | `I[²2]C\|\bSMBUS\b\|TWO[- ]WIRE` |
| SPI | `\bQ?SPI\b\|QUAD[- ]SPI\|SERIAL (?:NOR )?FLASH\|\bNOR FLASH\b` |
| DDR | `\bL?P?DDR\d?\b\|\bSDRAM\b` |
| STORAGE | `\bE?MMC\b\|\bNAND\b` |

## 需求类别与审查方面

每条需求分解成审查方面，计划按（需求，方面）各生成一项 REQ-D01，判据取方面模板。分解的单位是需求里的量：带参数的方面由 `requirements[].parameters` 里有没有这个参数决定，有就问，不管选了哪些类别；不带参数的方面由类别决定。一条需求一个参数都没写时，才按类别问全部方面，计划同时列出原文里没读进参数的带单位数字（`REQUIREMENT_NUMBERS_UNREAD`）。类别拿不准就多选：多出的不带参数的方面判 NA 要写依据，少选是漏查。

| 类别 | 名称 | 怎么选 | 审查方面 | 落到 |
|---|---|---|---|---|
| INPUT_RANGE | 输入电气范围 | 原文说板子从外面接什么电：输入电压、频率、瞬态、热插拔 | INPUT_STAGE_RATING 输入级器件额定覆盖、INPUT_THRESHOLDS 启动与欠压门限覆盖、CONVERTER_INPUT_RANGE 变换级工作范围覆盖 | 系统 SYS-POWER，输入相关电路 |
| OUTPUT_SPEC | 输出电气规格 | 原文给输出的电压、电流、功率、精度或纹波的数 | OUTPUT_LEVELS 各档输出可达、OUTPUT_LIMITS 电流与功率限制、OUTPUT_ACCURACY 精度与纹波 | 输出相关电路、供电接口 |
| FUNCTION | 功能与数量 | 原文要求有某个功能或接口，或给出路数、端口数、通道数（“4 路 RS-485”“2 个 USB”） | FUNCTION_PRESENT 功能与接口存在且数量达标 | 落实该功能的电路、接口 |
| PROTOCOL | 协议与接口功能 | 原文点名协议、角色（主/从、Host/Device、PD 角色）、识别或对外引脚定义 | PROTOCOL_ROLE 协议角色与能力、PORT_DETECTION 端口识别通路、EXTERNAL_PINOUT 对外引脚定义 | 接口、主控电路 |
| TIMING | 时序与启动 | 原文说上电/掉电顺序、启动时间、复位、保持时间、看门狗 | POWER_SEQUENCE 上电与掉电顺序、STARTUP_TIMING 启动、复位与保持时间 | 系统 SYS-SEQUENCE、启动与复位电路 |
| PROTECTION | 保护与故障响应 | 原文说过流、过压、短路、反接、浪涌、ESD 等故障要怎样检测、在哪动作、动作后怎样 | FAULT_DETECTION 检测通路存在、FAULT_THRESHOLD 动作门限、FAULT_RESPONSE 动作后状态与恢复 | 保护电路、监控 SYS-MONITOR |
| MEASUREMENT | 测量与监测 | 原文要求测量或监测某个量（温度、电流、电压）并给范围或精度 | MEASUREMENT_CHAIN 检测链完整、MEASUREMENT_ACCURACY 测量精度 | 模拟与检测电路 |
| ENVIRONMENT | 环境条件 | 原文给工作或储存温度、湿度、海拔、气候条件 | TEMPERATURE_GRADE 器件温度等级覆盖、TEMPERATURE_DERATING 按温度降额、TEMPERATURE_DRIFT 敏感参数温漂、ALTITUDE_HUMIDITY 海拔与湿度影响额定 | 全板器件应力，各电路 |
| SAFETY_ISOLATION | 安规与隔离 | 原文说隔离、绝缘电压、安规类别、爬电与电气间隙 | ISOLATION_PARTS 跨隔离器件资格、ISOLATION_PATHS 隔离路径唯一、DOWNSTREAM_HANDOFF 原理图外部分移交 | 隔离接口、链路 |
| LIFETIME | 寿命与可靠性 | 原文给设计寿命、MTBF、工作时长或循环次数 | LIFETIME_BASIS 寿命计算依据、MISSION_PROFILE 按任务剖面复算 | 相关电路器件检查项 |
| POWER_BUDGET | 功耗与效率 | 原文给待机功耗、静态电流或效率的数 | STANDBY_POWER 待机与静态功耗上界、EFFICIENCY 效率 | 电源树、变换器电路 |
| INDICATION | 指示与人机 | 原文要求指示灯、蜂鸣器、按键等人机部件及其状态 | INDICATOR_PRESENT 指示功能存在、INDICATOR_SUPPLY 指示供电独立 | 相关电路 |
| TESTABILITY | 测试与生产 | 原文要求测试点、烧录口、调试口或生产测试方式 | TEST_ACCESS 测试点与烧录调试口 | 全板 |
| CLOCK | 时钟精度 | 原文给时钟或 RTC 的频率精度（ppm）或走时误差 | CLOCK_ACCURACY 时钟频率精度 | 时钟电路 |
| OPTIMIZATION | 优化目标 | 原文是成本、体积、取舍优先级这类没有原理图判据的目标 | NO_SCHEMATIC_CRITERION 没有原理图判据 | 全板 |
| COMPLIANCE | 合规与认证 | 原文点名标准、认证或 EMC 等级 | SCHEMATIC_COMPLIANCE 原理图可核部分、DOWNSTREAM_HANDOFF 原理图外部分移交 | 全板，移交 |
| EXCLUSION | 明确排除 | 原文明确不要求某功能、模式或认证 | EXCLUDED_FUNCTION 明确排除 | 被排除功能对应的检查项 |

方面有树上的检查承担时，需求检查项绑定这些规则的检查项（需求 `owners` 点名的电路、接口、系统功能拥有的检查项；没写 `owners` 时，全板方面绑定全板这些规则的检查项），结论取绑定检查项中最差者，需求检查项不再另判；没有检查承担的方面由需求检查项自己判。

需求的承接电路写在 `owners`（落实这条需求的功能电路；系统功能和接口也可以承接）。计划替每条需求找出可承接的电路：下表“可承接的电路”列出的电路类型、系统功能和接口种类里，拥有承担该方面的检查项的那些；表外的所属不算。有可承接的电路而没写 owners 的需求，计划拒绝生成并打印它们；审查员认定没有承接电路时写 `owners: []` 加能定位的 `no_owner_reason`，需求检查项自判。

| 审查方面 | 何时问 | 判据模板 | 承担的检查 | 可承接的电路 |
|---|---|---|---|---|
| INPUT_STAGE_RATING 输入级器件额定覆盖 | 原文有 input_voltage / surge_voltage | 需求输入范围的持续上下限下，输入级器件的持续电压、电流额定覆盖并有降额余量；需求的瞬态（一次一个）对瞬态额定或绝对最大额定，不另要降额余量 | DEV-C01、PWR-C02、PWR-C13 | 电路 POWER_PROTECTION、POWER_CONVERTER；系统功能 SYS-POWER |
| INPUT_THRESHOLDS 启动与欠压门限覆盖 | 原文有 input_voltage | 启动、欠压与过压门限落在需求输入范围之外或边界上，范围内不误动作 | PWR-C06、PRO-C02 | 电路 POWER_PROTECTION、POWER_CONVERTER；系统功能 SYS-POWER |
| CONVERTER_INPUT_RANGE 变换级工作范围覆盖 | 原文有 input_voltage / input_frequency | 变换级控制器与功率器件的工作输入范围覆盖需求输入范围 | PWR-C02、DEV-C05 | 电路 POWER_PROTECTION、POWER_CONVERTER；系统功能 SYS-POWER |
| OUTPUT_LEVELS 各档输出可达 | 原文有 output_voltage | 需求的每个输出电压档或范围由反馈与设定网络算得可达，并留调节余量 | PWR-E01、PWR-C15 | 电路 POWER_CONVERTER；接口 SUPPLY |
| OUTPUT_LIMITS 电流与功率限制 | 原文有 output_current / output_power | 需求的电流与功率限值有采样与限制通路，限值按元件值算得落在需求窗口内 | PWR-C01、PWR-C03、PWR-C06 | 电路 POWER_CONVERTER；接口 SUPPLY |
| OUTPUT_ACCURACY 精度与纹波 | 原文有 ripple / accuracy | 输出精度与纹波按基准、分压公差与输出滤波算得在需求窗口内 | PWR-C14、DEV-C03、ANA-C01 | 电路 POWER_CONVERTER；接口 SUPPLY |
| FUNCTION_PRESENT 功能与接口存在且数量达标 | 类别选中 | 需求的每个功能、接口由实际器件与连接落实，路数、端口数与需求一致 | 需求检查项自判 | — |
| PROTOCOL_ROLE 协议角色与能力 | 类别选中 | 所选控制器手册声明的协议角色与能力覆盖需求，外围连接与之相符；本机配置表不在原理图审查之内 | SIG-T04、SIG-D04 | 电路 USB、CAN、RS485、UART、SPI、I2C、ETHERNET、HSSERIAL、AV、STORAGE、DDR；接口 CIRCUIT_PAIR、LINK |
| PORT_DETECTION 端口识别通路 | 类别选中 | 需求依赖的对端、线缆或附件识别有完整信号通路 | SIG-D04、SIG-C05 | 电路 USB、CAN、RS485、UART、SPI、I2C、ETHERNET、HSSERIAL、AV、STORAGE、DDR；接口 CIRCUIT_PAIR、LINK |
| EXTERNAL_PINOUT 对外引脚定义 | 类别选中 | 对外连接器的每个引脚定义与需求一致，未用引脚的处理有依据 | DEV-D03 | 接口 EXTERNAL |
| POWER_SEQUENCE 上电与掉电顺序 | 类别选中 | 需求的供电建立顺序、掉电顺序与恢复由使能、监控或时序链保证 | RST-T03 | 电路 STARTUP；系统功能 SYS-SEQUENCE |
| STARTUP_TIMING 启动、复位与保持时间 | 原文有 startup_time / hold_up_time / reset_time | 启动时间、复位脉宽与掉电保持时间按元件值与器件参数算得在需求窗口内 | RST-C02 | 电路 STARTUP；系统功能 SYS-SEQUENCE |
| FAULT_DETECTION 检测通路存在 | 类别选中 | 需求的每种故障有检测通路接到能动作的器件 | ANA-T01、ANA-C04、PWR-T04 | 电路 POWER_PROTECTION、POWER_CONVERTER、ANALOG；系统功能 SYS-MONITOR、SYS-SEQUENCE |
| FAULT_THRESHOLD 动作门限 | 原文有 trip_current / trip_voltage / surge_voltage / esd_voltage | 检测门限按元件值与器件阈值算得落在需求窗口内，正常工作范围内不误动作 | PWR-C06、PRO-C02 | 电路 POWER_PROTECTION、POWER_CONVERTER、ANALOG；系统功能 SYS-MONITOR、SYS-SEQUENCE |
| FAULT_RESPONSE 动作后状态与恢复 | 类别选中 | 故障动作后的输出状态、锁定或自动恢复方式与需求一致 | PRO-C01、PRO-D03、RST-T03 | 电路 POWER_PROTECTION、POWER_CONVERTER、ANALOG；系统功能 SYS-MONITOR、SYS-SEQUENCE |
| MEASUREMENT_CHAIN 检测链完整 | 类别选中 | 需求的每个被测量有取样、返回地与判决链，取样点与被测量一致 | ANA-T01 | 电路 ANALOG；系统功能 SYS-MONITOR |
| MEASUREMENT_ACCURACY 测量精度 | 原文有 measurement_accuracy | 测量误差按传感器、偏置、采样链与 ADC 的误差和温漂合计在需求窗口内 | ANA-C01 | 电路 ANALOG；系统功能 SYS-MONITOR |
| TEMPERATURE_GRADE 器件温度等级覆盖 | 原文有 ambient_temperature / storage_temperature | 器件温度等级覆盖需求环境温度加内部温升 | DEV-C05（全板） | 全板，不要求 owners |
| TEMPERATURE_DERATING 按温度降额 | 原文有 ambient_temperature | 器件额定按需求温度降额后仍有余量；需求要求随温度降额输出时，有温度检测与降额通路 | DEV-C01（全板） | 全板，不要求 owners |
| TEMPERATURE_DRIFT 敏感参数温漂 | 原文有 ambient_temperature | 基准、门限、采样等敏感参数在需求温度范围的漂移计入窗口 | ANA-C01、DEV-C03 | — |
| ALTITUDE_HUMIDITY 海拔与湿度影响额定 | 原文有 humidity / altitude | 需求的海拔、湿度、气候条件对器件额定与绝缘等级的影响已计入 | 需求检查项自判 | — |
| ISOLATION_PARTS 跨隔离器件资格 | 原文有 isolation_voltage | 跨隔离边界的每个器件绝缘等级与资格满足需求的绝缘类别 | PRO-C03、PRO-D01（全板） | 全板，不要求 owners |
| ISOLATION_PATHS 隔离路径唯一 | 类别选中 | 隔离边界两侧之间只经有资格的跨隔离器件相连，没有别的电气路径 | PRO-D02（全板） | 全板，不要求 owners |
| DOWNSTREAM_HANDOFF 原理图外部分移交 | 类别选中 | 原理图判不了的部分（爬电与电气间隙、整机试验、认证）列为移交项并写复验条件 | 需求检查项自判 | — |
| LIFETIME_BASIS 寿命计算依据 | 原文有 lifetime | 寿命关键件有按需求工作条件算的寿命依据 | DEV-C02、DEV-C06（全板） | 全板，不要求 owners |
| MISSION_PROFILE 按任务剖面复算 | 原文有 lifetime | 寿命按需求任务剖面（工作时间、温度、负载）复算，实测温度后复算的条件写明 | DEV-C02、DEV-C06（全板） | 全板，不要求 owners |
| STANDBY_POWER 待机与静态功耗上界 | 原文有 standby_power / quiescent_current | 待机或静态功耗按各轨空载电流与器件静态电流算得上界在需求窗口内 | PWR-C16 | — |
| EFFICIENCY 效率 | 原文有 efficiency | 效率只能样机实测：原理图核拓扑与主要损耗上界是否允许达到需求值，实测列为移交 | 需求检查项自判 | — |
| CLOCK_ACCURACY 时钟频率精度 | 原文有 clock_accuracy | 晶体或振荡器的频率精度、负载电容偏差与温漂合计在需求 ppm 窗口内 | CLK-C01 | 电路 CLOCK |
| TEST_ACCESS 测试点与烧录调试口 | 类别选中 | 需求的测试点、烧录与调试接口在原理图上电气预留；可触达性与夹具交移交 | DOC-D02（全板） | 全板，不要求 owners |
| INDICATOR_PRESENT 指示功能存在 | 类别选中 | 需求的每个指示有驱动通路，指示的状态与需求一致 | 需求检查项自判 | — |
| INDICATOR_SUPPLY 指示供电独立 | 类别选中 | 指示的供电与被指示对象的关断或故障互不影响，与需求一致 | 需求检查项自判 | — |
| NO_SCHEMATIC_CRITERION 没有原理图判据 | 类别选中 | 优化目标或取舍原则在原理图上没有判据：记不适用（NA）并引原文 | 需求检查项自判 | — |
| SCHEMATIC_COMPLIANCE 原理图可核部分 | 类别选中 | 标准或认证中原理图能核的器件资格与电路要求逐条核 | 需求检查项自判 | — |
| EXCLUDED_FUNCTION 明确排除 | 类别选中 | 需求明确排除的功能或认证：记排除原文，相应检查记不适用（NA） | 需求检查项自判 | — |

需求里的数字读进 `requirements[].parameters`（`name`、`min`/`max`、`unit`、`condition`）；每个数字须在该条原文里出现，条件须是原文里的一段，数值按下表换算到规范单位。

| 参数 | 名称 | 规范单位 | 可写单位 | 问的方面 |
|---|---|---|---|---|
| input_voltage | 输入电压 | V | V、mV、kV、Vac、VAC、Vdc、VDC | INPUT_STAGE_RATING、INPUT_THRESHOLDS、CONVERTER_INPUT_RANGE |
| input_frequency | 输入频率 | Hz | Hz、kHz | CONVERTER_INPUT_RANGE |
| output_voltage | 输出电压 | V | V、mV、kV、Vac、VAC、Vdc、VDC | OUTPUT_LEVELS |
| output_current | 输出电流 | A | A、mA | OUTPUT_LIMITS |
| output_power | 输出功率 | W | W、mW、kW | OUTPUT_LIMITS |
| ripple | 纹波 | V | V、mV、Vpp、mVpp | OUTPUT_ACCURACY |
| accuracy | 精度 | % | % | OUTPUT_ACCURACY |
| surge_voltage | 浪涌或瞬态电压 | V | V、mV、kV、Vac、VAC、Vdc、VDC | INPUT_STAGE_RATING、FAULT_THRESHOLD |
| esd_voltage | 静电放电电压 | V | V、mV、kV、Vac、VAC、Vdc、VDC | FAULT_THRESHOLD |
| ambient_temperature | 工作环境温度 | °C | °C、℃ | TEMPERATURE_GRADE、TEMPERATURE_DERATING、TEMPERATURE_DRIFT |
| storage_temperature | 储存温度 | °C | °C、℃ | TEMPERATURE_GRADE |
| humidity | 相对湿度 | %RH | %RH、% | ALTITUDE_HUMIDITY |
| altitude | 海拔 | m | m、km | ALTITUDE_HUMIDITY |
| lifetime | 设计寿命 | 年 | 年、year、h | LIFETIME_BASIS、MISSION_PROFILE |
| trip_current | 保护动作电流 | A | A、mA | FAULT_THRESHOLD |
| trip_voltage | 保护动作电压 | V | V、mV、kV、Vac、VAC、Vdc、VDC | FAULT_THRESHOLD |
| isolation_voltage | 绝缘电压 | V | V、mV、kV、Vac、VAC、Vdc、VDC、Vrms、kVrms | ISOLATION_PARTS |
| startup_time | 启动时间 | s | s、ms、µs、us | STARTUP_TIMING |
| hold_up_time | 掉电保持时间 | s | s、ms、µs、us | STARTUP_TIMING |
| reset_time | 复位时间 | s | s、ms、µs、us | STARTUP_TIMING |
| standby_power | 待机功耗 | W | W、mW | STANDBY_POWER |
| quiescent_current | 静态电流 | A | A、mA、µA、uA | STANDBY_POWER |
| efficiency | 效率 | % | % | EFFICIENCY |
| measurement_accuracy | 测量精度 | % | % | MEASUREMENT_ACCURACY |
| clock_accuracy | 时钟精度 | ppm | ppm | CLOCK_ACCURACY |

<!-- vocabulary:end -->
