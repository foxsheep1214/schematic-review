# AC0 Automated Check（自动检查）规则库

规则号 `Rule-NN` 是**规则身份标识**，与检查标识（AC0/ER1–ER7）无关——其中 Rule-08/09/14/16 需 ER1 的 datasheet 结论才能判定，属 AC0 热跑项，其余为纯网表规则，AC0 冷跑即可完成。

纯机械、可穷举的规则，全量扫描。**输出是疑似问题清单，不是判决**——合法结构（Bob-Smith 终端、补偿网络、DNP 选项、有意单端测试点）需人工排除。每条规则附真实案例出处。

## 规则表

| ID | 名称 | 检查逻辑 | 真实案例 |
|---|---|---|---|
| Rule-01 | 单节点悬空网 | 网络节点数=1 且不在白名单（被删外设的 SoC 引脚、自动中间网） | `EFUSE2_EN_L` 只挂 Rxxx.2 → 24V 输出永远无法开通 |
| Rule-02 | 双胞胎网络名 | 两网络名相似度>90%（差下划线/后缀）→ 疑似拼写分裂 | `VCC_5V0_SYS` vs `VCC5V0_SYS`（5V 主轨分裂，PMIC 无电） |
| Rule-03 | 自动命名孤岛 | N 开头自动编号网中只挂无源件（无 U/J/Q/Y/M） | 中间节点悬空筛查 |
| Rule-04 | 电源轨无驱动 | 轨名（VCC/VDD/VDDA/VCCA…）网络中无 PMIC/电感/开关类驱动 | DRIVER 前缀按项目 PMIC/电源位号调整 |
| Rule-05 | 电源球无驱动 | SoC 每个含 VDD/VCC/AVDD 功能名的球，所在网络无驱动源 | 357 球全扫；`MIPI_DCPHY_AVDD→NC` 由此暴露（后经规范裁定合法） |
| Rule-06 | VSS 未入地 | 功能名含 VSS/AVSS 的球不在 GND 网 | 268 球只抓 1 例外且与参考设计一致 |
| Rule-07 | 关键器件计数 | 按设计意图核对器件存在性（该删=0，该有≥N） | TPS16530 应×2 实×1 → 输入保护缺失 |
| Rule-08 | 参数验算不符 | 代入实际阻值按公式库验算（见 wca-formulas.md） | FB 分压、限流、门限 |
| Rule-09 | 必需上拉/串阻缺失 | I2C 上拉、eMMC CMD 上拉、复位链、REXT 等按平台规则表 | — |
| Rule-10 | ESD 挂残网 | ESD 器件所在网络节点数<2 或不含真实信号端点 | Dxx1/Dxx2 挂在废弃 USB_DP/DM 空网，活线无防护 |
| Rule-11 | 检测点选错轨 | 判压/检测分压应挂"源"侧而非"保护后内部轨"侧 | VBUS 判压分压错接输出侧 VOUT_24V |
| Rule-12 | 使能逻辑极性/耐压 | EN 有效电平 vs 上/下拉方向冲突；EN 脚耐压 vs 所接电源 | TPS16530 EN 低有效却被上拉至 24V VIN（耐压 5.5V，会烧） |
| Rule-13 | 钳位器件直连电源 | 稳压管/TVS 直接跨接在超过其 Vz/Vrwm 的电源轨上 | BZT52B3V0（3V）误并在 24V VBUS 上（上电即烧毁） |
| Rule-14 | 新增符号引脚映射 | 新建/定制符号（连接器、新 IC）pin 名/号 vs 官方 datasheet 逐脚比对；沿用成熟库免检 | 45P 连接器引脚号与实物不符 |
| Rule-15 | "NC" 网络实为真网络 | 存在名为 NC/NC_* 的多节点网络。**必须先判别真短路 vs 工具伪网络**，见下方「NC 网络判别式」 | 真短路：164 引脚被短成一张网，含晶振脚/MII 输出脚/6 个外部连接器 pin1（OrCAD 经典陷阱）。伪网络：357 引脚挂在 PSTWRITER 的 No-Connect 汇集网上，看似隔离栅被跨接，实为工具产物 |
| Rule-16 | strap 违反强制条款 | 配置/测试脚上拉方向 vs datasheet 原文（must be pulled down / must be left floating / 内部默认态） | RTL8208 TEST[3:0] 上拉（强制下拉）；EN_PWRDWN 上拉=上电即 power-down（默认 0=Normal） |
| Rule-17 | 假闭环 | 历史意见声称"已修改"但 pstxprt/pstchip 中 VALUE/封装未变 | "已改 RTL8326BI"回复后网表仍为 RTL8326B-CG |
| Rule-18 | 同名不同域电源轨混用 | 相似轨名（VCC_3V3 vs VCC_3V3_SOM）被监测/供电对象张冠李戴 | 监控芯片 V2 看 SOM 轨、V4 看底板轨，判定需先分清 |

## NC 网络判别式（Rule-15 执行前必做）

名为 `NC` 的多节点网络有**两种截然不同**的成因，判反了非死即伤：报错会漏掉真短路，报对了才是缺陷。

| | 真短路（缺陷） | 工具伪网络（非缺陷） |
|---|---|---|
| 成因 | 设计者把 "NC" 当网络标号写在了不用引脚上 | 导出器把"带 No-Connect 属性且无连线"的引脚统一汇集 |
| `C_SIGNAL` | 带层次路径 `@<设计>(SCH_1):NC` | **裸字面量 `'NC'`** |
| 实例行 | 带层次路径 | 裸字面量 |

**判别步骤**

