# mlab-modules--solarmini01 · lane-1

固定源 `95e265bf878306dc1ff4e3044bb8295469fb971e`，GPL-3.0；SR `1302ac3e`，KiCad 10.0.7。用途推断：光伏 MPPT 升压/限压限流；类型 POWER_CONVERTER、POWER_PROTECTION、ANALOG，基线 industrial_telecom。

| 项目 | 数量/结果 |
|---|---:|
| 器件 / 网络 / XML端点 / 页 | 28 / 14（含4 NC伪网）/ 59 / 1 |
| 最终计划（自动+补问） | 157（155+2） |
| 局部结果 / 逐ID needs_human | 45（含1派生覆盖）/ 112 |
| 功能框架 / 完整审结 | 9 / 0 |
| 归因发现（扫描5条+专家归因，去重按条目） | 23 |
| true_defect / false_alarm | 2 / 10 |
| criterion_issue / knowledge_gap / needs_human | 0 / 2 / 9 |
| Top50核对 / 计划漏问 / 已证硬件漏检 | 50 / 2 / 0 |
| 原生门禁 / 准出 | FAIL（valid=false）/ NO_GO |

最重要的 3 条观察：
1. **合并步先修升压方向。** U1.3 LX→L1→PV 被当成输出源，C1 被归输出电容；实际 PV 是输入，U1.4/D1.K 才是输出。该错会污染电源树、候选成员及预算对象，优先做 buck/boost 对照回归。
2. **两个真缺陷均为设计数据。** R2="-"且无明确DNP；D2=SMBJ5.0A却指定D_SMA（原厂为SMB）。钳位6.4V击穿起点高于U1的5.5V绝限已证，但AN3319 p17的无电池轻载接入适用性未锁，仍归需人工，未声称实物必坏。R3的0Ω自使能由AN3319 p18明确支持。
3. **漏问与已有覆盖分开。** XSHUT默认态漏RST-T04、U1采样UVLO漏其自己的PWR-C06，已用rule_gaps补入。J3的SIG-C08、J1/J4源侧PRO-C04和U1的PWR-C04本版已展开，不能重复报成整轮漏检。两条漏问未确认原板硬错；seed给出明确外端/预偏置合同的合成变异，不能当原板缺陷。

用法坑：strict只因M1–M4安装孔缺名失败，回退成功；独立XML/db59端点和BOM28值零差异。稀疏检出漏BOM/原厂AN，须按固定提交取blob；CSV需截取Individual表再read_bom，Value另独立比。合法add丢nets/anchors；孔又污染手册与pinmux。FERROCORE原表IDC4A未定义饱和/温升，不能当全温Isat。schema15没有needs_human/未定外端合同格式，本轮以逐ID pending与逐功能范围保留；原生“资料不足0/仅1功能失败”不等于其余已审。报告按脚本原样复制、未打包，record相对索引不代表已交付有效包，真实台账在 `~/.cache/sr-boards/mlab-modules--solarmini01/review/`。没有修改检查器、准则或源板。
