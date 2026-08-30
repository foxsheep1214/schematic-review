# 原理图审查报告模板

本报告只签署原理图是否可冻结并进入 PCB Layout，不签署整板投板、SI/PI、EMC、
热、DFM 或生产准出。中间产物放 /tmp；项目目录只交付报告和用户要求的机器结果。

## 报告骨架

    # <项目名> 原理图审查报告（首审/复审/合并版）

    - 审查对象：<原理图版本、页数、网表导出时间、板卡一句话>
    - 审查依据：<datasheet、平台原理图 checklist、需求、历史记录>
    - 输入覆盖：<器件/网络/引脚/pintype/页数；AC0 计划与热跑 executed/pending>
    - 对比基线：<复审时填旧版 db.json、Diff 和历史断言文件>
    - 范围声明：本报告结论仅为原理图准出，不代表 PCB 或整板通过
    - 日期 / 限制说明：<缺失输入和规格符合性受限项>

    ## 一、总体结论
    <只能选择：原理图准出 / 有条件准出 / 不准出>

    ### 原理图准出判定
    | 准出条件 | 结果与证据 |
    |---|---|
    | BLOCKER = 0 | |
    | Warning 已关闭或书面接受 | |
    | 阻断级 INSUFFICIENT 已补齐或书面接受 | |
    | 必需 HANDOFF 已形成可执行约束并指定接收阶段 | |
    | AC0 适用规则已执行，未执行项已解释 | |
    | 关键 datasheet 与热跑证据完整 | |
    | 关键供电/链路/WCA 已验证 | |
    | BOM/符号/引脚/封装字段唯一且一致 | |
    | 复审 Diff 与历史闭环断言通过 | 首审填 NA |

    ## 二、逐项审查记录
    | ID | 检查对象 | 判据 | 适用性 | 结果 | 证据置信度 | 审查意见 | HANDOFF |
    |---|---|---|---|---|---|---|---|
    | <AC0/ER...> | <网络/位号/页码/功能> | <本项判据> | APPLICABLE | PASS/FAIL/INSUFFICIENT | A/B/C | <本项独立意见> | <无或 H-xx> |

    ## 三、FAIL：BLOCKER / Warning
    <每条按 ECO 格式>

    ## 四、INSUFFICIENT：材料不足
    | ID | 缺失信息 | 受影响结论 | 是否阻断 | 关闭条件 |
    |---|---|---|---|---|

    ## 五、HANDOFF：独立 PCB/测试/结构动作
    | ID | 来源检查项 | 状态 | 接收阶段 | 约束 | 验证方法 |
    |---|---|---|---|---|---|

    ## 六、PASS：已验证关键项
    <只列关键通过项，给网表/datasheet/计算证据，防止下轮重复劳动>

    ## 七、NA：经适用性判断不适用
    <每项给设计意图或范围依据；未检出特征不能单独作为 NA 依据>

    ## 八、历史意见闭环（复审）
    - PASS：<断言 ID + Diff 证据>
    - FAIL/Rule-17：<声称已改但机器断言失败>
    - INSUFFICIENT：<缺少旧版数据或意见不可机器化>

    ## 九、更正说明
    <原结论 → 更正后结论 → 依据>

    ## 附录 A：AC0 适用性与执行计划
    <逐项 APPLICABLE/NOT_APPLICABLE/UNDETERMINED、READY/WAITING_EVIDENCE、缺失输入>

    ## 附录 B：关键计算
    <公式、位号、实际值、公差、min/typ/max、判定窗口和出处>

    ## 附录 C：自动检查覆盖
    <FINDING/CANDIDATE/PASS/SKIPPED、hot_executed/hot_pending、Diff summary>

## 发现项格式

    [ID] [BLOCKER/Warning/Info] 标题
    审查结果：FAIL
    HANDOFF：<无 / H-xx，OPEN/ACCEPTED/VERIFIED>
    位置：位号/网络/页码
    证据：网表数据或 datasheet 条目（证据置信度 A/B/C）
    根因：为什么会错
    改法：具体到位号、阻值、网络名
    验证：重出网表后复扫/热跑/专项测量

HANDOFF 不是审查结果，也不使用 BLOCKER/Warning 严重度；它必须给来源检查项、
接收阶段、约束和验证方法，可与 PASS/FAIL/INSUFFICIENT 并存。
INSUFFICIENT 不是建议项，必须说明缺失材料、受影响结论和是否阻断。
A/B/C 只写在证据置信度字段中。

## 写作要求

- 不得把“PCB 约束已传递”写成 PCB 已通过。
- BLOCKER 必须在原理图准出前清零；Warning 必须关闭或书面接受。
- 每个适用检查项有自己的结果、证据和审查意见；总体准出另行聚合，不用一段总评替代逐项记录。
- 每个 BLOCKER/Warning 给可复现证据链。
- 被反驳后用证据复核，错误结论显式写入“更正说明”。
- 最后一句必须是原理图准出结论，不能写“整板可以投板”。
