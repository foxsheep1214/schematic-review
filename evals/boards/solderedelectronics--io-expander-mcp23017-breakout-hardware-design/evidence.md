# 独立审查证据

## 来源锁
固定提交 1d614e5f49013931a2c1fd8460bf48e1b3790c36，根图 CAD/V1.2.1/GPIO_Expander_MCP23017.kicad_sch；TAPR-OHL-1.0。KiCad 10.0.7 严格导出成功。30 器件、43 网络；无同版生产 BOM，未以 V1.1.1/V1.3.0 BOM 替代。原图标题栏 Rev V1.2.0，文件目录 V1.2.1，故仅锁定 commit+文件hash。用途推断自 README About the Product，不把营销描述当作已批准的环境/负载规格。原生导出的一页 PDF 已目检，无已证遮字、反接或短接。

## 逐路事实与边界
供电：K2.2→5V→JP3.2/1→Net-(U3-EN)→U3.1 VIN，与 U3.3 EN 同网；U3.2→GND；U3.5→3V3→U1.9 VDD；U1.10→GND。C3.2/1跨VIN/GND，C4.2/1跨3V3/GND，均2u2，非极性0603C。JP4默认开路，闭合会将5V与3V3短接；仅作为另一个同电压供电配置才可能合理，不假设已闭合。K1.3/K3.3也直连3V3，存在外部回灌入口；K1/K3的1=SCL、2=SDA、3=3V3、4=GND、5=SHIELD/GND（按物理脚号，图上排列不等于编号）。所有返回为GND，未发现隔离域。
源 PCB 同版 JP1/JP2 的1-2、2-3以fp_poly铜桥相接；JP3的1-2铜桥相接；JP4无铜桥。JP5/6/7仅凭CONNECTED_RIGHT字样不定最终焊接档位；焊膏/生产工序/实际装配表未取得。PCB只用于证明这些装配事实，不构成布局审查。
总线：U1.12→SCL3,3→U2.4 S1；U2.3 D1→SCL5→K2.4。U1.13→SDA3,3→U2.1 S2；U2.6 D2→SDA5→K2.3。U2.2 G2与U2.5 G1都接3V3。映射来自完整原生符号的两个通道；SOT-363没有唯一采购料号，不能假定任一2N7002双管的内部配对、VGS阈值、RDS或体二极管/Ioff。R4/R1把低侧SCL/SDA经JP2上拉3V3；R2/R3把高侧经JP1上拉5V，均10k。铜桥闭合时单侧上拉存在；导通低态两侧电流相加，不把有源器件两侧当成一根高态网络。
地址：U1.15/16/17分别A0/A1/A2到JP5/6/7中点；各左端接GND，右端经R6/7/8=10k到3V3。有效两档允许0x20..0x27；必须先断原桥再改档；中点浮空与双边同时桥接需按实际装配排除，不能宣布已排除。
复位：U1.18→~{RESET}→R5.1/2→3V3，R5=10k，K5.1为外部复位入口；无外置复位定时电容/监控IC，不把C3当作U1复位RC。U1.19/20分别INTB/INTA到K7.1/2；16路GPIO全部直出K4/K6，未接电机/继电器/功率门极等危险负载；复位高阻不自动判误动作。
U1.11/14均为NC且有未连接标记；U3.4 NC未接。其余脚与原厂SSOP28/SOT23-5脚表编号核对。U1的准确符号值MCP23017T-E_SS可对应MCP23017T-E/SS；U3只有SE5218系列名，3.3V应为SE5218ALG-LF（p2）；U2仅NMOS-DUAL，两者选型身份均未固定，不声称已发生实物故障。

## 原厂资料与计算
Microchip DS20001952D：p1/p11明确MCP23017 GPA7/GPB7仅输出；U1.28→GPA7→K6.1，U1.8→GPB7→K4.1。旧DS20001952C与原生符号的双向声明不可直接用于新资料下的输入功能承诺。连接器外接用途不明，记needs_human，不判这两路接线错误。p3全部IO绝限−0.6..VDD+0.6V，单脚25mA绝限、VDD总125mA、VSS总150mA；绝限不是推荐驱动能力。p4 D041 VIH≥0.8VDD，D031 VIL≤0.2VDD；3.3V名义下为2.64/0.66V。p4 D080 SDA保证点为0.6V@3mA、VDD=1.8V与0.8V@3mA、VDD=4.5V；不能无依据把0.4V@3mA当成本芯片全温保证，3.3V工作点低态需补厂家界或适用定界。p6 Table1-3 100/400k模式tr限1us/300ns。p11 Table2-1 RESET须外部偏置，R5已实现；无MCU固件镜像要求。
名义两侧V=3.3/5.0V、R=10k时，在VOL=0.4V且转换已导通的条件下I=(3.3−0.4)/10k+(5−0.4)/10k=0.75mA；VOL=0极限为0.83mA。8板同样上拉全部保留时为6.0mA@0.4V、6.64mA@0V，已超过单芯片3mA给出的测试点，但外部并联/剪桥配置未固定，不能判这块单板实际过流。10k的RC条件：Cb≤1us/(0.8473×10k)=118.0pF（100k）；Cb≤300ns/(0.8473×10k)=35.4pF（400k）。若Cb=400pF，tr=3.3892us，两模式均不满足；Cb是条件算例，不是该板已测事实；阻值公差、外源容差、双管传播尚未有界，不能据名义计算判系统PASS或FAIL。所有四段上拉只证拓扑，型号和动态未证。
SE5218 Rev4/19/2016：p1 top-view 1VIN/2GND/3EN/4NC/5VOUT与图相符；p2各输出档SE5218A..G，VIN操作2.8..5.5V、EN−0.3..VIN；p3 EN开启保证门限1.6V、关闭0.4V，dropout只给典型值，不能用其证明全温满载。p6输入/输出均至少1uF、输出距VOUT≤1cm；C3/C4名义2.2uF比最低大1.2uF，但0603容量/耐压/偏压后有效值无同版BOM，暂不判有效容量通过。手册未规定数值ESR窗口，不凭空要求0.1..1ohm；局部连接符合，布局距离交PCB。p6热公式PD=Iout(Vin−Vout)、thetaJA约230C/W仅估算：5→3.3V时每100mA为0.17W、估计升温39.1C，500mA为0.85W、195.5C；板未声明500mA工作要求，不能据封面500mA判实际热失效。p1/2/3/6未取得VOUT>VIN时反向电流/可靠性保证；K1/K3供3V3且5V断电的状态不可默认安全。

