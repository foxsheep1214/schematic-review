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
    status: { type: 'string', enum: ['done', 'partial', 'needs_input'] },
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
若输入是设计工作流的交付目录，先读 references/workflow-handoff.md：只读其中的原理图、网表、PDF、BOM 和需求，设计方的报告和 record/ 不读不引用。`

function workPrompt(s, feedback) {
  return `${common}

你是审查员，只做审查流水线的第 ${s.n} 步（${s.title}）。先读 ${SKILL}/SKILL.md、references/pipeline-overview.md 和本步细则 references/${s.file}，再读本步细则指到的参考文件。前面各步的产物已在工作目录里；先看工作目录里已有什么，接着做，不重做已完成且有效的部分。
只做本步：不做后面步骤的事，不改前面步骤的产物（发现前一步的产物有错，在 summary 里写明并返回 needs_input）。
本步做完的标志以细则里的关卡命令为准，自己先跑到通过。
${feedback ? `上一轮关卡没过，原因：\n${feedback}\n先处置这些再继续。\n` : ''}
返回：status 为 done（本步全部做完且自查关卡通过）、partial（工作量大，本轮做了一部分，进度已写进工作目录，下一轮接着做）或 needs_input（缺了只有人能给的东西：资料、需求澄清、设计未定项的决定；写进 questions，每条写清要什么、为什么、给了之后哪一项能关闭）。summary 写本轮做了什么、还剩什么。`
}
function gatePrompt(s) {
  return `${common}

你是关卡检查员，不是审查员：不写、不改工作目录里的任何审查产物，不替审查员补内容。读 ${SKILL}/SKILL.md 的“执行流程”步骤表和 references/${s.file}，找出第 ${s.n} 步（${s.title}）做完的标志和关卡命令，在工作目录上实际运行这些命令，并核对本步应有的产出文件都在。
返回 passed（关卡命令全部通过且产出齐全才为 true）和 details（跑了哪些命令、各自的结果；没过时逐条列出错误原文，够审查员照着改）。`
}

const done = []
for (const s of STEPS) {
  if (a.start && s.n < a.start) continue
  phase(s.title)
  let feedback = '', passed = false
  for (let round = 1; round <= s.rounds; round++) {
    const w = await agent(workPrompt(s, feedback), { label: `${s.title} 第${round}轮`, phase: s.title, schema: WORK })
    if (!w) return { status: 'stopped', step: s.n, done }
    if (w.status === 'needs_input') return { status: 'needs_input', step: s.n, questions: w.questions || [], summary: w.summary, done }
    if (w.status === 'partial') { log(`${s.title} 未完，继续：${w.summary}`); feedback = ''; continue }
    const g = await agent(gatePrompt(s), { label: `${s.title} 关卡`, phase: s.title, schema: GATE, effort: 'low' })
    if (g && g.passed) { passed = true; done.push({ step: s.n, summary: w.summary }); break }
    feedback = g ? g.details : '关卡检查没有返回结果'
    log(`${s.title} 关卡未过，返回本步处置`)
  }
  if (!passed) return { status: 'blocked', step: s.n, reason: feedback || '本步在限定轮数内没有做完', done }
}
return { status: 'complete', workdir: a.workdir, report: `${a.workdir}/审查报告.md`, done }
