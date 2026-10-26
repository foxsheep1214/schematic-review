# 变异门：注入具名缺陷，单元测试必须杀死

[run.py](run.py) 把仓库复制到临时目录（不带 `.git`/`.claude`/`runs`），按 [mutations.json](mutations.json)
逐条把一段实现改坏，跑单元测试，记录 KILLED（有测试失败）/ SURVIVED（全部通过）。源仓库不改。

```sh
python3 evals/mutation/run.py                 # 全部变异 × 单元层与约定测试，结果写 RESULTS.md
python3 evals/mutation/run.py --only M4       # 只跑某几条
python3 evals/mutation/run.py --tier unit     # 只跑单元层（门槛）
python3 evals/mutation/run.py --changed      # 只跑落在未提交改动文件上的变异（日常；--changed main 比到 main），不改写 RESULTS.md
```

- **单元层**：`pytest scripts/tests -x`，去掉典型电路、种子基准与 KiCad 回放三块板级基准。
- **约定测试**：同上加 `-m contract`（规则约定、校验器不变量、解析器），只报告，不设门槛。
- **门槛**：每条变异都必须被单元层杀死；有存活或模式没唯一命中时退出 1。
- **基线**：先跑一份未变异的副本，单元层不通过就退出 1 并打印首个失败——副本里缺文件（例如台账点名的训练轮产物）会让每条变异都“被杀死”，那不是守住了判据。
  副本只去掉 `.git`/缓存、顶层 `runs/` 和训练轮里的网表扫描/基准产物（`reviews/`、`seeded/`、`replay/`、`critic/`、`*.log`）。

## 变异清单

M1–M8 来自 2026-10-19 的审计：板级基准（42 块典型板、种子基准、KiCad 回放）只杀死其中 2 条，
单元测试杀死 7 条，存活的是 M4（DEV-E02 只核上限、不核下限）。补了
`test_electrical_safety.py::test_operating_range_fails_when_the_rail_minimum_is_below_the_recommended_minimum`
和 DEV-E02 约定后 M4 被杀死。M9–M12 删掉建约定前从未被测试点名的四条 A 规则（NET-A03、PWR-A04、RST-A01、
REQ-A01）的报出，只有规则约定能杀死它们。
M13–M18（2026-10-20）守功能判定机制：F2（设计值不向厂家要）、F4（正余量必须下结论）、框架检查行绑定、
`derive_rows.py` 按开放项派生、问题禁止句检查、计划生成功能框架，各由 `test_review_functions.py`、
`test_derive_rows.py`、`test_catalog.py`、`test_plan_review.py` 的一条测试杀死。
M19（2026-10-20）把与工作态无关的电路检查项（`catalog.STATE_INVARIANT`）重新按状态展开，由
`test_plan_review.py` 的检查行计数测试杀死（首个失败是 `ReviewPlanTests::test_level_shift_name_hit_is_candidate_until_circuit_is_declared`，
`FunctionFrameTests::test_state_invariant_rules_get_one_row_per_circuit` 同样失败）。
M23–M24（2026-10-20，训练第 1 轮裁决）守两条放宽：IC 双向脚的单节点网降 CANDIDATE（`test_board_scans.py::SingleNodeNetTest`）、
驱动脚经最多 3 级电阻可达的栅极降 CANDIDATE（`test_power_switch.py::ChainedDriverTest`）。
M25–M26（2026-10-20，热审试点）守台账两条放宽：同对象框架的行只能绑到覆盖该行对象的功能（`test_review_functions.py::SharedObjectFrameTests`）、
`review_scope` 只免范围外的行（`ScopedReviewTests`）。
M27–M32（2026-10-20）守开放项的四条收紧：VENDOR_DATUM 的 `worst_case` 必须给公开资料界限（M27）、公开资料界限下的正余量就是结论（M28）、
亏欠保留开放要点名取松的条款（M29）、DELIVERABLE_PENDING 要写交付物/责任方/假定（M30）、亏欠的失败项要带改法（M31）、
称“无法定界”要列查过的曲线表（M32），都由 `test_review_functions.py::PublicBoundTests` / `DeliverablePendingTests` 杀死。
M33–M43（2026-10-20，架构收紧）守“没人判过的方面不默认通过、出口有类型且看得见”：交付物要写 `deliverable_kind`（M33）、
`scope` 必填（M34）、报告显示 `assumed`（M35）、派生行不把没判过的方面判 PASS（M36）、校验拒绝没判过方面的 PASS 行（M37）、
`judgements` 要引条款（M38）、手工核对覆盖不了缺输入的工具缺口（M39）、不同对象不共用一段核对方法（M40）、
手册未规定的工作点不当缺资料（M41）、报告显示为什么不按余量下结论（M42）、同一句假定不抄进几个功能（M43），
由 `test_derive_rows.py`、`test_review_functions.py`、`test_render_and_pack.py` 的对应测试杀死。
M44–M51（2026-10-21，两名审查员同板记录对比）守七条让记录趋同的护栏：功能至少一条能定位、带数字的条款（M44）、
判断至少引一条能定位的条件（M45）、DESIGN_VALUE/VENDOR_DATUM 写了理由也不许超过 3 个方面（M46）、同一句理由不抄到几个开放项（M47）、
框架功能的对象不越出 intent 电路（M48）、审查员绑定的行要在功能对象上（M49）、带 clamp_refs 的连接器行不手填（M50）、
需求行不整行阶段 NA（M51），由 `test_review_functions.py::ReviewerAgreementTests` 和 `test_review_stage_scope.py` 杀死。
M52–M55（2026-10-21，电路候选步 1–2）守 IC 角色与参考地分区：没核验角色的 U/M 位号不登记 DEV-D02 缺口（M52，`test_ic_kinds.py::PlannerGapTests`）、
泛称 ic 的原文写明角色仍通过（M53，`QuoteVerificationTests`）、推导参考地分区时电容导通（M54，`test_domains.py::DomainTests`）、
截止网络的一跳规则穿过地（M55，`RailStopTests`）。
M56–M61（2026-10-21，电路候选步 3–7）守候选生成与决定：走线穿过跨域器件（M56，`test_circuit_candidates.py`）、同距离的共享件只给第一个候选（M57）、
没有决定的候选通过（M58，`test_circuit_decisions.py`）、拆分漏下成员（M59）、手画电路与决定不一致仍通过（M60）、
有电路的记录没有候选文件也能打包（M61，`test_render_and_pack.py`）。
M62–M72（2026-10-21，Codex 合并方案 §3–§5）守影响条目、证据依据和检查项标识：GT 比较把零裕量当通过（M62）、没写 states 的证据覆盖全部状态（M63）、同一范围的通过与失败不报 EVIDENCE_CONFLICT（M64）、跨 regime 比较不写换算（M65）、典型应用当作强制条款（M66）、失败项既无已证缺口也无强制条款（M67）、保证最坏值建在典型值上（M68），由 `test_review_functions.py::EvidenceBasisTests` 和 `FunctionShapeTests` 杀死；电路名进入检查项标识（M69）、同一项检查问两次（M70）、没有定位引用的别名算作配对（M71），由 `test_compare_reviews.py::StrictIdentityTests` 和 `test_validate_review.py` 杀死；证明通过的裕量与阻断同一范围的缺口并存（M72）。
同一批改指向：F7 的 3 个方面上限和 decides_reason 退役后，M46 改守"缺口的每条影响条目都要写 via"；F10 的理由模板降为提示后，M47 改守"判断句不许引数字限值"。M14、M20、M21、M28、M29、M37、M38、M42、M44、M45 跟着新代码换了注入位置，守的行为不变（M42 从"不显示裕量为何不决定"改为"不显示缺口影响哪些判断"）。
M73–M79（2026-10-21，功能电路树第 1 步：器件归属唯一）守认领次序与归属：链路成员与隔离带同级（M73）、电路成员不强于链路成员（M74）、打平的器件归每个打平者（M75），由 `test_circuit_candidates.py::OwnershipTests` 杀死；没有 own 决定的打平被接受（M76）、own 决定没有定位引用（M77）、候选文件里一颗器件两个所属（M78）、手写的 owned 与决定不符（M79），由 `test_circuit_decisions.py::OwnershipTests` 杀死。M57 改指向归属一步生成的共享清单（原先的共享清单代码已删除）。

