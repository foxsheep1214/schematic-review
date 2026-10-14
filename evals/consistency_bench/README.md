# Consistency Bench：同一技能、不同 agent 的判定一致性

同一份计划行，交给不同 agent（如 Codex、Claude）各跑两次，量分歧，不判对错：

| 指标 | 含义 | 期望 |
|---|---|---|
| 同 agent 一致率 | 同一 agent 两次运行结论相同的行比例，是模型自身波动的底线 | 高 |
| 跨 agent 一致率 | 不同 agent 之间结论相同的行比例 | 改动后上升，接近同 agent 一致率 |
| PASS↔FAIL 互翻 | 任意两次运行一判 PASS、一判 FAIL 的行 | 0 |
| 按规则的分歧 | 有分歧的行按规则统计，分歧最多的规则进入下一轮训练 | 下降 |
| 门禁违规 | 预判 PASS 被改判 FAIL/INSUFFICIENT 而无有效 proposal_override 的行（validate_review 会拒绝） | 0 |
| INS 率 | 每次运行 INSUFFICIENT 行占比 | 下降 |

跨 agent 一致率只说明读法是否收敛，不说明谁对；改判方向要回到具体行核对依据。
误放 PASS 由保留题等其他基准把关。

## 题包

`build_pack.py` 从一份已有审查的板级目录出题包：拷贝 db/intent/资料，用被测 SR 重新生成计划，
写出选定行的完整规格（计划里已没有的手工行沿用原计划规格并标明来源）和固定指令 `prompt.md`。
不拷贝审查结果、报告和计算，避免先入为主。题包冻结后不覆盖；SR 改动后要比较新旧技能时，
用同一题包、不同技能副本各跑一遍。

```bash
python3 -B evals/consistency_bench/build_pack.py --source <板级目录> --rows rows.json --out <题包目录>
```

题包含真实板数据，放在训练批次目录，不进本仓库。

## 运行

每个 agent 每次运行都是全新会话。技能副本去掉 `evals/` 与 `scripts/tests/`，避免接触答案或原始网表。
把 `prompt.md` 中的 `{SKILL}`、`{PACK}`、`{OUT}` 换成技能副本、题包和本次输出目录后原样发给 agent；
同一轮内各 agent 用同一份指令。每个 agent 至少跑 2 次，否则无法区分读法差异和模型自身波动。

## 评分

```bash
python3 -B evals/consistency_bench/score.py --pack <题包目录> \
  --run claude/1=<输出>/answers.json --run claude/2=<输出>/answers.json \
  --run codex/1=<输出>/answers.json --run codex/2=<输出>/answers.json --out <评分目录>
```

运行标签的 `/` 前部分是 agent 名，同名视为同一 agent。
