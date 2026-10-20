# 热审试点说明（局部台账）

- 对象：Olimex ESP32-PoE-ISO Rev N（fix pair olimex-esp32-poe-iso-revN-revN1 的 before 版），只审 intent 里声明的两个功能电路
  UART-DBG（UART）与 UART-XLAT（LEVEL_SHIFT），共 12 条科目行 + 2 个功能判定。台账声明 `review_scope`，
  `review-gate.json` 的 `valid` 为 true，阻断里带“不是整板结论”；全板其余 250 余行未审。
- 资料：ESP32-WROOM-32E 数据手册 v2.1（乐鑫官网）、CH340 数据手册 V3C（第三方镜像副本）。文本在审查工作目录 `evidence/ds/`，
  未随仓库提交（第三方文件）；`engineering.md` 记了用到的页码与数值。
- 结论：finding F-001（P1，COMPONENT_DAMAGE）——U6 复位期间 R18 从 5 V 经 D7 把 U0TXD 抬到引脚上限以上；
  与作者 Rev N1/O 的修法（分压/串 FET、R18 改 1 k）同一病因。第一版台账曾为 V3 窗口记 VENDOR_DATUM（CH340 5 V 模式 V3 没有保证窗口，最坏多出 0.1 V、注入 ≤ 10 µA），
  按新增的“微注入上拉”底线（references/commodity-floors.md）改判 PASS（B），开放项撤销。
- 台账摩擦（已改）：同一组对象同时声明 UART 与 LEVEL_SHIFT 时 SIG-C07 在两个框架各有一行；现在 UART 框架的 SIG-C07 行
  绑到 FN-UART-XLAT（该功能的对象覆盖这些行），开放项不再复制，DUPLICATE_WORK_ITEMS 消失。
