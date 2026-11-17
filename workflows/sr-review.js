export const meta = {
  name: 'sr-review',
  description: '原理图审查（SR）：五个步骤各用新的上下文执行，每步的关卡通过才进下一步',
  whenToUse: '对一份原理图设计结果做首审或改版复审，产出审查报告；输入是需求、设计结果和资料目录，或设计工作流的交付目录',
  phases: [
    { title: '① 读入' }, { title: '② 出计划' }, { title: '③ 判断' }, { title: '④ 校验' }, { title: '⑤ 出报告' },
  ],
}

// args: {
//   workdir: 审查工作目录（绝对路径；状态和全部产物都在这里）,
//   inputs: 一段话说明输入在哪里：需求文件、原理图/网表/BOM、资料目录；或“ASG 交付目录 <路径>”,
//   revision: 可选，改版复审时旧审查工作目录的路径,
//   start: 可选，从第几步开始（1–5，接着上次停下的地方做）,
//   mode: 可选，auto（默认：器件不超过 quick_limit 个走快审，否则走分区快审）、quick、zones、full（五步流水线，只在点名时走）,
//   quick_limit: 可选，快审的器件数上限，默认 40,
//   skill: 可选，技能目录，默认 ~/.agents/skills/schematic-review
// }
const a = args || {}
if (!a.workdir || !a.inputs) throw new Error('args 需要 workdir 和 inputs')
const SKILL = a.skill || '~/.agents/skills/schematic-review'
const STEPS = [
  { n: 1, title: '① 读入', file: 'step-1-intake.md', rounds: 2 },
  { n: 2, title: '② 出计划', file: 'step-2-plan.md', rounds: 2 },
  { n: 3, title: '③ 判断', file: 'step-3-judge.md', rounds: 8 },
  { n: 4, title: '④ 校验', file: 'step-4-validate.md', rounds: 3 },
  { n: 5, title: '⑤ 出报告', file: 'step-5-report.md', rounds: 2 },
]
const WORK = {
  type: 'object', required: ['status', 'summary'],
  properties: {
    status: { type: 'string', enum: ['done', 'partial', 'needs_input', 'upstream'] },
    upstream_step: { type: 'integer' },
    summary: { type: 'string' },
    questions: { type: 'array', items: { type: 'string' } },
  },
}
const GATE = {
  type: 'object', required: ['passed', 'details'],
  properties: { passed: { type: 'boolean' }, details: { type: 'string' } },
}
const common = `全程中文。技能目录 ${SKILL}（只读，不改其中任何文件）。审查工作目录 ${a.workdir}，全部产物写在这里。
输入：${a.inputs}${a.revision ? `\n这是改版复审，上一轮的审查工作目录是 ${a.revision}；按 references/revision-review.md 在②和④加旧网表和旧计划。` : ''}
若输入是设计工作流的交付目录，先读 references/workflow-handoff.md：只读其中的原理图、网表、PDF、BOM 和需求基线（设计资料/需求基线.md，已定的澄清照它审、不重问），设计方的报告和 record/ 不读不引用。`

function workPrompt(s, feedback, fromDown) {
  return `${common}

你是审查员，只做审查流水线的第 ${s.n} 步（${s.title}）。先读 ${SKILL}/SKILL.md、references/pipeline-overview.md 和本步细则 references/${s.file}，再读本步细则指到的参考文件。前面各步的产物已在工作目录里；先看工作目录里已有什么，接着做，不重做已完成且有效的部分。
只做本步：不做后面步骤的事，不改前面步骤的产物；intent.json 例外，它是①②共写的声明：第 2 步缺 owners、assemblies、power_rails 这类声明时自己补进 intent.json 再重跑，不为它返回第 1 步。发现前面某一步的产物有错或不够（例如要在 intent 里补声明并重新生成计划），返回 upstream，在 upstream_step 写该回到第几步，summary 逐条写清要那一步补什么、补完后本步哪一项能关闭。
本步做完的标志以细则里的关卡命令为准，自己先跑到通过。
${fromDown ? `后面的步骤做不下去，指出本步的产物有错或不够（本步自己的关卡通过不等于后面够用）：\n${fromDown}\n本轮先按这些改本步的产物，改完重跑本步关卡。认为某条不该由本步改的，在 summary 里逐条写明理由。\n` : ''}${feedback ? `上一轮关卡没过，原因：\n${feedback}\n先处置这些再继续。\n` : ''}
返回：status 为 done（本步全部做完且自查关卡通过）、partial（工作量大，本轮做了一部分，进度已写进工作目录，下一轮接着做）、upstream 或 needs_input（缺了只有人能给的东西：资料、需求澄清、设计未定项的决定；写进 questions，每条写清要什么、为什么、给了之后哪一项能关闭）。summary 写本轮做了什么、还剩什么。`
}
function gatePrompt(s) {
  return `${common}

你是关卡检查员，不是审查员：不写、不改工作目录里的任何审查产物，不替审查员补内容。读 ${SKILL}/SKILL.md 的“执行流程”步骤表和 references/${s.file}，找出第 ${s.n} 步（${s.title}）做完的标志和关卡命令，在工作目录上实际运行这些命令，并核对本步应有的产出文件都在。
步骤表的“过关”一栏是摘要，判定以细则里“做完的标志”的原文为准：细则允许“处置后保留”的提示（写了说明、登记了缺口或留给后面某一步的），核对处置确实写在产物里，不因工具仍然打印这条提示而判不过；细则没有允许保留的才算没过。
返回 passed（关卡命令全部通过且产出齐全才为 true）和 details（跑了哪些命令、各自的结果；没过时逐条列出错误原文，够审查员照着改）。`
}

