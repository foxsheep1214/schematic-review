# 86 块实板暴露的待采集资料（2026-11-02）

日期：2026-11-02。来源：[criteria-from-boards-2026-11-02.json](criteria-from-boards-2026-11-02.json) 的 `datasheets_to_collect`（31 项），
统计口径见该草案第六节。格式与 ASG `evals/calibration_boards/datasheets-to-collect.md` 相同，供并入那份清单；
这里只写要采集什么、为什么要，不写参数，下载后读原件再判断是否合用。

**存放**：`~/Documents/知识库/HardwareWiki/raw/Datasheet/<分类>/<子类>/`，文件名 `Vendor - PartNumber.pdf`；
厂商简称查 `VENDORS.yaml`，分类查 `元器件体系/器件统一分类大表.md`。标准原文放 `raw/Standard/`，模组载板指南放 `raw/Applicationnote/`。
子类写“（新子类）”的，分类大表里还没有，入库时由维护者定名。

**系列名来源**：**板上料号** = 板子 BOM/符号上的准确料号（采集该料号原厂手册即可）；**模组厂** = 资料由模组或平台厂发布，不是器件手册；
**标准组织** = 标准原文。**出现板数**按去重板名计；**缺口数**是这些板上因缺这份资料而停在“资料不足”的检查项次数。

**关键指标**：从缺口所在的 SR 检查项反推这份资料必须给出的内容。凡写“订货/脚表/推荐条件”的，就是原厂手册的订货信息、完整引脚表（含封装变体）和推荐工作条件三处。

## 一、平台与模组资料（不是器件手册，决定连接器每个脚的含义）

| # | 器件类（存放子类） | 需求里的关键指标 | 建议搜集的系列 | 来源 | 出现板数（缺口数） |
|---|---|---|---|---|---|
| 1 | Jetson AGX Thor 模组 B2B 连接器（27_连接器/板对板(Board-to-Board)；资料放 raw/Applicationnote） | 模组针表与载板设计指南：每个脚的方向、电平、上电默认态与必须端接的脚（NET-A07 声明输入脚悬空 25 处） | NVIDIA Jetson AGX Thor 模组数据手册与载板设计指南（板上为 Molex 203456-0003） | 模组厂 | 1（25）：antmicro--jetson-agx-thor-baseboard |
| 2 | Jetson Nano 模组 SO-DIMM 插座（27_连接器/板对板(Board-to-Board)；资料放 raw/Applicationnote） | 模组针表与载板设计指南：脚义、使能与复位来源、悬空脚处置（DEV-D02/DEV-D03/DEV-E01/NET-A07/RST-E01） | NVIDIA Jetson Nano 模组数据手册与载板设计指南（板上为 DDR4 SO-DIMM 定制插座） | 模组厂 | 1（5）：antmicro--jetson-nano-baseboard |
| 3 | M.2 插座（27_连接器/板对板(Board-to-Board)） | 所插 M.2 模块的脚义与未用脚处置（NET-A07 6 处）；PCI-SIG M.2 规范或所插模块手册 | PCI-SIG M.2 Specification（板上为 TE 2199230-2） | 标准组织 | 1（6）：antmicro--jetson-agx-thor-baseboard |
| 4 | 模块对插针座（27_连接器/板对板(Board-to-Board)） | 所接模块的针表：信号方向、基准与输入保护（SIG-C19/ANA-C03/DEV-C01/DEV-C02/DEV-D01） | 所接模块手册（板上为 Molex 93628-3721） | 模组厂 | 1（7）：pionixpublic--reference-hardware |
| 5 | Qwiic/STEMMA QT 四针座（27_连接器/线对板(Wire-to-Board)） | 外设约定：脚序、供电电压、I²C 上拉在哪一侧（DEV-D02/DEV-D03/DEV-E01/SIG-C07） | SparkFun Qwiic / Adafruit STEMMA QT 约定（板上为 JST SM04B-SRSS-TB） | 模组厂 | 1（8）：antmicro--jetson-nano-baseboard |
| 6 | USB 2.0 / USB 3.2 规范（raw/Standard） | 传统 USB 连接器（Standard-A/B、Mini/Micro-B）的 VBUS 电压窗、入口电容与浪涌条款；G01-026/029/030/031 修订后“另核”的依据（Type-C R2.5 §4.4.2 p152 指向它们；SIG-C05） | USB-IF Universal Serial Bus Revision 2.0 Specification；USB 3.2 Specification | 标准组织 | 7（—）：mlab-modules--usbi2c01、antmicro--scalenode-cm4-baseboard、pionixpublic--reference-hardware、rmingon--chlinknet、tonydefilippis--poepico、brainsmoke--usb2_hub、nabucasa--yellow |

