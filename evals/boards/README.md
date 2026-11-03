# 板子驱动的改进回路（boards program）

> 读者：SR/ASG 维护者。2026-11-02 用户：用更多的实际电路板来驱动问题的改进；再多找一些板子，比如 100 块，在 Codex 里运行 4 个对话分批跑，每块跑得细致一些。

目的：用真实公开电路板逐块跑 SR 的完整审查，把每条发现归因到四类之一，产出能直接变成修改的材料；
不在这里改检查器、准则或共用层——那是合并步的事。

## 目录

| 路径 | 内容 | 谁写 |
|---|---|---|
| `catalog.json` | 候选板目录：`{"boards": [{id, repo, commit, schematic, license, kicad_version, types: [词表电路类型…], note}]}`，约 100 块，类型不重复优先 | 侦察（一次） |
| `_lanes/lane-N.json` | 第 N 条流水线的板子 id 列表（4 条，各约 25 块，类型交错） | 侦察（一次） |
| `_lanes/lane-N/memo.md` | 该流水线跑过的板子留给下一块的经验（SR 用法坑、常见误报模式），每块追加几行 | 流水线 |
| `_tools/fetch_board.py` | 按 `catalog.json` 的 id 拉源仓库到缓存目录（固定 commit）、`kicad-cli` 导出网表、`scripts/parse_kicad.py` 解析成 `db.json`；第三方文件只留在缓存 | 侦察（一次） |
| `_tools/board-prompt.md` | 每块板给 Codex 的任务模板（`{{BOARD_ID}}`、`{{LANE}}` 占位） | 维护者 |
| `_tools/run_lane.sh` | 流水线驱动：逐块调用 `codex exec`，跳过已有 `round-report.md` 的板子，每块结束提交一次 | 维护者 |
| `<board-id>/` | 一块板的全部产出（见下） | 流水线 |

缓存目录 `~/.cache/sr-boards/<board-id>/`：源仓库、导出的 XML 网表、`db.json`、审查工作文件。仓库里不放第三方文件。

## 一块板的六步

1. **立案**：读目录项，确认许可证允许审查与引用（CERN-OHL、TAPR OHL、MIT、BSD、Apache、CC-BY/CC-BY-SA 可；GPL 可审查但不复制内容；无许可证不收）。
2. **SR 审查**：按 `SKILL.md` 的流程从 ① 到 ⑧ 走到能走的最远处：`parse_kicad.py` → 冷扫 → 写 `intent.json`（板子用途从源仓库 README 推断并写明“推断”）→ `circuit_decisions.py` → 带候选重扫 → 合并扫描出最终计划 → 对计划项逐项判（能从网表、BOM、HardwareWiki 里的手册独立判定的写 `review-results.json`，不能判的记 `needs_human`）→ `validate_review.py` → `render_report.py`。审查工作文件放缓存目录，报告复制到 `<board-id>/审查报告.md`。
3. **逐条归因**：报告里的每条发现，判成一类并给证据（位号、网络、数值、手册页或标准条款）：
   - `true_defect`：板子确有问题（或该参考设计已知 errata）
   - `false_alarm`：SR 判错——对象识别错、判据不适用、数值取错；写出检查器应该怎么判
   - `criterion_issue`：设计准则本身写得不可判、太宽或太窄；写出建议改法（不改登记文件）
   - `knowledge_gap`：缺手册、缺典型电路、缺定界表格子，SR 只能留依赖
   - `needs_human`：要实物、要原设计者意图才能判
4. **漏报核对**：按 `docs/proposals/criteria-top50-examples-2026-11-02.md` 的 50 条正反例和本板触发的电路类型，人工过一遍网表，找 SR 该报没报的；每条写应报的 SR 规则、对应准则、证据。
5. **产出修改材料**（不执行）：每条 `false_alarm` 和每条漏报给 `proposed_fix`（文件、函数、改什么、判据出处）；每条 `true_defect` 和能用网表表达的漏报给 `seed`（种子类型名、注入方式、目标规则），供合并步加进 `evals/seeded_bench`。
6. **写产出**：`findings.json`（机器读）、`round-report.md`（人读）、追加 `memo.md`。

## `<board-id>/findings.json`

