# antmicro--jetson-nano-baseboard · lane-2

固定提交 `d8d0b2d71ab4cc4bcdb204a09f78be40d4c8cda3`，Apache-2.0；用途**推断**为 Jetson Nano/Xavier NX/TX2 NX 载板，基线 `industrial_telecom`。8 页、373 器件；主类型 HSSERIAL、USB、ETHERNET、POWER_CONVERTER，另核 CAN、I²C、显示、电平转换及启动保护。

| 项目 | 数量 / 结果 |
|---|---:|
| 最终计划 / 已逐项记判定 | 1468 / 1468（含 1 项人工定位补问） |
| PASS / FAIL / NA / INSUFFICIENT | 102 / 5 / 47 / 1314 |
| 归因条目总数 | 446 |
| true_defect / false_alarm / criterion_issue | 5 / 50 / 0 |
| knowledge_gap / needs_human | 197 / 194 |
| 漏报 | 4（Top50 覆盖簇 3，额外以太网 1） |
| 原生门禁 / 准出 | **FAIL / NO_GO**；报告记录无效 |
| 质量筛查候选 / 已留处置 | 154 / 154（仍有未闭环限制） |

**最重要的三条观察**

1. **硬结论限于局部证据。** IC3 FLAG 的 R43=470Ω，原厂要求≥10kΩ且灌电流上限1mA；标称需求约9.79mA。LED1 A/K 同网经 XML 与同版 PCB 双核；另有 D14 的33V截止额定不覆盖宣称36V输入、4.7s RC直入普通CMOS、U6手册链接指向另一型号组。合计4项电气/功能、1项资料错误，未声称实物已经失效。
2. **误报集中在脚义、装配及对象角色。** SiC477 NC21/GL输出/VDRV内部电源、HD3SS3220 GPIO模式、FT232RQ内部偏置不能套普通浮空/断供；无脚M2占位、连接器与ESD地不能套IC去耦。50项均给排除依据和修改位置；不确定项没有算误报。0项准则问题表示本轮未独立证实准则本身有错。
3. **先合并多通道ESD覆盖修复。** `protected_net` 的整颗两网络假设漏掉10颗阵列的 PRO-E02；按准确活线/公共返回逐通道展开，排除TPD4直通NC，并加入带工作窗口契约的低VRWM变异。另补LDO启动负载、外引电源支路、RJ45/SoM MDI专项；这4项是计划覆盖遗漏，尚非4个硬件缺陷。

**用法与证据边界。** KiCad10.0.7导出成功，但3个TPD4地脚缺功能名导致strict失败；保留原DB，未伪造通过。固定提交无独立BOM，使用XML的MPN/Val/DNP，未冒充装配清单。示例准则版本1.4.1与当前1.6.1分别记录。原生schema15不接受本任务要求的`needs_human`/未定级记录，加上资格、条款及宽范围待判共5790条展开记录错误；不是5790个电路故障。报告如实保留无效提示，未打包、未修改检查器。

[审查报告](审查报告.md)、[逐条归因及修复/种子材料](findings.json)、[Top50逐条核对](top50-audit.md)。报告为原生输出的同字节副本；完整台账、手册与局部图在[缓存报告](/Users/skyfend/.cache/sr-boards/antmicro--jetson-nano-baseboard/review/审查报告.md)，仓库不复制第三方图纸，副本中的相对证据链接需在缓存版打开。