## 二、处理器、存储与无线

| # | 器件类（存放子类） | 需求里的关键指标 | 建议搜集的系列 | 来源 | 出现板数（缺口数） |
|---|---|---|---|---|---|
| 7 | 应用处理器（01_微控制器与处理器/微处理器MPU） | 订货/脚表/推荐条件；悬空输入脚的要求、钳位器件窗口对应的 IO 耐压（NET-A07/PRO-E02） | NXP i.MX 8M Mini 数据手册与硬件开发指南（板上为 MIMX8MM6DVTLZAA） | 板上料号 | 1（5）：groupgets--kimchi-micro |
| 8 | Cortex-M0 MCU（01_微控制器与处理器/32位ARM_Cortex-M_MCU） | 订货/脚表/推荐条件；IO 绝对最大值与注入电流（PRO-E02 钳位窗口 7 处） | Infineon XMC1400 系列（XMC1404） | 板上料号 | 1（8）：tinkerforge--evse-v2-bricklet |
| 9 | BLE SoC（14_无线连接/Bluetooth_LE） | 订货/脚表/推荐条件；GPIO 电平与驱动、基准与输入保护（SIG-C07/ANA-C03） | Nordic nRF52840 产品规格书 | 板上料号 | 1（6）：antmicro--m2-smart-iot-module |
| 10 | 2.4 GHz 射频收发器（14_无线连接/专有RF(Proprietary 2.4GHz)） | 订货/脚表/推荐条件；未用输入脚处置（NET-A07 7 处） | Analog Devices（原 Maxim）MAX2831 | 板上料号 | 1（7）：greatscottgadgets--hackrf-pro |
| 11 | eMMC（04_存储器/eMMC（新子类）） | 订货/脚表/推荐条件；VCC/VCCQ 供电与 CMD/DAT 上拉要求（NET-A01/PWR-A01） | SanDisk iNAND SDINBDG4-8G | 板上料号 | 1（5）：groupgets--kimchi-micro |

## 三、接口、逻辑与电源管理