M80–M84（2026-10-21，功能电路树第 2 步：行归属与电路行身份）守所属与身份：电路级行的成员表和网络留在身份里（M80）、按电路展开的系统规则行归到系统功能（M81）、器件归每个列出它的电路而不是所属电路（M82）、校验器接受与所属表不符的 owner（M83）、电路行按显示名而非候选编号作键（M84），都由 `test_row_owner.py` 杀死。

M85–M90（2026-10-21，功能电路树第 3 步：接口识别）守接口推导：地网成为接口网络（M85）、碰到链路自有器件的网络又进电路对接口（M86）、只凭像电源轨的名字就生成供电接口（M87）、手册库类型为输入的引脚被当作轨的源（M88）、接口编号用电路显示名（M89）、推不出角色的端点不记缺口（M90），都由 `test_interfaces.py` 杀死。

M91–M97（2026-10-22，功能电路树第 4 步：接口检查项）守接口行：SIG-C08 在每条接口网络上都问（M91）、连接器不问载流（M92）、每条轨都问纹波噪声（M93）、接口行归全板（M94）、供电接口也建框架（M95）、接口规则的扫描行落在接口网络上仍归全板（M96）、连接器上的网络先归电路对（M97）；M95 由 `test_circuit_decisions.py` 的框架用例杀死，其余由 `test_interface_rows.py` 杀死。

