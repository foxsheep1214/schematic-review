# schematic-review

面向硬件原理图首审、冻结前检查和改版复审的 Agent skill。按需求、电路和工况逐项检查，
交付有证据的 P0–P3 缺陷、可执行的修改步骤与复验条件；待核项给出具体补证或设计路径。

- 目的与取舍：[七项审查要点](references/review-charter.md)。
- 全部检查按 [规则总表](references/check-catalog.md) 编号（`内容域-方式序号`，如 `PWR-E01`），11 个内容域、8 种检查方式；
  DDR、USB、电源保护等功能以“功能电路”组织，确认实际用途后逐电路、逐工况展开。
- 判“证据不足”前先用已有参数定界，规则见 [最小充分证据](references/evidence-proportionality.md)。
- SR 自己的改动按 [改进台账](docs/improvement-ledger.md) 记事件来源与归因，`scripts/check_ledger.py` 检查最新条目。

## 使用与安装

    按 schematic-review 审查 <项目路径> 的原理图，核对需求和所有适用电路，
    按严重度列出证据、修改步骤和复验条件；缺证据与覆盖缺口单列。

按所用 Agent 的技能目录安装：

    git clone https://github.com/foxsheep1214/schematic-review.git <你的skills目录>/schematic-review

执行步骤和命令见 [SKILL.md](SKILL.md)。Python 脚本只用标准库；读取 PDF 需要现有的提取/渲染工具（例如 Poppler）。

## 输入与边界

- 完整模式需要原理图 PDF、有效网表/导出日志、当前装配 BOM/配置、需求/接口定义及器件资料。
  随附解析器支持 Cadence/OrCAD 三件套与 KiCad（`.kicad_sch` 或 kicadxml 网表）；其他 EDA 需验证适配器。
- 仅有 PDF 时逐页受限审查，明确未完成网表/ERC/逐脚机器覆盖。
- 结果校验只证明记录一致；结论 NO_GO 的报告也可正常交付。
- 准出对象是原理图冻结进入 PCB Layout；PCB 布局布线、SI/PI、EMC、实测热和生产另作移交。

报告结构与修改说明见 [报告与修改说明](references/report-and-remediation.md)，格式示范见
[合成示例](examples/worked-example-industrial-gateway.md)。公开仓库只保存脱敏合成用例，
真实原图、BOM、私有手册与过程产物留在项目目录。

## 工具回归评测

门禁（一条 pytest，含规则合同、回放与典型电路）和变异检查的用法见 [架构说明 四、规则维护](references/architecture.md#四规则维护)。
评测只测声明范围内的工具能力，不代替真实项目审查或电路准出。

MIT License，见 [LICENSE](LICENSE)。

## 共用层更新入口

共用判据（共用规范 G01–G10：G01–G09 设计准则、G10 降额与应力规范）在硬件设计知识框架的 `设计准则/` 维护，和知识包（`references/knowledge/`）一起由本技能同步进来，技能内不得编辑这些文件。技能里有哪些共用文件、谁读、指纹怎么算见 [共用层说明](references/shared/shared-layer.md)；维护源（规范 `准则登记/`、`规范正文/G10_元器件降额与应力规范/`、`工具/`（含 `包说明/`））在知识框架的 `设计准则/README.md`。

框架更新后重新同步（只有这一步读框架目录，技能运行时只读自己这一份）：

```bash
python3 scripts/knowledge_package.py sync <硬件设计知识框架目录>      # 加 --dry-run 只看差异
python3 scripts/knowledge_package.py verify-installed
python3 scripts/guideline_criteria.py verify-installed
```

同步把与上一次的差异写进 `docs/knowledge-sync/<框架版本>.md`（新增、改了、删除、搬了位置的条目和准则）。新增的准则没有对应规则、删除的准则还被规则引用时，`test_guideline_criteria.py` 等测试会失败；改了判据的准则，在 `scripts/catalog.py` 的 `BASIS` 里按编号找依据它的规则逐条看。按它补规则和触发板，再跑全量测试与变异测试。
