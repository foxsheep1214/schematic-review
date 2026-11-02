# protocentral--protocentral_ads1293 · lane-4

固定源 `f512dd285a9e`，CERN-OHL-P-2.0，KiCad10.0.7 strict；推断三通道ECG研究板，ANALOG / LEVEL_SHIFT / SPI / POWER_CONVERTER，补CLOCK；industrial_telecom基线。

| 计划项 | 发现观察 | 真缺陷 | 误识别 | 准则问题 | 知识缺口 | 待人工 | 漏报 |
|---:|---:|---:|---:|---:|---:|---:|---:|
|216|70|3|8|0|5|54|0|

216项逐项记录：33 PASS / 22 NA / 3 FAIL / 158未闭。**FAIL / NO_GO**；valid=true只是记录校验通过。原生renderer因未完审查退出2，交《审查报告.md》执行记录，未假冒正式报告。自动层无FINDING/CANDIDATE；70是人工归因主题，非70个硬件缺陷。

1. **先闭报警模式**：U4.15 ALARMB开漏→U5 TXB0108 A8，R20=1M；TXB p15/17只支持推挽。另有U6资料字段错配、原生图面标注重叠，共3项已证缺陷；均给种子。
2. **优先合并修电源身份传播**：V1其实J3.S→U4.IN5电极，却扩成电源预算/跨域/保护问题。DIN965安装孔又误命中工业DI。两者均有物理反证与精确修改落点。
3. **不扩大证据**：TCR2EF33与AP2112符号此分支脚序兼容，不能由缓存名认定实贴1.8V。晶体18pF与10p/10p仅得外接5pF，寄生未定不判不起振。Top50逐条记录，未确认额外覆盖漏项。

用法坑：features与已有circuits不能重复写；NA类型消失后直接merge旧计划会拒绝旧REQ-Q07，保留原计划逐项反证。JP2三端选择不能写1-2，只能unknown，且污染无关电源分析；不写closed全短接。REQ-Q07 PASS只答覆盖。完整手册三份已锁；无BOM不伪造导入。未闭外部合同不装成厂家数据或通过约束。