```json
{
  "board": "id", "source": {"repo": "", "commit": "", "schematic": "", "license": ""},
  "types": ["POWER_CONVERTER", "RS485"],
  "run": {"db_sha256": "", "plan_items": 0, "findings_total": 0, "results_judged": 0, "gate": "PASS|FAIL|not_run", "sr_commit": ""},
  "findings": [
    {"id": "F01", "sr_rule": "PWR-C04", "criteria": ["G03-003"], "severity": "", "refs": ["U3"], "nets": ["+3V3"],
     "sr_text": "SR 报告里的原句", "verdict": "true_defect|false_alarm|criterion_issue|knowledge_gap|needs_human",
     "evidence": "位号/网络/数值/手册页或条款", "proposed_fix": {"owner": "checker|criterion|typical_circuit|datasheet", "where": "scripts/checkers/x.py:func 或 G0x-nnn", "what": ""},
     "seed": {"kind": "D-…", "mutation": "对 db 做什么改动", "target_rule": "PWR-C04"}}
  ],
  "misses": [
    {"id": "M01", "criterion": "G04-032", "sr_rule": "SIG-C03", "refs": [], "nets": [], "why_expected": "", "evidence": "",
     "proposed_fix": {"owner": "checker", "where": "", "what": ""}, "seed": {"kind": "", "mutation": "", "target_rule": ""}}
  ],
  "summary": {"true_defect": 0, "false_alarm": 0, "criterion_issue": 0, "knowledge_gap": 0, "needs_human": 0, "misses": 0}
}
```

`proposed_fix` 和 `seed` 没有就写 `null`。`verdict` 必须五选一；拿不准写 `needs_human` 并在 `evidence` 说为什么。

## `<board-id>/round-report.md`

数字一张表（计划项、发现、五类各几、漏报几）；最重要的 3 条观察（哪条误报模式会在别的板上重复、哪条漏报最该先修、哪条准则写得不可判）；SR 用法上遇到的坑。不超过一页。

## 流水线不做的事

- 不改 `scripts/`、`references/`、`references/shared/`、`evals/seeded_bench/`、`docs/`；修改材料只写进 `findings.json`。
- 不往仓库复制第三方电路文件；报告里引用位号、网络名、数值可以，整段抄原理图不行。
- 不 push；提交由 `run_lane.sh` 做。

## 合并步（每条流水线每跑完 8 块做一次，维护者或一个 Codex）

汇总四条流水线的 `findings.json`：重复出现的 `false_alarm` 模式 → 改检查器 + 加变异；`true_defect`/漏报 → 加种子位点；`criterion_issue` 攒成一张表给用户；`knowledge_gap` 并入 `evals/calibration_boards/datasheets-to-collect.md`。改完重跑 `evals/detection/run.py`，台账一条。

## 目录统计（2026-11-02）

本轮发现 2517 个去重搜索仓库，检查 893 个仓库的固定默认分支 HEAD 与文件树；完成筛查 716 个，其中 235 个进入实际取板流水线，190 个通过导出、解析及 ≥15 器件技术门槛，其中 2 项在许可证终核被排除，合规技术候选 188 项，最终按用途、许可证和根图选择 100 块、100 个独立仓库。其余已检查但未完成筛查的 177 个不计为失败。过程元数据见 `discovery.json`；只登记自主整理的元数据，第三方原理图、许可证全文和 README 留在缓存。

`catalog.json` 的 `types` 严格使用共用词表，每板 1–4 个；`application` 表示主要用途，同一用途最多 5 块（本目录实际最多 4 块）。标签可重叠，不能相加当作板数；电机驱动、电池、FPGA 没有专用词表项，按实际功率变换、保护、模拟/数字接口打标签。没有把普通 +48V 或 PoE 输入冒充词表的 −48V 输入；本批未补齐 `DC_48V`、`VEHICLE_28V`、`SHIP_AC` 场景。

### 取板与验证

```sh
python3 -B evals/boards/_tools/fetch_board.py <board-id> --cache ~/.cache/sr-boards
```

取板工具仅用标准库；复用 `git init` → `fetch --depth 1 <commit>` → `checkout`，以 `--filter=blob:none` 和稀疏检出节省三维模型等无关大文件。检出全部层次 `.kicad_sch`、项目、符号库、库表及许可证/README；KiCad 从根图递归导出。复用缓存时先恢复固定 SHA 并清理改动；中断的未完成 git 仓库会重取。自定义 KiCad 路径可用 `--kicad-cli` / `KICAD_CLI`，离线测试可用 `--catalog` 提供本地仓库目录。`--cache` 应指向专用缓存，重复取板会重建该板的输出并清除其 `src/` 中的本地改动。

