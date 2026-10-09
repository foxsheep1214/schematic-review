# 器件资料与证据计算

本页覆盖三件事：资料覆盖审计与补取（`audit_datasheets.py`）、证据计算的保证值契约（`evidence.json`，方式 E）、PWR-E01 的 Vref 参数复用（`datasheet_facts.py`）。资料只描述“应当怎样”；当前网表/BOM 证明“实际怎样”。

## 一、资料覆盖审计与补取

scripts/audit_datasheets.py 只做确定性的逐物料覆盖审计，不访问网络。联网检索、
下载、型号核对和来源判断由执行 agent 完成。脚本与 agent 通过
datasheet-audit.json 和 datasheet-resolution.json 闭环。

### 执行顺序

1. 首次审计资料包：

       python3 scripts/audit_datasheets.py db.json \
         --datasheet-dir <资料包目录> \
         --json datasheet-audit.json

2. 执行 agent_requests：

   - VERIFY_LOCAL_DATASHEET：打开候选 PDF，核对完整型号、后缀、封装和版本。
     候选不匹配时立即转 FETCH_DATASHEET_ONLINE。
   - FETCH_DATASHEET_ONLINE：agent 自主联网补取，不先把搜索工作转交用户。
     按 value 精确检索；先查 LCSC/立创商城，再查原厂官网。
   - REQUEST_USER_DATASHEET：前两类动作已闭环且结果为 NOT_FOUND 时，先执行逐参数补证流程，再向用户报告状态与仍需补充的具体资料。
   - 某个渠道拒绝访问或超时时，换下一个渠道，不要停在第一个失败上。仍取不到时，
     按 [evidence-proportionality.md](evidence-proportionality.md) 的“原定资料取不到时”，
     核对同型号其他证据、受控规格、反算要求与相似器件参考等路径；替代资料不改变
     本物料的 AVAILABLE 判定。
   - PDF 文本提取可能错字符（µ 显示成 m 等）；决定结论的数值对照渲染页核对。

3. Agent 把结果写入 datasheet-resolution.json，再次运行审计：

       python3 scripts/audit_datasheets.py db.json \
         --datasheet-dir <资料包目录> \
         --resolution datasheet-resolution.json \
         --json datasheet-audit.json

4. 把审计结果传入计划或 lint：

       python3 scripts/plan_review.py db.json \
         --intent intent.json \
         --datasheet-audit datasheet-audit.json \
         --json review-plan.json

       python3 scripts/lint.py db.json \
         --intent intent.json \
         --datasheet-audit datasheet-audit.json \
         --plan-json review-plan.json \
         --json lint-cold.json

datasheet-audit.json 存在时，它覆盖
intent.materials.datasheets.available 这个全局布尔值，并按位号控制 DEV-D01
准备度。状态不是 AVAILABLE 的物料，依赖其 datasheet 的自动准备度仍为 WAITING_EVIDENCE；
这不直接判定所有人工检查的电气结果。T/C/D 按具体主张核实补充证据，自动 E 仍遵守保证值契约。
计划与 lint 还会核对审计里的物料/位号是否与当前 db.json 一致。

### Audit 状态

| 状态 | 含义 | Agent 动作 |
|---|---|---|
| AVAILABLE | 已验证本地或联网 PDF 与完整物料身份匹配 | 进入资料取证与 DEV-D01 |
| NEEDS_VERIFICATION | 文件名存在候选，但尚未核实 PDF 抬头与变体 | 打开核对；不匹配则联网 |
| MISSING | 资料包无候选且未有 agent 结论 | 联网补取 |
| NOT_FOUND | 已按白名单渠道检索，仍无有效 datasheet | 逐参数补证；仍影响判断的缺口保持 INSUFFICIENT/C |

文件名命中永远只产生 NEEDS_VERIFICATION，不能直接证明 AVAILABLE。

### datasheet-resolution.json

顶层格式：

    {
      "schema_version": 1,
      "entries": []
    }

