# 热审试点 · ESP32-PoE-ISO Rev N（before 版）· UART 跨域互连

## UART-XLAT

拓扑（db.json）：U1 CH340X VCC=/+5V_USB（5 V 模式，V3 只接 C8 0.1 µF）。
- U1.8 TXD → D6（K 在 U1 侧，A 在 ESP 侧）→ /GPIO3/U0RXD = U6.34；R19 10 k 把 /GPIO3/U0RXD 上拉到 Net-(U1-V3)。
- U6.35 U0TXD → D7（K 在 ESP 侧，A 在 U1 侧）→ Net-(D7-A) = U1.9 RXD；R18 10 k 把 Net-(D7-A) 上拉到 /+5V_USB。

状态 run（两侧都供电、U6 在运行）：
- ESP→CH340：U6 TX 高 ≥ 0.8×3.2 = 2.56 V，节点 = VOH + VF(D7) ≈ 2.8–3.6 V ≥ CH340 VIH 2.3 V；TX 低 ≤ 0.32 V + VF，节点 ≤ 0.9 V 要求 VF ≤ 0.58 V（0.15 mA 下肖特基 VF ≈ 0.2 V）。CH340 RXD 电压 ≤ 5.25 V ≤ VCC+0.5。通过。
- CH340→ESP：U1 TX 高 ≥ VCC−0.6 ≥ 3.8 V，D6 反偏，ESP RX = V3（经 R19）；U1 TX 低 ≤ 0.5 V，ESP RX ≤ 0.5 + VF ≈ 0.7 V ≤ VIL 0.25×3.2 = 0.8 V。V3 在 5 V 模式下手册没有给保证窗口（§6.2 只给 VCC 4.0–5.3 V 与"V3 只接电容"），ESP VIH 上限 = VDD+0.3 ≥ 3.5 V；按 3.3 V 模式表外推 V3 ≤ 3.6 V 时最坏多 0.1 V、经 10 k 注入 ≤ 10 µA。保证值缺口，记开放项。

状态 esp-reset（EN 低或 3.3 V 尚未建立，U6.35 不驱动）：
- R18 从 /+5V_USB（≤ 5.25 V）经 D7 正向把 U6.35 抬高：开路节点 = 5.25 − VF = 4.65–5.25 V（VF 取 0–0.6 V），超过 ESP 引脚上限 VDD+0.3 = 3.5–3.7 V；实际由 ESP 焊盘 ESD 结构钳位，注入电流 ≤ (5.25−3.6)/10 k = 0.165 mA。余量 = 3.6 − 4.65 = −1.05 V（最有利角点）。
- WCH 手册 §7.7（p13）明确这一路径："CH340 RXD 上拉电流经 MCU TXD 内部二极管倒灌 MCU"，推荐在 D7 支路串 NMOS（Q5）。本版没有该管，上拉还是 5 V。
- 结论：失败项 RXD-5V-PULLUP。

状态外说明：USB 未插、PoE 供电时 U1 无电，V3 = 0，R19 把 U6 的 U0RXD 拉低（10 k 对 ESP 内部弱上拉 ~45 k），UART0 RX 空闲电平为低。不在声明状态内，列为改进候选，未判。

## UART-DBG
同一组对象；SIG-D08（供电与默认态）：U1 只在 USB 插入时供电（独立供电方式，WCH §7.7），空闲电平 run 态两线为高；SIG-T04 方向 TXD→RXD 交叉正确（U1.8 TXD→U6.34 U0RXD，U6.35 U0TXD→U1.9 RXD）。SIG-C07 与 UART-XLAT 同一结论。

## 审查假定

- 1N5819 VF 取 0–0.6 V（未读该手册）
- 节点电容 ≤ 50 pF
- 115200 bps，位宽 8680 ns
- 1N5819 在 ≤ 0.2 mA 下 VF 取 ≤ 0.2 V（典型值，未读该手册；engineering 正文同此取值）
