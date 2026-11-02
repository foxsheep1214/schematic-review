# teapotlaboratories--feather-rak3172 · lane-3

源 `3d07959fe17d5e80ef144d2306df94c57608312a`；MIT；KiCad10.0.7 strict成功，51器件。用途**推断**：RAK3172 Feather LoRa节点、USB-C/CH340E、单节LiPo充电、XC6220 3.3V与可选电池采样；评估基线industrial_telecom，不代表工业级认证。补STARTUP/DEBUG/ANALOG。

| 项目 | 数量 |
|---|---:|
| 最终计划 / 已逐项判 | 387 / 387 |
| PASS / NA / FAIL / 未定 | 122 / 45 / 5 / 215 |
| 归因发现（独立根因） | 44 |
| true_defect / false_alarm | 3 / 19 |
| criterion_issue / knowledge_gap / needs_human | 0 / 8 / 14 |
| Top50核对 / Top50证实漏报 | 50 / 0 |
| 额外覆盖漏项（G04-055，非板缺陷） | 1 |
| 原生门禁 / release / render | FAIL / NO_GO / 成功 |

1. **已确认**：U3.VDD USB热插拔输入未实现原厂p18要求的过压处置；电池常供U2且VBUS不到检测脚，未实现Sink断开前提；D1准确Everlight料号IF绝限10mA，图/BOM误写25mA（现有1k串阻未证实过流）。5条FAIL合并3根因，不能声称实物已坏。
2. **应先合并修复**：17条NET-A01把DNP排针的可后装铜孔过滤成“单节点”，忽略可闲置GPIO；另把H1零脚机械孔/USB探针当调试协议对象。保留铜孔边界、按有源端点判接口，再回归本板及现有种子；具体改点在findings.json。
3. **漏报边界**：G04-054已有ANA-C03.U1-3，不能重复报漏。另缺ANA-C02/G04-055高阻源采样建立：4.7M∥10M=3.197MΩ，100nF使τ≈0.320s、理想1%约1.472s；补1计划项，需采样要求/原厂ADC模型才判板缺陷。保护/电容规则均已有项，缺资料不是漏报。

**用法坑**：intent绑定用board_intent.input_fingerprint，结果db_digest用validate_review.fingerprint；补角色重生候选后才确认漏项，STARTUP正是补RAK手册后自动出现。原生schema15不支持needs_human/knowledge_gap：549条原始错误中521条属该承载问题，其余条款/清单/表示门槛仍未满足，**不冒充valid或完整包**。derive387项与独立账一致；报告为原生full副本并保留无效警告。审查账/输入锁在`/Users/skyfend/.cache/sr-boards/teapotlaboratories--feather-rak3172/review`，复制报告的record链接在缓存读取。没有改SR共享代码、提交、push或写Wiki。
