# 器件资料与保证值核对

本页覆盖两件事：资料覆盖审计与补取（`audit_datasheets.py`）、保证值核对（方式 E）的判据要点。资料只描述“应当怎样”；当前网表/BOM 证明“实际怎样”。

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
   - PDF 文本提取可能错字符（µ 显示成 m 等）；决定结论的数值对照渲染页核对。审计给每份资料记 `unit_glyphs`
     （文本层 kΩ 印成 kW 且全文没有 µ 的记 SYMBOL_FALLBACK，诊断 `DATASHEET_UNIT_GLYPHS`），④ 对引它的 ms、mA、mH、W 条款出 `UNIT_GLYPH_SUSPECT`。
   - 原厂 PDF 取不到、只能用网页或工具抽取的文本时，`path` 指向该文本文件，审计记
     `document.document_format = text_extract`，摘要计入 `available_text_only`，并给出 `DATASHEET_TEXT_ONLY` 诊断。
     表格列可能被拍平：只有归属及适用条件可有据定界时才取保守值；否则保留具体参数缺口。
     文件格式标记不证明原厂身份或内容有效，不能把文本改名为 PDF 来冒充原件；图形、曲线、极性/封装视图
     的结论仍需可定位的原始图形证据，文本 AVAILABLE 不支持这些结论。

3. Agent 把结果写入 datasheet-resolution.json，再次运行审计（带 `--intent` 才核验 `intent.device_kinds`）：

       python3 scripts/audit_datasheets.py db.json \
         --datasheet-dir <资料包目录> \
         --resolution datasheet-resolution.json \
         --intent intent.json \
         --json datasheet-audit.json

4. 把审计结果传入合并扫描，命令见 SKILL.md 2.2（命令 ⑦）。

没有 datasheet-audit.json 时，资料是否可用按 `intent.materials.datasheets.path` 是否存在推（intent 不写 `available`，写了被拒）；
有审计文件时按位号控制 DEV-D01 准备度。状态不是 AVAILABLE 的物料，依赖其 datasheet 的自动准备度仍为 WAITING_EVIDENCE；
这不直接判定所有审查者检查的电气结果。T/C/D 按具体主张核实补充证据，E 检查项仍只认本器件保证值。
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
已充分支持的审查者主张给独立结果；仍影响判断的主张记录 review_result=INSUFFICIENT、
具体缺口（gaps：参数/身份/工况）、受影响检查、最小补证方法和关闭条件。
共享缺口合并到同一 work_item，不为多个检查重复索取资料。

### 公开曲线表先于索取

