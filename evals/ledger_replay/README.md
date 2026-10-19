# Ledger Replay：真实审查台账的定级回放

三份 R3 全新独立审查记录（4b3b406、d32855c、3924cd7，100 W 适配器）按 schema 3 冻结在 `records/`，
重放校验、质量筛查和报告渲染。改定级、汇总、待办或报告逻辑后跑一次，不到一秒：

    python3 evals/ledger_replay/replay.py

**冻结答案（`answer`）来自审查者当时运行的 SR**，不是被测版本算出来的：汇总计数、证据不足原因、
每个证据不足行的潜在等级、每项待办的等级与期限。转成 schema 3 后这些字段与原 `review-gate.json` 逐项一致。

**已知偏差（`known_deviations`）**写明当前 SR 应当不同的字段和理由。目前都在 4b3b406：一是按后果类别计数，
原记录有 6 行的行级类别与该行缺口自身的类别矛盾，schema 3 只保留缺口上的一份严重度，
COMPONENT_DAMAGE 36→38、REQUIRED_FUNCTION 54→52，潜在等级不变。

**基线（`baseline`）**是当前 SR 的质量筛查代码计数、报告标题和“结论”一节，冻结后有变化就会报出。它不是独立真值：
读过变化、确认是有意改动后用 `--freeze-baseline` 重写，并在提交说明里写理由。

原 gate 全部有效，所以 `grading_errors`（除路径相关外的校验错误）必须为空。夹具把项目路径换成 `project/`、
临时目录换成 `work/`，db 的输入指纹随之改变，由此引起的错误（`replay.py` 的 `PATH_BOUND`）与定级无关，不计入；
这是 4b3b406 的第二条已知偏差。报告因此带“记录有错”横幅，但“结论”一节仍按台账渲染，冻结在基线里。重建夹具：

    python3 evals/ledger_replay/make_records.py <原理图审查结果目录> 4b3b406 d32855c 3924cd7

单测 `scripts/tests/test_ledger_replay.py` 属合同层。
