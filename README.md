# schematic-review

V2.1。面向硬件原理图首审、冻结前检查和改版复审的 Agent skill：
按需求、电路和工况检查，交付有证据的 P0–P3 问题、待核项及可执行的修改说明。

## 使用与安装

    按 schematic-review 审查 <项目路径> 的原理图，核对需求和所有适用电路，
    按严重度列出证据、修改步骤和复验条件；缺证据与覆盖缺口单列。

按所用 Agent 的技能目录安装：

    git clone https://github.com/foxsheep1214/schematic-review.git <你的skills目录>/schematic-review

执行步骤、命令及首审/复审分支统一见 [SKILL.md](SKILL.md)。Python 脚本仅用标准库；
读取 PDF 需要现有提取/渲染工具（例如 Poppler）。安装依赖前按入口要求盘点资源与授权。

## 输入与运行边界

- 完整模式需要原理图 PDF、有效网表/导出日志、当前装配 BOM/配置、需求/接口定义及器件资料。
  随附解析器支持 Cadence/OrCAD 三件套；其他 EDA 需验证适配器。
- 仅 PDF 时继续逐页受限审查，明确未完成网表/ERC/逐脚机器覆盖；缺项继续完成独立检查。
- Agent 核实物料、资料、模型与工程结论，不能从零 Lint 命中、READY 或典型值生成 PASS。
  最终结果校验只证明记录一致性；有效的 NO_GO 报告仍可交付，冻结门另核准出结果。
- 准出对象是原理图冻结进入 PCB Layout；PCB 布局布线、SI/PI、EMC、实测热及生产另作移交。
  不能承诺发现所有未知缺陷，也不能找到几项问题后停止其余覆盖。

输入基线和最终证据持久保存在项目审查目录，见 [覆盖与留档](references/coverage-protocol.md)。
报告结构见 [报告模板](references/report-template.md)，修改说明见
[remediation-guide](references/remediation-guide.md)，格式示范见
[合成示例](examples/worked-example-industrial-gateway.md)。公开仓库只保存脱敏合成用例，
真实原图、BOM、私有手册与过程产物留在项目目录。

MIT License，见 [LICENSE](LICENSE)。