| # | 器件类（存放子类） | 需求里的关键指标 | 建议搜集的系列 | 来源 | 出现板数（缺口数） |
|---|---|---|---|---|---|
| 12 | 施密特缓冲器（18_逻辑与电平转换/缓冲器_收发器） | 订货/脚表/推荐条件；VIH/VIL、VOH/VOL 与各供电档的驱动能力（SIG-C07 12 处、DEV-D01 10 处） | Nexperia / TI 74LVC1G17（取板上准确后缀） | 板上料号 | 1（22）：pionixpublic--cb-eval-board |
| 13 | 开漏缓冲器（18_逻辑与电平转换/缓冲器_收发器） | 订货/脚表/推荐条件；开漏耐压与封装脚序（DEV-C01/DEV-C02/DEV-D02/DEV-D05/DEV-E01） | Diodes 74LVC1G07QW5-7 | 板上料号 | 1（8）：pionixpublic--reference-hardware |
| 14 | CAN 收发器（15_接口与隔离/CAN_LIN收发器） | 订货/脚表/推荐条件；逻辑电平、使能/待机脚极性、上电期间输出态（SIG-C07 15 处、RST-E01/RST-T04/SIG-C13） | Analog Devices（原 Maxim）MAX3051EKA | 板上料号 | 1（18）：antmicro--jetson-nano-baseboard |
| 15 | 3G-SDI 接收器（15_接口与隔离/视频SDI接口） | 订货/脚表/推荐条件；差分输入电平、端接与偏置、去耦清单、复位脚（SIG-E02/SIG-T03/SIG-A02/PWR-D01/RST-A01） | Semtech GS2971A | 板上料号 | 1（9）：antmicro--sdi-mipi-bridge-hw |
| 16 | USB 2.0 集线器（15_接口与隔离/USB接口） | 订货/脚表/推荐条件；48 脚封装的完整脚表与未用脚处置（DEV-C01/DEV-C02/DEV-D01/DEV-D02/DEV-D05） | Microchip USB2514 / USB2514B（取板上后缀） | 板上料号 | 1（6）：pionixpublic--reference-hardware |
| 17 | 仪表放大器（05_放大器与比较器/仪表放大器 (In-Amp)） | 订货/脚表/推荐条件；输入共模范围、基准脚与输入保护（SIG-C07/ANA-C03） | TI INA333AIDGKR | 板上料号 | 1（6）：pionixpublic--cb-eval-board |
| 18 | 高边智能开关（08_电源管理/负载开关与高低侧驱动） | 订货/脚表/推荐条件；去耦要求、诊断脚电平（PWR-C09 9 处、SIG-C07 9 处） | TI TPS27S100ARRKR | 板上料号 | 1（18）：pionixpublic--cb-eval-board |
| 19 | 限流电源开关（08_电源管理/负载开关与高低侧驱动） | 订货/脚表/推荐条件；使能来源与极性、FLAG 脚电平、通断管 SOA（SIG-C07/DEV-D02/RST-C01/RST-T01/DRV-C02） | onsemi NCP380LSNAJAAT1G | 板上料号 | 1（11）：antmicro--jetson-nano-baseboard |
| 20 | 限流电源开关（08_电源管理/负载开关与高低侧驱动） | 订货/脚表/推荐条件；W5 封装脚序与额定（DEV-C01/DEV-C02/DEV-D01/DEV-D02/DEV-D05） | Diodes AP22804AW5-7 | 板上料号 | 1（6）：pionixpublic--reference-hardware |
| 21 | LDO（08_电源管理/线性稳压器(LDO_标准压差)） | 订货/脚表/推荐条件；EN 极性与耐压、输出精度（RST-E01/RST-T01/SIG-C07） | TI TPS7A05 系列，取 TPS7A0518P 的 SOT-23-5 订货号 | 板上料号 | 1（6）：antmicro--jetson-nano-baseboard |
| 22 | 同步降压集成功率级（08_电源管理/DC-DC 降压转换器 (Buck)） | 订货/脚表/推荐条件；输入滤波、EN 与 PG 脚（DEV-D02/PWR-A05/PWR-C09/RST-E01/RST-T01） | Vishay SiC477ED-T1-GE3 | 板上料号 | 1（6）：antmicro--jetson-nano-baseboard |

## 四、分立器件与保护器件