## 非电气故障与工具边界
K1/K3实际easyC五脚插座，没有线圈，DRV-C01/T01继电器钳位项排除。K1/K3被分类成relay造成EXT-K1/EXT-K3四项接口问题不生成；这是漏问，不是已证外部反接损坏。POWER_CONVERTER-U2是电平转换的误候选；拒绝后工具不允许把仍被原候选持有的U2/R1-R4 add进I2C，保留未归属复核。LINK-STARTUP-U3.EN只含5V供电网，却生成SIG-C07逻辑电平，按供电而非数据链排除。PWR-A02(跳线供电)和RST-A03(EN直连VIN)是事实提示，不自动等于故障；JP3默认铜桥、EN与VIN同轨已有证据。
需求未给时不能伪造已答复clarification，也不把源/负载/故障规格归为厂家数据。任务明确允许needs_human，原生结果仅允许VENDOR_DATUM/REVIEW_INCOMPLETE，故此处如实使用任务要求的NEEDS_HUMAN开项，校验会拒收该扩展；这是本轮门禁FAIL的真实格式限制，不是厂家数据缺失，也不是已读资料尚未审完。不得用假厂家请求或假PASS消除门禁错误。schema实际脚本15，results-format.md标题仍14，依脚本15运行。

# 本轮范围与证据界限

用途由固定提交 README About the Product 与原理图文件名推断：I2C GPIO 扩展板，标称 3.3V 核心及 5V 接口。不是已批准的工业环境、负载、热插拔或防护规格。catalog 原始类型 I2C、POWER_PROTECTION 保留于归因文件；实际无独立输入保护器件，U2 为电平转换，U3 为稳压器。
同版 V1.2.1 无输出 BOM/PDF，其他版本 BOM 不混用；从原生图导出当前 PDF。标题栏 Rev V1.2.0 与目录 V1.2.1 不同，物理更改历史未判。
HardwareWiki find_parts --mpn MCP23017/SE5218 均 0 命中；从原厂/立创原厂 PDF 补取，未写 Wiki。
降额等级、外源容差、GPIO 负载、环境温度、外部线缆和同时供电规则未给，按用户任务保留 needs_human；不自动采纳新需求。

## 原文定位与交付边界

- 完整工作记录与265条门禁格式错误保留在 `/Users/skyfend/.cache/sr-boards/solderedelectronics--io-expander-mcp23017-breakout-hardware-design/review`；最终`review-plan.json` SHA-256 `c1a97fe34622374d5edb15f87324357e5f5d6d61da74d43a431df726181feae0`，`review-results.json` SHA-256 `53ea2c48d3ffea68cac965250fa780030619ae082921986646e3ef15bed30528`，`review-gate.json` SHA-256 `db2a2fc766397c38e3918f54c2071098e1d2a12e1d3e15334e6ccd9596d401c1`。
- 原生renderer生成的报告未改写。未打包：报告内`record/...`相对索引是打包目录格式，本轮工作文件按任务保留缓存，不在仓库放第三方db/网表/PDF。应在缓存读取同名记录；此报告不是独立准出包。
- MCP23017：Microchip DS20001952D（2022，40页），p1/p11输出专用脚及全针图、p3绝限、p4 DC/POR、p6 Table1-3 I²C、p38订货码。[原厂PDF](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP23017-Data-Sheet-DS20001952.pdf)。
- SE5218：Seaward Rev4/19/2016 Preliminary（7页），p1针图、p2订货/工作/绝限、p3电气特性、p6电容/热。为厂家编写的原文，经立创分发镜像取得，并非立创自制规格。[分发PDF](https://atta.szlcsc.com/upload/public/pdf/source/20170918/C118233_1505726818905976144.pdf)。
- `MCP23017.pdf` SHA-256 `63cb5f2bec44434cdeeada1790d0316c9dc06b33febb489ad87bb0e2d540496a`（原件仅缓存）。
- `MCP23017-C.pdf` SHA-256 `14159c6f5655e943e93ed1e34947e46844f114ec893f305a889898828e4055cb`（原件仅缓存）。
- `SE5218.pdf` SHA-256 `ccd9d56290f8ab6a4762ca814b22e2a3dd34b892baa0e000f5d101b46b82d1c7`（原件仅缓存）。
- 仅用同版PCB核JP1/2/3铜桥及JP4默认断开，不签署PCB/布局/热验收。输出专用GPA7/GPB7限制已加入K4/K6待办；无输入用途需求，不另加真缺陷。
