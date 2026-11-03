# leonardoward--dpp-architecture-pcb · lane-2

用途推断：DPP/MPPT单通道隔离功率级测试板；实际类型 POWER_CONVERTER、ISOLATION，catalog 的 ANALOG 经网表排除。固定源 `cc7e3c913c05`，KiCad 10.0.7，21器件，GPL-3.0；SR `176068ba139c`。

| 计划项 | 已判 | 发现归因 | true_defect | false_alarm | criterion_issue | knowledge_gap | needs_human | 漏报 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 109 | 109 | 25 | 0 | 9 | 0 | 2 | 14 | 1 |

31 PASS、7 NA、71 INSUFFICIENT；后者按根因归到16待办。25项=16待办+5主动工具反馈+4安装孔自动提示；并非25个电路故障。冷/热扫电气疑似均0。门禁 **FAIL / valid=false**（166条格式/功能条款错误），报告首行保留不可准出警示；没有有效打包。

1. **先修栅极驱动识别。** U1.4 OUT*经1k R1真实驱Q1，却被正则漏掉；100k R2通向GND上的J2/J3接触针反而被当driver。修后需把RST-T04展开到U1/Q1实际上电/高阻状态；Top50第29条为M01，附带有安全关断契约的候选种子。
2. **主功率拓扑不能靠局部RC形状判断。** D1+C1被误标RCD，C1实际是输入bulk。C4直接跨T1次级且无板载整流，但J4用途/外部系统未定，留needs_human；原厂要求5+6/7+8并接，R3/R4的0ohm连接不能报短错绕组。
3. **被动隔离件与数字隔离器须分流。** T1上的数字默认态/速率/CMTI项均NA；保留真实PRO-D02（无旁路）和PRO-C03（资格待定）。DIODES品牌误判diode、无脚安装孔要求扩电气定界表也可跨板重复。

**SR用法坑：** KiCad6 CSV有元数据前导和Reference(s)，先留原件再无损规范表头；C1/C4裸2200由准确MPN原表解单位。Q1原PDF是图片页，p1/p2/p4/p9须看原页。T1只取得原厂p1网页文字，完整PDF被403，AVAILABLE不代表针图齐。needs_human不受schema15支持，保留失败而不伪造厂家数据或用户答复。16待办已按根因合并，8条WIDE_GAP逐边复核留痕。

报告及逐条归因见本目录；完整计划/台账/原厂资料在 `/Users/skyfend/.cache/sr-boards/leonardoward--dpp-architecture-pcb/review`。复制的报告中record链接未有效打包，查看证据请用该缓存路径。未改检查器/准则/种子库，未提交。
