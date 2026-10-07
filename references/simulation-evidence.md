# 绑定实际电路的 R/C 仿真证据

对象/状态/判据先由审查确定。`scripts/simulate_rc.py` 从 `db.json` 的实际物理脚归网生成理想电阻、电容和单一理想电压源模型；支持 DC 工作点和指定时刻的 RC 瞬态电压。只支持 KiCad `Device:R/R_Small/C/C_Small`，其他元件、器件模型、交流、噪声、固件和全板时序仍由专家选择工具分析。

规格包含以下字段（均必填）：

```json
{
  "schema_version": 1,
  "db_sha256": "实际 db.json 文件的 SHA256",
  "check_id": "本项目实际检查 ID",
  "state": "run",
  "model": "ideal_linear_RC",
  "components": {
    "R1": {"kind": "R", "min_si": 990, "max_si": 1010},
    "R2": {"kind": "R", "min_si": 990, "max_si": 1010}
  },
  "ground": "GND",
  "source": {"net": "VIN", "min_v": 5, "max_v": 5},
  "analysis": {"kind": "op", "net": "OUT"},
  "window": {"min_v": 2.47, "max_v": 2.53},
  "excluded_nodes": {"U1.1": "本有界模型按理想高阻输入；实际漏电/钳位另审"},
  "assumptions": ["理想线性元件，参数范围及外部源工况来自已读资料"],
  "basis": [{"path": "资料路径", "sha256": "原文件 SHA256", "locator": "实际页码/表格/保证条件"}]
}
```

上述网络名、位号、范围是说明用例，不能直接作为真实项目保证。`min_si/max_si` 分别用 Ω/F，必须包含图上的标称值；电容的 DC bias、温度、老化必须计入有据的有效电容范围。`basis.path` 相对规格文件所在目录，或绝对路径；工具验证原件哈希，资料含义和保证范围仍须实际阅读。

瞬态时将 `analysis` 改为 `{"kind":"tran","net":"OUT","at_s":0.0001,"max_step_s":0.00000005,"initial_v":0}`。单位秒；`initial_v` 是各电容 pin1→pin2 的初始电压，源在 t=0 施加常值。使用 `uic`，不把它冒充实际上电波形或任意初始化状态。采样至少 100 步、最多 100 万步；需要时缩小步长确认数值收敛。

选中网络上的每个未建模物理脚必须出现在 `excluded_nodes`，写明为何允许理想化、真实加载如何另审。不填不自动跳过；DNP、缺脚、错型、过期输入/资料、未知条件及超过 64 个端点角点拒绝产出有效证据。

```sh
python3 scripts/simulate_rc.py --db db.json --spec rc-spec.json --out 新的证据目录 --ngspice /path/to/ngspice
python3 scripts/simulate_rc.py --db db.json --spec rc-spec.json --verify 证据目录/simulation.json
```

目录保留每个角点的 deck、stdout、stderr 和工具版本；回放重新从绑定输入生成 deck，核哈希、角点覆盖、原始测量和报告一致性。回放是完整性核对，不是不可伪造的执行认证；需要独立数值复核时另跑求解器或解析式。

`WITHIN_SAMPLED_WINDOW` / `OUTSIDE_SAMPLED_WINDOW` 只描述声明的理想模型端点样本；没有证明角点之间的全域最坏情况，也没有证明器件行为或需求整体符合。模型、边界、资料、数值精度和适用性经专家核实后，才能作为对应 C/E 项的计算证据，仍按既有台账协议写结果。不得由脚本批量替整板标 PASS。缺工具/输入条件/模型或求解失败保持 INSUFFICIENT；求解失败目录没有有效 `simulation.json`。

实现依据：[ngspice 官方控制语言说明](https://ngspice.sourceforge.io/ngspice-control-language-tutorial.html)。启动加 `-n -b`，不读用户 `.spiceinit`；不接收任意 SPICE 指令或外部模型代码。