M98–M103（2026-10-22，功能电路树第 5 步：系统功能与自有器件）守触发与归位：只有一个地网也问 PWR-T06（M98）、只有一条轨也问 RST-T03（M99）、全部 IC 都核验为非主控也问 SIG-D13（M100）、DEV-C02 取电路的全部器件而非电容（M101）、没有电路拥有的器件不问（M102）、有行的系统功能不建框架（M103）；M98/M99 由规则约定板杀死，M101 由全板规则用例、M102 由生成判据用例、其余由 `test_system_functions.py` 杀死。
M104–M110（2026-10-22，功能电路树第 6 步：树上的覆盖与报告）守两条覆盖审计和报告分组：器件归属审计不跑（M104）、一颗器件归两块电路也放过（M105）、没有电路拥有的贴装器件只按候选文件的清单进 REQ-Q08（M106）、缺接口行（M107）或缺接口框架（M108）也放过、报告功能表不按树分组（M109）、发现项不写“所属”（M110）；全部由 `test_tree_coverage.py` 杀死。
M111–M115（2026-10-22，功能电路树第 7 步：拆分计划生成、拒收旧记录）守旧记录的界线：缺所属表（M111）或缺接口（M112）的计划被放行、校验器（M113）、合并（M114）和改版比对（M115）连带读上一版计划（2026-10-23 计划升到 7 后 M113、M114 改指 6 版）；全部由 `test_tree_modules.py` 杀死。同步把代码搬到 `plan_circuits.py`、`plan_system.py`、`plan_board.py`、`interfaces.py` 的 15 条变异改指新文件，全量重跑；M81 自第 5 步（RST-T03 不再按电路展开）起只剩直接调用 `row_owner.owner` 能触发，由 `test_row_owner.py` 新加的用例杀死。
M116–M122（2026-10-22，配对补缺：装配状态按内容命名）守检查项标识：检查器行仍带审查员起的装配名（M116）、清单句柄（M117）或清单摘要（M118）进标识、电路行的工作态被当成装配（M119）、装配键不看跳线（M120）、校验器放行没有装配表的计划（M121）、`compare_reviews.py` 不用装配表算键（M122）；全部由 `test_assembly_identity.py` 杀死。
M123–M130（2026-10-22，去耦行收紧：固定要求种类、返回脚由脚表推出）守：只按写了条款的种类出行（M123）、审查员条款当成行的判据进标识（M124）、返回脚只取一个（M125）、`return_net` 不参与取脚（M126）、返回脚跨网却不写 `return_net`（M127）或只有一个返回网也写（M128）被放行、同一类两条条款被放行（M129）、无电容组的 NA 行把条款出处写进判据（M130）；M123 由 `test_decoupling.py`、其余由 `test_decoupling_fixed_kinds.py` 杀死。
M131–M138（2026-10-22，需求固化第 1 步：需求由工具抄录）守：只抄第一列（M131）、首列不是编号的表也当需求表（M132）、重复编号放行（M133）、需求文档改了仍照读（M134）、intent 里手写原文或出处放行（M135）、文档里的需求在 intent 里缺项（M136）或 intent 里有文档没有的编号（M137）放行、需求条款按判据而不按原文拼接（M138）；M131、M138 由 `test_requirement_clauses.py`、其余由 `test_requirement_source.py` 杀死。
M139–M145（2026-10-22，需求固化第 2 步：类别、方面与判据模板）守：几个类别只取第一类的方面（M139）、审查员的理解变成行判据（M140）、方面不进行对象（M141）、未知类别放行（M142）、自由判据放行（M143）、理解不挂在行上（M144）、几个类别的共有方面重复成两行（M145）；全部由 `test_requirement_categories.py` 杀死。
M146–M155（2026-10-22，需求固化第 3 步：需求参数）守：数字后的短横读成负号（M146）、± 只给正值（M147）、原文里没有的数字放行（M148）、原文里没有的条件放行（M149）、表外单位放行（M150）、换算单位不换算（M151）、计划不按需求取轨窗口（M152）、应力行不带需求条件（M153）、包络取最窄下限（M154）、电源树框架不写需求输入范围（M155，初次存活：测试只查了数字，改为核对完整片段）；全部由 `test_requirement_parameters.py` 杀死。
M156–M165（2026-10-22，需求固化第 4 步：需求行绑定树上的检查）守：绑定 owners 不拥有的行（M156）、全板方面不写 owners 就不绑定（M157）、需求行结论与绑定行不符仍放行（M158）、取绑定行中最好的结论（M159）、NA 的绑定行也算判过（M160）、计划里改过的 bound_checks 放行（M161）、不拥有任何行的 owner 放行（M162）、派生的 FAIL 需求行不进发现项（M163）、手填的需求行被覆盖（M164）、计划不绑定需求行（M165）；全部由 `test_requirement_bindings.py` 杀死。
M166–M176（2026-10-22，需求固化第 5 步：资料、电路类别与电源轨推导后确认）守：像电源的网只扫已声明的（M166）、像电源却没确认的网放行（M167）、排除非候选网放行（M168）、排除不写依据放行（M169）、同时声明又排除放行（M170）、资料文件不在也算可用（M171）、写 available 放行（M172）、需求源不算需求资料（M173）、候选已有的类别仍写 features 放行（M174）、候选没检出的类别写 APPLICABLE 放行（M175）、计划不列像电源的网的确认方式（M176）；M168、M171、M174 初次存活（测试里另有错误或只测了存在的文件），改测试后与其余一起由 `test_derived_declarations.py` 杀死。
M177–M183（2026-10-22，需求固化第 6 步：去耦组按官方脚表成组）守：同网的供电脚不并组（M177）、组条目的条款不进组（M178）、条目写在器件没有 power 脚的网上放行（M179）、同一（位号，网）写两条放行（M180）、条目写 id/supply_nodes 放行（M181）、核验为连接器的器件不写条目也成组（M182）、只有写了条目的网才成组（M183）；由 `test_decoupling_auto_groups.py`、`test_decoupling.py`、`test_asg_review_scope.py` 杀死。M126、M127 随实现改写目标片段，仍被杀死。
M184–M196（2026-10-22，需求固化第 7 步：补加行改为规则缺口）守：缺口缺字段放行（M184）、缺口按 REQ-D01 放行（M185）、未知规则放行（M186）、位号不在网表放行（M187）、缺口编号重复放行（M188）、缺口行不标 REVIEWER_ADDED（M189）、合并带入手加行（M190）、门禁放行手加行（M191）、计划外的行都当作工具写的（M192）、补加行计入配对率（M193）、计划不计补加行（M194）、门禁列缺口不带结论（M195）、报告漏列缺口（M196）；由 `test_rule_gaps.py` 等杀死。改动文件上的旧变异（M8、M26、M35、M39、M40、M42、M70、M71、M109、M110、M113、M114、M121、M122、M135–M138、M142、M143、M152、M158、M165、M167–M170、M172、M174–M176）重跑仍被杀死。
M197–M204（2026-10-22，IC 脚经串联电阻接高轨逐脚出行）守：分压点出脚行（M197）、取最高供电而不是最低（M198）、上拉到本 IC 供电出脚行（M199）、与别的 IC 共网出脚行（M200）、power 脚出脚行（M201）、脚电流不计电阻公差（M202）、不写脚行（M203）、检查器读未解析的需求轨窗口（M204）；由 `test_pin_feeds.py`、`test_requirement_parameters.py` 杀死。同日全部 204 条变异重跑，全部被杀死。
M205–M212（2026-10-22，阻值字段的额定功率与额定电压，读不出的阻值进诊断）守：不认额定功率（M205）、不认额定电压（M206）、同一额定写两次放行（M207）、mW 按 W 读（M208）、额定不记下（M209）、读不出的阻值不报（M210）、标 NC 的件也报（M211）、计划漏掉读不出的阻值（M212）；由 `test_native_resistor_value.py`、`test_unread_values.py` 杀死。解析器与扫描上的旧变异（M1、M4、M7、M9–M12、M23）重跑仍被杀死。
M213–M219（2026-10-22，审查意图的出处与行证据不引用设计方文档）守：审查意图引用设计方文档放行（M213）、行证据来自设计方文档放行（M214）、设计报告不算设计方文档（M215）、名为“设计方案/”的目录也算（M216）、SR 自己的计算预检查也算（M217）、设计方计算结果不算（M218）、列表里的出处不查（M219）；由 `test_independent_review.py` 杀死。
M220–M250（2026-10-22，R5 两份复审对比出的 C1–C9）守：文档类 FAIL 没有待办（M220）、感性负载行按整个续流回路判归属（M221）、功能框架与器件行不带 BOM 文字（M222、M223）、每行都相同的 BOM 列挂到每颗件上（M224）、一行多个位号只认第一个（M225）、BOM 写的电阻额定与电容耐压不用（M226、M227）、写了两次的额定照读（M228）、“工作点在手册规定区外”不算失败依据（M229）、它不列查过的曲线（M230）、它引网表事实（M231）、它引的条款不算被引用（M232）、BOM 行上只点名常规件的开放项不拒（M233）、非位号的词当位号（M234）、值后一个词让阻值读不出（M235）、DNP 当备注词（M236）、这个词不进诊断（M237）、同一交付物不提示（M238）、料号当位号（M239）、反馈断开行不出（M240）、以 FB 开头的脚都算反馈脚（M241）、晶体管与钳位二极管要声明才出器件行（M242）、普通二极管也固定出（M243）、定制电感要声明（M244）、“见功能判定”前缀与对象回显遮住模板（M245、M246）、同一器件的身份/脚表/引脚处置算不同问题（M247）、需求各方面算同一问题（M248）、同一规则各状态共用判断也报（M249）、空话通过不阻断冻结（M250）；由 `test_validate_review.py`、`test_review_functions.py`、`test_read_bom.py`、`test_passive_stress.py`、`test_bom_constraints.py`、`test_pin_feeds.py`、`test_feedback_open.py`、`test_fixed_device_rows.py`、`test_declared_device_coverage.py`、`test_review_quality.py` 杀死。M228 首轮存活（测试电容的电压两个耐压都够，看不出取了哪个），补了 `bom_ratings` 的直接断言后杀死。实现改写后 M67、M210 的原文改指新代码；M211 因 `47R/pulse` 现在读得出而存活，测试改用真正读不出的 `47R/5%/1%` 后杀死。

