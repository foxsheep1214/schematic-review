# 电路原理图审查方法论

> V2.1。保留文件名和旧节号供已有引用定位；执行流程与命令统一见
> [SKILL.md](../SKILL.md)。

## 旧编号映射

L0→AC0，L1–L7→ER1–ER7。AC0 产生可复核候选，ER1–ER7 承担工程审查；身份/图形
疑点可前置处理。Rule-01–20 保留身份，Rule-11 归 ER2，Rule-17 归复审 Diff，
其余按冷/热输入依赖执行；READY、执行一次或零命中均不等于最终 PASS。

### 5.7 检测点取样侧（Rule-11）

先定义被测量和保护目的，再核取样网络、ADC/比较器终点及反馈控制：检测输入存在可取
源侧，验证输出有效或负载电压可取保护后，不能仅凭取样在保护后判缺陷。
首次使能不能依赖尚未使能的输出，除非有独立启动条件和故障回退。

覆盖要求见 [coverage-protocol.md](coverage-protocol.md)，分级与准出见
[severity-calibration.md](severity-calibration.md)，专业移交边界见
[scope-boundary.md](scope-boundary.md)。历史报告只作线索，当前结论须重新核实。