1. 取该网在 `pstxnet.dat` 中的头部三行，看 `C_SIGNAL` 是否带 `@` 层次路径。全库唯有伪网络是裸字面量——比对其余网络即可确认。
2. **交叉验证**（决定性）：在导出日志 `netlist.log` 中取全部 `No_connect 属性被忽略并强行连线` 的告警，逐条比对被连接的网。若这些引脚**一律落在真实网络、无一落入该 NC 网**，则该 NC 网确为伪网络。

`scripts/parse_netlist.py` 已自动完成第 1 步并把结果放进 `pseudo_nets`；`scripts/lint.py` 据此把伪网络降级为 `Rule-15-INFO`，不再产生灾难级误报。

## 驱动源判定（Rule-04/Rule-05 前提）

判断"电源轨有无驱动"时，以下**五类全部**算驱动源。漏掉任何一类都会产生大批假"无驱动轨"——实测漏算 0R 与模组输出时，Rule-05 从 1 条真命中膨胀到 44 条：

1. 稳压器/DCDC/LDO 的输出脚（`VOUT`/`SW`/`OUT`）
2. 电感、磁珠、保险丝、二极管
3. **0R 跳线**——配置用的直连，最容易漏
4. **模组自身输出的电源**（4G/WiFi 模组给出的 1.8V 电平参考、`VDD_EXT` 等）
5. 连接器（外部供入）

DRIVER 前缀不必手工枚举，`scripts/lint.py` 按上述五类自动识别。

## 参考实现

**可直接运行**：`python3 scripts/lint.py db.json --log netlist.log --json out.json`

下方为核心逻辑摘录，供理解规则用；**执行时请用 `scripts/lint.py`**，它包含伪网络判别、五类驱动源识别、差分对/同族总线过滤等本文所述的全部处理。

<details><summary>核心逻辑摘录</summary>


```python
import re, difflib

def lint(db, DRIVER_PREFIX=('U230.', 'L23', 'Q240')):  # 按项目电源器件位号调整
    nets, parts, pinname, pin2net = db['nets'], db['parts'], db['pinname'], db['pin2net']
    F = []
    # Rule-01 单节点网络
    for n, nds in nets.items():
        if len(nds) == 1 and not n.startswith(('N37', 'N31')):
            F.append(('Rule-01', '悬空网络', f'{n}: {nds[0]}'))
    # Rule-02 双胞胎网络名
    names = sorted(nets)
    for a, b in zip(names, names[1:]):
        if a != b and difflib.SequenceMatcher(None, a, b).ratio() > 0.9:
            F.append(('Rule-02', '疑似网络名分裂', f'{a} <-> {b}'))
    # Rule-03 自动命名孤岛
    for n, nds in nets.items():
        if n.startswith(('N37', 'N31')):
            refs = {x.split('.')[0] for x in nds}
            if not any(r[0] in 'UJQYM' for r in refs):
                F.append(('Rule-03', '孤岛中间节点', f'{n}: {refs}'))
    # Rule-04/05 电源审计
    for n, nds in nets.items():
        if re.match(r'(VCC|VDD|VDDA|VCCA|VOUT)', n):
            if not any(x.startswith(DRIVER_PREFIX) for x in nds):
                F.append(('Rule-04', '电源轨疑似无驱动', f'{n} ({len(nds)} 节点)'))
    for node, pn in pinname.items():
        if any(k in pn.upper() for k in ('VDD', 'VCC', 'AVDD')):
            n = pin2net.get(node)
            if n is None:
                F.append(('Rule-05', '电源球无网络', f'{node}({pn})'))
            elif not any(x.startswith(DRIVER_PREFIX) for x in nets[n]):
                F.append(('Rule-05', '电源球所在轨无驱动', f'{node}({pn}) <- {n}'))
    # Rule-06 VSS 未入地
    for node, pn in pinname.items():
        if 'VSS' in pn.upper() and pin2net.get(node) != 'GND':
            F.append(('Rule-06', 'VSS 未入 GND', f'{node}({pn}) <- {pin2net.get(node)}'))
    # Rule-15 NC 网络实为真网络
    for n, nds in nets.items():
        if re.fullmatch(r'NC[_\d]*', n, re.I) and len(nds) > 2:
            F.append(('Rule-15', '"NC"被当作网络名导致短接', f'{n}: {len(nds)} 节点'))
    return F
```


</details>
## 符号审计（Rule-14 执行方法）

1. 从 pstchip.dat 提取**新符号**的 pin 名/号映射（`'<PINNAME>': PIN_NUMBER='(<num>)'`）。
2. 与该器件官方 datasheet 引脚定义逐脚比对。
3. **先确认实物封装变体，再看对应封装的引脚图**——多封装同页时按标题逐张对应，禁止跨图引用（实例：把 QFN-20 脚位当 TSSOP-20 判读，产生整页误报后又撤回）。
4. 封装变体间的差异点（NC 位置、功能脚位移）是高频坑，逐脚核对而非抽样。

## strap/配置脚审计（Rule-16 执行方法）

1. 从 pstxprt/pstchip 还原每个 strap 的实装状态（实例级 /NC 标记只在这里）。
2. 对照 datasheet 引脚表逐脚确认：默认态（内部上/下拉）、强制条款（must 类原文）、功能真值表。
3. 上/下拉对（一实装一 NC）属合法设计；同一 strap 实装了与 datasheet 强制方向相反的电阻才是问题。
4. strap 节点上同时挂 LED/其他上拉时，复位采样窗口内算分压（实例：1K 下拉 + 220R 串 LED 至 3.3V → 采样电压 1.0~1.3V > VIL，strap 误读）。
