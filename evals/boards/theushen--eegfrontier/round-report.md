# theushen--eegfrontier · lane-3

固定源：`TheusHen/EEGFrontier@ecf3a485`，MIT；KiCad 10.0.7 strict 成功，29件。用途**推断**为四通道EEG采集，ADS1299-4＋XIAO RP2040；catalog类型 ANALOG、SPI，基线 industrial_telecom。

| 计划项 | 报告根因/反馈 | 真缺陷 | 误报 | 准则问题 | 知识缺口 | 待确认 | 覆盖漏报 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 148 | 27 | 8 | 6 | 0 | 3 | 10 | 3 |

原生结果：54 PASS、12 NA、16 FAIL、66未定；16 FAIL归并8个缺陷。门禁 **FAIL**（177条记录错误），未打包、未认可冻结。全部148项逐条落账；未把66项未定当作已审通过。50条Top 50核对详见 findings.json 的 `top50_audit`。

1. **真实硬错误足以阻断采集。** AVDD/AVDD1=3.3V，低于4.75V下限；SPI_SCK接RESV1(31)，SCLK(40)NC；CLKSEL=0却CLK(37)NC。另有VCAP1 10µF对指定100µF、VREF 1.1µF对最小10µF、未用GPIO/DAISY_IN处置和图面文字遮挡。均独立查图、网表与TI SBAS499C具体页/脚。
2. **最应先合并的是模组边界/主控角色。** U1内部USB→LDO→3V3确有源，却产生VBUS单节点告警、模块图标题diode冲突、主控未列而SPI锚到LED；又漏PWR-C04、SIG-C05和RST-T04。三条漏报都是目标规则覆盖缺口，**没有证实三项新增电气违规**。先补有来源的模组角色/供电端点，并保留模块外加负载与电容复核。
3. **拿不准不能改成误报。** ADS1299-4的1–8脚在通用脚表仅其他变体有功能，但通用未用输入脚注仍需明确；VCAP2–4用10µF替代、模组LDO约30.4µF的稳定窗口分别留知识缺口。人体BIAS回路、外部隔离和故障限流边界留待确认，不把工业基线等同人体安全。

SR用法：`1kΩ`会拒读，必须保留原值和独立计算；AVSS@1/@2别名会错进供电组，补官方完整return脚表后消失；单地不可显式填 `decoupling.return_net`。需求推断文件应单独放requirements目录，避免同目录事实摘录被当需求。schema15不承载NEEDS_HUMAN/KNOWLEDGE_GAP，另有普通件采购约束/局部数值尚不满足原生margin结构和定位问题；如实保留FAIL，不能把台账齐全说成有效SR交付。

仓库仅保存报告镜像和归因元数据；[完整本机记录与图像](/Users/skyfend/.cache/sr-boards/theushen--eegfrontier/review/审查报告.md)在缓存，镜像相对附件依赖该目录。未复制第三方电路文件，HardwareWiki只读；未改检查器/准则，未commit/push。
