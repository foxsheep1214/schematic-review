# lane-3 逐板经验

- 2026-11-02 antmicro--rdimm-ddr4-tester：1660 项／148 发现／2 覆盖缺口，门禁 FAIL；strict 缺 U17/U24 共 8 个脚名不能用 no-strict 关闭。
- R_0R01_1206 等编码、IC1 位号及 SW_VPP/VTT 来源识别会连锁制造无驱动告警；先画路径，再判压降和额定，不全局静默。
- 电路所有权不等于规则适用范围：USB 内 Y2 仍需晶体检查；PAC1954 监测器兼有 ADC，不能因 ANALOG_PIN 未资格化就裁空。
- 原生 schema15 不能直接表达板评估 needs_human；明确保留格式 FAIL 与逐项待判，不冒充 VENDOR_DATUM，不据台账条目数声称电气证明完成。
- 桥式整流器局部符号脚号须经自定义 footprint 映射物理脚；PAC1954 地址脚及分流电阻 Value/MPN 须独立核，不信图注。

- 2026-11-02 solderedelectronics--1s-li-ion-battery-protection-hardware-design：95项／14归因（0真缺陷、5误报、0准则、5知识缺口、4待确认）／2漏报；门禁FAIL，不能将台账填全当作格式有效。
- DW01 TD允许留空；FS8205A的1/8是内部共漏极D12，NET-A01正确候选读手册后可消解，勿算检查器误报或要求外部短接。双MOS需逐通道，断OC(U2.5)不能只检查OD(U2.4)。
- R2=1k是CS保护串阻，OCP来自MOS导通压降；先取电芯/源阻抗/I(t)/温度，勿把4.35V动作点或6A器件标签当系统保证。
- 同电池焊盘/JST不是独立双源；CS不是数字接口；POWER_PROTECTION大类会误派eFuse却漏PRO-C05，battery_protector角色/资格应一起补。
- 分号BOM先无损转CSV；补C1类别/条款后重建清单并重审95项，旧lint摘要不能当当前绑定。schema15不承载needs_human/评估知识缺口时保留FAIL；纯拓扑与共享缺口的9条条款承载错误也要如实列出。
