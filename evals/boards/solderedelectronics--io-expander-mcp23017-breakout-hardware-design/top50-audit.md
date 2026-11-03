# Top 50逐条漏报核对

源：`docs/proposals/criteria-top50-examples-2026-11-02.md`；SHA-256 `0b743d8a6e80d4a31db7862474578934c103b9e1b28a445b038d8ab45504a60e`。
范围：固定提交V1.2.1、181项最终计划、industrial_telecom；名义条件计算不作保证。50条全部过网表；M01为同根因计划覆盖遗漏，不是已证物理损坏。

| 序号 | 准则 | 应报SR规则（原表BASIS） | 本板判定 | 证据/与计划对照 |
|---|---|---|---|---|
| 01 | G01-018 | PWR-C17 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 02 | G01-019 | PWR-C17 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 03 | G01-020 | PWR-C18 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 04 | G01-021 | PRO-C01 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 05 | G01-022 | PWR-C19 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 06 | G01-023 | PWR-C13 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 07 | G01-024 | PWR-C18 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 08 | G01-025 | PWR-C18 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 09 | G01-026 | SIG-C05 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 10 | G01-027 | SIG-C05 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 11 | G01-029 | PWR-C13, SIG-C05 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 12 | G01-030 | SIG-D07 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 13 | G01-031 | SIG-C05 | NOT_APPLICABLE | 无−48V通信输入、交流输入或USB端口；K2是通用5V针座，不由5V网名推成USB。 |
| 14 | G03-003 | PWR-C04 | APPLICABLE_UNRESOLVED | U3.5→C4.2→C4.1/GND，2u2名义，SE5218 p6至少1µF；有效容量/同版采购未知。PWR-C04/C09已问，非漏报。 |
| 15 | G03-004 | PWR-C04 | APPLICABLE_NO_NUMERIC_WINDOW | SE5218 p6未规定数值ESR窗；不把教学反例0.1..1Ω移植。PWR-C04已有对象，未知有效容量不等于ESR超窗。 |
| 16 | G03-016 | DRV-C02 | NOT_APPLICABLE | U2是I2C电平转换；不是上电限流/负载通路MOS，不套用功率SOA启动例。 |
| 17 | G03-018 | PWR-C06 | APPLICABLE_UNRESOLVED | U3.EN=VIN，SE5218 p3 EN1.6V/0.4V；输入容差/欠压启动窗未给，PWR-C02/C18/RST已留缺口，不报确定UVLO不当。 |
| 18 | G03-019 | PWR-C06 | APPLICABLE_UNRESOLVED | K2外源阻抗、满载和UVLO恢复波形未给；EN直连VIN无独立分压。PWR-C18/启动工作窗已问，不据缺参捏造振荡。 |
| 19 | G03-021 | PWR-D03 | APPLICABLE_UNRESOLVED | C3/C4名义2.2µF，U3无外置软启动脚；SE5218限流/负载/外源爬升界未齐，PWR-C18/C24及启动项已有覆盖。 |
| 20 | G03-025 | PWR-T04 | APPLICABLE_UNRESOLVED | U1 RESET经R5=10k拉3V3并外引K5；内部POR p4D003仅指导，实际斜率/复位需求未给。RST-T01/C01/C02/PWR-T04覆盖，无外置监控不自动是错。 |
| 21 | G03-028 | PWR-C24 | APPLICABLE_UNRESOLVED | 5V经JP3/U3→3V3，但K1/K3可外供3V3；RST-T03/PWR-C24已有系统与状态检查，实际组合/次序未给。 |
| 22 | G03-032 | PWR-C05 | APPLICABLE_UNRESOLVED | K1/K3.3→3V3→U3.5，VIN可由K2断电。SE5218 p1/2/3/6未规定反灌用法；PWR-C05已问，先确认是否要求该状态，不能伪造指定工作区。 |
| 23 | G03-037 | DEV-C01 | NOT_APPLICABLE | C3/C4均0603C无极性符号；无电解/钽电容，无已证反接。未知介质不应替换为某颗有极性电容。 |
| 24 | G03-038 | DEV-C01 | NOT_APPLICABLE | G03-038选中例为电解/钽；本板无该对象，C3/C4一般耐压仍由DEV-C01/PWR-C10/DEV-D04审，不由此豁免。 |
| 25 | G03-040 | DEV-C01 | NOT_APPLICABLE | C3/C4分别跨VIN/GND和3V3/GND，非串联电解栈。 |
| 26 | G04-005 | SIG-C08 | APPLICABLE_UNRESOLVED | U1 IO绝限p3−0.6..VDD+0.6V；U2分隔5V/3V3的SDA/SCL，GPIO外接未知。SIG-C07/C08及外端检查覆盖；easyC遗漏并入M01同根因。 |
| 27 | G04-007 | PRO-D04, SIG-C08 | APPLICABLE_UNRESOLVED | U2跨域及K4/K6/RESET/INT掉电承受边界未给，SIG-C08/PRO-D04和PWR-C05已有缺口，不能拿连通当Ioff保证。 |
| 28 | G04-009 | SIG-C08 | APPLICABLE_UNRESOLVED | U2未知MPN，两侧拉高及U1裸GPIO可经实际芯片钳位耦合；SIG-C08/PRO-D04已有问题但无故障电压/源阻抗可算确定灌流。 |
| 29 | G04-010 | RST-T04 | APPLICABLE_UNRESOLVED | U1默认输入高阻，GPA7/GPB7当前手册只输出；未接已声明危险负载，没有关键输出安全态要求。RST-T04/REQ-D05已有系统问题，不虚构电机失控。 |
| 30 | G04-017 | SIG-C01 | APPLICABLE_UNRESOLVED | R1/R4/2/3各10k，Cb最大100k约118pF/400k约35.4pF；SIG-C01/C13/C15已问。实际Cb与模式未知，400pF例不能指控原板。 |
| 31 | G04-018 | SIG-C01 | APPLICABLE_UNRESOLVED | 两侧0.4V名义低态电流合计0.75mA，8板并联为6mA仅条件例；MCP p4D080的测试点需原样保留。SIG-C01/C07/C08已问，未指定8板实际并接。 |
| 32 | G04-032 | SIG-C03 | NOT_APPLICABLE | 无CAN收发器及CANH/L端接。 |
| 33 | G04-040 | PRO-D02 | NOT_APPLICABLE | 无隔离器/隔离电源域，GND同域不是隔离短接。 |
| 34 | G04-041 | ANA-C01 | NOT_APPLICABLE | 无运放输入共模对象。 |
| 35 | G04-054 | ANA-C03 | NOT_APPLICABLE | 无ADC/采样满量程对象。 |
| 36 | G04-078 | CLK-C01 | NOT_APPLICABLE | 无晶体、负载电容或振荡器。 |
| 37 | G04-079 | CLK-C01 | NOT_APPLICABLE | 无晶体起振/负阻对象。 |
| 38 | G04-082 | CLK-C01 | NOT_APPLICABLE | 无晶振共享时钟网络。 |
| 39 | G05-019 | PRO-C04 | SCOPE_GAP_M01 | K1/K3.3直连3V3可为配电/外源口，缺实际源/支路角色。已有K2 PRO-D03但easyC不生成接口，归同一端口识别M01，不另计第二漏报根因。 |
| 40 | G05-022 | DEV-C01, DEV-C04 | CONDITIONAL_SCOPE_UNRESOLVED | 无板载OCP器件和动作阈值；SE5218有限流但仅典型值，外部保护/负载窗未知。PRO-D03/PRO-D05已问，不捏造熔断器协调失败。 |
| 41 | G05-025 | PRO-C05 | CONDITIONAL_SCOPE_UNRESOLVED | 无外置保护动作链、故障源/耐受时间未给。PRO-D03/PRO-D05/REQ-D05已有源故障前提问题；热/短路样机验收不冒充原理图计算。 |
| 42 | G05-030 | PRO-E02 | NOT_APPLICABLE | 全板无TVS，不能比较不存在的VRWM；端口ESD要求未知另列。 |
| 43 | G05-031 | PRO-E02 | NOT_APPLICABLE | 无TVS和规定浪涌源，不能报告Vcl超限。 |
| 44 | G05-032 | PRO-E02 | NOT_APPLICABLE | 无TVS浪涌能力对象或故障波形。 |
| 45 | G05-040 | DRV-C02 | NOT_APPLICABLE | U2是I2C信号双管，无负载通路MOS短路启动SOA对象。 |
| 46 | G05-041 | DRV-C02 | NOT_APPLICABLE | 同#45，无热短路负载通路MOS。 |
| 47 | G05-048 | PRO-C01 | NOT_APPLICABLE | 无熔断器，不能报告某F分断不足；上游覆盖未知归端口问题。 |
| 48 | G05-054 | PRO-D04, PWR-T05 | PLAN_COVERAGE_MISS | K1/K3电源脚3=3V3、4/5=GND直接到U1.9/U3.5；最终没有EXT-K1/K3或相应PRO-D04，M01。反接幅值/上游覆盖未知，遗漏的是逐端口询问。 |
| 49 | G05-057 | PWR-C26 | NOT_APPLICABLE | 无单向TVS或防反器件前后关系。 |
| 50 | G05-087 | PWR-T05 | NOT_APPLICABLE | 无MOS防反接功能；U2信号电平转换不能套PMOS防反图。 |
