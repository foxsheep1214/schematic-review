# tinkerforge--evse-v2-bricklet · lane-1

固定源 `57c742094efb379ee10876dbacae977a18119153`，CERN-OHL-1.1；KiCad 10.0.7。用途从 README/源图推断为 WARP2 EVSE 控制板；基线 industrial_telecom。类型：AC_MAINS、ISOLATION、RS485、ANALOG，补 POWER_CONVERTER、POWER_PROTECTION、SPI、CLOCK。

|项目|数量/结果|
|---|---:|
|器件 / 网络 / XML节点|139 / 125 / 443|
|电路 / 功能框架 / 计划项|24 / 70 / 821|
|局部已判 / needs_human逐项待核|53 / 768|
|局部 PASS / NA / FAIL|14 / 38 / 1|
|归因发现总数|37|
|true_defect|1（图面；电气确认0）|
|false_alarm|12|
|criterion_issue|0|
|knowledge_gap|17|
|needs_human（根因观察）|7|
|漏报|3（2计划对象、1自动候选）|
|原生门禁 / 准出|FAIL / NO_GO|

1. **先补接口掉电检查。** HOST-SPI/EXT-P101 已有，却全计划无 SIG-C08；U111 市电模块的隔离带/工作资格也未展开。两项是对象覆盖缺口，不是已证注入或绝缘失效。U110 的大电容仅记自动层漏提示：专家 PWR-C04 已问，不能称整轮漏检。
2. **最大 Cout 和厂家分支要保留。** U110 全部直接并联名义 102.82 µF，手册窗口 1.5–47 µF/ESR 0–0.2 Ω；缺 C111 的有效容量边界，暂不判实物失稳。U109 的 3V3 点没有准确厂家保证，不能把 Broadcom 推荐下限无条件套到 onsemi。RS485 双120 Ω时名义偏置仅0.127 V，仍缺远端合同。
3. **误识别影响后续计划。** Diodes 品牌、Load Switch 应用和 PWM 工作描述分别误导 U103/Q102/U106 类型；磁珠 L101/L103 被套续流、485-D/485-DE 被判分裂、TPS709 合法悬空 EN 被报不确定。唯一确认缺陷是 P111 位号与 MCU 31脚号真墨迹重叠（P2）。

**用法坑：** strict 因 F101/F102/L102 六个无名脚失败，按约定非严格回退；XML→db 443节点零差异不代替原厂脚义。无独立BOM，未运行 read_bom；三只DNP按图面推断。schema15不原生支持 needs_human/局部功能事实：逐ID留 pending，不编造 VENDOR_DATUM 或完整功能 PASS，70框架均未完成。门禁错误完整保留，报告为未完成诊断记录，未打包，不能按原生“资料不足0”理解为审完。

[逐条归因及Top50](findings.json) · [原生渲染报告](审查报告.md) · [完整工作证据](/Users/skyfend/.cache/sr-boards/tinkerforge--evse-v2-bricklet/review/evidence/engineering-review.md) · [Top50逐条核对](/Users/skyfend/.cache/sr-boards/tinkerforge--evse-v2-bricklet/review/evidence/top50-crosscheck.md)。仓库报告是原样复制；未生成 record 包，相对归档链接不代表已打包。没有修改共用代码/准则、第三方源图或 HardwareWiki，没有提交或推送。
