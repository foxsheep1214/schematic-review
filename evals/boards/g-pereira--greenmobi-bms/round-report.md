# g-pereira--greenmobi-bms · lane-1

固定源码 `651b1159553d30470fa7436aee6fe7eb638baa78`；CERN-OHL-S-2.0；KiCad 10.0.7 strict成功，140件/396节点/4页，XML/db逐节点零归网差异。用途**推断**为VESC兼容、单AFE的充电管理BMS；产品基线industrial_telecom。源README明确仍在原理图阶段，最多32S不是本图已实现能力或受控输入窗口。

| 指标 | 数量 |
|---|---:|
| 计划项 | 474 |
| 局部已判 / 逐ID needs_human | 48 / 426 |
| 归因观察（含原生6项数据缺陷） | 22 |
| true_defect | 6 |
| false_alarm | 6 |
| criterion_issue | 0 |
| knowledge_gap | 1 |
| needs_human | 9 |
| 漏报分层：自动诊断 / 对象计划 / 已证硬件 | 2 / 1 / 0 |
| Top50逐条对照 | 50 |

**门禁 FAIL / NO_GO**：原生校验、报告渲染均执行。schema15不能表达needs_human；已在结果中逐ID保留426项、逐功能列范围，没有造厂家缺口或整功能PASS。报告为失败诊断稿、不可打包，不能作完整电气审结。原生6项均为设计数据错误，不代表6个已证实物失效。

最重要的3条观察：

1. **先核采购身份**：Y1无源晶体符号/接法与C3007519的TCXO身份冲突；U3/U4库与Value/链接矛盾；D1稳压值、U5具体变体、TH1曲线仍是占位。U2的C2858491实际FH4，不能误报无flash；USB线虽名DN/DP相反，物理默认脚义是对的。
2. **供源与所有权误判可复现**：机械库功率焊盘H1被漏作外部供源、还被纳入DEBUG；Buck候选吞独立Q1充电支路。合并步首件事：修外部功率焊盘的供源/接口资格并加正反例；共输入候选停止边界随后处理。
3. **三处漏项分层**：自供电USB的VBUS全NC、后级3.3V回拉U3.EN，现有人工规则已问但自动层无特定诊断；J6.1→120ohm R22→U5.BAT绕过主F1，未逐源支路展开PRO-C04。以上均需合同/保证输入，未冒充已证硬件漏检。

SR用法坑：`add`不能抢仍由STARTUP候选持有的U3，且会丢nets/anchors；本轮保留决定与诊断，没手改circuits/plan。原生报告会把未填needs_human列为覆盖错误，资料不足0不代表审完。四份关键手册本地取证，另有LM5163/LM5164/TPS79333原厂PDF；Epson/保险官方网页已读，但后续curl DNS失败，没有声称完整PDF落盘。无独立BOM；全部台账/证据在 `/Users/skyfend/.cache/sr-boards/g-pereira--greenmobi-bms/review`，仓库只交报告与自主归因，不复制第三方电路文件。

报告按要求仅复制MD；因门禁FAIL未打包，报告内相对record索引须到上述缓存台账目录读取，不能当作可迁移的定稿交付包。