联网找到：

    {
      "identity": "LM5069MM-2/NOPB",
      "status": "FOUND",
      "identity_verified": true,
      "source_kind": "network",
      "path": "<项目审查目录>/evidence/datasheets/LM5069.pdf",
      "source_url": "https://www.ti.com/lit/ds/symlink/lm5069.pdf",
      "document_model": "LM5069MM-2/NOPB",
      "document_version": "SNVS452G",
      "retrieved_at": "2026-09-02"
    }

资料包已有并核实：

    {
      "identity": "LM5069MM-2/NOPB",
      "status": "FOUND",
      "identity_verified": true,
      "source_kind": "package",
      "path": "datasheets/LM5069.pdf",
      "document_model": "LM5069MM-2/NOPB",
      "document_version": "SNVS452G"
    }

检索后仍找不到：

    {
      "identity": "CUSTOM-ASIC-X1",
      "status": "NOT_FOUND",
      "searched_sources": [
        "LCSC query CUSTOM-ASIC-X1",
        "manufacturer official website query CUSTOM-ASIC-X1"
      ],
      "searched_at": "2026-09-02"
    }

NOT_FOUND 至少记录两个检索来源，第一项必须是 LCSC/立创。单个 URL 失败、
Cache miss、网络受限或一次搜索无结果都不足以写 NOT_FOUND。

### 用户提示与审查结果

审计会按物料生成提示：

> 找不到这颗物料的 datasheet：<完整型号>（位号：<refs>）。可补充同型号原厂资料或受控规格；具体缺失参数及工况见审查证据不足项。

Agent 汇总 datasheet-audit.json.user_messages 的缺失物料/位号及检索结果，并结合逐参数补证
结果报告，不机械索取整本手册。
已充分支持的人工主张给独立结果；仍影响判断的主张记录 review_result=INSUFFICIENT、
evidence_confidence=C，以及具体参数/身份/工况、受影响检查、最小补证方法和关闭条件。
共享缺口合并到同一 work_item，不为多个检查重复索取资料。

