# pionixpublic--reference-hardware｜lane-3

固定 `0a9f9c9bd2c6b347671518fcea7e06e2410d8df6`，CERN-OHL-P-2.0；219 器件、9 页。依据 README **推断**为 CM4 充电桩上层控制参考板；CAN/RS485/Ethernet/双 Buck，并补 USB、SPI、RTC、AV、存储等；基线 industrial_telecom。范围仅 Yak。

| 项目 | 数量 |
|---|---:|
| 计划项：原生 + 补项 | 1320：1307 + 13 |
| 逐项处置：PASS / NA / FAIL / 待判 | 164 / 179 / 8 / 969 |
| 报告归因 | 378 |
| true_defect / false_alarm / criterion_issue | 5 / 7 / 1 |
| knowledge_gap / needs_human | 90 / 275 |
| Top50 核对 / 漏报类（补对象） | 50 / 4（13） |
| 原生门禁 | FAIL / NO_GO；2461 条错误 |

1. **确认根因**：U8 的 5V CMOS 输入不能保证识别 CM4 的 3.3V RUN_PG；U7 的 RC 恢复约21.6ms/V，规定≤5ns/V。另有 Hub `110`逐口配置却共用 PWR1、Y3 的16/24MHz冲突、采购尺寸/封装及资料指针不同步。8个FAIL行归5个根因。
2. **合并步先修 TVS**：7颗角色已VERIFIED的TVS仍无原生PRO-E02，关键词及“恰两网”一起漏掉型号/数组；应按官方通道派项并加种子。另补唤醒默认态、CM4 AnalogIP、Hub片内滤波；不重复计已有CAN、晶体和I²C规则。
3. **归因边界**：378=5个确认根因+365个逐功能待补任务+8条SR反馈，不是378个电气缺陷。电池/USB端口/CM4未用输出会生成假去耦，CFG_SEL0不是工作I²C，本地帽不是外接设备。Type-C的G01-031不可泛套USB-A。

**用法上的坑**：strict缺U7/U8/U10六个脚名，no-strict不关闭输入问题；Yak无独立BOM，不借Yeti CSV。U14/U15明确互斥，J9/J11是三针选择帽，勿当同时分压。USB2514旧版滤波≥1µF，B版为up to0.1µF，先锁变体。I²C rails须同步schema2上下文再重扫。

派生对账无ERROR；schema15不承载NEEDS_HUMAN/KNOWLEDGE_GAP，纯拓扑条款及部分整改结构也未满足，原生FAIL全部保留。原生渲染成功，未打包；仓库报告为原样评估快照，其record/链接须有效打包后才成立。完整台账/原件在 `~/.cache/sr-boards/pionixpublic--reference-hardware/review/`。仅写本板三文件及memo；未改检查器/准则、未复制第三方电路入库、未commit/push。