记 VENDOR_DATUM 之前先在公开资料里找界，顺序见 [判“证据不足”之前先定界](evidence-proportionality.md#判证据不足之前先定界)：
手册电气表里不利方向上相邻的测试点、手册后部的典型曲线（转移特性、栅电荷、VF–IF–温度、CTR–IF）、厂家网站或样本的
特性表（NTC 的逐度 R-T 表、电解电容的 ESR/纹波频率系数表、保险丝 I²t 曲线）、厂家应用笔记里的损耗与降额公式。
这些是下载和阅读，不是索取；找到的界写进功能判定的 `conditions` 和 `worst_case.bound`，翻过而没有的写进 `curves_checked`。
`acquisition` 写“向 X 取得本机工况下的保证”而公开表已能夹出界限的，是检索未完成（REVIEW_INCOMPLETE），不是缺资料。

按 [逐参数补证与替代](evidence-proportionality.md#原定资料取不到时) 记录其他证据；
同系列、近似后缀资料可辅助分析，但不得冒充原器件 datasheet 或更改身份/保证范围。
审计状态只描述资料覆盖；审查者结论不能反向把 NOT_FOUND 改成 AVAILABLE。

### 按参数依赖补齐物料

默认仍审计已装配 U/M/Q/D。需要电感 Isat/DCR、保险丝时间电流曲线、晶体 ESR/CL、
连接器组合电流/引脚、电容偏压/ESR 或电阻额定/公差时，用 --require-ref REF（可重复）
扩展。audit 输出
required_refs 并与当前 db 一起验证，未知位号不允许静默漏审。

VALUE 是型号/系列时仍优先用于生成检索候选；VALUE 明确是带单位的参数或阻值写法、
PART 已给出非通用物料身份时，用 PART 生成候选，并保留 VALUE 为别名证据。
参数别名仅在可解析为本器件量纲的真实数值时等量归组；保留小数、符号、指数及 SI 前缀大小写的数值意义，
不以去标点键把不同容量或订货码合并。准确 MPN 优先于通用参数；数字型型号不能按参数猜测，
通用/TBD/UNKNOWN 身份保持未解析。稳定物料 ID 须区分不同身份/参数，不能因可读名称相同而碰撞。
带尺寸的通用符号/封装名（如 CRYSTAL_3225_4_PAD、C_0603）仍是通用身份，不能因此替代参数为精确订货码。
纯数字 VALUE 不按参数处理，真实 VALUE/PART 型号冲突仍按身份分支审查。
BOM 中仅有通用阻容值时先解析实际 MPN，不能把
“10K”当成已核实采购型号。AVAILABLE 表示该候选的文档已核实；用于参数验算前，
还须记录确切的身份解释和实际文档指纹。文档覆盖系列时按
订货表匹配实际后缀/封装，不要求系列文档标题逐字等于每个订货号。

临时下载可放 /tmp；最终引用的 PDF、审计及补取记录须保存到项目审查目录，并更新文档
路径。文档内容不变时指纹不变；路径不存在时资料视为缺失，不能只交临时目录中的证据。

## 二、保证值核对（方式 E）

方式为 E 的规则（[规则总表](check-catalog.md)）由网表定出对象，计划行为 WAITING_EVIDENCE，审查者按两端器件规格书的
保证 Min/Max 核数值窗口，经功能判定写结论。缺保证值、资料未 AVAILABLE 或身份未解决时判资料不足（例外见
[保证值核对的例外](evidence-proportionality.md#保证值核对的例外)）；不填 1% 电阻公差、零 Vref 误差、零偏置电流，
不用典型值、经验值、相似型号参数、反算要求或样本实测值冒充本器件保证值；比值/系数类门槛（体电容比）
必须来自项目规定；光耦寿命末所需的 CTR 保留比例由寿命检查项 DEV-C06 算出并写成选型约束，SR 不自编衰减系数。每个数值写出处（文档、版本、页码/表号），文档覆盖多个后缀时定位订货表对应行。
最坏角点按 [wca-formulas.md](wca-formulas.md) 计算，`scripts/calc.py` 可做数值复算。

各规则的判据要点：

- **PWR-E01 反馈设定窗口**：Vref Min/Max、各电阻单颗公差（从 VALUE 读）与 FB 偏置电流共同定出输出窗口；
  共享支路按节点分析，未知支路、多参考地、0 Ω 或未解析电阻不出结论。参考网是计算零点，与负载地的偏差另行核对，
  不把 PGND/AGND 视作同一网。
- **SIG-E01 无源连接与等效阻值**：同两网间所有已装配电阻按并联及单颗公差计算；只核连接与阻值，
  I²C 灌电流、上升时间、端点电平和掉电能力归 SIG-C01、SIG-C07、SIG-C08、SIG-D01。
- **RST-E01 / RST-E02 引脚电压与采样**：用完整电路模型求采样窗口内的引脚电压（列出外部支路、内部上下拉与漏电、
  供电斜坡、温度、装配和电容初值），再与 VIH min / VIL max 比较；RST-E01 还核正负绝对额定。禁止只用稳态分压、
  典型翻转点或样品实测。float 只核没有已装配的外部连接，没有外部上拉不直接证明默认电平错误。
- **DEV-E01 引脚映射**：逐脚核符号脚号与手册脚名；只覆盖列出的引脚，全部引脚覆盖（DEV-D02）与对端定义（DEV-D03）另核。
- **检查器定出对象的 E 规则**（DRV-E01、PWR-E02、PWR-E03、RST-E03、SIG-E02、PRO-E01）：判据写在
  [自动检查](automation.md#二检查器) 对应检查器一节。

PASS 写明未判定的部分（开关速度、全频阻抗、瞬态、抖动、隔离耐压等）；FAIL 写“保证条件不满足”，保留角点计算。