// 快审：器件不多的板不走五步流水线。一位审查员按工程判断直接审，知识框架作为查漏清单；另一位独立复核每条发现。
// H-001 2026-11-16：11 个器件的板走五步流水线用了 92 分钟、149 项检查，只报出两条文档类 P3；
// 同一份设计不带技能直接审 3 分钟，报出指示灯正向压降、热插拔过冲等 6 条。
const FRAMEWORK = '知识框架目录见技能目录的 .knowledge-framework 文件（或环境变量 HARDWARE_KNOWLEDGE_FRAMEWORK）'
let mode = a.mode || 'auto'
if (mode === 'auto' && !a.start && !a.revision) {
  const size = await agent(`${common}\n\n只做一件事：数出这份设计的 BOM（或网表）里有多少个器件位号，返回 count。不做别的，不写任何文件。`,
    { label: '数器件', phase: '① 读入', schema: { type: 'object', required: ['count'], properties: { count: { type: 'integer' } } }, effort: 'low', model: 'haiku' })
  mode = size && size.count <= (a.quick_limit || 40) ? 'quick' : 'zones'
  log(`器件 ${size ? size.count : '?'} 个，走${mode === 'quick' ? '快审' : '分区快审'}`)
} else if (mode === 'auto') mode = 'full'
if (mode === 'quick') {
  const QUICK = { type: 'object', required: ['status', 'summary'], properties: {
    status: { type: 'string', enum: ['done', 'needs_input'] }, summary: { type: 'string' }, questions: { type: 'array', items: { type: 'string' } } } }
  phase('③ 判断')
  const r = await agent(`${common}

你是资深硬件工程师，做这块板的快审：读 ${SKILL}/references/quick-review.md 并照它做（不走 SKILL.md 的五步流水线，不生成检查计划，不写 intent.json）。
先凭工程判断把图审一遍，再用知识框架查漏。${FRAMEWORK}。报告写到 ${a.workdir}/审查报告.md。
返回 status（done；缺了只有人能给的东西才 needs_input）和 summary（发现条数按严重度、每条一句话）。`,
    { label: '快审', phase: '③ 判断', schema: QUICK })
  if (!r) return { status: 'stopped', step: 3, done: [] }
  if (r.status === 'needs_input') return { status: 'needs_input', step: 3, questions: r.questions || [], summary: r.summary, done: [] }
  phase('④ 校验')
  const v = await agent(`${common}

你是复核人，没有参与上一位审查员的审查。读 ${SKILL}/references/quick-review.md 的“复核”一节并照它做：对 ${a.workdir}/审查报告.md 的每条发现，回到网表、BOM、PDF 和器件手册原文独立核一遍，
站不住的删掉或降级，写错位号、页码、数值的改正；再按该节的漏查清单扫一遍有没有漏掉的问题。直接改 ${a.workdir}/审查报告.md，并在末尾“复核记录”里逐条写处置。
返回 status 和 summary（改了哪几条、删了哪几条、补了哪几条）。`,
    { label: '复核', phase: '④ 校验', schema: QUICK })
  return { status: 'complete', mode: 'quick', workdir: a.workdir, report: `${a.workdir}/审查报告.md`, done: [{ step: 3, summary: r.summary }, { step: 4, summary: v ? v.summary : '复核没有返回结果' }] }
}