M251–M289（2026-10-22，R5 复审总结里的 P1–P10）守：阻容应力清单不存 `devices` 段、清单上下文丢掉扫描另读的段（M251、M252）、REQ-Q08 未归属清单行被当成手加行、任何 REQ-Q08 行都被放过（M253、M254）、没有封装的阻容静默跳过、每颗都出行、算不出应力也当超出预判、超出所写耐压照判通过、值里写的额定不用、值里的耐压读不出、按假定封装预判的位号不进诊断（M255–M261）、寿命需求不出逐颗行、每颗电容都出寿命行（M262、M263）、串阻读不出时脚电流行不写计算也能通过、算出的串阻当成没算（M264、M265）、改写后的框架问题不点名本电路、成员行在别处 FAIL 或资料不足时框架仍算通过、计数与功能表读写入的结论（M266–M270）、同一原因逐个方面重复、入口显示内部条件编号（M271、M272）、计划诊断不进报告（M273）、资料不足子类分错或不进待办和计数（M274–M277）、BOM 约束不进报告（M278）、BOM 约束站在非 PASS 行、最低要求不是数、等级不跟后果类别、已写入不给 BOM 行位置、待写入不阻断冻结、形状不校验、冻结不看（M279–M285）、常规件额定留作开放项、需求跟随行打断拒收、安全电容当常规件、非应力行的缺口也拒（M286–M289）；由 `test_passive_stress.py`、`test_pin_feeds.py`、`test_tree_coverage.py`、`test_bom_constraints.py`、`test_review_functions.py`、`test_render_and_pack.py` 等杀死。M254、M267、M269、M279、M286、M288 首轮存活：分别补了“别的 REQ-Q08 行仍算手加”、成员行在别处 FAIL、数字一览的功能计数、非 PASS 行的约束、审查闸门整体拒收常规件开放项、安全电容不是常规件的测试后杀死。

