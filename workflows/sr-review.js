export const meta = {
  name: 'sr-review',
  description: '原理图审查（SR）：器件不多的板一位审查员加一位复核人；器件多的板分区并行审，另有整板审查员，复核人合成报告',
  whenToUse: '对一份原理图设计结果做首审或改版复审，产出审查报告；输入是需求、设计结果和资料目录，或设计工作流的交付目录',
  phases: [
    { title: '分区' }, { title: '审查' }, { title: '复核' },
  ],
}

// args: {
//   workdir: 审查工作目录（绝对路径；全部产物都在这里）,
//   inputs: 一段话说明输入在哪里：需求文件、原理图/网表/BOM、资料目录；或“ASG 交付目录 <路径>”,
//   revision: 可选，改版复审时上一轮审查工作目录的路径（里面有上一轮的审查报告，旧网表在不在都写明）,
//   mode: 可选，auto（默认：器件不超过 quick_limit 个走快审，否则走分区快审）、quick、zones,
//   quick_limit: 可选，快审的器件数上限，默认 40,
//   skill: 可选，技能目录，默认 ~/.agents/skills/schematic-review
// }
const a = args || {}
if (!a.workdir || !a.inputs) throw new Error('args 需要 workdir 和 inputs')
const SKILL = a.skill || '~/.agents/skills/schematic-review'
const common = `全程中文。技能目录 ${SKILL}（只读，不改其中任何文件）。审查工作目录 ${a.workdir}，全部产物写在这里。
输入：${a.inputs}${a.revision ? `\n这是改版复审，上一轮的审查工作目录是 ${a.revision}；照 references/quick-review.md 的“改版复审”一节做：先逐条核上一轮的意见是否关闭，再审改动处和受它影响的电路。` : ''}
若输入是设计工作流的交付目录，先读 references/workflow-handoff.md：只读其中的原理图、网表、PDF、BOM 和需求基线（设计资料/需求基线.md，已定的澄清照它审、不重问），设计方的报告和 record/ 不读不引用。`



// 快审：器件不多的板。一位审查员按工程判断直接审，知识框架作为查漏清单；另一位独立复核每条发现。
// H-001 2026-11-16：11 个器件的板走五步流水线用了 92 分钟、149 项检查，只报出两条文档类 P3；
// 同一份设计不带技能直接审 3 分钟，报出指示灯正向压降、热插拔过冲等 6 条。
const FRAMEWORK = '知识框架目录见技能目录的 .knowledge-framework 文件（或环境变量 HARDWARE_KNOWLEDGE_FRAMEWORK）'
let mode = a.mode || 'auto'
if (mode === 'auto') {
  const size = await agent(`${common}\n\n只做一件事：数出这份设计的 BOM（或网表）里有多少个器件位号，返回 count。不做别的，不写任何文件。`,
    { label: '数器件', phase: '分区', schema: { type: 'object', required: ['count'], properties: { count: { type: 'integer' } } }, effort: 'low', model: 'haiku' })
  mode = size && size.count <= (a.quick_limit || 40) ? 'quick' : 'zones'
  log(`器件 ${size ? size.count : '?'} 个，走${mode === 'quick' ? '快审' : '分区快审'}`)
}
if (mode === 'quick') {
  const QUICK = { type: 'object', required: ['status', 'summary'], properties: {
    status: { type: 'string', enum: ['done', 'needs_input'] }, summary: { type: 'string' }, questions: { type: 'array', items: { type: 'string' } } } }
  phase('审查')
  const r = await agent(`${common}

你是资深硬件工程师，做这块板的快审：读 ${SKILL}/references/quick-review.md 并照它做。
先凭工程判断把图审一遍，再用知识框架查漏。${FRAMEWORK}。报告写到 ${a.workdir}/审查报告.md。
返回 status（done；缺了只有人能给的东西才 needs_input）和 summary（发现条数按严重度、每条一句话）。`,
    { label: '快审', phase: '审查', schema: QUICK })
  if (!r) return { status: 'stopped', done: [] }
  if (r.status === 'needs_input') return { status: 'needs_input', questions: r.questions || [], summary: r.summary, done: [] }
  phase('复核')
  const v = await agent(`${common}

你是复核人，没有参与上一位审查员的审查。读 ${SKILL}/references/quick-review.md 的“复核”一节并照它做：对 ${a.workdir}/审查报告.md 的每条发现，回到网表、BOM、PDF 和器件手册原文独立核一遍，
站不住的删掉或降级，写错位号、页码、数值的改正；再按该节的漏查清单扫一遍有没有漏掉的问题。直接改 ${a.workdir}/审查报告.md，并在末尾“复核记录”里逐条写处置。
返回 status 和 summary（改了哪几条、删了哪几条、补了哪几条）。`,
    { label: '复核', phase: '复核', schema: QUICK })
  return { status: 'complete', mode: 'quick', workdir: a.workdir, report: `${a.workdir}/审查报告.md`, done: [{ summary: r.summary }, { summary: v ? v.summary : '复核没有返回结果' }] }
}

