# groupgets--kimchi-micro · lane-1

来源：`groupgets/kimchi-micro@1afeb30034cc824c47e1375efba6867965e94fe3`，CERN-OHL-S-2.0；KiCad 10.0.7 strict，311器件/393网，XML独立核1678端点。用途从README推断为i.MX8M Mini视频/无线SBC；DDR/eMMC/USB-C/充放电/PMIC，基线industrial_telecom。

|项目|数量/结果|
|---|---:|
|最终计划 / 功能框架|1337 / 60|
|局部已判 / needs_human旁账|39 / 1298|
|已判PASS / NA / FAIL|31 / 6 / 2|
|归因记录（不是硬件缺陷总数）|36|
|true_defect / false_alarm / criterion_issue|2 / 7 / 0|
|knowledge_gap / needs_human|18 / 9|
|漏报 / Top50逐项核对|2 / 50|
|原生门禁 / 准出|FAIL / NO_GO|

1. **优先修PMIC输出条件展开。** U4.55的NVCC_SD2仅C113=1µF+C54=.22µF；ROHM Rev003 p110规定有效11–33µF。F29是选值偏离，未声称实物必振荡。U4却没有PWR-C04，人工在PWR-C09发现；M01是具体计划/自动层漏报，已有广义人工覆盖，合并步先补多输出PMIC针义及D-PMIC-MUX-COUT种子。
2. **输入身份与实际器件分开。** F28为U3显示256M32、采购512M32的数据冲突（容量相差2倍）；缓存库名不独自证明用错料。M02为燃料计SRP/SRN缺ANA-C03具体计划，尚未证实过量程，seed=null。
3. **重复性工具问题。** R55 DNP仍被当100k下拉；MIC94164被派LDO dropout；NVCC供电轨未被I²C模块继承，四总线初始并成两区域，补局部rails后八信号恢复，仍有NVCC_I2C供电脚伪区域。分别有可定位proposed_fix，未改检查器。

**用法坑与边界：** BOM/PDF是LFS指针，须取真实对象并核哈希；Populate=DNP不等于解析nc。U4补完整官方脚表后计划由1372降至1337，SW脚不再冒充去耦供电脚。schema15无needs_human枚举，1298项逐ID保留pending，未编VENDOR_DATUM/PASS；全部功能均未完整闭合。原生报告明确“记录不可用”，其局部功能合格计数与“资料不足0”不代表整板完成；无关强制条款未用于消除no-clause校验。PDF仅p2/6/7/9细读，其余总览。报告按原生渲染原样复制，未打包；相对台账链接应在[完整缓存](/Users/skyfend/.cache/sr-boards/groupgets--kimchi-micro/review)中查看，仓库不复制第三方输入。