M290（2026-10-22，删旧格式兼容）守：说明版本不是当前版本的计划照读。由 `test_check_explanations.py::test_a_plan_of_an_earlier_explanation_version_is_refused` 杀死。
M296–M307（2026-10-23，R5 独立复审报告的问题）守：有料号或资料的阻容仍按假定封装预判（M296）、BOM 已写规格的值后词仍要求改写（M297）、
同一段计算结果抄进几个功能（M298）、同一余量逐个方面重复和不取整（M299、M300）、只复述缺口的理由逐个方面重复（M301）、
电路连接网络上的轨被当成负载窗口（M302）、自动网名的节点凭对地电容成为电源轨（M303）、功能文字里的位号粘连不筛（M304）、
NA 行写了 blocking 给出 FAIL/INSUFFICIENT 的提示（M305）、串联分压串每颗电阻都按全轨压（M306）、电容稳住的抽头不分段（M307）；
由 `test_passive_stress.py`、`test_pin_feeds.py`、`test_review_functions.py`、`test_catalog.py`、`test_supply_net_names.py`、
`test_review_quality.py`、`test_review_stage_scope.py` 杀死。M271 随 `blocked_judgements` 重写改了注入位置（按理由分组），守的行为不变。
M308–M309（2026-10-23，B5 架构决定）守：框架行挂到审查员自建的功能（M308）、计划电路的行从自建功能取开放项（M309）、位号全在一个电路框架里的自建功能通过（M310），由 `test_review_functions.py::SharedObjectFrameTests` 杀死。
M311–M327（2026-10-23，一致性方案第 4、5、7、9 条）守：定制件图纸要列 BOM 没写的参数（M311）、BOM 写了的参数不算缺（M312）、引自 BOM 的限值要在 BOM 行里（M313）、同一余量不能抄到别的方面（M314）、厂家参考电路能撑起判断（M315）、手册写了用法的要指出在哪写的（M316）、超出规定区要查过工作条件节（M317）和引脚说明节（M318）、REQ-Q07 手填须等于覆盖结果（M319）且不复制子项结论（M320）、端口短路行不派给两侧都是连接器轨的开关（M321）、被 IC 读取的 NTC 不派浪涌行（M322）、接到母线大电容的升压二极管不算 RCD（M323）、地网上的 LED 不把地脚当驱动脚（M324）、光耦接 DIS 等关断脚也派使能行（M325）、对比工具认出需求条款的边（M326）和余量依据里写的角点（M327），由 `test_custom_part_spec.py`、`test_operating_point_tiers.py`、`test_coverage_rows.py`、`test_single_fault_rows.py`、`test_compare_causes.py` 杀死。
M328–M339（2026-10-23，一致性方案第 1 条，结果格式 5）守：经需求条款的边只挡绑定该需求的行（M328）、需求目录下的其他文档也是需求文档（M329）、绝缘需求绑定隔离行（M330）、计算类方面一句话不能判通过（M331）而厂家参考电路可以（M332）、决定结论的余量写推界方式（M333）、典型曲线推出的界不决定（M334）、不利一侧的测试点不能外推（M335）、公差端须是条件给出的那一端（M336）、定不出界先答单调定界尝试（M337）、经温度系数推须引系数（M338）、格式 4 不读（M339），由 `test_requirement_edges.py`、`test_requirement_bindings.py`、`test_calculation_aspects.py`、`test_bound_derivation.py` 杀死。

## 维护

- 改规则或检查器时，为新判据加一条变异：`old` 是实现里唯一出现的一段原文，`new` 是“判据失效”的改法。
  `old` 不唯一时运行器报 ERROR，不会悄悄改错位置。
- 某条变异存活 = 有一条判据没有任何测试守着；先补触发板/近似板或单元测试，再提交。
- 实现重写导致 `old` 找不到时，按新实现改写该条变异，不要删掉。

M340–M359（2026-10-23，一致性方案第 2 条，计划格式 7）守：电路规则按网表前提派行（M340）、网表说不清时照问（M341）、反馈脚与驱动脚算上经电路电阻或电路网相接的外部 IC（M342、M343）、共用地不算连接器输入路径（M344）、串在电源里的 NTC 不是传感器（M345）、低边开关不是防反接开关（M346）、`_RTN` 一类参考地也是地（M347）、一颗电阻不成分压（M348）、驱动器 OUT 脚不算稳压输出（M349）、两脚未知件不算晶体管或 IC（M350）、符号名出热敏/压敏的件不算未知（M351）、行对象取前提找到的器件（M352）、框架只列问了的规则的盲区（M353）、类型几乎不问时提示换类型（M354）、报告列“未问”（M355）、只说不适用的通过被拒（M356）、前提成立的 NA 须引网表事实（M357）且名字须在网表里（M358）、格式 6 不读（M359），由 `test_subject_requires.py`、`test_tree_modules.py` 杀死。

M360–M373（2026-10-23，一致性方案第 3 条，intent 格式 4）守：格式 3 的 intent 不读（M360）、pd_controller 有固定配置组（M361）、没有固定组的可编程器件要求声明组（M362）、没声明的组等声明（M363）、写了输出档位的组问逐档精度（M364）、配置组写手册出处和允许范围（M365）、写它决定的方面（M366）、自定组写名称（M367）、一组不声明两次（M368）、只在某个设置下成立的条件须写进配置行（M369）、设置所在组须在计划里（M370）、配置表缺口不挡硬件行（M371）、按器件和组找配置行（M372）、设置写全器件/组/值（M373），由 `test_configurable_devices.py`、`test_catalog.py`、`test_architecture.py` 杀死。

M374–M397（2026-10-23，一致性方案第 6 条，寿命与老化）守：任务剖面各段合计覆盖设计寿命（M374）、引文取自需求原文（M375）、负载不超额定（M376）、剖面挂在有设计寿命的需求下（M377）、次数为正（M378）、点名器件的次数只给它们（M379）、小时数按设计寿命算（M380）、电解电容也按 BOM 料号/规格（M381）和铝电容封装（M382）识别、钽电容不出寿命行（M383）、超级电容另核电压降额（M384）、寿命行移交热设计（M385）、没写剖面时寿命行等它（M386）、次数没给的耗损件行记 NA（M387）、被 IC 读取的 NTC 不是浪涌限制件（M388）、自恢复保险丝单列（M389）、EEPROM 是耗损件（M390）、电位器按开关核（M391）、估算余量只放行寿命行（M392）且须达标（M393）、凭估算通过须写 BOM 约束（M394）且写明估算（M395）、寿命行不开 VENDOR_DATUM（M396）、只有寿命方面的估算余量可以不留开放项（M397），由 `test_life_rows.py`、`test_wearout_rows.py` 杀死。M263 改指到电解电容识别的最后一步（不认得的电容也出寿命行），M332 跟着 1e 那一行换了注入位置，守的行为不变。

