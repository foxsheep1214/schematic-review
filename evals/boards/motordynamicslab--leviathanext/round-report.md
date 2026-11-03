# LeviathanExt · lane-2（2026-11-02）

来源 `MotorDynamicsLab/LeviathanExt@060af34d9eecc6e967473f04f5e677e55a51dda8`，GPL-3.0；180器件，KiCad10.0.7严格解析。用途从README与图面推断：双TMC5160高压步进驱动、12V buck、12/24V风扇、热敏/蜂鸣扩展板。基线industrial_telecom；无独立装配BOM/受控需求。

| 指标 | 数量 |
|---|---:|
| 最终计划 / 已逐项记判 | 772 / 772 |
| 已判可关闭 / needs_human逐项记录 | 178 / 594 |
| 报告归因根因（含未决/排除） | 113 |
| true_defect / false_alarm / criterion_issue | 2 / 17 / 0 |
| knowledge_gap / needs_human（共享根因） | 10 / 84 |
| Top50 / 独立覆盖漏项 | 50 / 5 |
| 原生门禁 / release / 校验错误 | FAIL / NO_GO / 2620 |

最重要的3条观察：
1. **准确采购字段决定电气判定。** R42/R43=RC0603JR-071KL，24V持续导通可达0.4616W>0.1W；D1准确Jingdao手册VRWM54V不覆盖README55V上限。二者不是“实物已烧毁”的结论；F2=2A/L1=5A与采购码资料冲突仍保留未决。
2. **合并步优先补双MOS通道模型。** SiZ270DT每封装两通道，但DRV-E01/C02只列G1（1脚），漏G2（8脚）及内部D2=S1（9脚）。M04给出反例注入；其余漏项为Q1/Q12防反、D1位置、TMC内部稳压启动、Q10/Q11/Q13默认态。
3. **身份/角色错误会放大提问。** QFN56实际只有47个功能编号，裸露地自定义48合法；PAD误作供电、VCP误作外供、无源热敏占位U1、MOV口套eFuse/保险、EN套救砖均已逐项排除。没把正确未决问题当误报。

用法坑：公共VMOT把两桥并入U3候选，按图面split后add U1/U2及外围；旧V1.1 PDF与当前Rev1.2不一致，改用同源导出。TMC完整原件超时与“已在线读到表”分开记。schema15不接NEEDS_HUMAN，另有数值证明/记录格式拒收，**原生报告保留“结论不可用”警示**；未冒充PASS、未打包。完整计划、台账、50条核对、哈希与独立计算：[review缓存](/Users/skyfend/.cache/sr-boards/motordynamicslab--leviathanext/review)。仓库报告为render_report.py原样副本；不复制第三方电路。
