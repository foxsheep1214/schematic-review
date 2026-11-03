# Cynthion／lane-3 本轮记录

固定来源 `greatscottgadgets/cynthion-hardware@13aa71c2fb0b`；CERN-OHL-P-2.0。推断用途：ECP5 FPGA USB 测试仪，含三颗 USB3343、Type-C/PD、HyperRAM、Flash、调试和多端口电源切换。catalog 四类已核对，实际补 CLOCK、I2C、SPI、DDR/HyperBus、ANALOG、STARTUP、POWER_PROTECTION；HSSERIAL 标签不等于存在 USB3/SerDes。

| 数字 | 本轮 |
|---|---:|
| 器件／图页／最终计划 | 348／20／1193 |
| 归因条目（开放根因＋误报反馈） | 319（304＋15） |
| 真缺陷／误报／准则问题 | 0／15／0 |
| 知识缺口／待人工或集成判断 | 33／271 |
| Top 50 目标规则覆盖漏报 | 3 |
| 已判 PASS／NA；未定检查 | 144／77；972 |
| 门禁／记录校验错误 | **FAIL**／2412 |

最重要的三条观察：

1. **先修准确 MPN 分组。** `PMOS` 把六颗 SIA483 与两颗 YJL3401A 混组，会把前者手册误绑后者；Diodes 公司名、MOSFET 应用栏也会污染角色。已保存真实手册复现，未拿混绑资料判通过。
2. **核心轨上侧窗口值得优先复核。** U4 实际为 1.15 V，ECP5 推荐上限 1.155 V，仅 5 mV 名义余量；±18 mV 初始精度测试点上包络为 1.168 V。但其 VIN=2.15 V，板上 VIN=3V3；负载、线/负载调整和结温未锁定，保留待判，没有把包络越界当实物已超压。
3. **漏问与未证明分开。** PAC1954 的 ANALOG 仍为 0/7；Q9/Q12 输入 OR 路径缺专门 PWR-T05 对象；FPGA 配置期缺实际 RST-T04 对象。已有 USB 反灌、系统时序、I2C 计算题未重复算漏报。三条均附修改建议和带合成前提的种子提案，不指控原板有三项缺陷。

用法坑：XML 自带 Description/MPN/13 个自定义 DNP，须无损转存再 read_bom；R54 默认供 3V3，U15 不贴。候选 CLOCK/SPI 空 states 需有出处的 run 声明；G/S 稳压管的合法双侧窗口不能因正常导通误裁。schema15 无法承载本任务要求的 needs_human/整份资料缺口；仍有 111 个阻容预判缺独立全工况证明，以及脚表/分组声明绑定错误，均如实保留，未编 override。221 项已判不等于整板审结。报告为原生渲染副本，非有效打包/准出文件；完整记录留在本板缓存 review/。未修改检查器、共用准则或第三方源文件，未提交。