M398（2026-10-23，R5 验收重审发现）守：手册标题写“Power Factor Controller”（没有 correction 一词）也核验为 pwm_controller，由 `test_ic_kinds.py` 杀死。

M399–M404（2026-10-23，R5 验收重审 SR-B01–B05）守：门禁按计划存的候选摘要重建 REQ-Q08 行（M399）、add 已归属的器件不再要求 add/reject（M400）、引 BOM 的 Value 列原文算在 BOM 行里（M401）、派生不覆盖审查员判的 NA 行（M402）、重新派生保留 bom_constraint 和需求条款（M403）、没有供电脚的磁件不要求去耦用的完整脚表（M404），由 `test_tree_coverage.py`、`test_circuit_decisions.py`、`test_custom_part_spec.py`、`test_derive_rows.py`、`test_decoupling_local_scope.py` 杀死。

M405–M406（2026-10-23，R5 验收重审 SR-B06）守：全 NA 框架没有功能判定时，派生（M405）和门禁（M406）都不要求它，由 `test_derive_rows.py` 杀死。

M407–M415（2026-10-23，定界一致性方案第 4 条，对比工具计数）守：照抄理由的 why_not 算定界套话（M407）、多条开项同一句不利侧算套话（M408）、空白不挡照抄（M409）、没读过的条件不算测试点当用法依据（M410）、典型曲线当依据不算（M411）、需求文档不算共同资料（M412）、别的方面的余量不决定这一行（M413）、估算不决定这一行（M414）、失败项引的资料也算（M415），由 `test_compare_bounding_signals.py` 杀死。

M416–M418（2026-10-23，定界表方案 F 的文字矛盾）守：光耦传输行不再要求项目寿命衰减系数（M416）、相似器件和典型 ±30% 的估算可用于 P1 功能判据并移交样机实测（M417）、典型应用等效同样处理（M418），由 `test_optocoupler.py`、`test_catalog.py` 杀死。

M419–M432（2026-10-23，定界一致性方案第 1 条，结果格式 6）守：开着的一侧只能是上界或下界（M419）、写明是哪个量（M420）、工作点范围是数（M421）、测试点是读过的条件（M422）且与工作点同单位（M423，u 按 µ 算 M424）、why_not 不照抄理由（M425）、写明另一侧（M426），不决定时写理由（M427），已决定时有余量（M428）、每条边写开着的一侧（M429）、工作点在测试点范围以内不准开项（M430）、只开测试点之外那段（M431）且里面那段写余量（M432），由 `test_one_sided_bounds.py` 杀死。M337 改指到新的定界检查入口，M339 改为格式 5 不读，守的行为不变。

M433–M442（2026-10-23，定界一致性方案第 2 条和 2-A）守：没覆盖工作点的测试点不能当“写了这种用法”的依据（M433）、引典型曲线时要给估算（M434）、曲线写明覆盖的范围（M435）、估算是数（M436）、估算引的是这条曲线（M437）且是 ESTIMATE（M438）、估算已经不够就记失败项（M439），GT 比较零余量不算够（M440）、失败项的余量可以按典型曲线记 REACHABLE_CASE（M441）而决定通过的余量不行（M442），由 `test_described_usage.py` 杀死。

M443–M455（2026-10-23，定界一致性方案第 3 条）守：设计值列出没选的参数（M443）且每条写参数名（M444）、BOM 行已写的参数不算没定（M445），没写单位的不拿去对 BOM（M446）、`depends_on` 不为空（M447）、只有设计值能写这两个字段（M448）、挂的开项存在（M449）、只挂一层（M450，挂自己也由这条拦住）、挂上的设计值算到那个开项名下（M451）：不另出待办（M452）、行并过去（M453）、行的不足原因取那个开项的（M454）、报告的资料不足细分也按那个开项计（M455），由 `test_design_value_scope.py` 杀死。

M456–M486（2026-10-23，工作点定界表）守：判“定不出界”的缺厂家数据写定界表的格（M456）且门禁按格核对（M457）：格的一侧与开着的一侧相同（M458）、总能定界的格不开项（M459）、超出规定区的格记失败项（M460）、单调参数按有利一侧的测试点定界（M461 方向、M462 须给这一侧的限值、M463 不单调的不按单点定界）；余量写格时按格核对（M464）：推法是这一格允许的（M465）、带公式的推法写公式（M466）、公式属于这个推法（M467）、门禁重算并比对（M468）且容许舍入（M469）；公式库各式的方向和系数（M470–M482：斜率界、温度系数、表的上下列、NTC 按 1/T、B 值角、热不稳定段 80%、按开始壳温降额、散热要求、强制 β 取 2、典型 ±30%、浪涌不外推到更长脉宽、表不外推、热态浪涌 I²t）；按器件类别取格（M483）、检测用 NTC 没表也定界（M484）、定界表文档由表生成（M485）、公式登记进计算库（M486），由 `test_bound_formulas.py`、`test_bounding_table.py` 杀死。M337 改指到新的定界检查入口，守的行为不变。

M487–M493（2026-10-24，计划框架带定界表的格）守：电路框架列出器件对应的格（M487）、NTC 按 NTC 取格（M488）、电解按电解取格（M489）、IC 按器件类别也按角色取格（M490）、每格只列它适用的器件（M491）、格写出公式（M492）、电解格不落到 MLCC（M493），由 `test_frame_bounds.py` 杀死。