| # | 器件类（存放子类） | 需求里的关键指标 | 建议搜集的系列 | 来源 | 出现板数（缺口数） |
|---|---|---|---|---|---|
| 23 | 小信号 N 沟道 MOSFET（09_功率半导体/MOSFET） | 订货/脚表/推荐条件；VGS(th)、SOA 与降额曲线、SOT-323 脚序（DEV-D01 8 处、DRV-C02 8 处） | Nexperia BSS138PW | 板上料号 | 1（16）：antmicro--jetson-nano-baseboard |
| 24 | 小信号开关二极管（23_分立半导体/小信号二极管（新子类）） | 订货/脚表/推荐条件；SOD-323 脚序与极性标识（DEV-D02 5 处） | 1N4148WS（板上未写厂家，先查 BOM 定厂家） | 板上料号 | 1（5）：antmicro--jetson-nano-baseboard |
| 25 | 单线 ESD 二极管（28_保护器件/TVS_ESD保护器件） | 订货/脚表/推荐条件；VRWM、VBR、钳位电压与 IPP 的波形条件（PRO-E02 7 处） | Nexperia PESD3V3L1BA | 板上料号 | 1（7）：tinkerforge--evse-v2-bricklet |
| 26 | 双向 TVS（28_保护器件/TVS_ESD保护器件） | 订货/脚表/推荐条件；VRWM、VBR、钳位电压、IPP 与温度降额（PRO-E02 6 处） | SMF4L13CA（板上未写厂家，先查 BOM 定厂家） | 板上料号 | 2（6）：tinkerforge--evse-bricklet、tinkerforge--evse-v2-bricklet |
| 27 | USB 数据线 ESD 阵列（28_保护器件/USB端口保护） | 订货/脚表/推荐条件；脚序与封装变体（DEV-D01 5 处） | Nexperia PESD2USB5UV | 板上料号 | 1（5）：antmicro--jetson-nano-baseboard |
| 28 | 1206 贴片保险丝（28_保护器件/保险丝） | 订货/脚表/推荐条件；额定电流、分断能力、I²t 与温度降额（DEV-C01 5 处、DEV-D04、PRO-C08） | 板上只写“1206FUSE-500MA”，先查 BOM 定厂家；候选 Littelfuse 0466 / Bel 0685 系列 | 板上料号（厂家待定）；候选系列为经验 | 2（7）：solderedelectronics--connect-programmer-hardware-design、solderedelectronics--usb-uart-ch340c-converter-board-hardware-design |

## 五、连接器

| # | 器件类（存放子类） | 需求里的关键指标 | 建议搜集的系列 | 来源 | 出现板数（缺口数） |
|---|---|---|---|---|---|
| 29 | Micro-B 插座（27_连接器/IO连接器） | 原厂图：脚序、屏蔽脚与 ID 脚、额定电流（DEV-D02/SIG-C07/DEV-E01/SIG-C05/DEV-D03） | Molex 47346-0001 | 板上料号 | 2（12）：antmicro--jetson-nano-baseboard、antmicro--scalenode-cm4-baseboard |
| 30 | Type-C 插座（27_连接器/IO连接器(USB-C_HDMI_DP)） | 原厂图：脚序、CC/SBU 引出、屏蔽脚、额定电流（SIG-C07/DEV-D02/DEV-E01/SIG-C05/DEV-D03） | Würth 632723300011 | 板上料号 | 1（6）：antmicro--jetson-nano-baseboard |
| 31 | USB 插座（27_连接器/IO连接器） | 原厂图：脚序与屏蔽脚（板上符号沿用 Molex 67298-4090，订货号为 690-008-221-904，两者须核为同一件；DEV-C01/DEV-C02/DEV-D01/DEV-D02/DEV-D05） | EDAC 690-008-221-904 | 板上料号 | 1（6）：pionixpublic--reference-hardware |

## 说明

- 31 项与 JSON 一一对应；只改了排列（按资料性质分组），没有增删。JSON 第 31 项（USB 规范）的板名列表里 pionixpublic--reference-hardware 重复一次，这里去重后为 7 块。
- 第 1–6 项不是器件手册：SR 缺的是“这个脚接的是什么”，器件厂手册给不了，要模组厂或标准组织的资料。
- 第 28 项板上没有厂家，先回板子 BOM 定厂家再下载，不要按系列名猜参数。
- 采到后核对的是 SR 检查项本身（脚表一致、推荐条件、钳位窗口等），不新增准则（草案第六节已说明这些缺口不进准则）。