每板输出 `<cache>/<id>/{src/,netlist.xml,db.json,fetch.log,verification.json}`。日志保存各阶段命令、输出及 strict 失败原因；strict 失败后重试 `--no-strict`，解析仍失败或少于 15 器件则退出非零、删除 db/成功标记，避免旧结果混入。所有最终条目已通过正式 catalog 全量重放，根图与递归子图存在性已核查；`verification.json` 保存固定来源、原理图格式版本、器件数、strict 状态和 db SHA-256，catalog 另含根图 SHA-256 与 commit 绑定的许可证证据链接。

最终 100 块中 strict 通过 56 块，允许的 `--no-strict` 回退 44 块。回退只允许解析结果保留供后续审查，不表示引脚名称/库完整性已解决；详细原因见各自缓存 `fetch.log`。这些取板结果不是 SR 电气审查、验证或准出结论。

### 类型标签分布

| 类型 | 块数 |
|---|---:|
| `POWER_CONVERTER` | 81 |
| `ANALOG` | 36 |
| `POWER_PROTECTION` | 30 |
| `USB` | 26 |
| `ISOLATION` | 18 |
| `RF` | 17 |
| `ETHERNET` | 16 |
| `AV` | 13 |
| `CLOCK` | 13 |
| `CAN` | 11 |
| `RS485` | 10 |
| `STORAGE` | 10 |
| `HSSERIAL` | 8 |
| `SPI` | 8 |
| `AC_MAINS` | 7 |
| `I2C` | 7 |
| `POE_PD` | 7 |
| `DEBUG` | 5 |
| `LEVEL_SHIFT` | 5 |
| `UART` | 4 |
| `DDR` | 3 |
| `INDUSTRIAL_DI` | 1 |
| `STARTUP` | 1 |

### 许可证分布

| 许可证 | 块数 |
|---|---:|
| MIT | 23 |
| GPL-3.0 | 19 |
| Apache-2.0 | 15 |
| TAPR-OHL-1.0 | 15 |
| CERN-OHL-P-2.0 | 11 |
| CERN-OHL-S-2.0 | 8 |
| CERN-OHL-W-2.0 | 3 |
| CC-BY-SA-4.0 | 2 |
| CERN-OHL-1.1 | 2 |
| BSD-3-Clause | 1 |
| CC-BY-4.0 | 1 |

GPL/LGPL、TAPR、CERN 互惠及 CC-BY-SA 条目均标 `copyleft: true`。OpenRefMic 的 MIT 为仅将 Software 改为硬件 Design 的等价措辞，目录 `license_note` 已明确原文名称。许可证只说明允许的使用范围，后续引用仍须保留来源并遵守各许可证。

### 器件数分布

| 解析器器件数 | 块数 |
|---|---:|
| 15–49 | 33 |
| 50–99 | 20 |
| 100–249 | 26 |
| 250–499 | 13 |
| ≥500 | 8 |

总计 16940 个解析器器件；最小 15，中位数 95，最大 1170。器件数按 `db.json.parts` 计，包含测试点/连接器等；精选时另排除了纯连接器面包板、软件测试夹具和误选的子图。

### 筛除与流水线

完成筛查的仓库中：无 `.kicad_sch` 289；许可证缺失或不在允许集合 194（含非商业限制及 Apache WITH Solderpad 例外）；实际取板中不足 15 器件 34，回退后仍无法解析 8，KiCad 导出失败 2，旧版/无效格式 1。另有技术流水线通过、许可证终核未被排除但未入选的 88 项，主要用于去除用途重复、软件夹具、纯转接或子图选择等；未把它们计入最终 100 块。详细来源与阶段结果见 `discovery.json`。

| 流水线 | 板数 | 器件总数 | 不同标签数 |
|---|---:|---:|---:|
| lane-1 | 25 | 4263 | 22 |
| lane-2 | 25 | 4199 | 21 |
| lane-3 | 25 | 4211 | 22 |
| lane-4 | 25 | 4267 | 20 |

四条流水线组成无重复的完整分区；≥4 块样本的每种标签均分布到四条线，DDR 的 3 块分居三条线。这里仅准备取板和分流，尚未启动逐板 SR 改进回路。
