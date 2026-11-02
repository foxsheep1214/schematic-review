# badgineer--mp2-esc · lane-1

固定源 `badgineer/MP2-ESC@b35a76b2e42295465f11120ea94c14c4919edb2c`，BSD-3-Clause已核。用途**推断**为模块化三相无刷电机ESC；类型 POWER_CONVERTER / ISOLATION / ANALOG，基线 industrial_telecom。

| 项目 | 数量/状态 |
|---|---:|
| 器件 / 网络 / XML↔db端点 | 216 / 123 / 550，零差异 |
| 计划项 / 功能框架 | 621（618原生＋3补问）/ 29 |
| 局部已判 / 逐ID needs_human | 118 / 503 |
| 报告归因根因 | 27（含候选、计划观察）|
| true_defect / false_alarm | 3 / 9 |
| criterion_issue / knowledge_gap / needs_human | 0 / 5 / 10 |
| Top50 / 漏问 / 确认硬件电气漏检 | 50 / 3 / 0 |
| 门禁 / 准出 | FAIL（valid=false）/ NO_GO |

最重要的三条观察：
1. **合并步先修官方脚表贯通。** 18只MOS已给G/D/S，NetGraph仍只读原生缺名脚，全部pin-roles未解，漏桥默认态/驱动条款。加保留官方脚表、抹原生G名的回归，再测R43 DNP使QA1栅极真悬空。
2. **三处确认问题均为资料矛盾。** U4显示NCS20034却采购COS724；PDF栅阻6R8与原生/BOM的4R7不同；R100/R150按RKM是0.1/0.15Ω，采购码为100/150Ω。不据README目标认定实装过压或热损坏。
3. **漏问不等于硬件缺陷。** VBAT源侧PRO-C04、U6输出电容PWR-C04、主桥RST-T04已补入计划，仍待工况。U6两负端同GND已证，但缺系统隔离目的，不判隔离硬错；未确认准则本身问题。

用法坑：KiCad10.0.7导出成功，strict因22个功能脚缺名失败后回退；BOM仅145个SMT件，须改列名后read_bom并独立核Comment。`0.5mR`解析器正确，导入层仅`^R数字`调度漏SHA。BOOT-OUT/VCC-GND须显式分组。schema15无needs_human/未完成功能格式，503项及29功能未完成旁账保留；原生“资料不足0”不代表审完，不编整体PASS、不打包准出。

工作文件、手册、逐ID待核及独立计算留在 `~/.cache/sr-boards/badgineer--mp2-esc/review/`。未获电池最高值、PWM/负载/热态与准确模块合同，未执行ERC/PCB/样机验证；本仓库未复制第三方电路文件。
