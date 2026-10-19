# 选型与归因复核

ASG 的交付包 `record/` 里有两份 SR 要独立复核的记录：

| 文件 | ASG 写了什么 | SR 复核什么 |
|---|---|---|
| `selection.json` | 每个核心器件角色的决定性条件（`param/op/limit`）、候选、每个候选读到的值与页码、选中/淘汰依据 | 决定性条件是否完整（有没有漏掉需求里能淘汰候选的量）；选定型号是否真的满足；淘汰理由是否成立 |
| `review-responses.json` 的 `cause` 与 `lessons.json` | 上一轮每条意见为什么没被技能自己拦住：`rule_missing`、`rule_not_enforced`、`knowledge_missing`、`knowledge_wrong`、`judgment`、`none`，以及改了哪个文件 | 归因是否成立：同一条意见复发而 ASG 仍归为 `judgment`，或改动的文件与归因类别不符，都要指出 |

复核不迁移 ASG 的结论：先读需求和候选手册再看 ASG 的理由。流程：

```bash
python3 scripts/review_selection.py worksheet <ASG交付目录> --out selection-review.json   # 空白复核表
# 逐角色、逐意见填写
python3 scripts/review_selection.py validate selection-review.json --asg <ASG交付目录>      # 校验并打印摘要
```

## 复核表字段

每个角色：

| 字段 | 取值 |
|---|---|
| `verdict` | `AGREE` / `DISAGREE` / `INSUFFICIENT` |
| `conditions_complete` | ASG 的决定性条件是否覆盖了需求里能淘汰候选的量；`false` 时写 `missing_condition` |
| `basis`、`pages` | 结论依据与手册页码；`AGREE` 和 `DISAGREE` 都要 |
| `alternative_mpn` | 不同意时给出的型号，不能是 ASG 已选定的；可以是 ASG 淘汰的候选 |
| `asg_error` | 或者指出 ASG 淘汰/选中理由里的具体错误，点名候选型号与条件 |

每条已归因的意见：`agree` 为 true/false；不同意时给另一类 `cause` 和 `reason`。

## 结果怎么回到 ASG

`validate` 打印的摘要进 SR 报告的处理清单：每个 `DISAGREE` 角色和每条不同意的归因各成一条待办，
编号沿用报告里的 `W-…`；ASG 下一轮按 [review-comments.md](../../autonomous-schematic-generation/references/review-comments.md) 登记，
改选型的记 `REDESIGN` 或 `DESIGN`，改归因的直接改 `lessons.json`。`missing_condition` 是 ASG 的 `knowledge_missing`：
要补进 `references/core-part-selection.md` 或 `part-roles.md` 的决定性参数。

本页的检查不替代 DEV-D01（器件身份）、DEV-D04（物料）和 DEV-C05（推荐工作条件）：那些仍按规则总表逐器件做；
本页只回答"在候选里选它对不对"和"ASG 对上一轮意见的归因对不对"。
