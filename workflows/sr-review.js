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
