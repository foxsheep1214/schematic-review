# 热审试点说明（局部台账）

- 对象：Olimex ESP32-PoE-ISO Rev N（fix pair olimex-esp32-poe-iso-revN-revN1 的 before 版），只审 intent 里声明的两个功能电路
  UART-DBG（UART）与 UART-XLAT（LEVEL_SHIFT），共 12 条科目行 + 2 个功能判定；全板其余 250 余行未审，
  所以 `review-gate.json` 的 `valid` 为 false，剩余错误全是覆盖类（缺行、scope_checks、coverage），不是结论错误。
- 资料：ESP32-WROOM-32E 数据手册 v2.1（乐鑫官网）、CH340 数据手册 V3C（第三方镜像副本）。文本在审查工作目录 `evidence/ds/`，
  未随仓库提交（第三方文件）；`engineering.md` 记了用到的页码与数值。
- 结论：finding F-001（P1，COMPONENT_DAMAGE）——U6 复位期间 R18 从 5 V 经 D7 把 U0TXD 抬到引脚上限以上；
  与作者 Rev N1/O 的修法（分压/串 FET、R18 改 1 k）同一病因。开放项 V3-WINDOW（VENDOR_DATUM，P2）是 SR 的疑似过严候选：
  CH340 5 V 模式下 V3 没有保证窗口，最坏多出 0.1 V、注入 ≤ 10 µA。
- 台账摩擦：同一组对象同时声明 UART 与 LEVEL_SHIFT 两个框架时，SIG-C07 在两个框架各有一行，开放项 key 又要求全局唯一，
  只能复制一份（V3-WINDOW / V3-WINDOW-UART），质量筛查随即报 DUPLICATE_WORK_ITEMS；框架成员也不允许绑定到另一框架的功能。
