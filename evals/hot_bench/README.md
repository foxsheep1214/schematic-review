# 热证据 bench（hot_bench）

冷跑 bench 只能证明 A 类规则在真实网表上不误报；E 类规则要靠 evidence.json 和数据手册事实才会运行，
以前只有合成夹具测过。这个 bench 用 `evals/typical_circuits/fixtures/` 里的开源真实板，配上从原厂数据手册
逐页抄录的参数，把 E 类规则放到真实网表上跑。

- `sources.json`：每份数据手册的 URL、标题、SHA-256 和取得日期。PDF 不随仓库分发；
  `run.py` 生成占位文件，写明来源 id 和 SHA-256，以满足 datasheet-audit 的绑定。
- `cases.json`：每块板的 intent、evidence checks（每条注明来源文档和页码）、
  人工判定的 `expected`，以及 `expected_notes` 说明非 PASS 的原因。
  每个 `mutations` 条目只改一个值或一处连接，必须翻转它列出的检查；其余检查保持原答案。
- 变异操作：`swap_pin_names`、`remove_parts`、`add_resistor`、`intent_rail`、`evidence_override`。

```bash
python3 -B evals/hot_bench/run.py
```

任一行 MISMATCH 即退出 1；`scripts/tests/test_hot_bench.py` 把它作为单元闸门。

判定原则：
- `expected` 写的是电路的真实答案，不是 SR 当前输出。SR 输出与之不符时，先查证据抄录，再查 SR。
- 数据手册确实没给的参数（如 AP2112、ESP32-C3 的 EN 引脚负向绝对额定），答案是 INSUFFICIENT，
  并在 `expected_notes` 写明缺的是什么。
- 修改 `expected` 或证据时提升 `revision`，并在提交说明里写出依据的页码。

已暴露并修复的 SR 误报：多功能引脚名（`IO2/GPIO2/ADC1_CH2`）和 KiCad 低有效上划线名（`~{INT}`）
导致 DEV-E01 误报；出厂短接的焊盘跳线（`SolderJumper_*_Bridged*`）后面的上拉被 SIG-E01 判为不存在。

尚无真实板正例的 E 类规则见 `python3 -B evals/bench_coverage.py`。
