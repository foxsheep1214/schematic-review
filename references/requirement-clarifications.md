# 需求澄清项：独立报告与决策闭环

需求澄清项是报告的问题类别，不是第五种检查结果，也不是已确认电气缺陷。
本节是该类别的唯一字段与判定契约。新报告使用 `requirement_clarification_version: 1`，
顶层 `requirement_clarifications` 保存唯一问题，未发现时填 `[]`。

## 收录范围

只收录影响本次原理图判断、且实际尚待需求责任方决定的需求：缺失（MISSING）、表述含糊
（AMBIGUOUS）、互相冲突（CONFLICTING）、尚未确认（UNCONFIRMED）。先查提供的需求文档、
接口约定、已确认对话和设计输入，记录查过什么、哪些内容仍不能确定。审查者没找到资料
不证明需求不存在；与当前电路无关的模板空白不列入，SR 不承担全产品需求完整性验收。

- 未确定最大负载：需求澄清。
- 已确定最大负载但缺器件规格：证据缺口（EXTERNAL_DATA）。
- 规格齐全且器件不满足确定的负载：电气缺陷（FAIL）。
- 需求已定但型号/实现方案未选：设计待完成（DESIGN_OPEN）。
- 已有输入尚未阅读或计算：审查待完成（REVIEW_INCOMPLETE）。
- 实际热性能等后续工作：独立 HANDOFF，不作为需求澄清。
- 项目未给降额规则等设计约束：先按标明的假设判定（写明假设值及出处，如行业常用或器件厂家建议）；
  在合理假设范围内结论都不变时不建澄清项，只在报告注明假设；假设取值会改变 PASS/FAIL 时建需求澄清项，
  关联检查改记 INSUFFICIENT + REQUIREMENT_OPEN，不以审查者自选的假设定缺陷。

提案（PROPOSED）可先做有明确前提的电气判断；只有未确认事项确实留下待决问题时才建澄清项。
需求方明确暂缓的条目保留 USER_DEFERRED 及授权记录，不冒充已确认或一般缺资料。

## 一项问题与多条检查

一个独立决定使用一个稳定 ID；同一最大负载决定影响多条检查时只建一项，不能逐器件复制。
不同参数即使来自同一本需求书，也不自动合并。一个检查依赖多个独立决定时可被多个问题引用。
有 REQ ID 时引用该 ID；尚无编号时可省略 requirement_ids，以澄清 ID 和来源定位追溯，不伪造需求编号。

```json
{
  "requirement_clarification_version": 1,
  "requirement_clarifications": [{
    "id": "CL-LOAD-01",
    "title": "确定输出最大连续负载",
    "kind": "MISSING",
    "status": "OPEN",
    "question": "受控需求的输出电流尚未确定，当前资料未给出可用于选型的范围",
    "decision_needed": "需求责任方确定最大连续电流和适用工况；候选值及建议应附依据",
    "owner": "系统需求负责人（角色，实际人员待指定）",
    "decision_due": "BEFORE_DESIGN",
    "closure_criteria": "形成受控需求修订，并按确定负载重审损耗和额定值",
    "requirement_ids": ["REQ-LOAD"],
    "check_ids": ["<实际需求检查ID>", "<实际损耗检查ID>"],
    "evidence": [{"source": "需求规格 Rev A", "locator": "输出电流条目及本轮输入核查记录"}],
    "freeze_impact": "BLOCKING",
    "impact_reason": "电流范围影响器件额定和损耗，尚不能确定原理图选型"
  }],
  "workflow_version": 1,
  "work_items": []
}
```

字段均为上例所示，仅未编号需求可省略 requirement_ids；关联检查已有 REQ ID 时必须填写，其余为必填。owner 可写真实责任角色，不虚构人员；
question 写事实与歧义，decision_needed 写要决定什么并尽可能给有依据的选项/建议；
closure_criteria 写确认方式和复验范围。evidence 必须定位已检查的输入和待决依据。

OPEN 项的 check_ids 只关联 `INSUFFICIENT + REQUIREMENT_OPEN` 检查。这些检查仍须有
missing_inputs、rationale、证据和 C 置信度，但不填写 severity/potential_severity。
独立电气 FAIL、证据缺口、已完成的窄判据另留检查，不能把它们改成需求问题来改变严重度或放行。

澄清记录直接生成本轮 workflow 任务，保留 owner、decision_due 和 closure_criteria；
不要在 work_items 重复添加相同需求待办。其他 FAIL/INSUFFICIENT 继续用 work_items。

## 冻结影响与决策时点