// 分区快审：器件多的板。分区后各区审查员并行审，一位整板审查员按供电方式和工况走查，复核人合成报告并独立复核。
// M-001 2026-11-17：169 个器件的板走五步流水线 79 分钟、1386 项检查没有判完；直接审 18 分钟报出 1 条 P0、4 条 P1，P1 都是跨功能块的。
if (mode === 'zones') {
  const R = { type: 'object', required: ['status', 'summary'], properties: {
    status: { type: 'string', enum: ['done', 'needs_input'] }, summary: { type: 'string' }, questions: { type: 'array', items: { type: 'string' } } } }
  const QR = `${SKILL}/references/quick-review.md`
  const base = `读 ${QR} 并照它做。${FRAMEWORK}。`
  phase('分区')
  const z = await agent(`${common}

只做 ${QR}“分区快审”一节的第 1 步（分区）：读网表和 BOM，把器件分成 3 到 6 个区，写 ${a.workdir}/分区.json（每区 id、name、refs、进出本区的网络）。不审查。
返回 zones（每区的 id 和 name，id 用短的英文或拼音，能作文件名）。`,
    { label: '分区', phase: '分区', effort: 'low', model: 'sonnet',
      schema: { type: 'object', required: ['zones'], properties: { zones: { type: 'array', items: { type: 'object', required: ['id', 'name'], properties: { id: { type: 'string' }, name: { type: 'string' } } } } } } })
  if (!z || !(z.zones || []).length) return { status: 'blocked', reason: '没有分出区', done: [] }
  phase('审查')
  const jobs = z.zones.map(zone => () => agent(`${common}

你是资深硬件工程师，做这块板的分区快审，只审“${zone.name}”这个区（${a.workdir}/分区.json 里 id 为 ${zone.id} 的那一区）。${base}
照“分区快审”第 2 步做，写 ${a.workdir}/分区/${zone.id}.md。别的区同时有人在审，不写别的文件。
返回 status 和 summary（本区发现条数按严重度、每条一句话、交给整板审查员的跨区疑点）。`,
    { label: `审 ${zone.name}`, phase: '审查', schema: R }).then(r => ({ zone: zone.name, r })))
  jobs.push(() => agent(`${common}

你是资深硬件工程师，做这块板的整板审查员。${base}
照“分区快审”第 3 步做，写 ${a.workdir}/分区/整板.md。各区的器件有别的审查员在逐个核，你只做跨区的走查、预算、引脚分配和过度设计。
返回 status 和 summary（发现条数按严重度、每条一句话、能省的器件数）。`,
    { label: '审 整板', phase: '审查', schema: R }).then(r => ({ zone: '整板', r })))
  const parts = (await parallel(jobs)).filter(Boolean)
  const zdone = parts.map(p => ({ summary: `${p.zone}：${p.r ? p.r.summary : '没有返回结果'}` }))
  phase('复核')
  const v = await agent(`${common}

你是复核人，没有参与各区和整板的审查。读 ${QR} 的“报告”“复核”和“分区快审”第 4 步并照它做：把 ${a.workdir}/分区/ 下各份的发现合成 ${a.workdir}/审查报告.md，
每条发现回到网表、BOM、PDF 和器件手册原文独立核一遍，站不住的删掉或降级，写错的改正，重复的并成一条；再按漏查清单扫一遍。末尾“复核记录”逐条写处置。
返回 status 和 summary（最终发现条数按严重度、P0 和 P1 每条一句话、删了和补了哪几条）。`,
    { label: '合成与复核', phase: '复核', schema: R })
  return { status: v && v.status === 'done' ? 'complete' : 'blocked', mode: 'zones', workdir: a.workdir, report: `${a.workdir}/审查报告.md`,
    done: [...zdone, { summary: v ? v.summary : '复核没有返回结果' }] }
}
