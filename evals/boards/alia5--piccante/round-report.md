# alia5--piccante · lane-1

推断用途：Pico W 车载三路 CAN/USB 探索接口，附 microSD、TPS5430 降压及电池分压检测。固定源 `62ede82f56ae`，GPL-3.0；KiCad 10.0.7 strict 通过，33 件、52 网、136 节点，XML/db 归网差异 0。基线 `industrial_telecom`。

| 项目 | 数量／结果 |
|---|---:|
| 电路／功能框架 | 7／21 |
| 计划项（含 3 个 rule_gaps） | 299 |
| 局部已判／逐 ID needs_human | 55／244 |
| 发现归因（含候选、工具观察） | 34 |
| true_defect／false_alarm | 0／7 |
| criterion_issue／knowledge_gap | 0／1 |
| needs_human | 26 |
| 漏问／已证硬件漏检 | 3／0 |
| 原生门禁／release | FAIL／NO_GO |

1. **模组外端不等于内部裸脚。** ADC_VREF 内部已供电、AGND 已接公共地，两条电源疑点被排除；TPS5430 BOOT 是自举脚，被错当 strap。A1 初审资料漏收可用 `--require-ref A1` 恢复。
2. **合并步先修 ADC 功能展开。** VBATT 的 100k/10k 分压被 STARTUP 候选吸收，却未问 ANA-C03；另有源侧保护、模组内 USB 两处漏问。均已补本轮计划，提案与合成种子在 findings；不是三个已证硬件错误。
3. **先锁 ENA 的 7 V 边界。** U4.5 直连 VBATT，高于 7 V 即越绝限；实际源窗未受控，12 V 只作条件例，保留 needs_human。CAN 的 120 Ω 经跳帽，C4 的 220 µF 未给 ESR，不硬判端接或稳定性。

用法坑：schema15 无 needs_human／未定工况表达；本轮未伪造厂家缺口或完整功能 PASS。244 项及全部功能边界留缓存旁账，原生报告明确标为记录无效；其“资料不足 0”不代表审完。门禁 FAIL 未打包，报告的 `record/` 为标准包链接；完整台账、PDF 和证据在 `~/.cache/sr-boards/alia5--piccante/review/`。Top 50 已逐条登记。
