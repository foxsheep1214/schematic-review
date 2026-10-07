# 电平转换（LEVEL_SHIFT）：成对判例

用于验证 LEVEL_SHIFT 功能包、[WCA 公式](../../references/wca-formulas.md)“MOSFET 双向开漏电平转换”行
及 [计划与结果台账](../../references/plan-and-results.md) 中电平转换的展开边界。全部为合成数据，不是自动测试；
回放时只给“输入”，再与“应产生的行为”对照。

共同约定：电阻 ±1%，电源 ±5%；“Q-X”为合成 N 沟道 MOSFET，VGS(th)max 1.5 V，RDS(on)max 5 Ω 仅在 VGS=2.5 V 保证。

## 电气判例

| 编号 | 输入 | 应产生的行为 |
|---|---|---|
| LS1 正例 | Q-X 构成双向开漏转换。低侧 3.3 V/10 kΩ，高侧 5 V/10 kΩ。两侧驱动端都保证 4 mA@VOL 0.4 V；高侧器件 VIL 1.5 V、VIH 3.5 V；低侧 VIL 0.99 V、VIH 2.31 V。100 kHz，tr ≤ 1 µs，每侧 Cb ≤ 100 pF。两侧电源同源，需求不含单侧掉电 | SIG-C07 PASS：最坏灌电流 (3.465−0.4)/9.9k + (5.25−0.4)/9.9k ≈ 0.80 mA ≤ 4 mA；VGS = 3.135−0.4 = 2.735 V ≥ 2.5 V，RDS(on) 有保证；对侧低电平 ≈ 0.40 V（两个驱动方向相同），满足两侧 VIL；高电平各由本侧上拉，满足 VIH。SIG-C09 PASS：tr ≈ 0.8473×10.1k×100 pF ≈ 0.86 µs。SIG-C08 以“两侧同源、需求不含单侧掉电”为依据判 NA |
| LS2 反例 | 同结构，低侧 1.8 V/4.7 kΩ，高侧 3.3 V/4.7 kΩ，低侧驱动 VOL max 0.45 V，仍用 Q-X | SIG-C07 FAIL（保证要求未满足），P1：VGS = 1.71−0.45 = 1.26 V < VGS(th)max 1.5 V，高侧不能保证被拉低 |
| LS2′ 正例 | 同 LS2，但换用 Q-Y：VGS(th)max 0.9 V，RDS(on)max 8 Ω@VGS=1.2 V；低侧驱动保证 2 mA@0.45 V，高侧驱动保证 2 mA@0.4 V；高侧 VIL 0.99 V，低侧 VIL 0.63 V | SIG-C07 PASS：VGS 1.26 V ≥ 1.2 V；I_H ≈ (3.465−0.45)/4.653k ≈ 0.65 mA，高侧低电平 ≈ 0.455 V ≤ 0.99 V；驱动端吸收 ≈ 0.31 + 0.65 ≈ 0.96 mA ≤ 2 mA；高侧驱动时 VGS ≈ 1.71−0.40 = 1.31 V ≥ 1.2 V，低侧低电平 ≈ 0.40 + 0.31 mA×8 Ω ≈ 0.40 V ≤ 0.63 V |
| LS2″ 边界 | 同 LS2，换用 Q-Z：VGS(th)max 1.0 V，RDS(on) 仅在 VGS=2.5 V 保证；无覆盖 1.26 V 的曲线 | SIG-C07 INSUFFICIENT：VGS 1.26 V 高于 VGS(th)max，只说明开始导通，RDS(on) 在 1.26 V 下无保证且无法定界；补证为该 VGS 下的保证 RDS(on) 或覆盖该点的曲线界限。不能判 PASS；有可信曲线界限证明对侧低电平越限时才判 FAIL |
| LS3 反例 | 低侧 3.3 V/10 kΩ（MCU 常供电），高侧 5 V/10 kΩ 为可热插拔外设，未接电时 5 V 轨被负载拉到 0 V；外设输入钳位注入上限 1 mA。需求：外设未供电时，低侧总线仍须与其他 3.3 V 器件正常通信 | SIG-C08 FAIL，P1：低侧经 RL→体二极管/沟道→RH 流向掉电轨，低侧空闲电平在沟道全通的约 1.55 V 与仅体二极管导通的 (3.465×10.1k + VF×9.9k)/20k 之间，VF 取保守上限 1.0 V 时约 2.25 V，仍 < VIH 2.31 V，总线被拉入不定区，违反需求。注入外设引脚钳位最坏约 3.465/9.9k ≈ 0.35 mA，未超 1 mA |
| LS3′ 正例 | 同 LS3，但需求只要求外设未供电时不损坏任何器件，允许低侧总线暂停 | SIG-C08 PASS（器件不损坏）：注入 ≤ 约 0.35 mA ≤ 1 mA；“外设掉电时低侧总线不可用”记为使用约束，不判 FAIL |

## 计划判例

| 编号 | 输入 | 应产生的行为 |
|---|---|---|
| LP1 | TXS0102 位于 MCU GPIO（3.3 V）与 1.8 V 传感器 GPIO 之间，不属于 I²C/SPI/UART | 名称命中只生成 LEVEL_SHIFT 的 UNDETERMINED 候选；确认用途后在 `intent.circuits` 声明 `type: LEVEL_SHIFT`（refs、states），逐电路×工况展开 SIG-C07、SIG-C08、SIG-C09、SIG-T04。TXS 按其手册的上拉/负载/边沿限制核，不套 MOSFET 公式 |
| LP2 | 分立 MOSFET（如 2N7002）转换器位于 I²C 总线上 | 无名称线索，不会自动检出；把转换器列入 I²C 电路的 refs（`type: I2C`），不另声明 LEVEL_SHIFT，避免重复检查；计算用 WCA 的 MOSFET 双向开漏电平转换小节，I²C 包的 SIG-C01 另核上升时间与灌电流；REQ-Q08 中的 LEVEL_SHIFT 写“已并入 I²C 电路”；在 `intent.power_switches` 把转换管声明为 `role: "level_shifter"`，不再生成 DRV 检查项 |
