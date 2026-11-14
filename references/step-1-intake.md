# ① 读入

> 读者：审查员。

做本步前读 SKILL.md 和本文件；五个步骤的总览见 [SKILL.md 的执行流程](../SKILL.md#执行流程)。

## 1.1 需求与基线

从资料和对话提取功能/量化指标、接口角色与数量、输入范围/负载、温度、降额依据、保留/删除项，
写入 `intent.json`（字段见 [intent 格式](intent-format.md)）：需求原文由
`requirements_extract.py` 从需求文档逐字抄录（`requirement_source` 写文件与 sha256；任务书给了几份需求文档就登记几项，写成列表，一份都不少），每条要求只写 REQ ID、类别（规则总表的需求类别表）、对需求的理解（`interpretation`）、从原文读出的数字（`parameters`）、承接它的电路（`owners`，承接电路：落实这条需求的功能电路、系统功能或接口；计划会列出可承接的电路，有就必须写，认定没有承接电路写 `[]` 加能定位的理由）和确认状态，审查方面由参数和类别推出（有参数的方面只在原文读出了那个数时才问，拿不准的类别多选），判据取方面模板，扫描会列出原文里没读进参数的数字；设 `review_phase`（日常设计 `design_iteration`，
用户明确要冻结才用 `schematic_freeze`）。其余 intent 字段在有它的输入的那个任务里写：装配配置 1.2，资料路径、脚表、器件类别 1.3，电源轨 2.1。需求缺失、含糊或冲突而判断要靠它的，**当场问用户**（[需求澄清](requirement-clarifications.md)）：
录完需求后一次汇总提问，不逐颗器件打断用户，问题写 `intent.clarifications`；用户给定需求、采纳 SR 建议的条文或明确暂缓，
三选一，不留“先挂着”。定下的需求马上加进 `intent.requirements` 再往下做，并问用户是否直接改原始需求文件（点名哪个文件哪一处、写什么），
确认后直接改，记 `answer.requirement_files`；无人值守时读任务书附的澄清答复，没覆盖的问题停在这一步，
把问题清单交给用户。②、③ 中途发现新的需求问题同样当场问。
录入前按 [需求原文到审查要求](requirement-clarifications.md#需求原文到审查要求) 分清确实待用户决定的、
客观设计要求、明确排除和下游工作；不能把源文件的 OPEN 标题机械变成问题。
核需求是否给全时，对照知识框架 `知识/需求要素/`：按本板的端口和负载找条目，条目列的条件缺了而判断要靠它的，照上面当场问。
按 [输入与覆盖](inputs-and-coverage.md) 记录输入版本/哈希；PDF 与网表须核修订号证明同版。
仅有 PDF 时逐页读图并声明范围，不能声称网表/ERC/逐脚全量通过。缺工具先盘点现有能力，安装须另获授权。

做完的标志：`requirements` 每条有类别、理解、参数和承接电路（或 `[]` 加理由）；需求原文里带单位的数字都读进了参数，
或在理解里说明为什么不读；`intent.clarifications` 每个问题都有答复（冷扫不再打印 `CLARIFICATION_PENDING`）；
`requirement_source`、输入文件的版本与哈希已记录；`review_phase` 已设。

## 1.2 解析与完整性

解析器、字段映射与自检失败怎么读见[输入解析](input-parsing.md)。

    python3 scripts/parse_netlist.py <allegro目录> -o db.json
    python3 scripts/parse_kicad.py <文件.kicad_sch|kicadxml> -o db.json
    python3 scripts/read_bom.py db.json <BOM.csv>        # 有装配 BOM 时必跑，在生成计划之前

BOM 里每个位号除位号、值以外的列原样进 db，计划把它们挂到功能框架（`bom_specs`）和器件检查项（`bom_fields`）上：
里面写的器件规格（额定、公差、漏感上限等器件必须满足的值）是设计结果，照用；写在那里的设计方计算值不用。

核对重复归网、缺失 primitive、索引互反、符号声明脚与网表实有脚；导出日志有错误或中止（DOC-A01）先作为输入阻断。
NC 汇集伪网、No-connect 属性、DNP 不贴是三件事；不贴的串联通路视为断开，多配置分别分析，装配配置（贴装、跳线）写入 `intent.assemblies`。
原生输入受阻仍按 [受限输入中的独立主张](inputs-and-coverage.md#受限输入中的独立主张)
审查可读材料；记录具体资料矛盾或保证缺口，不用全板通用阻断代替逐项结论。
逐页提取 PDF 文本并建页码/页名/网表路径映射；极性、旋转不清时渲染局部放大。

`db.json` 有了就跑一遍冷扫（命令同 2.1 清单的 a）：

    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --plan-json review-plan-cold.json --json lint-cold.json

它打印的提示是 ① 各任务做完的标志的来源：阻值读不出的电阻在这里当场告诉用户（写法见 2.1）；没核验类别的器件、
泛称 ic、脚表没有供电脚（`DEVICE_KIND_GENERIC`、`DEVICE_PINS_NO_SUPPLY`、DEV-D02 的类别缺口）归 1.3；需求原文没读进参数的
数字（`REQUIREMENT_NUMBERS_UNREAD`）归 1.1；未声明电压的轨和无界节点留给 2.1 的 `power_rails`。intent 每补一批就重跑。
这里写出的 `review-plan-cold.json` 是中间产物，2.1 清单的 a、e 会重写它；步骤之间传的文件见架构说明（SR 维护者读）。

做完的标志：`db.json` 生成，导出日志没有错误（有则 DOC-A01 阻断，先解决）；装配 BOM 已读入；装配配置已写；
PDF 与网表核过同版；页码映射建好；冷扫跑过，阻值读不出的电阻已告知用户。

## 1.3 资料取证与器件身份（DEV-D01、DEV-D02）

    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --intent intent.json --json datasheet-audit.json   # 取证并核验 intent.device_kinds

这条命令在 2.1 的清单里是 b：候选（c）要用核验过的器件类别，所以器件类别每补一批就重跑；资料补齐后的重审计是 g（2.2）。
资料只在 intent 写路径（`materials.<名>.path`，文件在即可用）。

- 先核 MPN、封装/温度/档位与 BOM/符号；关键采样电阻、保护/安规件、储能电容和磁件也按原厂订货表核对
  阻值/容量/耐压组合，不把系列范围当具体后缀的可订购范围。候选不代表身份成立。
- PART/VALUE 冲突或图面/BOM 与链接资料矛盾时，按 [身份冲突与身份分支](evidence-proportionality.md#身份冲突与身份分支)
  处理：不一致本身判 DEV-D04 FAIL，电气判据逐分支给条件结论，全部分支都违反才判电气 FAIL。
- 按实际用途读引脚、额定/推荐条件、相关 min/max、模式和 errata；“官方物理脚”指手册引脚定义的编号或名称，
  焊盘映射属于 PCB 阶段。核过的脚表写入 `intent.devices`（声明抄全的脚表要含封装名说出的每个脚号），DEV-D02 差集和 DEV-D05 引脚处置据此列出；
  去耦组由官方脚表逐器件逐供电网推出，只按（位号，网）写用途与条款。
- 器件类别写 `intent.device_kinds`（手册页码加原文，`audit_datasheets.py --intent` 核验，原文与手册标题须一致）：分立件、磁件和连接器写
  对外功能的类型，集成电路写手册标题给出的角色（角色登记表见 [审查词表·器件角色](review-vocabulary.md#器件角色)，
  `catalog.DEVICE_ROLES`；标题没有任何登记角色的才写泛称 ic，计划把每个 ic 列成 `DEVICE_KIND_GENERIC` 诊断：这些器件
  不生成电路候选，累计清单是下一批角色的来源）。须定类的器件（按分类器读出的类型，不看位号）没核验过是 DEV-D02 缺口，认不出、接两个以上网的器件由审查员归类；角色决定电路候选的
  核心器件和它生成的电路类型，计划顶层 `domains` 据此列出参考地分区、跨域器件与截止网络（[检查器共用约定](checker-conventions.md)）。
- AI 已逐端核对的器件角色和电源/返回分组按 [可复用声明](reviewed-declarations.md) 保存来源与输入指纹；
  下次先验证声明，输入变化则重新核对，不能只刷新摘要。`manual_*` 兼容字段不代表人员确认，核对者身份须如实记录。
- 器件保证值先查知识框架 `知识/器件参数/`（带手册页码），没有条目或版本不符再读手册；引框架 `原件勘误.md` 列出的原件的数，看页面图像（[器件资料](datasheets.md#二保证值核对方式-e)）。
- 资料缺失时按 [器件资料](datasheets.md) 补取（先 LCSC/立创，再原厂），仍取不到按逐参数补证；
  PDF 提取的关键数值对照渲染页核单位。

做完的标志（看 1.2 那条冷扫重跑后的提示）：审计跑过，每颗须定类器件的 `device_kinds` 核验 VERIFIED（认不出的已归类）（DEV-D02 不再列器件类别缺口）；
`DEVICE_KIND_GENERIC` 列出的泛称 ic 逐颗看过标题；关键器件脚表 `pinout_complete`，`DEVICE_PINS_NO_SUPPLY` 逐颗看过；
资料没拿到的留给 2.2 的资料请求，不在这里卡住。
