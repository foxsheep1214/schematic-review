# CopperPilot Jetson AI Cam · lane-4

固定提交 `dc59d7a1d1d050f89d21760242896d05edd34e29`；CERN-OHL-P-2.0；推断为Jetson摄像头载板。基线 industrial_telecom，HSSERIAL/I2C/LEVEL_SHIFT/POWER_CONVERTER并补CAN/USB/POWER_PROTECTION/STARTUP。

| 计划／登记 | PASS／FAIL／NA／未闭 | 观察 | 真缺陷 | 误报 | 准则 | 知识缺口 | 待人工 | 漏报根因 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1488／1488 | 96／9／30／1353 | 58 | 4 | 28 | 1 | 4 | 21 | 2 |

58含36热扫观察（INFO另有语义）、7被拒候选、15专家观察；不是58个板上缺陷。135项作出决定，其余明确needs_human/REVIEW_INCOMPLETE。门禁 **FAIL，valid=false，NO_GO**：116条F1未闭；质量筛查751建议未全部关闭。renderer实际退出2，交付[审查执行记录](审查报告.md)，不冒充正式报告。

1. **准确后缀与电源状态改变结论。** U2 BPP固定3.3V却接100k/44.2k外分压（TI p2/p33）；Type-C IC7.27 NC使低有效IC3.EN常高；D17/L3向J9反灌且FTDI复位无VBUS资格（FT232R p20）。另BOM漏4个原生贴装位号。共4根因，10.766V只是名义模型，不是实测。
2. **官方脚义和封装别名能撤销重复误报。** SiC477的21=NC、15=GL输出、16=内部LDO输出；官方29/30已由自定义封装同号7/9大焊盘表达，不是已证EP浮空。HD3SS3220 GPIO模式及FTDI内偏置也不按通用悬空输入判。
3. **合并优先修覆盖枚举。** PRO-E02原仅D14，漏12个信号ESD对象；PRO-C04漏J1/J2/J10/J12外供支路，共补16项。建议先按保护件通道/真实外供支路枚举，再加M01/M02种子；“同网最低耐受”还须改为事件可达保护域，缺波形不能臆造钳位故障。

用法坑：IC前缀须audit `--require-ref`；read_bom保留字段但不改DNP；I²C须另填已核rails，HDMI_PWR否则把两线上拉合成同域（最终声明已纠正，增7项）；拒绝假变换器/USB候选后held成员仍难回收；schema用15，派生行不写台账。缺准确SoM/相机模块、受控输入/负载与实算时保留未闭，不塞VENDOR_DATUM或无关条款凑门禁。
