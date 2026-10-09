# Seeded Bench：真实电路植入缺陷的自动层快检

把盲审缺陷库里**能用网表表达**的缺陷类型（D-GND-PIN、D-RAIL-SPLIT、D-CAP-POL、D-TVS-STUB、
D-EN-FLOAT、D-FLY-MISS/REV、D-OPTO-R/PU、D-I2C-PU、D-LED-R、D-CAP-VR、D-REF-ANNO、D-BOM-WS）
程序化地植入多块真实公开电路的 db，逐位点跑 SR 冷跑（lint + 计划），统计：

| 列 | 含义 |
|---|---|
| 自动检出（目标规则） | 植入后新增、且点名该位点的目标规则发现 |
| 位点有任意新发现 | 目标规则或其他规则（如 NET-A01）点名该位点的新增发现 |
| 计划有逐对象检查指向 | 计划里有逐对象检查点名该位点，即专家审查至少会被引到这里 |

它只衡量**自动层**，不衡量专家审查，也不证明任何电路合格。语料是已在往轮校准中评过分的公开电路，
不能放入待盲审的电路。位点是“若这样改就是缺陷”的假设，个别位点在电气上可能不构成缺陷，
结论要回到具体发现核对。

## 在校准循环中的位置

盲审一轮要 3～10 小时，只能得到 2～3 个缺陷的检出信号；本基准一次几十秒，覆盖几十个位点。
建议每轮先跑本基准：

1. 改规则/检查器前后各跑一次（`--compare`），自动检出率只能升不能降，基线发现数的增量要逐条核对是否误报；
2. 本基准已稳定检出的缺陷类型，盲审出题时少植入，把名额留给需要判断的缺陷（D-FLOOR、计算、条款类）；
3. 盲审漏检的自动类缺陷，先在这里复现成位点，再修。

## 运行

```sh
python3 -B evals/seeded_bench/prepare.py --cache <缓存目录>
python3 -B evals/seeded_bench/run.py --cache <缓存目录> --out <输出目录> [--sut <另一个 SR 副本>] [--compare <旧 results.json>]
```

`prepare.py` 按 `corpus.json` 的固定 commit 拉取源仓库、用 kicad-cli 导出网表并解析；第三方文件只留在缓存目录。
`strict: false` 的板子按 `strict_note` 记录的原因用 `--no-strict` 解析。