decision_due 区分“继续相关设计前”（BEFORE_DESIGN）与“冻结前确认”（BEFORE_FREEZE），
以及“持续跟进但不作为冻结前置”（FOLLOW_UP），与缺陷 P0–P3 无关；所有开放澄清仍在本轮队列中反馈。是否阻断冻结独立填写：

- BLOCKING：决定影响拓扑、选型、额定值或判据，现有设计无法完成所需证明。按唯一问题阻断，
  不因关联十条检查生成十个独立阻断。BEFORE_DESIGN 必须为 BLOCKING。
- COVERED：候选需求范围已明确且受控，已有独立检查证明当前设计覆盖全部候选，不需要再改原理图。
  可不阻断冻结，但需求仍 OPEN，不能将它改为已确认或删除。decision_due 为 FOLLOW_UP，
  在本轮推进确认并在冻结报告列明覆盖依据和待确认责任，不将此项设为冻结前置。

COVERED 额外提供 `coverage`：candidate_scope（完整候选范围及来源）、rationale（为何全部
覆盖且不需改图）、check_ids（独立且当前 PASS 的检查 ID 数组）、evidence（覆盖计算和依据）。
没有候选界限、只有“风险不大”、只验证一个候选或只引用无关 PASS，都不能使用 COVERED。
软件核对引用和状态，工程审查者核对证据是否真正覆盖所有候选，不宣称机器能判断自然语言证明。

受影响检查的 blocking 等于所有关联 OPEN 项中是否有 BLOCKING；一项阻断就不能填 false。
确认记录不齐不能用 disposition=ACCEPTED 冒充需求已决定。其他真实缺陷、证据缺口、必需 HANDOFF
和输入完整性继续独立约束冻结，需求 COVERED 不豁免它们。

## 关闭与复审

状态为 OPEN / RESOLVED / RETRACTED：

- RESOLVED：责任方已作出决定，保存确认人、日期、决定内容和受控需求版本；重建受影响计划并
  重新审查，才关闭澄清。电气复审仍可能 FAIL 或有其他证据缺口，关闭需求不代表设计通过。
- RETRACTED：核查发现原有需求已经明确、或本项与审查范围无关，保存更正依据和受影响检查复核。
  不用“已解决”掩盖错误收录。

两种关闭状态均须 `closure`：by、date、decision、requirement_revision 四个非空字符串，
以及 evidence（决定/更正记录）和 reverification（受影响检查复审记录）两个来源/定位数组。
撤回未编号的需求可将 requirement_revision 写为所核输入的版本及撤回原因。保留原问题 ID 和 check_ids；
RESOLVED 关联的 REQ 条目在当前计划中必须为 CONFIRMED；撤回条目不能仍为 OPEN。仍有另一项独立需求缺口时必须关联另一条 OPEN 澄清。
不能批量把受影响检查改 PASS，也不能仅刷新哈希替代重审。

## 输出与统一协议

报告将“需求澄清项”与“电气设计缺陷”“审查证据缺口”“下游设计与验证”并列。
`requirement_clarification_summary` 给 total/open/resolved/retracted、affected_checks、
blocking_open/covered_open；例如“1 项待决需求，影响 10 条检查”，不计入 confirmed_defects。
`requirement_clarifications` 输出完整唯一记录，`insufficient_by_cause` 只表示检查行数。

所有报告必须声明 requirement_clarification_version: 1，并包含 requirement_clarifications 数组，
无需求澄清时填 []；校验器强制检查，缺字段直接拒绝。

## 关闭证据的例子

以下是假设示例，实际审查须引用真实记录：SR 发现“5 V 输出最大连续电流未定”，登记 CL-LOAD-01。

1. 需求责任方确认“最大连续输出 2 A”，保存在需求规格 Rev B，或本轮明确确认的对话及版本化 intent 中。
   closure.evidence 指向该条决定，closure 中写确认人、日期、决定内容和相应输入版本。
2. 审查者按 2 A 重查电源能力、限流门限、器件额定和损耗。检查记录中保留数据来源、计算及 PASS/FAIL
   或尚存的其他缺口，closure.reverification 指向这些记录。
3. 需求已经确定，相关检查已经重审，CL-LOAD-01 才能标 RESOLVED。只有“已沟通/已处理”没有可定位
   决定和复审记录时仍保持 OPEN。

证据可以是已有需求文档、可定位对话、网表核对或计算记录，不要求为了关闭澄清另作正式签字或实测。
若重审发现所选器件只能满足 1 A，需求澄清可以关闭，同时新增/保留“器件能力不满足 2 A”的电气缺陷。
需求闭环与缺陷闭环分别记录。
