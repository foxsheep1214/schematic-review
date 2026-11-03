# gyrocopterllc--flatmcu · lane-4

推断：STM32G4/DRV8353RS BLDC/FOC三相驱动，兼buck/LDO、USB、SWD、UART和模拟采样。固定`3aaa0e0`，MIT；KiCad10.0.7 strict成功，127器件。BOM与图存在身份分支。

| 指标 | 数量/结果 |
|---|---:|
| 计划 / 逐项登记 | 543 / 543（含2项人工补查） |
| PASS / NA / FAIL / 未审结 | 80 / 25 / 11 / 427 |
| 归因观察 | 121 |
| true_defect / false_alarm | 9 / 26 |
| criterion_issue / knowledge_gap / needs_human | 0 / 5 / 81 |
| Top50对象覆盖漏项 | 2 |
| 门禁 / 原生报告 | FAIL、valid=false、NO_GO；renderer退出2 |

1. **优先合并输出角色识别及其回归**：U3 GH/GL库类型全IN，原厂p8为O且p14/36有内部ROFF，引发12条伪断驱；同时保留库类型本身的真数据错误。PWM+/−又被3种差分规则重复误认（9项）。
2. **两个最该补的对象**：相电压22k/1k→ADC和U3内置三路CSA被主角色/归属裁剪漏掉；已保留before-gaps计划并补ANA-C03/ANA-C01。缺相电压/电流合同，不把覆盖漏项当实板超界。
3. **先锁装配与版本**：7个明确数据冲突 + AP1117本地Cin0.3uF/Cout1.3或2.2uF相对新版4.7uF的2处偏离；2007版10uF不作判据，同版ESR表/正文冲突另归知识缺口。没有确认准则本身不可判。

用法坑：assemblies须逐件明确原生贴装（R12不贴），只写R12会使其余贴装未知、少展开驱动项；补资料/装配后需重冷扫再merge，否则库存变更拒收。power_switches运行时schema=2、results=15。593个质量提示不是板级发现；64条门禁错误和427项REVIEW_INCOMPLETE如实保留，交付文件为执行记录，非正式报告/准出。没有改共享规则、第三方入库或提交。
