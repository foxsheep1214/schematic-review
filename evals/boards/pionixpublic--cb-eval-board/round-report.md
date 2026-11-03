# pionixpublic--cb-eval-board · lane-2

ChargeBridge EV/EVSE评估底板（用途推断）：隔离模拟、以太网、电源保护，兼有USB/CAN/RS485。源 `PionixPublic/cb-eval-board@4b71526`，CERN-OHL-P-2.0；264对象、29页，industrial_telecom。KiCad10.0.7导出；strict因30个功能脚空名失败后按规定回退。

| 计划/已记录 | 已判PASS/NA | 归因条目 | 真缺陷 | 误报 | 准则问题 | 知识缺口 | 人工待定 | 漏报 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1555/1555 | 220/45 | 175 | 0 | 43 | 1 | 73 | 58 | 3 |

**门禁FAIL，valid=false、release=NO_GO。** 保留5439条记录错误/拒收：NEEDS_HUMAN及未定等级不在schema15允许集合，并有条款/功能证明要求未满足。报告保留“结论不可用”标识，未打包、不能用于定稿。175是131件未定任务与44条工具/准则问题，不是硬故障数；“0真缺陷”也不证明板子合格。

最重要的三条观察：

1. **优先修U6的隔离侧别模型。** AMC3311的2/7/8与9/15脚分属两侧，实际无DC桥；工具因regulator单角色合并两地，连带整板域冲突及PWR-A02/A03误判。原厂SBASAQ5A p3/p26已反证，不能改真实地网迎合工具。
2. **EN≠LDO，模块ADC也要逐脚问。** 九路TPS27S100及U37误出10项PWR-E02，同时全计划没有U37的PWR-D03软启动（M03）。U1.73/R25/R26缺ANA-C03（M02）；+24V外引/可供入触点未逐支路展开PRO-C04（M01）。三项都是漏问，未证明原板违规；JSON已附修改及有条件种子提案。
3. **先分清无源、DNP和模拟对象。** U8不装、H1–H4是安装焊盘；J9 VBUS为NC、自供电；PT1000是无源桥，T1是MDI磁性。不能套有源输入、IC去耦、数字差分或负载续流模板。模块上拉/ADC边界和外部接触器/源保护仍保留未定。

用法上的坑：同版BOM两副本hash相同，244件读入；器件不装`nc`与引脚NC分开。C/R/FB类型和AMC高/低侧返回组须补声明再扫。PDF按图框Id而非物理顺序；决定器用`p7`，不认`page 7`。逻辑门ESD段/TMP100内部Diode框图不是器件标题。板级needs_human合同须在合并步统一，不能伪装成VENDOR_DATUM。

[findings.json](findings.json)含五类逐条证据、全部50项Top50对照及来源/哈希；[审查报告](审查报告.md)由工具生成并原样复制。完整台账在 `~/.cache/sr-boards/pionixpublic--cb-eval-board/review/`；仓库副本的record索引需回看缓存台账，不是可移植审查包。临时预览仅在`/tmp/codex-work/`；未改检查器/准则、未写HardwareWiki、未提交/推送。
