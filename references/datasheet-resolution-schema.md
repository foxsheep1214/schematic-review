# Datasheet 覆盖审计与 Agent 补取闭环

scripts/audit_datasheets.py 只做确定性的逐物料覆盖审计，不访问网络。联网检索、
下载、型号核对和来源判断由执行 agent 完成。脚本与 agent 通过
datasheet-audit.json 和 datasheet-resolution.json 闭环。

## 执行顺序

1. 首次审计资料包：

       python3 scripts/audit_datasheets.py db.json \
         --datasheet-dir <资料包目录> \
         --json datasheet-audit.json

2. 执行 agent_requests：

   - VERIFY_LOCAL_DATASHEET：打开候选 PDF，核对完整型号、后缀、封装和版本。
     候选不匹配时立即转 FETCH_DATASHEET_ONLINE。
   - FETCH_DATASHEET_ONLINE：agent 自主联网补取，不先把搜索工作转交用户。
     按 value 精确检索；先查 LCSC/立创商城，再查原厂官网。
   - REQUEST_USER_DATASHEET：保留此动作名以兼容现有审计格式。前两类动作已闭环且结果
     为 NOT_FOUND 时，先执行逐参数补证流程，再向用户报告状态与仍需补充的具体资料。
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
计划与 lint 还会核对审计里的物料/位号是否与当前 db.json 一致，避免误用旧版本审计结果。

## Audit 状态

| 状态 | 含义 | Agent 动作 |
|---|---|---|
| AVAILABLE | 已验证本地或联网 PDF 与完整物料身份匹配 | 进入资料取证与 DEV-D01 |
| NEEDS_VERIFICATION | 文件名存在候选，但尚未核实 PDF 抬头与变体 | 打开核对；不匹配则联网 |
| MISSING | 资料包无候选且未有 agent 结论 | 联网补取 |
| NOT_FOUND | 已按白名单渠道检索，仍无有效 datasheet | 逐参数补证；仍影响判断的缺口保持 INSUFFICIENT/C |

文件名命中永远只产生 NEEDS_VERIFICATION，不能直接证明 AVAILABLE。

## datasheet-resolution.json

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

## 用户提示与审查结果

审计会按物料生成提示：

> 找不到这颗物料的 datasheet：<完整型号>（位号：<refs>）。可补充同型号原厂资料或受控规格；具体缺失参数及工况见审查待核项。

Agent 汇总 datasheet-audit.json.user_messages 的缺失物料/位号及检索结果，并结合逐参数补证
结果报告，不再机械索取整本手册。历史审计中的旧提示也按此流程解释，无须篡改历史记录。
已充分支持的人工主张给独立结果；仍影响判断的主张记录 review_result=INSUFFICIENT、
evidence_confidence=C，以及具体参数/身份/工况、受影响检查、最小补证方法和关闭条件。
共享缺口合并到同一 work_item，不为多个检查重复索取资料。

按 [逐参数补证与替代](evidence-proportionality.md#原定资料取不到时) 记录其他证据；
同系列、近似后缀资料可辅助分析，但不得冒充原器件 datasheet 或更改身份/保证范围。
审计状态只描述资料覆盖；人工结论不能反向把 NOT_FOUND 改成 AVAILABLE。

## 按参数依赖补齐物料

默认仍审计已装配 U/M/Q/D。需要电感 Isat/DCR、保险丝时间电流曲线、晶体 ESR/CL、
连接器组合电流/引脚、电容偏压/ESR 或电阻额定/公差时，用 --require-ref REF（可重复）
扩展；--evidence evidence.json 也会纳入声明的 depends_on 和目标器件。audit 输出
required_refs 并与当前 db 一起验证，未知位号不允许静默漏审。

VALUE 优先仅用于生成检索候选；BOM 中仅有通用阻容值时先解析实际 MPN，不能把
“10K”当成已核实采购型号。AVAILABLE 表示该候选的文档已核实；用于参数验算前，
evidence.basis.sources 还须记录确切的身份解释和实际文档指纹。文档覆盖系列时按
订货表匹配实际后缀/封装，不要求系列文档标题逐字等于每个订货号。

临时下载可放 /tmp；最终引用的 PDF、审计及补取记录须保存到项目审查目录，并更新文档
路径。文档内容不变时指纹不变；路径不存在会使热跑保持待核，不能只交临时目录中的证据。
