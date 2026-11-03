# USBI2C01 · lane-2 本轮记录

固定源：`mlab-modules/USBI2C01@8fc108913f407128495c47fdca671d2adf68268c`，GPL-3.0（只审查引用，未复制第三方电路）。推断用途：USB-B 供电的 CP2112 USB→I²C/SMBus 主桥，附 GPIO、可选总线供电；实际还含内置 LDO、启动与保险/TVS 保护。基线 `industrial_telecom`。

| 计划项 | 归因总数 | true_defect | false_alarm | criterion_issue | knowledge_gap | needs_human | 漏报 | 门禁 |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 184 | 58 | 0 | 15 | 1 | 9 | 33 | 7 | FAIL |

计数口径：42 个报告未决任务逐条归因，另有 14 个已关闭错对象项、1 个错误数值预判、1 个准则适用问题；不是 58 个硬件故障。184 项记录为 PASS 55 / NA 20 / 未决 109；PASS 仅限所述事实或采购可达性范围。Top50 已逐条留痕于 `findings.json.top50_crosscheck`；7 条漏报均为检查覆盖漏项，没有新增已证硬故障。

最重要的 3 条观察：
1. **合并步先修身份优先级。** X1 桥片、X2 USB_B、X3–X6 安装孔被 X 前缀当晶体，P1 保险被 P 前缀当外口，自动候选为零；显式 `--require-ref X1` 才取到已存在的 CP 手册。应优先真实 Part/Footprint/针脚语义，并覆盖桥片的内置 LDO/复位角色。
2. **TVS 阵列会同时错问和漏问。** D4 跨 3 条活线、公共地及未用脚；`protected_net` 要整颗恰好两网，误出 PRO-C02 而漏 PRO-E02。更正 TVS 类别还不够，要按真实通道映射核工作窗/残压；11/13 V 脉冲钳位不能直接与 CP 的直流绝限比较后判必坏。
3. **供电名字和参考参数不能代替工作点。** VDD 实为 3.3–3.6 V；LDO 的 100 mA 含自身负载；C4 VPP 编程可至 7.2 V，工具却用 5.25 V 封顶。本板无板内 I²C 上拉属实，但外板可能供上拉，保留未决。USB-B 不能无条件套 Type-C/PD 的 5.5 V/100 µF/40 ms 例值。

SR 用法坑：BOM 串接位号先仅拆分隔符，读回 26/26。`add` 电路无候选 ID，重叠 X1 的 `own` 无法定位；本轮令 X1 归 I²C、USB 经路径引用。`add` 派生 `nets=[]`、NEEDS_HUMAN/未定级不被 schema15 接受及部分余量/去耦资格绑定仍留 520 个记录错误，11 个质量提示已逐类处置，未伪造输入过门禁。原生生成的[审查报告](审查报告.md)明确标无效；未打包，`record/` 相对链接未落地，完整台账/哈希见 [findings.json](findings.json) 的 `evidence_index`（缓存 `~/.cache/sr-boards/mlab-modules--usbi2c01/review/`）。CP 完整原厂 PDF 已取；SP1001 仅在线全文可读、本地短摘录，下载 403，针图资格未闭合。未改共享代码/准则，未 commit/push。