M494–M497（2026-10-24，SR 自查第一组）守：`lint.py` 打印计划要审查者先处理的提示（M494），其中包括电路类型几乎问不到规则的提示（M495）；单调格允许按有利侧测试点定界（G2，M496）；参考电路只覆盖负载不重于它的本板（G10，M497），由 `test_plan_diagnostic_lines.py` 与 `test_bounding_table.py` 杀死。

M498–M506（2026-10-24，SR 自查第三组：一个概念一处判法）守：VSS 族是地（M498）、TPS 开头的钽电容料号（M499）与 ALUM 缩写的电解电容（M500）按同一词表认出、同一值里写了两个不同耐压不读（M501）、汇总的“已写明”与门禁一样核后果类别（M502）、希腊字母 μ 与微符号 µ 是一个字（M503）、超大整数不是有限数且不抛错（M504）、只写“压敏”的器件是保护件（M505）、只写“NTC”的输入件是保护件（M506），由 `test_one_judgment.py`、`test_lint.py`、`test_input_filter.py` 与 `test_insufficient_impact.py` 杀死。

M507–M512（2026-10-24，SR 自查第二组 2.4、2.6–2.8）守：只有典型曲线要读估算，应用说明的文字不要（M507）；行只取点名了它的别的功能的开放项（M508），点名了就可以（M509）；门禁命令行要求计划的依赖记录（M510）；intent 拼错的字段（M511）和缺版本（M512）被拒收，由 `test_described_usage.py`、`test_derive_rows.py`、`test_gate_defaults.py` 与 `test_intent_fields.py` 杀死。
M513–M520（2026-10-24，SR 自查第二组 2.1）守：估算不放行损坏、过热、保护类规则（M513），只放行写明必需功能或性能后果的（M514、M519）；样机移交须是本功能写全的一条（M515），序号不能是布尔（M516）；派生行带上这条移交（M517），手填的行丢了移交被拒收（M518）；写全了的估算确实判通过（M520），由 `test_estimate_pass.py` 杀死。
M521–M525（2026-10-24，SR 自查第二组 2.3）守：打包按台账重新渲染报告，手改或台账改了没重出被拒收（M521），渲染时的 notes（M522）和标题、详略（M525）照样用；门禁不 valid（M523）和局部热审（M524）不打包，由 `test_pack_rerender.py` 杀死。
M526–M530（2026-10-24，SR 自查第二组 2.5）守：报告单列“需求要说清楚的地方”（M526），写出建议写进需求的条文（M527），只列 OPEN 项（M530），不挡定稿的写明不挡（M529），待办里对应那件不重复（M528），由 `test_clarification_section.py` 杀死。
M531–M532（2026-10-24，SR 自查 5.8 导入方向）守：读入不从检查器取器件词（M531），派生行不从校验取功能判定的读法（M532），由 `test_ring_imports.py` 杀死。
M533–M537（2026-10-24，需求按量分解）守：带参数的方面没有参数不问（M533）、参数在所选类别之外也问它的方面（M534）、计划按参数而不只按类别展开需求行（M535）、原文里没读进参数的带单位数字列成诊断（M536）、参数已写的数字不算没读（M537），由 `test_requirement_categories.py::ParameterDecompositionTests` 杀死。
M538–M544（2026-10-24，需求行的 owners）守：有候选没写 owners 被拒（M538）、候选电路按方面的类型过滤（M539）、`owners: []` 要能定位的理由（M540）、OPEN 的需求不要求 owners（M541）、候选外的 owners 出诊断（M542）、校验重算候选（M543）、对比工具报 owners 差异（M544），由 `test_requirement_bindings.py::OwnerCandidateTests` 杀死。
M545–M546（2026-10-24，可承接的电路按方面白名单过滤）守：系统功能（M545）和接口（M546）不在方面那一格里就不是可承接的电路，M539 改为电路类型不过滤；由 `test_requirement_bindings.py::OwnerCandidateTests` 杀死。
M547–M552（2026-10-24，器件角色登记表）守：靶多种总线的角色按手册标题挑类型（M547）、标题挑不出总线记 role-bus 缺口（M548）、接口网上的连接器作成员（M549）、泛称 ic 列成 DEVICE_KIND_GENERIC 诊断（M550）、核心器件角色 = 登记表里有电路类型的角色（M551）、电机驱动器标题不再算栅极驱动器（M552），由 `test_ic_kinds.py` 杀死。
M553–M555（2026-10-24，脚表护栏）守：声明抄全的脚表缺封装脚号被拒（M553）、SOT-23 / TO-220 单独不算脚数（M554）、U/M 位号抄全却没有 power/return 脚列成 DEVICE_PINS_NO_SUPPLY 诊断（M555），由 `test_pin_table.py` 杀死。
M556–M557（2026-10-24，对比工具的电路决定一节）守：两边决定不同要单列（M556）、对齐电路的成员差要列（M557），由 `test_compare_reviews.py::CircuitDecisionTests` 杀死。
M558–M569（2026-10-25，R6 验收修法清单 A 组）守：寿命判据不含相位名（M558）、配置判据不引允许范围（M559）、承接电路按候选编号比（M560）、已被电路持有的器件不进 REQ-Q08（M561）、空测试点要写查过哪里（M562）、bias_v 不收负值（M563）、只有 DOWNSTREAM_HANDOFF 整行阶段 NA（M564）、普通阻容手册不向设计方索取（M565）、绕组与整流桥算来源（M566）、HV 脚经启动电阻算有源（M567）、返回脚不报无驱动（M568）、别的量的失败不进需求行（M569）；由 test_life_rows / test_configurable_devices / test_compare_reviews / test_circuit_decisions / test_one_sided_bounds / test_optocoupler / test_review_stage_scope / test_gap_inventory / test_board_scans / test_requirement_bindings 杀死。
M570–M579（2026-10-25，R6 验收修法清单 B 组）守：需求 id 跨文档重复被拒（M570）、核验过的有源 kind 才生成器件行（M571）、features 的 NOT_APPLICABLE 不生成 REQ-Q07 行（M572）、走线穿过被驱动的小信号管（M573）、未归属有源件必须决定（M574）、add 进已有电路即并入（M575）、器件级 reject 把器件移出 REQ-Q08（M576）、TVS 不按功能齐纳跳过 PRO-A02（M577）、到连接器的齐纳仍是防护件（M578）、低于供电的钳位定上界（M579）；由 test_requirement_source / test_declared_device_coverage / test_plan_review / test_circuit_candidates / test_circuit_decisions / test_electrical_safety / test_passive_stress 杀死。
M580–M589（2026-10-25，五步逐任务巡检第一批）守：任务剖面引用的需求不列未读数（M580）、未读数要列能收它的参数（M581）、光耦脚表不问供电脚（M582）、类别读不出的三脚件要决定（M583）、BZX 是钳位件（M584）、派生行不进复用措辞（M585）、派生 PASS 行不进模板措辞（M586）、派生移交不算模板（M587）、待机功耗需求生成 PWR-C16（M588）、STANDBY_POWER 绑 PWR-C16（M589）；由 test_life_rows / test_requirement_bindings / test_pin_table / test_circuit_decisions / test_electrical_safety / test_review_quality 杀死。
M590（2026-10-25，③ 预绑）守：电路拥有的器件行预绑到电路框架，由 `test_circuit_decisions.py::OwnedRowBindingTests` 杀死。巡检第一批改动文件上的 120 条变异：118 杀，M536、M574 锚点随代码移动已重指并复跑杀死。
M591–M605（2026-10-25，R7 修法 A 组 9 条与 B 组 4 项）守：工程ID 表头、"编号 标题"首格、斜杠编号（M591–M593）、缺脚角色 absent（M594）、别的功能用 check_ids 点名的开放项算决定（M595）、关键字识别的变压器不算未核器件（M596）、本功能行指向别的功能时汇总继承（M597）、HV 启动串阻不按 V²/R（M598）、源跟随器栅极齐纳不派 PRO-C02（M599）、正向 LED 当钳位（M600）、功能绑定行的筛查范围含功能对象（M601）、可编程器件未声明的诊断（M602）、加态要需求点名（M603）、开放项按种类能挡的行（M604）、PRO-A02 行点名被保护脚（M605）。
M606–M622（2026-10-25，④ 第一项功能复核的严格审核）守：文本层字形回退的签名与 `unit_glyphs`（M606–M608，`test_datasheet_kinds.py::GlyphFallbackTests`）、审计的 `DATASHEET_UNIT_GLYPHS` 诊断与计数（M609、M622）、带公差输入没有角点拒收、已列角点的不再问（M610、M611，`test_bound_derivation.py`）、决定性余量必写 `cell`、NONE 不带 method（M612、M613，`test_bounding_table.py::CellRequiredTests`）、25 °C 单点额定的三个条件（M614–M616）、`BOUNDING_CELL_AVAILABLE` 与 `UNIT_GLYPH_SUSPECT` 的提示条件（M617–M619，`test_review_functions.py::ReviewRecheckHintTests`）、筛查把结果目录交给提示（M620）、`cells_named_by`（M621）。
M627–M639（2026-10-26，4.3 跑校验与处置疑点：疑点分层）守：开放项和它的派生检查项算一个缺口（M627–M629，`test_review_quality.py::DownstreamTriageTests`）、派生检查项不进下游/对象越界/后果越界/引用本记录的逐项筛查（M630–M633）、派生时序窗口看开放项且只提示一次（M634、M635）、固件镜像与"已读只剩复算"读开放项：原理图前提不算、写了缺什么数据不算、"随后"分句不算、派生检查项不再逐项点（M636–M639，`test_review_functions.py::MisfiledItemTests`）。两批 197 条改动文件变异从快照重跑：196 杀，M329 锚点随 2026-10-24 的环导入整理移到 `function_reading.py`，已重指并复跑杀死。
M623–M626（2026-10-25，4.2 证据不足的分类）守：开放项关闭条件接受实测/样机/仿真的提示、"随后/留给"分句不算、只看 DESIGN_VALUE / VENDOR_DATUM（M623–M625，`test_review_functions.py::DownstreamClosureTests`）、同一句关闭条件或取得方式出现在几个开放项上是 TEMPLATE_REASON（M626）。
M640–M650（2026-10-26，判决边界按器件类型）守：安全危害/核心链路类任何格不估算（M640、M644，`test_estimate_pass.py`、`test_cell_boundary.py::CellBoundaryTests`）、估算能否判 PASS 由格决定而非规则 id（M641）、`estimate_factor` 须等于格的倍数（M642）、格的余量下限要满足（M643）、估算 PASS 的派生检查项写 C 级、门禁拒绝别的等级（M645）并把 `release` 压到 CONDITIONAL_GO（M646，`EstimateGradeAndReleaseTests`）、词表认不出的器件报 NEW_DEVICE_KIND（M647）、只有 `cell: NONE` 才报 NEW_BOUND_CELL（M648，`ExtensionSignalTests`）、`cell_boundary` 反馈须写真实的格（M649）、向厂家索取只对“行业不给”的格提示（M650，`UnobtainableDatumTests`）。
