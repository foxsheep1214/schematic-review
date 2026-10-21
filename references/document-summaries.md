# 计算派生摘要一致性（DOC-Q01）

交付包含计算库存、preflight 结果与当前 README/报告的汇总声明时，核三者内容，不能仅核文件哈希。
声明输入里的 ASG 交付带 `preflight-delivery.json` 时，本核对结果必须被 DOC-Q01 行引用，且其 `inputs_sha256` 含该文件当前哈希，
否则 `pack_review.py` 拒绝打包。普通无计算派生资料的电路不强制增加此依赖；按实际审查范围记录未适用或未执行，不能把未执行记成 PASS。
脚本只证明文档数据一致性，不复算公式、不评定参数保证、不推出电气 PASS。

## 输入与入口

冷跑读取已交付文件；热跑及报告定稿后使用最终文件重放同一入口。全部输入只读：

```bash
python3 scripts/audit_document_summaries.py --calculations calculations.json --preflight calculation-preflight.json --document README.md --document report.md --json document-summary-audit.json
```

`--document` 可重复，传实际含当前计算摘要的受控文件；无计算摘要的其他报告无需传入。
不要为让脚本发现问题另外手输一份错误计数。保留原文声明、文件哈希及行号；输入中有历史/引文/局部摘要时，
先界定当前全库存声明的语义范围，不把历史示例或局部计数当当前全板声明。
不支持的格式先记 INSUFFICIENT，审查者按同一三向判据核原文并留证，不能改写原冻结材料来过门。

库存契约为 `schema_version: 1` 与 `calculations` 非空列表，每行有非空规范字符串 `id` 和
`claim`（`SUPPORTED`、`CONDITIONAL`、`FAIL`）。其他字段留给算术/电气检查器。
preflight 为 `schema_version: 1`、顶层 `status`（`PASS`、`FAIL`、`INSUFFICIENT`）与非空
`results` 对象，键为 ID，每行的 `status` 使用相同三个支持状态；顶层 PASS 不替代逐行状态。
`INVALID`、未知状态、坏 JSON/schema、重复 JSON 键不可靠，均不能形成一致性 PASS。

当前自动入口仅解析以下两种完整、明确的全库存声明，读取原文而非单独声明文件：

```text
15项计算条件检查6SUPPORTED/9CONDITIONAL/0FAIL。
Calculation summary: total=15; SUPPORTED=6; CONDITIONAL=9; FAIL=0
```

中文固定短语可在句中，英文为独立一行；不猜任意自由文本数字，不省略零状态，不把部分匹配当完整摘要。
传入文件的所有完整声明均核对；标记存在但语法不完整时记录解析缺口，即使同文件其他声明正确也不 PASS。
没有支持的声明、没有库存或没有 preflight 时为 INSUFFICIENT。需要更广的文档格式时扩展有测试的明确解析器。

## 结果与处置

### ASG 父计算与子不等式格式

另支持 ASG 的非空计算 list（每项 `id/conclusion/coverage/checks`），以及执行后的
`preflight-delivery.json`（`status`、`calculations` 状态 map）。调用时增加
`--preflight-contract design-preflight.json`，该文件是输入合同，不能代替执行结果。
适配器只接受合同子项 inputs.evidence 中明确指向当前计算文件、locator 为 `父ID / 检查name` 的关联；
相对 source 从合同目录及其项目上一级解析。不能按 ID 后缀或相同数量猜对应。

先核合同和执行结果的全部子 ID、子 claim/status、每个父项的子检查覆盖，再汇总父项：任一子项 FAIL 即 FAIL；
无 FAIL 但有条件、partial、assumptions 或 omitted_terms 的保持 CONDITIONAL；只有完整且无条件才 SUPPORTED。
重复、未知状态、未对应项保留缺口或矛盾，不能取最后一条来消除问题。`adapter.links` 保留关联路径。
父计算总数与子检查总数分别保存，不能将 22 项计算与 66 条不等式直接判成资料冲突。

支持当前中文表格的完整行（冒号及标签固定，数量周围允许空格）：

```text
| 计算：上下界完整 / 只算了一部分 | 0 / 2 |
| 计算结论：满足 / 有条件满足 / 不满足 | 0 / 2 / 0 |
```

第一行只核 coverage，第二行核父计算结论；两行不是同一种状态计数。
窄一致性 PASS 只说明这些受控声明相符，不能证明公式、资料来源或电路通过。

### 对账与结论

逐 ID 检查库存重复/空 ID、与 preflight 集合的双向差集、逐行 claim/status 相等，再分别计算唯一 ID 总数
与三状态分布，与每个实际原文声明对账。相同计数或相同分布不能隐藏不同 ID 集合或逐项状态对调。
多份/多处摘要冲突、摘要内部总数与分项和不等、原文数字与可解析库存/结果不等，均为已证资料矛盾。

区分整份文件/schema、ID集合和单行状态的可靠性。其他行未知不阻断两侧唯一、状态已知的同ID核对；
已证可靠行矛盾与无关行的INS同时保留。同ID重复不取首值/末值，该ID不作状态比较；仍核其他唯一可靠行。
完整ID集合可解析且唯一时独立核集合/总数；完整状态分布须全部状态可靠，否则actual分布保持未知，
不能把可靠子集当完整库存计数。坏row/无效ID或重复ID不形成完整库存集合；坏文件/顶层schema不提取
该文件的行/集合/计数作证明。preflight重复JSON键整份拒绝，不能悄悄last-write-wins。

输出 `DOC-Q01.DERIVED-SUMMARY` 的窄候选。已证矛盾为 FAIL/P2；只有未知格式/输入缺口时为
INSUFFICIENT（本工具不推定该缺口的电气严重度）；所有要求均核实才为窄一致性 PASS。已证矛盾与解析缺口
并存时保留两者，FAIL 不消除缺口。退出码 PASS 为 0，其余为 2；JSON 完整保留逐项定位和输入 SHA-256。
审查者将该候选按实际原文语义复核、独立绑定计划对象和判据，不能把它覆盖到原有局部输入资格或需求 PASS。
修改动作是修正摘要或库存/结果的受控版本，复验相同集合和状态；未经证明不指定应改哪一侧。

## 冷/热与缓存边界

本入口不使用缓存，每趟从输入字节重新解析、核对并计算哈希；输出 `cache.enabled=false`、`hits=0`。
冷/热重复执行只是复算，不能宣称缓存命中。若其他 SR 入口有缓存，保留其独立真实记录，不把缓存复用当
本项内容一致性证据。冷热都保留调用 argv、返回码、工具/规则身份、输入哈希与各自 JSON。