按 [逐参数补证与替代](evidence-proportionality.md#原定资料取不到时) 记录其他证据；
同系列、近似后缀资料可辅助分析，但不得冒充原器件 datasheet 或更改身份/保证范围。
审计状态只描述资料覆盖；人工结论不能反向把 NOT_FOUND 改成 AVAILABLE。

### 按参数依赖补齐物料

默认仍审计已装配 U/M/Q/D。需要电感 Isat/DCR、保险丝时间电流曲线、晶体 ESR/CL、
连接器组合电流/引脚、电容偏压/ESR 或电阻额定/公差时，用 --require-ref REF（可重复）
扩展；--evidence evidence.json 也会纳入声明的 depends_on 和目标器件。audit 输出
required_refs 并与当前 db 一起验证，未知位号不允许静默漏审。

VALUE 是型号/系列时仍优先用于生成检索候选；VALUE 明确是带单位的参数或阻值写法、
PART 已给出非通用物料身份时，用 PART 生成候选，并保留 VALUE 为别名证据。
带尺寸的通用符号/封装名（如 CRYSTAL_3225_4_PAD、C_0603）仍是通用身份，不能因此替代参数为精确订货码。
纯数字 VALUE 不按参数处理，真实 VALUE/PART 型号冲突仍按身份分支审查。
BOM 中仅有通用阻容值时先解析实际 MPN，不能把
“10K”当成已核实采购型号。AVAILABLE 表示该候选的文档已核实；用于参数验算前，
evidence.basis.sources 还须记录确切的身份解释和实际文档指纹。文档覆盖系列时按
订货表匹配实际后缀/封装，不要求系列文档标题逐字等于每个订货号。

临时下载可放 /tmp；最终引用的 PDF、审计及补取记录须保存到项目审查目录，并更新文档
路径。文档内容不变时指纹不变；路径不存在会使热跑保持证据不足，不能只交临时目录中的证据。

## 二、证据计算契约（evidence schema_version 2）

`evidence.json` 为证据计算规则（[规则总表](check-catalog.md)中方式为 E 的规则）提供带出处的保证值。
`schema_version` 必须为 2。缺少依赖、保证范围或状态时不执行计算，输出逐项 INSUFFICIENT（例外见 [自动证据计算的例外](evidence-proportionality.md#自动证据计算的例外)）。
不自动填 1% 电阻公差、零 Vref 误差、零偏置电流或稳态采样。数值必须有限，min≤max；
每项 id 唯一、citation 可定位。证据计算结果不是整板准出。

缺原厂 datasheet 时，[逐参数补证与替代](evidence-proportionality.md#原定资料取不到时)
用于人工 T/C/D 取证与条件计算，不扩展本自动契约。相似型号参数、反算要求或样本实测值
不能冒充本器件保证值；其他文档不满足既有 AVAILABLE/来源绑定要求时，不强行填入 E。
人工结论引用实际证据并说明覆盖差异，自动 E 缺口如实保留。

### 共有字段与依赖

每条 checks 项包含 id、rule、kind、citation、目标 node/net/ref、depends_on 和 basis。
多个目标坐标必须一致；同网不同引脚不共享门限。depends_on 要列全参数来源，包括
非目标 IC、输入负载、外部驱动及用于保证曲线/额定值的关键无源器件。
脚本至少强制检查目标器件及目标网上的 U/M/Q/D；跨网的额外依赖由 agent 明确声明。
PWR-E01 的节点分析路径对可完整提取的网络，自动将全部电阻与被忽略输入/C 纳入计划
和计算的来源依赖；遗漏、过期或未 AVAILABLE 均保持 WAITING_EVIDENCE/INSUFFICIENT。

basis 包含：

- db_sha256：当前 db 的 parts/nets/pin2net/pinname/pintype 指纹。
- state：准确的装配版本、供电状态、温度/负载角点及采样情景；同一对象不同状态使用不同检查 id。
- sources：每个依赖位号恰有一个来源绑定；ref、identity、document_model、document_version 与 audit 的 AVAILABLE 物料一致；sha256 绑定实际文档；locator 给章节/页码/表号。
- 每个 source 的 identity_resolution：说明实际订货码、封装/档位、VALUE/PART/PRIM 别名或冲突如何被原始资料解决。文档涵盖多个后缀时要定位订货表对应行，不能只比文档标题。

指纹工具不生成结论，也不证明身份解释、计算或引文真实；agent 必须读原件核实。

```sh
python3 scripts/electrical_contract.py db.json --document /tmp/codex-work/task/datasheets/part.pdf
```

热跑命令见 [SKILL.md](../SKILL.md)；额外关键物料通过
`audit_datasheets.py --require-ref L1 --require-ref F1` 加入依赖，相关来源仍须写回 evidence。

audit 按需覆盖依赖位号。NOT_FOUND 必须先记录 LCSC/立创与原厂检索；MISSING/
NEEDS_VERIFICATION/NOT_FOUND 均不能让依赖检查变 READY。无关物料缺资料不阻断
已具备全部依赖的检查；总准出仍需处理所有适用阻断项。

### PWR-E01：已建模的反馈设定窗口

本规则的两个例外（边界已证明违反时同判 FAIL；无验收窗口的名义输出判 NA）见
[自动证据计算的例外](evidence-proportionality.md#自动证据计算的例外)。

可手工提供下面的 vref；重复读取同一已核实资料时，使用下文“Vref 参数复用”。vref_request 声明本次目标/完整工况，
目标 source 补精确 mpn/package。物化工具生成 vref 和 vref_binding；未物化不计算。
计划与 lint 共享事实/PDF/工况的实时失效门，不能删除绑定保留旧数值来绕过复验。

```json
{
  "schema_version": 2,
  "checks": [{
    "id": "U1-FB-STATIC",
    "rule": "PWR-E01", "kind": "divider", "node": "U1.1", "net": "FB",
    "citation": "REG-X Rev.A section 7.5 and BOM Rev.B R1/R2",
    "depends_on": ["U1"],
    "vref": {"min": 0.792, "typ": 0.8, "max": 0.808},
    "expected": {"min": 2.30, "max": 2.50},
    "divider_model": {
      "source_net": "VOUT", "reference_net": "GND",
      "bias_current_a": {"min": -0.0000001, "max": 0.0000001},
      "ignored_nodes": {"U1.1": "FB input loading included in bias_current_a; REG-X section 7.5"}
    },
    "basis": {
      "db_sha256": "replace-with-current-db-fingerprint",
      "state": "BOM Rev.B; feedback regulating; specified Vin/load/temperature range",
      "sources": [{
        "ref": "U1", "identity": "REG-X",
        "document_model": "REG-X", "document_version": "Rev.A",
        "sha256": "replace-with-verified-document-fingerprint",
        "locator": "section 7.5",
        "identity_resolution": "Verify actual ordering code/package against BOM Rev.B and ordering table"
      }]
    }
  }]
}
```

示例数值为合成输入，指纹和身份文字必须替换为实际证据；不能原样用于设计。
电阻公差从各 VALUE 提取。resistor_tolerance 是有 BOM/采购规格支持时才可显式设置的
统一回退值；不覆盖已写明的单颗公差。共享支路/桥式正电阻网络可在完整模型与来源绑定
下走线性节点分析，规模、角点与数值边界见 [wca-formulas.md](wca-formulas.md)。
未知支路、多参考域、0Ω、未解析电阻或超限继续 INSUFFICIENT。ignored_nodes 只允许
已说明输入负载的 U/M 和 DC 下已证明可忽略的 C 节点，新节点路径的 U/M 必须位于 FB 网，
不支持用该字段绕过中间输入电流或 Q/D。给定 reference_net 为计算的零点，
它与实际负载地的偏差另建检查；不把 PGND/AGND 等名称视作同一网。

### SIG-E01：无源连接与等效阻值

kind 为 required_pull（direction=up/down）或 required_series；给精确目标 net/node，
用 to 明确另一端。resistance_ohm 可给 min/max。直接连接在同两网间的所有已装配
电阻按并联及单颗公差计算；不再接受“其中一颗符合即可”。其他电阻支路/多源/
未解析公差需节点分析，返回 INSUFFICIENT。

没有 resistance_ohm 时，PASS 仅证明连接存在。该规则不计算 I2C 灌电流、上升时间、
端点电平或掉电能力，这些由 I2C 功能包的 SIG-C01、SIG-C07、SIG-C08、SIG-D01
分别检查；完整电气段不能漏掉经串阻/电平转换器连接的外部上拉。required_series 的结果
也仅指指定两网间直接电阻网络，不证明它是唯一信号通路或符合布局要求。

### RST-E01 / RST-E02：引脚电压及采样保证

分别用 kind=pin_bias、required_default=high/low/float，或 kind=strap、required=high/low/float。
高电平提供 vih_min_v，低电平提供 vil_max_v；RST-E01 的非 float 项还须给 abs_min_v 和 abs_max_v，
核对正负电压额定。非 float 检查还要 voltage_analysis：

```json
{
  "voltage_v": {"min": 0.30, "max": 0.33},
  "sample_window_s": {"min": 0.001, "max": 0.0011},
  "method": "single-pole RC corner calculation",
  "calculation": "V(t)=Vf+(V0-Vf)*exp(-t/(Rth*C)); list actual corners and artifact location",
  "loading": "List all external branches, internal pulls and leakage guarantees",
  "conditions": "List supply/ramp, temperature, population, initial capacitor voltage and sampling setup/hold"
}
```

此窗口由 agent 用完整电路模型计算/仿真并留档，脚本不求瞬态，只与保证门限比较。
禁止只填稳态分压、典型翻转点或某样品实测值。窗口不满足门限输出 FAIL，措辞是
“保证条件不满足”，不是“每颗必死”。scope 限定本状态和给定额定；其他时段的峰值、
钳位/注入电流、Ioff、时序条件仍要单独核对。

float 必须给精确 node；仅核对没有已装配的外部连接，不推断芯片内部拉阻或电压。
没有外部上拉不能直接证明默认电平错误，可能存在合适的内部拉阻/驱动。

### DEV-E01：引脚映射

kind=pin_map、ref 和 expected（引脚号到名称或允许名称数组的映射）。同样需要 basis
及资料审计；连接器可通过 --require-ref 加入。PASS 仅覆盖 expected 列出的引脚，
封装方向、全部引脚覆盖（DEV-D02）与对端定义（DEV-D03）需独立复核。

### DEV-E02：推荐工作条件

kind=operating_range、`ref`、所接轨 `net` 与 `supply_v`（资料保证的推荐工作电压 min/max，
缺任一边界即 INSUFFICIENT）。设计工况来自 `intent.power_rails.<net>.voltage_v`，两边都齐才
比较；PASS 只覆盖该轨的直流电压窗口，温度、负载、频率、瞬态与其他推荐条件仍归 DEV-C05。
绝对最大额定不得当作工作范围填进 `supply_v`。

### 检查器的证据计算规则

检查器的证据计算规则与上列规则同一契约：同样要 id/rule/kind/citation、目标坐标、
depends_on 与 basis，同样按资料审计绑定文档。差别只在各自的保证值字段——**缺任一项即
INSUFFICIENT，不得用典型值、经验值或"常见做法"顶替**；比值/系数类门槛（体电容比、CTR
寿命衰减）必须来自项目规定。各规则字段：

| 规则 | kind | 保证值字段 |
|---|---|---|
| DRV-E01 | `gate_drive` | `channel`（n/p）、`vgs_drive_v{min,max}`、`vgs_rds_on_v`、`vgs_abs_v{min,max}`；P 沟道按量纲翻转后比较 |
| PWR-E03 | `input_filter_damping` | `vin_min_v`、`pin_max_w`、`esr_bulk_ohm`、`c_bulk_f`、`c_in_f`、`l_filter_h`、`c_bulk_ratio_min`（项目规定） |
| PWR-E02 | `dropout` | `vin_min_v`、`dropout_max_v`（声明温度/负载范围的保证最大值）、`vout_required_min_v` |
| RST-E03 | `reset_pulse` | `pulse_width_s{min,max}`、`required_width_s{min,max}`、`output_type`（open_drain/push_pull） |
| SIG-E02 | `diff_level` | `coupling`（ac/dc）、`driver_swing_v`、`receiver_common_mode_v`、`receiver_input_diff_v`，直流耦合另需 `driver_common_mode_v`、交流耦合另需 `bias_common_mode_v` |
| PRO-E01 | `opto_ctr` | `drive_v`、`vf_v`、`driver_drop_v`、`r_led_ohm`、`r_pullup_ohm`、`v_pullup_v`、`vol_required_v`、`ctr_min`、`ctr_derating`（项目规定，(0,1]）、`if_abs_max_a` |

结果同样写入 check_results：PASS 带 scope 明示未判定的部分（开关速度、全频阻抗、瞬态、
抖动、隔离耐压等），FAIL/INSUFFICIENT 带 calculation 保留角点。逐检查器的识别范围与边界见
[automation.md](automation.md)。

### 输出

lint.json 的 check_results 每条保留 check_id、review_result、detail/citation；PASS
含 scope/state，计算项保留 calculation。readiness 与 review_result 独立，READY
只表示具备所需证据，求解仍可能因拓扑不支持而 INSUFFICIENT。规则级 hot_pending
是摘要，不能替代逐项结果（同规则可同时存在已执行和未就绪的检查）。

## 三、Vref 参数复用（事实库 schema_version 1）

仅用于 PWR-E01。资料事实存入项目审查目录的 `datasheets/facts.json`，原始 PDF 一并留档；
事实记录不含位号、电阻网络、审查结论或整板 PASS。每次使用绑定当前对象/状态并重算。
脚本不下载、不自动提取 PDF，也不按 LLM 置信度或完整性评分决定参数正确性。

### 1. 核对原件并记录事实

完整核对电气表头、保证值、适用温度定义、供电/负载、模式、脚注和订货表。
`VERIFIED` 只是已完成原件核对的记录，不是脚本证明了语义真实。缺项保存为
`UNVERIFIED`，未知数值用缺字段或 `null`；不填零、不以 typ 代替 min/max。

下面是**合成格式示例，不是真实器件规格**；哈希必须由实际 PDF 计算后替换。

```json
{
  "schema_version": 1,
  "facts": [{
    "id": "REG-X-QFN16-VREF-FULL-RANGE",
    "parameter": "vref",
    "mpn": "REG-X-QFN16-I",
    "package": "QFN-16",
    "unit": "V",
    "values": {"min": 0.792, "typ": 0.8, "max": 0.808},
    "guaranteed": true,
    "conditions": {
      "temperature_c": {"min": -40, "max": 85},
      "temperature_basis": "junction",
      "vin_v": {"min": 3, "max": 5.5},
      "load_a": {"min": 0, "max": 1},
      "mode": "regulating",
      "qualifiers": {}
    },
    "raw_conditions": "Synthetic table: TJ=-40..85 C, VIN=3..5.5 V, IOUT=0..1 A, regulating. No other restrictions.",
    "source": {
      "path": "REG-X.pdf",
      "sha256": "replace-with-actual-64-character-lowercase-sha256",
      "document_model": "REG-X family",
      "document_version": "Rev.A",
      "locator": "PDF p.7, Electrical Characteristics, VFB row; ordering table p.18",
      "footnotes": []
    },
    "verification": {
      "status": "VERIFIED",
      "conditions_complete": true,
      "note": "Synthetic example only; replace with actual table/header/footnote and ordering-code verification record."
    }
  }]
}
```

- `source.path` 相对于 **facts.json 所在目录**，也可为绝对路径；复制 PDF 但内容相同可复用。
- ID 在文件内唯一；每条记录只描述一个完整订货型号、封装、文档版本和适用行。
  不按去后缀、大小写归一化或“同系列”匹配。系列 PDF 标题不必等于 MPN。
- 数值只接受有限正数，单位必须 `V`。`guaranteed=true` 必须有原文保证依据；
  曲线估读、典型统计、样品值不能标成保证值。
- 三个范围都是闭区间，且请求的**整个范围**必须被同一条记录覆盖；不拼接多行范围。
  `temperature_basis` 明确结温/环境温度；脚本不作热转换。
- `mode`、`qualifiers` 精确相等。频率、档位、测试连接等额外限制用双方一致的 qualifier
  键值记录；没有时显式 `{}`。这只是精确条件匹配，不解析自由文本或做单位换算。
- `raw_conditions` 保留原始条件；`footnotes` 保留适用脚注（无则 `[]`），并将其限制
  编码进 conditions。无法完整表达时令 `conditions_complete=false`，改走人工核验。
  不能只填 true 来绕过尚未理解的脚注。完全缺少工况的提取草稿先留在阅读笔记中。
- 同时有多条适用、已核实的保证时，输出歧义及 ID，不按列表顺序、置信度、最新日期或
  更窄范围静默择一。回原件明确行的适用性，保留更正记录后再用。

### 2. 为本次检查声明身份与请求工况

仍按上文证据计算契约建 `basis` 和全部依赖。
在目标 `basis.sources` 项添加 `mpn`、`package`：它们是按当前 BOM/订货表核实的精确
身份，**不是**工具自动识别的结果。原 `identity_resolution` 必须解释 VALUE/PART/PRIM/
JEDEC 与真实订货码/封装的对应及冲突解决；仅把事实里的型号复制过来不算身份核对。
脚本还比较 audit 中该位号的 BOM 字段快照，字段改变后要重新审计，不能只刷新 db 哈希。

本版自动复用要求 `mpn` 精确等于 audit 所选的当前 BOM `value` 或 `part`，不接受仅从
PRIM 得到型号；`package` 精确等于当前 `jedec`。事实中的 package 使用同一封装标识，
与原厂封装名称的对应仍须原件核实。BOM 字段为别名、缺封装或冲突尚待解决时，
继续走原有手工证据流程，不为通过匹配而修改原始 BOM/网表或猜测别名映射。

PWR-E01 检查加以下请求，可暂不填写 `vref`：

```json
"vref_request": {
  "ref": "U1",
  "conditions": {
    "temperature_c": {"min": -40, "max": 85},
    "temperature_basis": "junction",
    "vin_v": {"min": 3.3, "max": 5},
    "load_a": {"min": 0.1, "max": 0.8},
    "mode": "regulating",
    "qualifiers": {}
  }
}
```

请求必须来自本次真实工况，与 `basis.state`、需求和实际配置相符，不从状态文字猜测。
目标必须是本检查反馈器件；多对象/多工况各自建检查 ID，多个 ID 可以复用同一 fact。

### 3. 生成证据，再用原热跑流程

以下命令的脚本路径按技能安装位置调整，输入/输出路径指向项目审查目录。
输出和报告必须使用**尚不存在的新文件名**，不要将项目证据写进技能仓库。
首次使用请求文件时，先让 `audit_datasheets.py --evidence evidence-request.json`
纳入该文件的依赖并更新 audit，再执行物化；其余资料补取和身份核对顺序不变。

```sh
python3 scripts/datasheet_facts.py materialize db.json \
  --facts datasheets/facts.json --evidence evidence-request.json \
  --datasheet-audit datasheet-audit.json \
  --out evidence.json --report vref-materialization.json
```

成功项填入现有 `vref.min/typ/max`，保留原来的来源/偏置电流依据，补充
`basis.sources[].parameter_locators.vref` 和 `vref_binding`（事实文件绝对路径、ID、
单条记录哈希、对象/工况/来源上下文哈希）。未解决项清除旧 vref 和绑定，保留请求及缺口；
退出 2，并在报告 `affected_check_ids` 中列出需要处理的检查，不回退到旧缓存数值。
退出 0 仅表示请求的 Vref 已物化，不保证偏置/公差/模型就绪，更不是电气 PASS。

再按 SKILL.md 对生成的 evidence.json 执行原有 lint/计划合并与独立结果校验。
计划和热跑每次都重读事实、复核 PDF 内容和唯一适用性；值被手改、记录变化、新增冲突
记录、对象/状态/条件/来源变化、PDF 缺失或变更均使使用者回到证据不足。原来的依赖、
公差、模型及准出门保留；未使用事实字段的手工 evidence 不受影响。
资料审计、物化、检查、计划和热跑共用严格 JSON 读取器，重复键不会被“最后一个值”
静默覆盖；该类歧义输入退出 2，不生成新结果。物化与下游也共用物理脚/网络一致性检查。

### 4. 查看失效影响

```sh
python3 scripts/datasheet_facts.py check db.json \
  --evidence evidence.json --datasheet-audit datasheet-audit.json \
  --report vref-impact.json
```

只读输入，列出**这份 evidence 中**所有事实使用者及失效原因；不会扫描其他项目，
不会修改历史结果或自动准出。PDF/事实/工况变更后先核对原件、更新事实及 audit/basis，
再生成新版本 evidence，重新热跑并复核受影响的最终结果；不能只刷新哈希解除阻断。
项目搬迁后重新物化以更新绝对路径。事实和原件持久保存在项目，不放进全局技能缓存。