// 分区快审：器件多的板。分区后各区审查员并行审，一位整板审查员按供电方式和工况走查，复核人合成报告并独立复核。
// M-001 2026-11-17：169 个器件的板走五步流水线 79 分钟、1386 项检查没有判完；直接审 18 分钟报出 1 条 P0、4 条 P1，P1 都是跨功能块的。
if (mode === 'zones') {
  const R = { type: 'object', required: ['status', 'summary'], properties: {
    status: { type: 'string', enum: ['done', 'needs_input'] }, summary: { type: 'string' }, questions: { type: 'array', items: { type: 'string' } } } }
  const QR = `${SKILL}/references/quick-review.md`
  const base = `读 ${QR} 并照它做（不走 SKILL.md 的五步流水线，不生成检查计划，不写 intent.json）。${FRAMEWORK}。`
  phase('② 出计划')
  const z = await agent(`${common}

只做 ${QR}“分区快审”一节的第 1 步（分区）：读网表和 BOM，把器件分成 3 到 6 个区，写 ${a.workdir}/分区.json（每区 id、name、refs、进出本区的网络）。不审查。
返回 zones（每区的 id 和 name，id 用短的英文或拼音，能作文件名）。`,
    { label: '分区', phase: '② 出计划', effort: 'low', model: 'sonnet',
      schema: { type: 'object', required: ['zones'], properties: { zones: { type: 'array', items: { type: 'object', required: ['id', 'name'], properties: { id: { type: 'string' }, name: { type: 'string' } } } } } } })
  if (!z || !(z.zones || []).length) return { status: 'blocked', step: 2, reason: '没有分出区', done: [] }
  phase('③ 判断')
  const jobs = z.zones.map(zone => () => agent(`${common}

你是资深硬件工程师，做这块板的分区快审，只审“${zone.name}”这个区（${a.workdir}/分区.json 里 id 为 ${zone.id} 的那一区）。${base}
照“分区快审”第 2 步做，写 ${a.workdir}/分区/${zone.id}.md。别的区同时有人在审，不写别的文件。
返回 status 和 summary（本区发现条数按严重度、每条一句话、交给整板审查员的跨区疑点）。`,
    { label: `审 ${zone.name}`, phase: '③ 判断', schema: R }).then(r => ({ zone: zone.name, r })))
  jobs.push(() => agent(`${common}

你是资深硬件工程师，做这块板的整板审查员。${base}
照“分区快审”第 3 步做，写 ${a.workdir}/分区/整板.md。各区的器件有别的审查员在逐个核，你只做跨区的走查、预算、引脚分配和过度设计。
返回 status 和 summary（发现条数按严重度、每条一句话、能省的器件数）。`,
    { label: '审 整板', phase: '③ 判断', schema: R }).then(r => ({ zone: '整板', r })))
  const parts = (await parallel(jobs)).filter(Boolean)
  const zdone = parts.map(p => ({ step: 3, summary: `${p.zone}：${p.r ? p.r.summary : '没有返回结果'}` }))
  phase('④ 校验')
  const v = await agent(`${common}

你是复核人，没有参与各区和整板的审查。读 ${QR} 的“报告”“复核”和“分区快审”第 4 步并照它做：把 ${a.workdir}/分区/ 下各份的发现合成 ${a.workdir}/审查报告.md，
每条发现回到网表、BOM、PDF 和器件手册原文独立核一遍，站不住的删掉或降级，写错的改正，重复的并成一条；再按漏查清单扫一遍。末尾“复核记录”逐条写处置。
返回 status 和 summary（最终发现条数按严重度、P0 和 P1 每条一句话、删了和补了哪几条）。`,
    { label: '合成与复核', phase: '④ 校验', schema: R })
  return { status: v && v.status === 'done' ? 'complete' : 'blocked', mode: 'zones', workdir: a.workdir, report: `${a.workdir}/审查报告.md`,
    done: [...zdone, { step: 4, summary: v ? v.summary : '复核没有返回结果' }] }
}

const done = []
let backtracks = 0, carry = ''
for (let i = Math.max((a.start || 1) - 1, 0); i < STEPS.length; i++) {
  const s = STEPS[i]
  phase(s.title)
  let feedback = '', passed = false, back = 0
  const fromDown = carry
  carry = ''
  for (let round = 1; round <= s.rounds; round++) {
    const w = await agent(workPrompt(s, feedback, fromDown), { label: `${s.title}${fromDown ? ' 回改' : ''} 第${round}轮`, phase: s.title, schema: WORK })
    if (!w) return { status: 'stopped', step: s.n, done }
    if (w.status === 'needs_input') return { status: 'needs_input', step: s.n, questions: w.questions || [], summary: w.summary, done }
    if (w.status === 'upstream') { back = w.upstream_step || s.n - 1; feedback = w.summary; break }
    if (w.status === 'partial') { log(`${s.title} 未完，继续：${w.summary}`); feedback = ''; continue }
    const g = await agent(gatePrompt(s), { label: `${s.title} 关卡`, phase: s.title, schema: GATE, effort: 'low', model: 'sonnet' })
    if (g && g.passed) { passed = true; done.push({ step: s.n, summary: w.summary }); break }
    feedback = g ? g.details : '关卡检查没有返回结果'
    log(`${s.title} 关卡未过，返回本步处置`)
  }
  if (back) {
    if (back < 1 || back >= s.n || ++backtracks > 3) return { status: 'blocked', step: s.n, reason: `需要回到前面的步骤但无法继续：${feedback}`, done }
    log(`${s.title} 发现前面步骤的问题，回到第 ${back} 步：${feedback}`)
    carry = feedback
    i = back - 2
    continue
  }
  if (!passed) return { status: 'blocked', step: s.n, reason: feedback || '本步在限定轮数内没有做完', done }
}
return { status: 'complete', workdir: a.workdir, report: `${a.workdir}/审查报告.md`, done }
