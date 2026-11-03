# tinkerforge--evse-bricklet · lane-4

用途推断：EVSE导引/测量、隔离交流开关、锁止电机/GP；catalog三类扩展SPI、STARTUP、POWER_PROTECTION。源beb6fc5dc95a、CERN-OHL-1.1；84器件/85网络，KiCad10.0.7。

| 数字 | 结果 |
|---|---:|
| 最终计划（自动+补查） | 499（498+1） |
| 已闭 / 未闭 | 74 / 425 |
| PASS / NA / FAIL检查项 | 41 / 33 / 0 |
| 归因观察 / lint候选 | 29 / 8 |
| 真缺陷 / 误报 / 准则问题 | 0 / 7 / 0 |
| 知识缺口 / 待人工 | 8 / 14 |
| 漏报（计划覆盖） / Top50核对 | 1 / 50 |
| 门禁 | FAIL；valid=true，NO_GO |

1. **先修隔离对象建模。** U102隔离DC/DC被regulator导通模型合并GND/AGND，派生4域冲突，还漏独立PRO-D02（M01）；MAX14850侧别亦把通道1/2当隔离A/B。均有厂家物理脚反证，不是板子地短路。
2. **区分合法结构与未确认工况。** HCPL2731是双通道，AQH是LED输入SSR，OPA171无GND脚；TPS709 EN可悬空、A5950 OCLSEL开路+LSS接地合法。AC反馈LED反向5V、PEM1每路最小5mA、ADC约39.2k源阻抗仍需真实输入/负载/配置，未强判缺陷。
3. **合并框架漏成员。** 7个PRO-E02+1个DRV-A03已有function_id但没进members；显式补判边后derive零错误。准则没有足够反证判为criterion_issue，故记0。

**用法坑：** 无BOM不造表；原厂网页可读≠PDF下载成功。strict仅L102缺脚名回退，不改db消门禁。原生结果499项全覆盖、0格式错误；425项保留REVIEW_INCOMPLETE，render_report实际退出2，所以交付明确标注的执行记录，未冒充正式报告/准出。第三方源和手册只留缓存/临时目录，未改检查器/准则、未提交。
