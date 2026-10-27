#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查规则总表：编号、检查方式、内容域、展开粒度、功能电路与判据的唯一来源。

编号格式为 <内容域>-<方式><序号>，例如 PWR-E01：前三个字母说明查什么，
短横后的字母说明怎么查。在用规则的编号不改；新规则接在所在组最大序号之后，
删除的编号不再登记。计划、Lint、证据校验、结果校验与文档规则表都从这里取规则，不另写副本。

    python3 catalog.py                     打印规则总表（Markdown）
    python3 catalog.py --write-doc PATH    重写文档标记区间内的规则总表（references/bounding-table.md 写定界表，references/review-vocabulary.md 写审查词表）
    python3 catalog.py --check-doc PATH    文档与本表不一致时退出 1
"""
import argparse
import re
import sys
from collections import OrderedDict, namedtuple

Domain = namedtuple('Domain', 'code name scope handoff')
Method = namedtuple('Method', 'code name executor inputs output stage')
Rule = namedtuple('Rule', 'id title criterion source scope')
CircuitType = namedtuple('CircuitType', 'name title domain pattern subjects materials')
RequirementCategory = namedtuple('RequirementCategory', 'name aspects targets when')
RequirementAspect = namedtuple('RequirementAspect', 'name template parameters', defaults=((),))
RequirementParameter = namedtuple('RequirementParameter', 'title unit units')

DOMAINS = (
    Domain('DOC', '图纸与数据', '导出与解析完整性、BOM/库字段、页面图形与命名、装配选项、测试节点、输入一致性',
           '测试点可触达性、邻近地、夹具与 ICT 覆盖'),
    Domain('DEV', '器件与引脚', '料号/封装/符号身份、物理脚与引脚处置、工作条件、应力与降额、连接器定义与载流',
           '特殊封装/摆放要求；PCB 走线载流'),
    Domain('NET', '网络连接', '悬空网、网名分裂、无源孤岛、NC 网络、引脚类型冲突', ''),
    Domain('PWR', '电源', '电源树、电源脚与地脚、地网、变换器/LDO、输入保护与滤波、去耦、纹波、监控覆盖',
           '去耦/储能位置与回路、大电流铜皮、PCB 压降与载流、散热与实测温升'),
    Domain('RST', '启动与复位', '使能、strap/启动配置、复位链与时序、IO 默认态、看门狗、上电顺序与恢复',
           '上电/掉电单调性与台阶实测'),
    Domain('CLK', '时钟', '晶体负载与起振、有源时钟、RTC', '晶振回路寄生、起振裕量与时钟走线'),
    Domain('SIG', '接口与信号', '逻辑电平与驱动、掉电注入、时序、各类总线与接口、差分链路、调试口、主控引脚分配',
           '阻抗、等长、间距、回流、过孔、stub 与防护器件摆放顺序'),
    Domain('ANA', '模拟与监测', '运放、ADC、基准、检测与监测链、温度传感', '传感器摆放与热路径'),
    Domain('PRO', '防护与隔离', 'ESD/TVS/浪涌防护链、钳位窗口、熔断器协调、隔离与光耦、对外连接器防护',
           '防护器件靠近连接器、实际爬电距离与电气间隙'),
    Domain('DRV', '功率驱动', '功率管栅极驱动、SOA、开关节点吸收、感性负载续流钳位',
           '换流/钳位回路面积、结温与散热'),
    Domain('REQ', '需求与闭环', '需求追溯、关键器件与功能存在性、功能电路与覆盖审计、改版与历史意见闭环', ''),
)

METHODS = (
    Method('A', '自动扫描', '脚本', '网表；关键器件计数另需意图', '疑点 FINDING / 候选 CANDIDATE / 提示 INFO',
           '网表扫描两趟都执行'),
    Method('E', '保证值核对', '审查者', '网表、规格书保证值与资料审计', '逐项结果',
           '专家审查：网表定出对象，按两端规格书保证值核数值窗口，缺保证值即资料不足'),
    Method('T', '连接追踪', '审查者', '网表、图面、装配与状态表', '逐项结果',
           '专家审查：逐跳追源、负载、使能与返回路径'),
    Method('C', '工程计算', '审查者', '资料保证值、公差、工况与需求', '逐项结果',
           '专家审查：按最坏工况复算窗口、裕量与应力'),
    Method('D', '条款核对', '审查者', 'datasheet、errata、平台规范、需求', '逐项结果',
           '专家审查：逐条对照官方条款与需求；器件身份在资料取证时先做'),
    Method('V', '图面目检', '审查者', '原理图 PDF', '逐项结果', '图面目检：每页留记录'),
    Method('Q', '覆盖审计', '审查者', '计划、结果台账与覆盖记录', '逐项结果', '报告前核对覆盖是否完整'),
    Method('H', '版本比对', '脚本 + 审查者', '新旧网表、旧计划与历史意见断言', '疑点与逐项结果',
           '复审时执行'),
)

SOURCES = {
    'lint': 'Lint 内置',
    'plan': '计划逐对象生成',
    'subject': '功能电路检查项',
    'board': '全板通用',
    'interface': '接口逐个生成',
    'system': '系统功能（有对象才生成）',
    'owned_parts': '逐电路的自有器件',
    'revision': '改版比对',
    'i2c_topology': '检查器·I²C 连接覆盖',
    'decoupling': '检查器·去耦覆盖',
    'inductive_load': '检查器·感性负载钳位',
    'power_switch': '检查器·功率开关',
    'input_filter': '检查器·开关电源输入滤波',
    'power_up': '检查器·上电使能与压差',
    'supervision': '检查器·监控与看门狗',
    'diff_levels': '检查器·高速差分电平',
    'optocoupler': '检查器·光耦',
    'passive_stress': '检查器·通用阻容应力预判',
}

# 展开粒度：一条规则在计划中按什么对象逐项生成。
SCOPES = {
    'input': '输入文件',
    'board': '全板一次',
    'page': '逐页',
    'net': '逐网络',
    'pin': '逐引脚',
    'device': '逐器件',
    'rail': '逐电源轨',
    'link': '逐链路/区域',
    'circuit': '逐电路×工况',
    'interface': '逐接口',
    'owned_parts': '逐电路的自有器件（另一项收未归属器件）',
    'circuit_type': '逐功能电路',
    'assembly': '逐装配配置',
    'requirement': '逐需求',
    'history': '改版基线',
}

RULES = (
    # DOC 图纸与数据
    Rule('DOC-A01', '网表导出错误或中止',
         '导出日志出现 ERROR 或中止记录；先隔离为输入阻断，残留文件不能证明当前版本有效', 'lint', 'input'),
    Rule('DOC-A02', 'No-Connect 属性被忽略',
         '导出日志中被忽略并强行连线的 No-Connect 属性，逐条核对实际网络', 'lint', 'input'),
    Rule('DOC-A03', 'BOM/库字段首尾空白',
         'PART/VALUE/JEDEC/primitive 字段含首尾空白，会破坏 BOM 与版本比对', 'lint', 'device'),
    Rule('DOC-A04', '位号未标注',
         '位号含 ? 或缺序号，无法定位、对账与追溯；导出前必须完成标注', 'lint', 'device'),
    Rule('DOC-T01', '装配选项一致性',
         '逐装配配置核 0Ω/跳线/不贴选项：互斥件不同时贴装，每种配置的供电、信号与配置通路完整，'
         'BOM 选项表与图面标注一致', 'plan', 'assembly'),
    Rule('DOC-D01', 'BOM 值字段笔误',
         'BOM 值字段无异常字符串（如 4.7F），数值、单位与器件类型一致', 'board', 'board'),
    Rule('DOC-D02', '测试节点电气预留',
         '关键电源轨、strap 点与调试信号按需要电气预留测试节点；可触达性、邻近地与夹具另交 HANDOFF',
         'board', 'board'),
    Rule('DOC-V01', '页面图形目检',
         '目检极性、方向、pin1、Option/NC 表和图形语义；页间连接符与层次端口的名称、方向一致；'
         '原生图面功能脚名、标签和关键注释可可靠辨认，真实墨迹重叠/遮挡造成混读记独立可读性缺陷；'
         '邻近或边界框相交本身不判FAIL，疑点用原生局部图核实；连接正确不关闭可读性缺陷', 'plan', 'page'),
    Rule('DOC-V02', '图纸卫生',
         '页面注释与实贴 BOM 一致（注释是意图，BOM 是现实，两者都核），换方案残留的命名与注释已清理；'
         '网络命名与实际电平、功能一致（如 DBG_*_3V3 实为 1.8V 属误导）；图框信息与 PDF/网表版本一致',
         'board', 'board'),
    Rule('DOC-Q01', '输入一致性覆盖',
         '核对本轮输入版本、哈希、导出完整性与装配配置；网表、PDF 与 BOM 之间'
         '已证矛盾判FAIL，缺数据或无法可靠解析记证据不足；文件哈希一致不替代内容一致；严格自检只因功能名/类型覆盖不足失败、'
         '编号与归网已核实时记证据不足并写明已证实范围，库符号缺陷归 DEV-D04，不判本项 FAIL',
         'plan', 'input'),

    # DEV 器件与引脚
    Rule('DEV-A01', '电容耐压低于轨名电压',
         '电容 BOM 值里写明的耐压低于按网名推断的电压；网名只是线索，降额规则按项目定', 'lint', 'device'),
    Rule('DEV-A02', '极性电容方向反接',
         '按 +/- 脚名判别：+ 脚接已知地而 - 脚接命名电源轨即为反接；无极性脚名的按图面目检', 'lint', 'device'),
    Rule('DEV-A03', 'LED 无限流元件',
         'LED 两脚直接跨接命名电源轨与已知地，通路上没有串联电阻；恒流驱动须有资料或声明证据',
         'lint', 'device'),
    Rule('DEV-E01', '符号引脚映射',
         '逐脚核对连接器符号与官方/对端 pinout；多排排针/跳线座的配对与档位按封装焊盘坐标或符号图形读取，'
         '不按编号习惯推测', 'plan', 'device'),
    Rule('DEV-C01', '器件应力与降额',
         '受应力的电阻、电容、开关与稳压器逐颗核功耗、连续/脉冲电压、电流及适用温度条件下的额定值；'
         '本项核过应力（应力上界对额定）；IC 脚经外接电阻驱动内部开关或检测通路（放电、泄放、驱动、检测脚）时，'
         '按外部节点最高电压与外接电阻最小值核脚电流不超手册上限，逐脚补查 DEV-C01.<IC位号>-<脚名> 并由所在的 DEV-C01 项以 split_out 拆出；'
         '供电或输入整个窗口确定低于推荐工作范围下限时，与 DEV-C05 同判 FAIL、共用 finding，理由引用 DEV-C05.<位号>；'
         '下限是否满足取决于未知压降或参数时，本检查项不因下限判 INSUFFICIENT，归 DEV-C05；'
         '连接器/排针/按键触点连续（有效值）电流 ≤25 mA 且电压 ≤6 V 时按 commodity-floors 微应力判 PASS(B)，信号边沿瞬态电流不计；'
         '连接器库名/封装名指向具体原厂系列或料号（如 JST_VH、MKDS、XT30UPB）时按该系列原厂触点额定定界，'
         '≤50% 判 PASS(B)，“须采购该原厂系列”归 DEV-D04，不因无 MPN 记 INSUFFICIENT；泛称排针/间距不适用；'
         '先按用途和受控采购范围定界：有适用最弱档时，应力上界不超过其50%可判PASS；'
         '超过且仍可选到满足档位时写最低额定约束，不当作已满足；无适用范围不借用最弱档；'
         '计划已生成逐颗预判检查项（proposal）的器件按该检查项计算判定，改判只用其封闭理由码；'
         '陶瓷电容与功率电感优先按commodity-floors的独立可订购额定/BOM约束分支判断，'
         '满足该分支全部适用条件时可判局部PASS，采购字段仍由DEV-D04核对，不以普通最弱档路径重复阻断；'
         '降额取项目规则，缺规则时按标明的假设判定，假设取值会改变结论时转需求澄清；'
         '电位器按实际分压/rheostat接法核活动轨段、滑臂与端点，不能把整轨功率额定用于任意局部轨段；'
         '按wca-formulas的适用模型全范围核轨电流、局部功耗及滑臂/脉冲限制，未选实际器件不借候选或通用最弱档放行；'
         '实际温升与散热实现转 HANDOFF，不以缺热测试判电气缺陷',
         'owned_parts', 'owned_parts'),
    Rule('DEV-C02', '电容有效容量与寿命',
         '按电容实际用途核耐压与容量；仅当该用途的原厂条款或受控需求依赖有效容量/ESR时索取对应边界，'
         '不能给所有旁路、BOOT或SS电容统一加联合Ceff/ESR证明；'
         '电解、固态与超级电容的寿命按 intent.mission_profile 估算所需耐久等级（厂家寿命公式，没有就 10 °C 翻倍，都标估算），'
         '写成 bom_constraint“耐久 ≥ X h @T（估算，热点 ≤ Y °C）”，不开厂家数据缺口；热点温度与纹波自热移交热设计实测后复算',
         'owned_parts', 'owned_parts'),
    Rule('DEV-C03', '精度器件选择',
         '分压、采样、ZQ 等精度要求由允许误差窗口与器件要求决定，不能默认 1% 即合格；'
         '按实际误差传递及适用角点核本项，不用无关热、载流或接口接受任务替代精度判据；'
         '这些条件只有真实改变该误差窗口时才成为本项关闭依赖，其余另按适用规则核对', 'owned_parts', 'owned_parts'),
    Rule('DEV-C04', '连接器载流',
         '按实际并针降额、接触电阻/均流、线缆与故障电流核连接器载流，不能按单针额定乘针数放行；'
         '额定取实际采购系列的资料，只有间距或泛称时不借用他厂系列额定或“通常”值放行，按范围未定处理；'
         'PCB 走线载流另交 HANDOFF', 'interface', 'interface'),
    Rule('DEV-C05', '推荐工作条件覆盖',
         '逐颗核供电电压、输入电压、负载、频率及温度等级/参数保证条件覆盖声明工况；'
         '区分环境温度、壳温与结温，形成允许温度约束，实际结温实现转 HANDOFF；'
         '借用相似器件保证范围或典型±30%估算可用于必需功能和性能判据（含P1，P1时整个范围内结论不变，并把样机实测记为必需移交），不能据此放行损坏边界、过热或保护保证；'
         '本器件或受控身份全分支均适用的保证边界仍可按实际判据核对，不属于借相似器件估算；'
         '供电/输入低于推荐范围下限在本项判定（整个窗口确定欠压时 DEV-C01 同判 FAIL 并共用 finding）；绝对最大额定只作损坏边界，不当作工作范围',
         'plan', 'device'),
    Rule('DEV-C06', '耗损件寿命',
         '有寿命需求时，按 intent.mission_profile 逐颗核耗损件（WEAROUT_CLASSES：电池、光耦、LED、压敏电阻、保险丝、浪涌限制 NTC、'
         '自恢复保险丝、继电器、连接器与开关、Flash/EEPROM）的寿命；按次数核的类别，需求与剖面都没给次数时记 NA 并写明，不开缺口项；'
         '结论写成选型或 bom_constraint；参数漂移并入精度预算，绝缘老化归隔离检查，热循环、焊点疲劳和衰减实测记阶段 NA 并移交',
         'plan', 'device'),
    Rule('DEV-D01', '器件身份与封装',
         '核对实例 MPN/BOM、符号引脚、封装字段、参数档位和替代兼容性；符号缓存来源名不独自证明实际采购身份冲突', 'plan', 'device'),
    Rule('DEV-D02', '官方物理脚差集',
         '官方物理脚与符号声明/网表实有脚双向差集，含未连/EP/隐藏电源；'
         '已取得准确完整针表并核实对应映射时，不以无关载流额定或尚未选定外部设备阻断该差集；'
         '实际缺针图或映射仍留缺口，额定、端点兼容及其他输入资格分别按适用判据核对；'
         '计划按两端子快速通道给出空差集（pin_difference 写明依据）时直接判 PASS，不再索取官方针图', 'plan', 'device'),
    Rule('DEV-D03', '连接器对端定义',
         'pinout 与对端定义逐针核对（板内自洽不等于对端正确）；防误插与 pin1 标识按平台规则', 'interface', 'interface'),
    Rule('DEV-D04', '库与物料卫生',
         '实际实例采购字段、BOM 参数与原厂 MPN 订货组合一致，包含关键无源件；'
         '已证实的物料/参数/资料冲突判本项FAIL，典型值或测试条件不得改称额定保证；'
         '需选料的最低额定汇总为BOM约束，并按误选的最严重可信后果定级；'
         '候选身份不得冒充已核准；沿用库按实际 MPN/封装/符号版本验证兼容映射，缓存来源名不单独视为采购冲突', 'board', 'board'),
    Rule('DEV-D05', '引脚处置',
         '按官方脚表逐脚核未用与特殊引脚：输入不悬空；NC/DNU 按手册处理，不随意接网；未用电源脚按平台规范'
         '悬空、接地或关闭；未用运放/比较器通道输入钳定、输出不短接到轨；连接器未用针按平台规则；'
         '未用不等于可以悬空', 'plan', 'device'),
    Rule('DEV-Q01', '资料覆盖',
         '全部关键器件适用章节/errata及官方物理脚双向差集已审', 'plan', 'board'),

    # NET 网络连接
    Rule('NET-A01', '单节点悬空网',
         '网络只有一个节点且不在白名单（被删外设的 SoC 引脚、自动中间网）', 'lint', 'net'),
    Rule('NET-A02', '疑似网络名分裂',
         '相邻网络名叶名相似度超过 90%（只差下划线或后缀），疑似拼写分裂；同族总线、差分对（_P/_N、+/-）、'
         '序号与字母序兄弟、收发对（RX/TX、MISO/MOSI、SCL/SDA）、同名双路（FB_12V/FB_5V）与'
         '工具按引脚自动生成的网名（KiCad Net-(…)/unconnected-(…)、Allegro N######）除外',
         'lint', 'net'),
    Rule('NET-A03', '自动命名无源孤岛',
         '自动编号网络上只挂无源件（无 U/J/M/Y），疑似中间节点悬空', 'lint', 'net'),
    Rule('NET-A04', 'NC 网络判别',
         '名为 NC/NC_* 的多节点网络先按判别式区分：带层次路径的是设计者画出的真实短接（疑点）；'
         '导出器的 No-Connect 汇集网不构成短接（提示）；已确认继电器 NC/COM/NO 常闭触点角色、'
         '各触点网络独立且仅接连接器或同类触点时，不将 NC 名称视为未连接脚短接（继电器类型只凭型号/库名关键词、'
         '未经手册声明核验时列候选）；准出前仍需图面或属性证据，触点额定值另审', 'lint', 'net'),
    Rule('NET-A07', '声明输入脚悬空',
         '引脚类型为输入的脚没有网络或只在单节点网上；标了 No-Connect 的输入脚作候选。'
         '明确器件角色为无源连接器且已标 No-Connect 的未用接触针不要求片内偏置；'
         '豁免须有核验器件声明或各已填型号/符号/值字段一致的连接器身份，'
         '不能只按位号或混合文本关键词豁免；有源脚义或封装冲突须审查，'
         '保留身份冲突、未知/IC输入、未标明的悬空及连接完整性检查',
         'lint', 'pin'),
    Rule('NET-A06', '引脚类型冲突',
         '多个输出脚直连为疑点；全输入网络、GROUND 类型脚未接已知地网为候选；开漏/三态等合法结构逐条排除',
         'lint', 'net'),

    # PWR 电源
    Rule('PWR-A01', '电源轨无驱动',
         '命名电源轨沿已装配通路追不到输出脚或声明的外部来源', 'lint', 'rail'),
    Rule('PWR-A02', '电源脚无驱动',
         '含 VDD/VCC/AVDD/DVDD/VBAT 功能名的电源脚无网络，或所在轨无驱动来源；'
         '非地名的原生 power_in 脚直接落在地网上（VDD 接地）', 'lint', 'pin'),
    Rule('PWR-A03', '地脚未入地',
         '功能名为 VSS/AVSS/DVSS 的脚不在已知地网；IC 地脚所在的地名网（GNDA、AGND、Net-(U1-GND) 等）'
         '经已装配直流连接件（电阻/电感/磁珠/跳线/保险、NetTie、共模扼流，电容不算）到不了主地，'
         '孤岛上又无连接器、已知隔离器件或 SENSE 遥测线（地名网孤岛）；同一 IC 或其他多端器件跨两地时为候选',
         'lint', 'pin'),
    Rule('PWR-A04', '同基名多轨',
         '同一基名对应多条电源轨（如 VCC_3V3 与 VCC_3V3_SOM），确认监测与供电对象没有张冠李戴', 'lint', 'rail'),
    Rule('PWR-A05', '输入串联滤波无阻尼元件',
         '开关稳压器输入经串联电感/磁珠滤波，但既无 RC 阻尼支路也无体电容候选', 'input_filter', 'device'),
    Rule('PWR-A06', '存在未被监测的电源轨',
         '已识别监控器时，给 IC 供电的轨既无 sense 脚也无到 sense 的分压', 'supervision', 'rail'),
    Rule('PWR-E01', '分压窗口验算',
         '仅对实际电阻分压反馈/监控模型，按电阻与适用 Vref 公差验证窗口；光耦电流或数字设定另用实际传递模型', 'plan', 'pin'),
    Rule('PWR-E02', '线性稳压最坏压差',
         '按最低输入电压与声明温度/负载范围内的保证最大压差核输出下限；最坏温度取器件保证条件，不预设为最低温度', 'power_up', 'device'),
    Rule('PWR-E03', '输入滤波阻尼',
         '按最低输入电压与最大输入功率求负输入阻抗，核体电容 ESR 与滤波电感的一阶阻尼'
         '判据及体电容/输入电容比值（比值须由项目规定，不得默认）', 'input_filter', 'device'),
    Rule('PWR-T01', '电源轨拓扑',
         '确认电源轨驱动源、负载、域电压、时序与反灌路径', 'plan', 'rail'),
    Rule('PWR-T03', '去耦连接覆盖',
         '逐物理脚核对本状态分组、返回节点、直接连接电容和装配；保留零电容/不贴/未知项，不跨串联边界，不判断电气合格',
         'decoupling', 'device'),
    Rule('PWR-T04', '逐电源域监控覆盖',
         '按需求确定哪些电源域必须监测，逐轨核监测点、阈值与动作；'
         '未监测的轨需给出书面依据，不能因为有一颗监控器就判全板覆盖', 'supervision', 'rail'),
    Rule('PWR-T05', '防反接与理想二极管',
         '防反接电路（MOSFET 理想二极管/二极管）的导通方向、体二极管朝向与栅极钳位', 'subject', 'circuit'),
    Rule('PWR-T06', '地网划分与连接',
         '列出全部地网（数字、模拟、功率、机壳/保护地、隔离地），核连接点位置与方式（直连、0Ω、磁珠、RC/电容）'
         '符合器件与平台要求；不同地网不因名称相近而视为同一网', 'system', 'board'),
    Rule('PWR-C01', '电源轨功率预算',
         '按最大负载、电压范围与器件能力验证功率预算和裕量；'
         '负载手册按工作模式列电流时取所列最重模式的最大值（只有典型值取典型×1.3）定界，需求声明超出所列模式的负载才另算，'
         '不向设计方索取逐模式或最高时钟预算', 'plan', 'rail'),
    Rule('PWR-C02', '变换器电压裕量',
         '在要求调节的 Vin/负载/温度状态核对输出窗口与负载范围；线性稳压器最坏压差由 PWR-E02 查，允许关断/保护时另核安全与恢复',
         'subject', 'circuit'),
    Rule('PWR-C03', '变换器电流应力',
         '按实际拓扑核电流应力：开关变换器查电感峰值/RMS、Isat 与限流；线性/跟随器查偏置与负载能力，不强加储能电感模型', 'subject', 'circuit'),
    Rule('PWR-C04', '变换器时序与输出电容条件',
         '开关变换器核最小导通/关断时间和Cout适用条件；反馈模型与补偿独立归PWR-C15，不能由峰流或吸收应力关闭；线性电路按实际条件查，不强加 PWM；'
         '原厂明确不要求Cout维持稳定且实际条件满足其条款时，可仅对本体稳定性判PASS，不能关闭独立电容额定或反向能量；'
         '仅凭典型应用等效的路径可用于必需功能和性能（P1时另记样机验证移交），不能放行损坏/保护保证；'
         '允许失调节的故障/关断状态查动作与恢复', 'subject', 'circuit'),
    Rule('PWR-C05', '损耗与反向电流',
         '核对声明工况下的损耗、反向电流、预偏置与放电路径，输出损耗边界与允许温度约束；'
         '实际结温、散热路径及闭壳温升转 HANDOFF，缺下游热数据不推翻已有电气结论', 'subject', 'circuit'),
    Rule('PWR-C16', '待机与空载输入功耗上界',
         '需求给了待机功耗或静态电流时，按各级变换器的空载损耗（手册空载/轻载输入功率或开关损耗与偏置电流）、偏置与监控电路的静态电流'
         '和指示/泄放电阻的损耗算输入功耗上界，与需求窗口比较；没有数据的级按手册典型值×1.3 定界并写明；需求没给这个量时不生成本检查项', 'system', 'board'),
    Rule('PWR-C15', '反馈模型与补偿资格',
         '按实际拓扑独立核反馈模型、补偿配置及规定角点的稳定性/动态边界；内部补偿也须匹配厂家适用条件，'
         '无反馈环的电路可据实际拓扑判NA；峰值电流、RCD或栅极应力不能代替本项，样机Bode测试不代替原理图补偿条件', 'subject', 'circuit'),
    Rule('PWR-C06', '保护门限',
         '存在主动门限时核 UVLO/OVLO/限流容差、检测目的与采样侧；被动输入按保险丝/MOV/NTC 等实际保护协调查，'
         '不强加检测使能链；连续电流、限流、快断与热保护不能互代', 'subject', 'circuit'),
    Rule('PWR-C09', '去耦容量',
         '按本状态器件条款分别核对直接供电/返回段的数量、容量组合及有效容量要求；串联边界另一侧电容不计本段；替代接法需适用依据，标称总量不代替保证容量',
         'decoupling', 'device'),
    Rule('PWR-C10', '去耦电容额定',
         '按受控电容规格与工况核耐压/降额及适用 ESR；依赖具体型号特性时核实际料号，不从封装或轨名猜参数；'
         '计划带预判（proposal）时按预判判定，改判只用其封闭理由码；ESR 只在器件条款或稳定性判据要求时核', 'decoupling', 'device'),
    Rule('PWR-C11', '输入滤波元件',
         '核滤波元件的饱和电流、RMS 电流与手册温升电流额定及其测试/降额条件、直流压降、损耗与所需衰减量；'
         '额定温升电流不证明板上实际温升，实际温升转 HANDOFF；'
         '截止频率与开关频率的关系按 EMC 需求确认，不以有磁珠即判合格', 'input_filter', 'device'),
    Rule('PWR-C13', '热插拔浪涌与输入电容',
         '按实际接口/输入方式核浪涌与源端能力；有明确平台电容限制时对照该限制，不默认热插拔或模板电容上限', 'subject', 'circuit'),
    Rule('PWR-C14', '纹波与噪声预算',
         '逐供电接口生成：轨的负载里有敏感功能电路（ANALOG、CLOCK、RF）时每条轨一项，不随变换器生成；按敏感负载（PLL、ADC、RF、基准）的电源噪声/PSRR 要求核纹波与噪声预算，含开关频率、后级 LDO/滤波与去耦；'
         '实测另交 HANDOFF', 'interface', 'interface'),
    Rule('PWR-D01', '去耦清单完整性',
         '结合完整器件/官方物理脚清单核对供电脚与去耦分组覆盖；无名称命中不代表不适用', 'decoupling', 'board'),
    Rule('PWR-D02', '去耦接法',
         '按准确器件条款核对本组实际电源脚、直接供电/返回段和串联边界；无直接电容须核适用替代接法，不用普通旁路证明专用滤波组；同网电容不证明布局充分', 'decoupling', 'device'),
    Rule('PWR-D03', '预偏置与软启动',
         '核同步变换器的预偏置启动支持与软启动配置：资料是否明确支持预偏置、'
         '软启动时间与输入浪涌/限流的配合', 'power_up', 'device'),

    # RST 启动与复位
    Rule('RST-A01', '使能脚上下拉待复核',
         '使能网（按网名或引脚名识别）上有上拉/下拉时列候选，核有效极性与脚耐压；已有对应证据的网络交保证值核对',
         'lint', 'net'),
    Rule('RST-A02', '使能/复位与供电轨同时建立',
         '器件的使能/复位输入与其自身供电脚同网，随电源同时建立', 'power_up', 'device'),
    Rule('RST-A03', '使能直连输入轨无 UVLO/延时',
         '稳压器使能脚直连自身输入网，无分压或 RC', 'power_up', 'device'),
    Rule('RST-A04', '使能来源不确定',
         '稳压器使能网上既无驱动源，也无分压、RC 或上/下拉；器件内部上/下拉需资料证据', 'power_up', 'device'),
    Rule('RST-A05', '喂狗输入悬空或固定电平',
         '已识别的喂狗输入悬空或直接接电源/地，需确认是否有意禁用', 'supervision', 'device'),
    Rule('RST-A06', '复位/看门狗输出未到复位输入',
         '输出网不含功能与接收方向均已确认的复位输入脚；网上无其他器件为疑点，只接到其他脚为候选', 'supervision', 'device'),
    Rule('RST-E01', '使能极性与耐压',
         '核对 EN 有效极性、默认态、上拉轨与绝对最大额定', 'plan', 'pin'),
    Rule('RST-E02', 'strap 强制态',
         '核对 BOOT/strap/test 引脚的强制态与采样窗口', 'plan', 'pin'),
    Rule('RST-E03', '复位脉宽',
         '按保证值核复位输出最小脉宽不低于目标复位输入要求；开漏输出须有上拉且电源域正确', 'supervision', 'device'),
    Rule('RST-T01', '使能来源确定性',
         '核使能来源在上电、掉电与故障恢复下的确定性：来源形态、UVLO/迟滞窗口、'
         '延时与被供电器件的要求顺序；使能脚耐压与所接轨按绝限核', 'power_up', 'device'),
    Rule('RST-T02', '复位链与喂狗',
         '逐跳核复位链：输出类型与上拉电源域、极性、到每个复位输入的连通、'
         '喂狗来源在启动期与固件异常时的行为，以及手动复位/去抖接法', 'supervision', 'device'),
    Rule('RST-T03', '上电顺序与恢复',
         '检查慢爬升、棕断、短暂掉电、单域掉电、外部先供电、重试及恢复模式', 'system', 'board'),
    Rule('RST-T04', '复位期间 IO 默认态',
         '核主控与外设在断电、复位、启动配置采样与固件接管前的 IO 默认态（高阻、内部上下拉、默认输出）'
         '对继电器、电源使能、驱动器、LED 与外部总线的影响；关键控制线在适用状态下须有保证的安全默认态，内部偏置或外部电路均须有据；'
         '断电或 IO 电源域未建立时内部偏置通常不存在，该阶段须由外部电路保证',
         'subject', 'circuit'),
    Rule('RST-C01', '采样窗口电平',
         '逐采样窗口计算 strap/EN 保证电压，含内部拉阻、LED、泄漏、电容和门限；'
         '带 state 的检查项只判该状态窗口内要求或被采样的电平，其他窗口的采样归对应状态检查项、RST-D01 或需求检查项', 'subject', 'circuit'),
    Rule('RST-C02', '复位时序',
         '按 V(t) 穿越门限时刻核对复位脉宽/释放与采样 setup/hold，不能以 RC 时间常数代替', 'subject', 'circuit'),
    Rule('RST-D01', '救砖通道',
         '可编程平台按实际恢复需求核编程/救援通道、进入条件与电平；'
         '硬件阶段核受控配置意图和硬件支持，最终烧录/回读回执移交上电前集成，不单以缺后期回执阻断；'
         '保护配置或协议能力未明确的真实缺口仍保留；不统一要求电源 IC 具备 Recovery/Maskrom', 'subject', 'circuit'),

    # CLK 时钟
    Rule('CLK-C01', '晶体负载与起振',
         '按晶体准确料号核对 CL/ESR/驱动功率、振荡器适配和起振条件，反馈电阻、串联电阻按 datasheet/参考设计取值；'
         '寄生及实测裕量转 HANDOFF', 'subject', 'circuit'),
    Rule('CLK-D01', '有源时钟输出与使能',
         '有源时钟输出幅度/电源域、使能态和上电有效时间', 'subject', 'circuit'),
    Rule('CLK-D03', 'RTC 晶体与备份电源',
         '按实际 RTC 的时钟源、频率/负载要求及模式核晶体或外部时钟，不默认固定频率；备份电池/超级电容的充电电压/电流不超器件上限，反向电流符合器件要求', 'subject', 'circuit'),

    # SIG 接口与信号
    Rule('SIG-A01', '交流耦合发送端无直流通路',
         'LVPECL/PECL 类电平交流耦合，发送侧无到地/到轨的直流通路；声明依据出疑点，名称线索出候选',
         'diff_levels', 'link'),
    Rule('SIG-A02', '交流耦合接收端无偏置/端接',
         '交流耦合后的接收侧既无端接也无偏置', 'diff_levels', 'link'),
    Rule('SIG-A03', 'I²C 线无上拉',
         'SDA/SCL 网（≥2 节点、含 IC 脚）上没有任何接到非地网的已装配电阻；上拉可能由主机侧、片内'
         '（如 TXS 类电平转换器）或其他段提供，按需求与资料确认后关闭，阻值与上升时间另按 SIG-C01', 'lint', 'net'),
    Rule('SIG-E01', '必需上拉与串阻',
         '核对指定两网间电阻装配与等效阻值；电平/上升时间另行检查', 'plan', 'net'),
    Rule('SIG-E02', '差分电平兼容',
         '仅对实际差分数据链路按两端保证范围核电平：充电识别或未启用差分模式另查实际功能；直流耦合时发送共模与摆幅落在接收端共模/差分输入'
         '范围内；交流耦合时核接收端偏置共模、耦合电容与低频截止', 'diff_levels', 'link'),
    Rule('SIG-T01', '差分对连通',
         '核对差分 P/N 两端语义、耦合/端接拓扑和全链路连通', 'plan', 'link'),
    Rule('SIG-T02', 'I²C 连接覆盖',
         '核对本状态 SDA/SCL 物理端点、装配/跳线、全部上拉与电源域、串阻路径及隔离/外接边界；仅连接覆盖',
         'i2c_topology', 'link'),
    Rule('SIG-T03', '差分端接与偏置',
         '核端接与偏置网络的位置、阻值与电源域：差分端接、接收端偏置、'
         '发送端直流通路，以及未用通道与掉电状态的处置', 'diff_levels', 'link'),
    Rule('SIG-T04', '接口方向语义',
         'TX/RX、P/N、Host/Device、Source/Sink 按两端官方语义复述，核对对端连接器视图与线缆针序；连通只证明导电路径',
         'subject', 'circuit'),
    Rule('SIG-C01', 'I²C 灌电流与上升时间',
         '先核所有实际端点的上拉条款及“外部”相对哪颗器件；另一 IC 的真实内建上拉可作为外部实现，'
         '但须证明连接、保证阻值、上拉电源及默认/掉电状态，并明确受控启用条件，不能假设已启用；'
         '原厂明确要求离散上拉或禁止替代时须遵守；固件或降速不能替代不存在的硬件或放宽保证值；'
         '再逐电气段合并全部上拉公差：Rp_min=(Vpullup_max-VOL_max)/IOL_guaranteed，'
         'Rp_max=tr_max/(0.8473*Cb_max)；核对串联压降', 'subject', 'link'),
    Rule('SIG-C03', '总线端接与偏置',
         '按实际总线端点和节点数核对端接等效负载、空闲偏置及接收保证差分门限', 'subject', 'circuit'),
    Rule('SIG-C04', '总线共模与未供电负载',
         '核对收发器 VIO/默认态、总线共模范围、地偏差与未供电负载', 'subject', 'circuit'),
    Rule('SIG-C05', 'USB VBUS 供电与保护',
         '核对 VBUS 供电资格、电压档位、放电、反灌、过流及端口未供电状态；放电外接电阻对片内放电开关的电流上限归 DEV-C01', 'subject', 'circuit'),
    Rule('SIG-C07', '逻辑电平与驱动匹配',
         '先按需求与实际装配拆分本体和外部端点：未指定外部主机、探头或负载且未承诺具体组合或标准兼容时，'
         '读算本体并给出门限、电压、灌电流、漏电、总电容/速率及掉电驱动的定量集成约束；'
         '未知外端数据不自动记证据不足或需求待决，整链子判据按范围记 NA，保留本体判据与真实缺口；'
         '已有指定对端或兼容承诺仍须核两端保证；本体关键参数、身份、低轨/启动默认、供电与反灌缺口'
         '不能由集成约束关闭，不能假定配置已启用；'
         '逐条实际链路核驱动端 VOH/VOL 与接收端 VIH/VIL（含负载电流与温度角）、驱动电流与扇出、上拉轨对所有接收端'
         '门限与耐压的满足情况；开漏端核上拉条款中“外部”的器件边界、真实实现及默认/掉电状态；'
         '另一 IC 内建上拉须按保证阻值与漏电核高低电平，并明确受控启用条件，不能假设已启用；'
         '明确要求离散上拉、禁止替代或已有实现不满足保证条件时，不能以固件配置关闭问题；'
         '跨电压域直连须由两端保证条件证明兼容，不兼容时采用适当转换；转换器方向与使能态明确', 'subject', 'link'),
    Rule('SIG-C08', '掉电与跨域注入',
         '逐域掉电和外部设备先上电时核 Ioff、输入耐压与注入电流限值，找出经上拉、ESD 结构或保护二极管的反灌路径；'
         '跨轨上拉先列候选，再核掉电容忍', 'subject', 'link'),
    Rule('SIG-C09', '时序裕量',
         '按两端保证值核传播延迟、建立/保持、时钟偏斜、电平转换器延迟及上拉/开漏信号的上升时间，给出最坏角点裕量；'
         '主控厂商设计指南明确指定该器件型号、接法与时钟配置且本设计未偏离时，按厂商合格配对判 PASS(B)，'
         '时钟上限等配置作为固件约束移交，不因主控手册缺接口时序记 INSUFFICIENT；换型号/改接法/提高时钟时仍按两端保证值计算；'
         '布线延迟另交 SI HANDOFF',
         'subject', 'link'),
    Rule('SIG-D01', 'I²C 地址与装配组合',
         '核对地址/复用/复位态和板载及外部可选上拉的装配组合', 'subject', 'link'),
    Rule('SIG-D02', 'DDR 校准端接',
         '分别按控制器和 DRAM 的具体型号/代际核对 ZQ/校准脚端接与精度，禁止跨器件套用', 'subject', 'circuit'),
    Rule('SIG-D03', 'DDR 端接与基准',
         '逐数据/地址/时钟/VREF/VTT 电源域核对拓扑、端接、基准及上电条件', 'subject', 'circuit'),
    Rule('SIG-D04', 'USB-C 角色与 CC',
         '按 Source/Sink/DRP 角色及 PD 模式核对 CC/Rp/Rd、方向检测、线缆 VCONN', 'subject', 'circuit'),
    Rule('SIG-D06', '调试接口',
         '按实际调试/烧录要求核 UART/JTAG/SWD 的信号电气引出、串阻与 ESD；接插件机械可触达性及夹具实现移交下游', 'subject', 'circuit'),
    Rule('SIG-D07', 'USB 物理层',
         'REXT、DP/DM 串阻、VBUS 检测、ID 与 ESD 挂在活线上', 'subject', 'circuit'),
    Rule('SIG-D08', '串口与现场总线',
         'UART/RS232/RS485/CAN 的收发器供电与 VIO、STBY/EN 默认态、端接策略（本端/对端书面明确）、空闲偏置、隔离与防护',
         'subject', 'circuit'),
    Rule('SIG-D09', 'SPI 与 SPI Flash',
         'SPI 片选/时钟极性与串阻；SPI Flash 供电域、上拉与写保护', 'subject', 'circuit'),
    Rule('SIG-D10', 'eMMC/SD 接口',
         'eMMC/SD 的 IO 电平、CMD 上拉、CLK/STROBE 串阻与测试节点电气预留；高速测试点与 stub 限制另交 HANDOFF',
         'subject', 'circuit'),
    Rule('SIG-D11', '以太网 PHY 与网变',
         '按实际 PHY、网变、接口模式及 PoE 配置核 MDI 对应、中心抽头与共模端接、MDIO、复位及 strap；外围数值与耐压取适用器件/接口要求，不套固定 Bob Smith 参数',
         'subject', 'circuit'),
    Rule('SIG-D12', '射频与模组',
         '按实际模组要求核天线路径默认通断、供电电容、开关机/复位及适用的 SIM 接口保护；参考设计作依据线索，偏离须按本设计条件验证，不以照抄为通过条件',
         'subject', 'circuit'),
    Rule('SIG-D13', '主控引脚复用与分配',
         '主控/SoC 引脚复用、功能分配与电平域符合平台约束（专用功能脚、启动相关脚、仅输入脚、5V 容忍），'
         '与固件配置表一致，无冲突与重复占用', 'system', 'board'),
    Rule('SIG-D14', '高速串行链路',
         'PCIe/SATA/USB3/SerDes 链路的交流耦合电容位置与容值、极性与通道映射、参考时钟与边带信号'
         '（PERST#/CLKREQ#/WAKE#）按规范连接', 'subject', 'circuit'),
    Rule('SIG-D15', '音视频接口',
         'HDMI/MIPI/LVDS 显示与摄像接口、I²S/编解码器的通道映射，热插拔/DDC/CEC 电平与上拉，'
         'MCLK/帧时钟来源，模拟音频供电与地按规范连接', 'subject', 'circuit'),

    # ANA 模拟与监测
    Rule('ANA-T01', '检测与监测链',
         '存在检测/监测链时先定义被测量与保护目的，再核取样侧、返回地、判决与控制；纯被动保护不强加该链：检测输入存在可取源侧，'
         '验证输出有效或负载电压取保护后；首次使能不能依赖尚未使能的输出，检查循环启动', 'subject', 'circuit'),
    Rule('ANA-C01', '直流范围与误差',
         '分立运放核输入共模/输出摆幅及偏置/失调/增益误差，含供电和温度极限；片内放大器+ADC 通道（检流、NTC 等直接接 IC 检测脚）'
         '按该 IC 手册的通道输入范围与失调/增益误差核，不另列运放子判据', 'subject', 'circuit'),
    Rule('ANA-C02', '动态与负载',
         '分立运放核 GBW/压摆率/容性负载；ADC（含片内）核源阻抗、采样保持获取时间与建立误差；'
         '片内放大器+ADC 通道按手册的输入滤波/源阻抗要求核，不另列运放子判据', 'subject', 'circuit'),
    Rule('ANA-C03', '基准与输入保护',
         'ADC 基准驱动/误差、输入满量程及钳位/注入电流，含掉电状态', 'subject', 'circuit'),
    Rule('ANA-C04', '传感器开短路判别',
         '传感器接控制器检测脚时，按控制器实际可选的偏置电流档/上拉、ADC 满量程或内部钳位，以及产品环境与工作温度全范围'
         '（含传感器、偏置与串并联电阻公差）计算正常读数区间，与开路、短路读数不重叠且留有裕量；偏置只能离散选档时写明'
         '所用档位、切档等待与去抖，单档覆盖不到时不判通过；缺控制器偏置档或环境范围不定判', 'plan', 'pin'),
    Rule('ANA-D01', '温度传感器',
         '温度传感器电气连接、量程和接口正确；传感器摆放与热路径另交 HANDOFF', 'subject', 'circuit'),

    # PRO 防护与隔离
    Rule('PRO-A01', 'ESD/TVS 挂残网',
         'ESD/TVS 器件所在网络节点数少于 2，或不含真实信号端点', 'lint', 'device'),
    Rule('PRO-E02', '钳位器件窗口',
         '跨接轨/信号与地的防护钳位（含电源轨 TVS、芯片脚对地的钳位齐纳和对外连接器信号线上的 ESD 钳位）逐器件核：'
         'VRWM（齐纳取 VZ 下限）不低于该网持续最高工作电压（含公差与纹波，不含瞬态：瞬态时导通是钳位器件的本职）；'
         '瞬态取能到达本节点的那一个：接对外连接器的网按需求的浪涌或 ESD 波形，内部节点按前级钳位后的残压或本地瞬态源'
         '（热插拔、感性关断），没有瞬态源的内部节点只核工作电压与稳态功耗；该瞬态下的钳位电压'
         '（没有就 VBR max）对同网每个器件的最低耐受（IC 脚绝对最大额定、电容耐压、开关管耐压），高于 IC 脚绝限即 FAIL，'
         '除非脚与钳位之间有串联阻抗且算出注入电流在芯片给出的允许范围内；该波形的脉冲能量对器件额定（按本板环境温度降额），器件温度等级覆盖本板环境（防护钳位不另出 DEV-C05）；'
         '型号/轨名只是检索提示，不能证明导通或烧毁',
         'lint', 'device'),
    Rule('PRO-A03', '光耦 LED 回路无限流元件',
         '光耦 LED 两条腿上都没有串联电阻，且未声明恒流驱动', 'optocoupler', 'device'),
    Rule('PRO-A04', '光耦输出集电极无上拉',
         '光耦集电极网上未见外部上拉，且无本状态适用、可定位到接收脚的内部上拉依据', 'optocoupler', 'device'),
    Rule('PRO-E01', '光耦传输能力',
         '按最小正向电流与保证 CTR（初始值）核输出可用电流是否满足上拉与负载要求；同时核最大正向电流不超额定；'
         '寿命末所需的 CTR 保留比例在寿命检查项 DEV-C06 算出并写成约束，本检查项不要求项目衰减系数', 'optocoupler', 'device'),
    Rule('PRO-C01', '防护器件协调',
         'TVS 的 VRWM/VBR/VC 按实际浪涌波形、电流与温度对照后级绝限；熔断器/PTC 的额定、时间电流与熔断能量按项目'
         '降额核对；熔断器另核额定分断能力不低于安装点预期短路电流（插墙一次侧无项目值时按 IEC 60127 H 档 1500 A，'
         '依据见 verdicts-and-release），只保证低分断档（如 100 A）判 FAIL；按实际保护链逐段核动作电压、时序与能量配合，不强制包含 GDT/TSS、ESD、端接或隔离的固定级联；缺工况不定判', 'subject', 'circuit'),
    Rule('PRO-C02', '阈值型保护双侧窗口',
         '保护门限脚（FAULT/OVP/UVLO/OCP/OTP 等）、门限链与基准/电平齐纳、跨开关节点或绕组的能量钳位逐对象两侧核算（跨网与地的防护钳位归 PRO-E02）：不误动作侧取正常工况被测量最大值'
         '（全部输出档位、瞬态与上电/掉电、公差、温度、漏电，含峰值整流或滤波捕获的尖峰；一次取一个瞬态）对门限最小值，'
         '两边按同一温度角点配对，各项已按最坏取值时零余量即满足；动作有效侧取需求内'
         '故障量对门限最大值，核执行、剩余能量及适用的保持/复位；门限脚计入接收端内部钳位吸流；栅源稳压管等正常驱动中允许限幅的器件，不误动作侧核不妨碍规定导通及钳位电流/功耗；正常及要求无损恢复的工况满足额定，允许破坏性安全失效的工况按受控安全判据关闭；峰值短暂越门限可用有据的滤波/消隐及波形证明不形成有效触发；只核一侧或缺决定性工况不定判', 'plan', 'device'),
    Rule('PRO-D01', '光耦隔离与耐压',
         '核隔离两侧的网络归属、参考地、跨接器件与耐压，以及输出侧速度/负载条件；'
         '爬电距离与实际隔离距离另交结构与版图', 'optocoupler', 'device'),
    Rule('PRO-D02', '隔离带跨接',
         '跨隔离带器件与网络归属及跨接用途；元件工作电压与绝缘资格独立归PRO-C03；实际爬电距离另交 HANDOFF', 'subject', 'circuit'),
    Rule('PRO-C03', '隔离器件工作条件与资格',
         '逐个跨隔离器件核实际工作电压、重复峰值/频率、绝缘类别和厂家资格适用条件；耐压试验数值或无直流跨接'
         '不能代替工作资格。缺少元件选型前提保留原理图缺口，实际PCB/机构距离与实物耐压另验', 'subject', 'circuit'),
    Rule('PRO-D03', '对外连接器防护',
         '对外连接器逐针考虑防护，ESD 器件挂在活线上，泄放路径接到对应的地；钳位器件的工作与钳位电压对被保护脚的数值核算归 PRO-E02；板内互连器件可按依据判不适用', 'interface', 'interface'),

    # DRV 功率驱动
    Rule('DRV-A01', '感性负载无续流/钳位路径',
         '开关驱动的线圈/绕组在该装配状态下无续流二极管、TVS/齐纳、RC 或有据的集成钳位', 'inductive_load', 'device'),
    Rule('DRV-A02', '续流二极管方向接反',
         '续流二极管阴极在开关节点、阳极在电源轨', 'inductive_load', 'device'),
    Rule('DRV-A03', '栅极无驱动源且无下拉',
         '分立开关管栅极网上既无驱动输出/外接驱动，也无下拉或上拉电阻', 'power_switch', 'device'),
    Rule('DRV-A04', '开关节点无吸收/钳位',
         '开关节点接感性元件或半桥对管，但无 RC/RCD/钳位', 'power_switch', 'device'),
    Rule('DRV-E01', '栅源驱动窗口',
         '仅对需保证导通能力的 MOS 开关核驱动与绝限：所需栅压取 RDS(on) 保证条件，或按本型号输出/转移曲线在实际电流与温度下证明够用的栅压（测试 VGS 不是硬门槛）；线性/源极跟随器按工作点、输出范围及 SOA 查，'
         'BJT 按基极驱动与 VBE/VCE 查，不套 RDS(on)；上电/故障/高阻态按实际角色确定', 'power_switch', 'device'),
    Rule('DRV-T01', '钳位拓扑与方向',
         '核对本状态该感性负载的续流/钳位路径是否存在、方向是否正确、钳位器件是否贴装；'
         '驱动器内部钳位须有资料证据，网名或型号不构成结论', 'inductive_load', 'device'),
    Rule('DRV-C01', '钳位器件额定',
         '仅对被切换感性负载按关断电流与电源最高电压核钳位额定；共模滤波和变换器磁件另按实际拓扑查：反向耐压、峰值/重复电流、'
         '钳位电压加电源电压不超过开关器件耐压、重复频率下的耗散', 'inductive_load', 'device'),
    Rule('DRV-C02', '功率管 SOA 与降额',
         '按器件与工作方式核驱动、应力及适用 SOA：BJT 查基极能力与 VBE/VCE，线性管查工作点，MOS 开关查电流/电压/脉宽/栅偏；保护管另核故障计时、热态降额与'
         '重复重试能量；不能只用 I²·RDS(on) 代替 SOA，重复脉冲与单次脉冲分别核；'
         '借用相似器件保证范围或典型±30%估算可用于必需功能和性能判据（含P1，P1时整个范围内结论不变，并把样机实测记为必需移交），不能据此放行绝限、过热或保护保证；'
         '本器件或受控身份全分支均适用的保证边界仍可按实际判据核对，不属于借相似器件估算；'
         '明确 SOA 的起始温度/壳温条件并形成约束，实际热路径与温度验证转 HANDOFF，不能把室温曲线当全温保证', 'power_switch', 'device'),
    Rule('DRV-D01', '开关节点吸收与驱动条款',
         '核开关节点尖峰与振铃：吸收/钳位网络的存在、参数与耗散，'
         '死区、自举欠压、负压与短路软关断按驱动器条款逐项核', 'power_switch', 'device'),

    # REQ 需求与闭环
    Rule('REQ-A01', '关键器件计数',
         '按需求定出的关键器件清单（intent.expect）核对数量（该有的写 ≥1，该删的写 0）；缺清单时不执行并列入未执行', 'lint', 'board'),
    Rule('REQ-A02', '要求的功能未检出',
         '验证需求要求的功能是否已在原理图中实现', 'plan', 'circuit_type'),
    Rule('REQ-D01', '需求逐条追溯',
         '需求逐条按类别展开成审查方面，每个方面一项，落到实现电路与检查项；原文由需求文档抄录，判据取方面模板，'
         '审查员对需求的理解写 interpretation、不写判据；'
         '原文拆成要求/前提条款（按顺序拼接等于原文），只有要求条款带结论，'
         '检查项结论取要求条款中最差者，前提条款与其他检查项的缺陷不连带本检查项', 'plan', 'requirement'),
    Rule('REQ-D02', '需求口径一致',
         '需求/规格书与原理图参数口径统一（电流/电压数字唯一来源）', 'board', 'board'),
    Rule('REQ-Q01', '需求覆盖',
         '需求逐条拆解并与电路检查双向追溯，缺口不得隐藏', 'plan', 'board'),
    Rule('REQ-Q02', '链路覆盖',
         '全部接口/电源/检测/使能/复位/时钟逐路终点与返回路径覆盖', 'plan', 'board'),
    Rule('REQ-Q03', '工况状态覆盖',
         '逐关键电路覆盖启动、复位、运行、掉电、外部带电及需求内故障状态', 'plan', 'board'),
    Rule('REQ-Q04', '历史意见覆盖',
         '首审/复审已裁定，历史意见逐条复验并保留撤回/复发', 'plan', 'board'),
    Rule('REQ-Q05', '改版影响覆盖',
         '核对新旧基线、变化、依赖缺口及扩大复验范围；全部必需项使用本轮证据，不迁移旧结论。', 'revision', 'history'),
    Rule('REQ-Q07', '功能电路覆盖',
         '功能电路的全部电路检查项逐电路、逐工况完成后汇总；功能电路只汇总覆盖，不能代替电路检查项', 'plan', 'circuit_type'),
    Rule('REQ-Q08', '未检出功能确认',
         '网表未检出的功能电路逐个确认不适用并给出依据；候选没有归属的器件和被拒候选的成员逐颗确认去处'
         '（写 add 决定，或留在清单上写原因）；未检出特征不等于不适用', 'plan', 'board'),
    Rule('REQ-H01', '改版 Diff 与历史意见闭环',
         '按历史意见断言核对新旧器件字段、引脚换网与网络成员变化，防止假闭环', 'revision', 'history'),
    Rule('REQ-H02', '改版删除项复核',
         '核对旧项在本版两次扫描的消失、恢复或替代及连带影响，不能以清单增减证明修复。', 'revision', 'history'),
)

# 主审查要点用于维护规则目的，不向项目台账新增字段；跨域关系由实际判据和 HANDOFF 保留。
OBJECTIVES = {
    'G1': ('需求与功能符合', '要求的功能、接口和性能是否落实到电路？'),
    'G2': ('器件与连接正确', '实际器件、物理脚、装配与端到端连接是否正确？'),
    'G3': ('工况下的功能与性能', '启动、运行、掉电等适用状态下，电源、控制与信号能否按要求工作？'),
    'G4': ('参数裕量与器件应力', '保证值、公差及工作范围是否满足指标和器件能力？'),
    'G5': ('保护与异常响应', '需求内的故障、防护及隔离是否有效，动作与恢复是否合理？'),
    'G6': ('实施、测试与下游约束', '原理图是否可落实和验证，必要布局、热及测试约束是否明确移交？'),
    'G7': ('证据覆盖、改进建议与复验闭环', '是否查全且结论有据，不通过项是否明确如何改进、如何复验？'),
}
OBJECTIVE_RULES = {
    'G1': tuple('REQ-A01 REQ-A02 REQ-D01 REQ-D02'.split()),
    'G2': tuple(('DOC-A02 DOC-T01 DOC-D01 DOC-V01 '
                 'DEV-A02 DEV-E01 DEV-D01 DEV-D02 DEV-D03 DEV-D04 DEV-D05 '
                 'NET-A01 NET-A02 NET-A03 NET-A04 NET-A06 NET-A07 '
                 'PWR-A01 PWR-A02 PWR-A03 PWR-A04 PWR-T01 PWR-T03 PWR-T06 PWR-D02 '
                 'SIG-E01 SIG-T01 SIG-T02 SIG-T03 SIG-T04 SIG-D13 PRO-A01').split()),
    'G3': tuple(('PWR-C04 PWR-C15 PWR-D03 '
                 'RST-A01 RST-A02 RST-A03 RST-A04 RST-A05 RST-A06 RST-E01 RST-E02 RST-E03 '
                 'RST-T01 RST-T02 RST-T03 RST-T04 RST-C01 RST-C02 '
                 'CLK-D01 CLK-D03 SIG-A01 SIG-A02 SIG-A03 SIG-E02 SIG-C01 SIG-C03 SIG-C04 SIG-C07 SIG-C09 '
                 'SIG-D01 SIG-D02 SIG-D03 SIG-D04 SIG-D07 SIG-D08 SIG-D09 SIG-D10 SIG-D11 SIG-D12 SIG-D14 SIG-D15 '
                 'ANA-T01 ANA-C01 ANA-C02 ANA-D01 PRO-A03 PRO-A04 PRO-E01 DRV-A03 DRV-E01').split()),
    'G4': tuple(('DEV-A01 DEV-A03 DEV-C01 DEV-C02 DEV-C03 DEV-C04 DEV-C05 DEV-C06 '
                 'PWR-A05 PWR-E01 PWR-E02 PWR-E03 PWR-C01 PWR-C02 PWR-C03 PWR-C05 '
                 'PWR-C09 PWR-C10 PWR-C11 PWR-C14 PWR-C16 CLK-C01 DRV-C02').split()),
    'G5': tuple(('PWR-A06 PWR-T04 PWR-T05 PWR-C06 PWR-C13 SIG-C05 SIG-C08 ANA-C03 ANA-C04 '
                 'PRO-E02 PRO-C01 PRO-C02 PRO-C03 PRO-D01 PRO-D02 PRO-D03 DRV-A01 DRV-A02 DRV-A04 DRV-T01 DRV-C01 DRV-D01').split()),
    'G6': tuple('DOC-D02 DOC-V02 RST-D01 SIG-D06'.split()),
    'G7': tuple(('DOC-A01 DOC-A03 DOC-A04 DOC-Q01 DEV-Q01 PWR-D01 '
                 'REQ-Q01 REQ-Q02 REQ-Q03 REQ-Q04 REQ-Q05 REQ-Q07 REQ-Q08 REQ-H01 REQ-H02').split()),
}


def build_objective_index(rule_ids, groups, objectives=OBJECTIVES):
    """Reject unaligned, duplicated or stale maintenance mappings, without judging circuits."""
    if set(groups) != set(objectives):
        raise ValueError('审查要点分组与已定义审查要点不一致')
    index = {}
    for goal, members in groups.items():
        if not members:
            raise ValueError('审查要点没有规则: ' + goal)
        for rule_id in members:
            if rule_id in index:
                raise ValueError('规则重复归属审查要点: ' + rule_id)
            index[rule_id] = goal
    missing, extra = set(rule_ids) - set(index), set(index) - set(rule_ids)
    if missing or extra:
        raise ValueError('审查要点映射遗漏/过期: missing=%s extra=%s' % (sorted(missing), sorted(extra)))
    return index


# 功能电路：正则名称命中仅作候选；由电路候选与决定推出的电路或已确认拓扑使其适用，再逐电路×工况
# （没有推出电路时按类型一次）生成全部电路检查项。意图中 features 的键与 circuits[].type 取类型名。
# PWR-C14 噪声预算挂在敏感负载的包上（ANALOG/CLOCK/RF），变换器本身不生成。
CIRCUIT_TYPES = (
    CircuitType('POWER_CONVERTER', '变换器与稳压器', 'PWR',
            r'(^|[:_-])(FB|VFB|LX\d*|PGOOD|PWRGD|VOUT\d*)([:_-]|$)|LDO|BUCK|BOOST|DC-?DC|PMIC',
            ('PWR-C02', 'PWR-C03', 'PWR-C04', 'PWR-C05', 'PWR-C15'),
            ('requirements', 'datasheets')),
    CircuitType('POWER_PROTECTION', '电源输入保护', 'PWR',
            r'FUSE|HOT-?SWAP|SURGE|PART:F\d+:|(^|[:_-])(OVP|UVP|OCP|ILIM)([:_-]|$)|SMBJ|SMAJ|SMCJ',
            ('PWR-C06', 'DRV-C02', 'PRO-C01', 'PWR-C13', 'PWR-T05', 'ANA-T01'),
            ('requirements', 'datasheets')),
    CircuitType('ANALOG', '模拟前端与监测', 'ANA',
            r'(^|[:_-])(AIN\d*|ADC\w*|VREF\w*|REFIN|REFOUT|OPA\w*|INA\d*|ISENSE\w*|CSP|CSN|NTC\w*|THERM\w*)([:_-]|$)',
            ('ANA-C01', 'ANA-C02', 'ANA-C03', 'ANA-T01', 'ANA-D01'),
            ('requirements', 'datasheets')),
    CircuitType('STARTUP', '上电、复位与启动', 'RST',
            r'RESET|(^|_)RST|POR(_|$)|(^|[:_-])(BOOT\w*|STRAP\w*|PWRON\w*)([:_-]|$)',
            ('RST-C01', 'RST-C02', 'RST-T04', 'RST-D01'),
            ('requirements', 'datasheets')),
    CircuitType('CLOCK', '时钟', 'CLK',
            r'CLK|CLOCK|OSC|XTAL|XIN|XOUT|32K',
            ('CLK-C01', 'CLK-D01', 'CLK-D03'),
            ('datasheets',)),
    CircuitType('I2C', 'I²C', 'SIG',
            r'(^|[:_-])(I2C\w*|SCL\d*|SDA\d*)([:_-]|$)',
            ('SIG-C01', 'SIG-C07', 'SIG-C08', 'SIG-D01'),
            ('requirements', 'datasheets')),
    CircuitType('LEVEL_SHIFT', '电平转换与跨电压域互连', 'SIG',
            r'TXS0\d{3}|TXB0\d{3}|TXU0\d{3}|PCA9306|NVT20\d\d|LSF0\d{3}|GTL2003|FXMA\d+|FXLA\d+|NLSX\d+'
            r'|(SN)?74(LVC|AVC|AXC|ALVC)\d*T\d+|LEVEL_?SHIFT|LVL_?SHIFT|TRANSLAT'
            r'|NET:\w*_(LV|HV)(_|$)',
            ('SIG-C07', 'SIG-C08', 'SIG-C09', 'SIG-T04'),
            ('requirements', 'datasheets')),
    CircuitType('SPI', 'SPI', 'SIG',
            r'\bSPI\w*|MOSI|MISO|SCLK',
            ('SIG-D09', 'SIG-C07', 'SIG-C09'),
            ('requirements', 'datasheets')),
    CircuitType('UART', 'UART/RS232', 'SIG',
            r'UART|\bTXD\w*|\bRXD\w*',
            ('SIG-D08', 'SIG-T04', 'SIG-C07'),
            ('requirements', 'datasheets')),
    CircuitType('CAN', 'CAN', 'SIG',
            r'CANH|CANL|CAN_TX|CAN_RX|\bCAN\d*\b',
            ('SIG-C03', 'SIG-C04', 'SIG-D08', 'PRO-C01'),
            ('requirements', 'datasheets')),
    CircuitType('RS485', 'RS485', 'SIG',
            r'RS485|485_TX|485_RX|485_A|485_B',
            ('SIG-C03', 'SIG-C04', 'SIG-D08', 'SIG-T04', 'PRO-C01'),
            ('requirements', 'datasheets')),
    CircuitType('USB', 'USB/Type-C', 'SIG',
            r'USB|VBUS|TYPEC|TYPE_C',
            ('SIG-D07', 'SIG-D04', 'SIG-C05', 'SIG-T04'),
            ('requirements', 'datasheets')),
    CircuitType('ETHERNET', '以太网', 'SIG',
            r'ETH|RGMII|RMII|SGMII|MDIO|\bMDI\d|PHY',
            ('SIG-D11', 'SIG-C09', 'PRO-C01'),
            ('requirements', 'datasheets', 'platform_checklist')),
    CircuitType('DDR', 'DDR', 'SIG',
            r'LPDDR|DDR[2345]?|SDRAM|DQS|\bZQ\b',
            ('SIG-D02', 'SIG-D03', 'SIG-C09'),
            ('requirements', 'datasheets', 'platform_checklist')),
    CircuitType('STORAGE', 'eMMC/SD', 'SIG',
            r'EMMC|SDIO|SDMMC|MICROSD|TF_CARD',
            ('SIG-D10', 'SIG-C07', 'SIG-C09'),
            ('requirements', 'datasheets', 'platform_checklist')),
    CircuitType('RF', '射频与模组', 'SIG',
            r'(^|[:_-])(RF|ANT|WIFI|WLAN|LTE|GNSS|SIM)([:_-]|$)',
            ('SIG-D12',),
            ('requirements', 'datasheets')),
    CircuitType('HSSERIAL', '高速串行', 'SIG',
            r'PCIE|PCI_E|SATA|SERDES|USB3|SSTX|SSRX|PERST|CLKREQ',
            ('SIG-D14', 'SIG-T01'),
            ('requirements', 'datasheets', 'platform_checklist')),
    CircuitType('AV', '音视频接口', 'SIG',
            r'HDMI|MIPI|(^|[:_-])(CSI|DSI|EDP|LCD)\w*|(^|[:_-])I2S|MCLK|LRCK|BCLK|CODEC|(^|[:_-])(SPK|MIC)([:_-]|\d|$)',
            ('SIG-D15', 'SIG-C07'),
            ('requirements', 'datasheets')),
    CircuitType('ISOLATION', '隔离', 'PRO',
            r'ISOLAT|(^|_)ISO(_|$)|DIGITAL_ISO',
            ('PRO-D02', 'PRO-C01', 'PRO-C03'),
            ('requirements', 'datasheets')),
    CircuitType('DEBUG', '调试与烧录', 'SIG',
            r'JTAG|SWDIO|SWCLK|(^|[:_-])(SWD|TCK|TMS|TDI|TDO|TRST\w*)([:_-]|$)|(^|[:_-])(DEBUG|DBG)',
            ('SIG-D06',),
            ('datasheets',)),
)

# 器件角色登记表：集成电路在 intent.device_kinds 声明的角色，一行一个。board_intent.IC_KINDS、part_words.IC_ROLES、
# datasheet_kinds.KIND_CUES 的 IC 部分和 circuit_candidates 的核心器件规则都从这张表读，加角色只改这里。
#   cues     手册标题词：去掉非字母数字、转小写后的子串（PDF 提取常丢空格）；核验用，标题含别的角色词即冲突。
#   circuits 该角色作核心器件时生成的电路类型；空表示不作核心器件（isolator 是跨域器件，ic 是泛称）。
#            多于一种且都在 INTERFACE_TYPES 内时，按 BUS_CUES 从手册标题挑一种；挑不出的记候选缺口，不猜。
#   pins     ANALOG 走线从哪些脚出发：sense 只走检测脚（circuit_candidates.SENSE_PIN_RE），all 走全部信号脚；
#            接口电路（INTERFACE_TYPES）的走线总是从全部信号脚出发，与 pins 无关。
# 泛称 ic 只能在标题不含任何角色词时声明（datasheet_kinds.verify），计划把每个 ic 列成 DEVICE_KIND_GENERIC 诊断：
# 这些器件不生成电路候选，累计清单就是下一批角色的来源。
DeviceRole = namedtuple('DeviceRole', 'title cues circuits pins', defaults=('sense',))
DEVICE_ROLES = OrderedDict([
    ('pwm_controller', DeviceRole('开关电源控制器', (
        'pwmcontroller', 'pfccontroller', 'flybackcontroller', 'currentmodecontroller', 'voltagemodecontroller',
        'switchingcontroller', 'offlinecontroller', 'quasiresonantcontroller', 'boostcontroller', 'buckcontroller',
        'powerfactorcorrectioncontroller', 'powerfactorcontroller', 'resonantcontroller', 'llccontroller',
        'switchmodecontroller', 'pwmcontrol'), ('POWER_CONVERTER',))),
    ('gate_driver', DeviceRole('栅极驱动器', ('gatedriver', 'mosfetdriver', 'igbtdriver', 'bridgedriver', 'fetdriver'),
                               ('POWER_CONVERTER',))),
    ('sr_controller', DeviceRole('同步整流控制器', ('synchronousrectif', 'srcontroller'), ('POWER_CONVERTER',))),
    ('pd_controller', DeviceRole('USB PD 控制器', ('pdcontroller', 'powerdelivery', 'usbpd', 'typeccontroller', 'usbccontroller'),
                                 ('USB', 'ANALOG'))),
    ('regulator', DeviceRole('稳压器与变换器', (
        'voltageregulator', 'lowdropout', 'ldoregulator', 'dcdcconverter', 'buckconverter', 'boostconverter',
        'switchingregulator', 'stepdownconverter', 'stepupconverter', 'powermanagementic', 'pmic', 'chargepump'),
        ('POWER_CONVERTER',))),
    ('supervisor', DeviceRole('电压监控与复位', ('supervisor', 'supervisory', 'voltagemonitor', 'resetcircuit', 'resetic', 'watchdog'),
                              ('ANALOG',))),
    ('opamp_comparator', DeviceRole('运放、比较器与放大器', (
        'operationalamplifier', 'opamp', 'comparator', 'erroramplifier', 'instrumentationamplifier',
        'currentsenseamplifier', 'currentshuntmonitor', 'differenceamplifier', 'audioamplifier'), ('ANALOG',), 'all')),
    ('shunt_reference', DeviceRole('并联基准', ('shuntregulator', 'voltagereference', 'shuntreference'), ('ANALOG',), 'all')),
    ('mcu', DeviceRole('微控制器与处理器', ('microcontroller', 'microprocessor', 'systemonchip', 'mcu'), ('ANALOG',))),
    ('transceiver', DeviceRole('总线收发器与 PHY', ('transceiver', 'ethernetphy', 'linedriver', 'busdriver'),
                               ('ANALOG', 'CAN', 'RS485', 'UART', 'ETHERNET', 'HSSERIAL'))),
    ('isolator', DeviceRole('数字隔离器', ('digitalisolator', 'isolatedgatedriver', 'isolator'), ())),
    # 2026-10-24 第一批补充：规则表里有检查项却没有角色能靶到的电路类型。
    ('load_switch', DeviceRole('负载开关与热插拔保护', (
        'loadswitch', 'hotswap', 'efuse', 'idealdiode', 'powerdistributionswitch', 'currentlimitswitch', 'highsideswitch'),
        ('POWER_PROTECTION',))),
    ('charger', DeviceRole('电池充电器', ('batterycharger', 'chargecontroller', 'chargemanagement', 'switchingcharger', 'linearcharger', 'chargeric'),
                           ('POWER_CONVERTER',))),
    ('adc_dac', DeviceRole('ADC 与 DAC', (
        'analogtodigital', 'digitaltoanalog', 'bitadc', 'bitdac', 'channeladc', 'channeldac', 'audiodac', 'audioadc',
        'sigmadeltaadc', 'deltasigmaadc'), ('ANALOG',), 'all')),
    ('oscillator', DeviceRole('时钟源', (
        'crystaloscillator', 'clockgenerator', 'clockbuffer', 'clocksynthesizer', 'jittercleaner', 'oscillator',
        'clockdistribution', 'realtimeclock', 'clockmultiplier'), ('CLOCK',))),
    ('memory', DeviceRole('存储器', (
        'flashmemory', 'serialflash', 'spiflash', 'eeprom', 'sdram', 'lpddr', 'ddr2', 'ddr3', 'ddr4', 'ddr5',
        'nandflash', 'norflash', 'sram', 'emmc'), ('SPI', 'I2C', 'DDR', 'STORAGE'))),
    ('level_shifter', DeviceRole('电平转换器', ('leveltranslat', 'levelshifter', 'voltagetranslat', 'voltageleveltranslat'),
                                 ('LEVEL_SHIFT',))),
    ('motor_driver', DeviceRole('电机驱动器', (
        'motordriver', 'steppermotor', 'brushlessdc', 'bldc', 'brusheddc', 'hbridgedriver', 'fullbridgedriver',
        'halfbridgedriver'), ('POWER_CONVERTER',))),
    ('ic', DeviceRole('泛称：手册标题没有登记的角色', (), ())),
])
GENERIC_IC_ROLE = 'ic'
# 一个角色能靶多种接口电路时，从手册标题（原文，区分大小写只对 CAN）挑第一个命中的类型；都不命中记候选缺口 role-bus。
BUS_CUES = OrderedDict([
    ('CAN', re.compile(r'\bCAN(?:[ -]?FD)?\b')),
    ('RS485', re.compile(r'RS[- ]?4(?:85|22)\b|\bPROFIBUS\b', re.I)),
    ('UART', re.compile(r'RS[- ]?232\b|\bUART\b|\bLIN\b', re.I)),
    ('ETHERNET', re.compile(r'\bETHERNET\b|\bPHY\b|\b(?:RG|R|SG)?MII\b', re.I)),
    ('HSSERIAL', re.compile(r'\bLVDS\b|\bSERDES\b|\bPCIE?\b|PCI EXPRESS|\bSATA\b|\bUSB ?3', re.I)),
    ('I2C', re.compile(r'I[²2]C|\bSMBUS\b|TWO[- ]WIRE', re.I)),
    ('SPI', re.compile(r'\bQ?SPI\b|QUAD[- ]SPI|SERIAL (?:NOR )?FLASH|\bNOR FLASH\b', re.I)),
    ('DDR', re.compile(r'\bL?P?DDR\d?\b|\bSDRAM\b', re.I)),
    ('STORAGE', re.compile(r'\bE?MMC\b|\bNAND\b', re.I)),
])
# 接口电路：核心器件的全部信号脚走两跳到截止网络，连接器作成员；别的类型各有自己的走法（circuit_candidates）。
INTERFACE_TYPES = ('POWER_PROTECTION', 'CLOCK', 'I2C', 'LEVEL_SHIFT', 'SPI', 'UART', 'CAN', 'RS485', 'ETHERNET', 'DDR',
                   'STORAGE', 'RF', 'HSSERIAL', 'AV')


def roles_for(circuit_type):
    """作核心器件时生成该电路类型的角色。"""
    return tuple(name for name, role in DEVICE_ROLES.items() if circuit_type in role.circuits)


def interface_type(role_name, quote):
    """角色作核心器件时生成的接口电路类型：唯一的直接取；多种的按 BUS_CUES 从手册标题挑；挑不出返回 None。"""
    types = [t for t in DEVICE_ROLES[role_name].circuits if t in INTERFACE_TYPES]
    if len(types) == 1:
        return types[0]
    for name, pattern in BUS_CUES.items():
        if name in types and pattern.search(str(quote or '')):
            return name
    return None


def device_role_errors():
    """登记表自检：角色电路类型在功能电路表内，标题词不重复，pins 取值合法。"""
    errors = []
    seen = {}
    for name, role in DEVICE_ROLES.items():
        for ctype in role.circuits:
            if ctype not in CIRCUIT_TYPE_BY_NAME:
                errors.append('角色 %s 的电路类型不在功能电路表: %s' % (name, ctype))
        if len([t for t in role.circuits if t in INTERFACE_TYPES]) > 1 and not any(t in BUS_CUES for t in role.circuits):
            errors.append('角色 %s 靶多种接口电路却没有 BUS_CUES 能挑' % name)
        for cue in role.cues:
            if cue in seen:
                errors.append('标题词 %s 同时属于 %s 与 %s' % (cue, seen[cue], name))
            seen[cue] = name
        if role.pins not in ('sense', 'all'):
            errors.append('角色 %s 的 pins 只能是 sense/all' % name)
    return errors


# 寿命（一致性方案第 6 条）：intent.mission_profile.events 可写的次数，按设计寿命总计。
LIFE_EVENTS = OrderedDict([
    ('power_cycles', '开关机次数'), ('surges', '浪涌次数'), ('fault_trips', '故障动作次数'), ('actuations', '动作次数'),
    ('mating_cycles', '插拔次数'), ('charge_cycles', '充放电循环次数'), ('memory_writes', '擦写次数'),
])
# 有寿命需求时派 DEV-C06 的耗损件类别：核什么、依据，以及按哪种次数核（None 按剖面时间核）。
# 电解、固态与超级电容由 DEV-C02 寿命检查项核（6a）。
WearoutClass = namedtuple('WearoutClass', 'title checks basis event')
WEAROUT_CLASSES = OrderedDict([
    ('BATTERY', WearoutClass('电池', '循环次数、容量保持、充电电压和温度', '手册循环寿命和日历寿命', None)),
    ('OPTO', WearoutClass('光耦', '按最小正向电流和保证 CTR 算出这条链寿命末所需的 CTR 保留比例，写成选型或 bom_constraint；'
                                  '厂家给了 CTR 随时间的曲线才用曲线核对，SR 不自编衰减系数', '手册衰减曲线', None)),
    ('LED', WearoutClass('指示或照明 LED', 'LED 光衰对可视要求；需求没有亮度或可视要求时记 NA 并写明', '手册衰减曲线', None)),
    ('VARISTOR', WearoutClass('压敏电阻', '浪涌幅值和次数对脉冲寿命降额曲线，持续工作电压', '需求浪涌等级和次数', 'surges')),
    ('FUSE', WearoutClass('保险丝', '开机浪涌 I²t 和次数对脉冲降额', '剖面里的开关机次数', 'power_cycles')),
    ('INRUSH_NTC', WearoutClass('浪涌限制 NTC', '负载电容对最大允许值、循环次数（热态重启另由 PWR-C13 热态重接入检查项核）',
                                '剖面开关机次数', 'power_cycles')),
    ('PTC', WearoutClass('自恢复保险丝', '动作次数与动作后阻值', '需求故障次数', 'fault_trips')),
    ('RELAY', WearoutClass('继电器', '负载电流和性质对电气寿命，动作次数对机械寿命', '剖面动作次数', 'actuations')),
    ('CONNECTOR', WearoutClass('连接器', '插拔次数', '需求次数', 'mating_cycles')),
    ('SWITCH', WearoutClass('开关、电位器、编码器', '动作次数', '需求次数', 'actuations')),
    ('MEMORY', WearoutClass('Flash / EEPROM', '擦写次数，数据保持年限对温度', '固件写入频度', 'memory_writes')),
])


# 电路规则的对象前提（一致性方案第 2 条，计划格式 7）：（类型，规则）→ 前提，由 plan_circuits 按网表判断；不成立不派这一项，
# 功能框架记 not_asked，报告列“未问”；成立时检查项对象取前提找到的器件。没列的组合对该类型的每块电路都问。
# 前提只去掉电路里不存在的机制的检查项；网表说不清（器件类别未知、IC 没有脚名）时照问。
SUBJECT_PRECONDITIONS = {
    'POWER_SWITCH': '电路里没有 MOSFET 或 BJT',
    'SUPPLY_SWITCH': '电路里没有 D、S 都不接地的 MOSFET',
    'FEEDBACK_PIN': '电路里没有反馈环：电路和与它相接的 IC 都没有反馈/补偿脚（FB、VFB、COMP、VCTRL、ITH、ADJ）或稳压输出脚，'
                    '也没有分压或光耦把输出送到 IC',
    'SWITCH_PIN': '电路里没有受控开关：电路和与它相接的 IC 都没有驱动/开关脚（GATE、DRV、OUT、SW、LX）或稳压输出脚',
    'CONNECTOR_INPUT': '电路里没有连接器，也不在连接器的输入路径上',
    'PROTECTION_PART': '电路里没有保险、压敏电阻、NTC、TVS、稳压管，也没有带 UV/OV/ILIM/EN 脚的 IC',
    'SENSE_ELEMENT': '电路里没有采样电阻（<1 Ω）、NTC 或接到 IC 检测脚的分压',
    'ANALOG_PIN': '电路里没有放大器、ADC 或温度传感器的脚',
    'START_PIN': '电路里没有带复位、使能或启动配置脚（RESET、EN、BOOT、strap）的 IC',
}
SUBJECT_REQUIRES = {
    ('POWER_CONVERTER', 'PWR-C04'): 'SWITCH_PIN',
    ('POWER_CONVERTER', 'PWR-C15'): 'FEEDBACK_PIN',
    ('POWER_PROTECTION', 'PWR-C06'): 'PROTECTION_PART',
    ('POWER_PROTECTION', 'DRV-C02'): 'POWER_SWITCH',
    ('POWER_PROTECTION', 'PRO-C01'): 'PROTECTION_PART',
    ('POWER_PROTECTION', 'PWR-C13'): 'CONNECTOR_INPUT',
    ('POWER_PROTECTION', 'PWR-T05'): 'SUPPLY_SWITCH',
    ('POWER_PROTECTION', 'ANA-T01'): 'SENSE_ELEMENT',
    ('ANALOG', 'ANA-C01'): 'ANALOG_PIN',
    ('ANALOG', 'ANA-C02'): 'ANALOG_PIN',
    ('ANALOG', 'ANA-C03'): 'ANALOG_PIN',
    ('ANALOG', 'ANA-T01'): 'SENSE_ELEMENT',
    ('ANALOG', 'ANA-D01'): 'ANALOG_PIN',
    ('STARTUP', 'RST-C01'): 'START_PIN',
    ('STARTUP', 'RST-C02'): 'START_PIN',
    ('STARTUP', 'RST-T04'): 'START_PIN',
    ('STARTUP', 'RST-D01'): 'START_PIN',
}

# 电路检查项的问题模板：计划按电路填空（{state}/{circuit}/{refs}/{window}），检查项的 question 就是审查员要回答的
# 问题；通用 criterion 保留为提示。问题只说要算什么、对照什么，禁止句（“不得…”“不把…外推”）由 question_errors 拒绝。
QUESTIONS = {
    'PWR-C02': '{state} 时 {circuit}（{refs}）在要求的输入、负载和温度范围内，输出是否落在负载要求的窗口内（{window}）；允许关断或保护时，动作与恢复是否安全',
    'PWR-C03': '{state} 时 {circuit}（{refs}）按实际拓扑算出的电流应力（开关变换器的电感峰值/RMS、Isat 与限流；线性电路的偏置与负载能力）是否在器件保证范围内',
    'PWR-C04': '{state} 时 {circuit}（{refs}）的最小导通/关断时间与输出电容是否满足控制器手册的适用条件；允许失调节的故障或关断状态下，动作与恢复是否成立',
    'PWR-C05': '{state} 时 {circuit}（{refs}）在声明工况下的损耗、反向电流、预偏置与放电路径是否在器件允许范围内，损耗边界和允许的温度约束是多少',
    'PWR-C15': '{state} 时 {circuit}（{refs}）的反馈模型与补偿配置是否符合厂家适用条件，规定角点的稳定性与动态边界是否成立（无反馈环时按拓扑记 NA）',
    'PWR-C06': '{state} 时 {circuit}（{refs}）的 UVLO/OVLO/限流门限含容差是否在要求范围内，检测目的与采样侧是否正确；被动输入的保险丝/MOV/NTC 是否协调',
    'DRV-C02': '{state} 时 {circuit}（{refs}）的功率管在实际驱动、电流、电压、脉宽和温度下是否处于适用的 SOA 与降额范围内（重复脉冲与单次脉冲分别核）',
    'PRO-C01': '{state} 时 {circuit}（{refs}）的防护链逐段的动作电压、时序与能量是否协调：TVS 的 VRWM/VBR/VC 对照后级绝限，熔断器/PTC 的额定、时间电流、熔断能量和分断能力是否满足',
    'PWR-C13': '{state} 时 {circuit}（{refs}）按实际接口/输入方式，浪涌电流与输入电容是否在源端能力和平台限制内',
    'PWR-T05': '{circuit}（{refs}）防反接电路的导通方向、体二极管朝向与栅极钳位是否正确',
    'ANA-T01': '{state} 时 {circuit}（{refs}）的检测/监测链的被测量与保护目的是否明确，取样侧、返回地、判决与控制是否闭合，首次使能是否能启动',
    'ANA-C01': '{state} 时 {circuit}（{refs}）的输入共模/输出摆幅与偏置、失调、增益误差在供电和温度极限内是否满足精度要求（片内放大器+ADC 通道按该 IC 手册的通道范围与误差）',
    'ANA-C02': '{state} 时 {circuit}（{refs}）的 GBW/压摆率/容性负载或 ADC 源阻抗、采样保持获取时间与建立误差是否满足要求',
    'ANA-C03': '{state} 时 {circuit}（{refs}）的 ADC 基准驱动与误差、输入满量程及钳位/注入电流（含掉电状态）是否在限值内',
    'ANA-D01': '{circuit}（{refs}）的温度传感器电气连接、量程和接口是否正确',
    'RST-C01': '{state} 时 {circuit}（{refs}）每个采样窗口内 strap/EN 的保证电压（含内部拉阻、LED、泄漏、电容和门限）是否落在要求的电平',
    'RST-C02': '{state} 时 {circuit}（{refs}）按 V(t) 穿越门限时刻算出的复位脉宽/释放与采样 setup/hold 是否满足要求',
    'RST-T04': '{state} 时 {circuit}（{refs}）在断电、复位、启动配置采样与固件接管前的 IO 默认态对继电器、电源使能、驱动器、LED 与外部总线是否安全，依据是什么',
    'RST-D01': '{state} 时 {circuit}（{refs}）的编程/救援通道、进入条件与电平是否满足实际恢复需求',
    'CLK-C01': '{state} 时 {circuit}（{refs}）按准确晶体料号核对的 CL/ESR/驱动功率、振荡器适配和起振条件是否满足',
    'CLK-D01': '{state} 时 {circuit}（{refs}）有源时钟的输出幅度/电源域、使能态和上电有效时间是否满足负载要求',
    'CLK-D03': '{state} 时 {circuit}（{refs}）的 RTC 时钟源、频率/负载要求及模式是否匹配，备份电池/超级电容的充电电压/电流与反向电流是否在器件要求内',
    'SIG-C01': '{state} 时 {circuit}（{refs}）每个电气段合并全部上拉公差后，Rp 是否落在 (Vpullup_max−VOL_max)/IOL 与 tr_max/(0.8473·Cb_max) 之间，串联压降是否可接受',
    'SIG-C07': '{state} 时 {circuit}（{refs}）每条链路驱动端 VOH/VOL 与接收端 VIH/VIL（含负载电流与温度角）、驱动电流与扇出、上拉轨对各接收端门限与耐压是否匹配；跨域直连是否由两端保证条件证明',
    'SIG-C08': '{state} 时 {circuit}（{refs}）逐域掉电和外部设备先上电时，Ioff、输入耐压与注入电流是否在限值内，经上拉、ESD 结构或保护二极管的反灌路径是否被堵住',
    'SIG-D01': '{state} 时 {circuit}（{refs}）的地址/复用/复位态与板载及外部上拉的装配组合是否正确',
    'SIG-C09': '{state} 时 {circuit}（{refs}）按两端保证值算出的传播延迟、建立/保持、时钟偏斜、电平转换器延迟及上升时间在最坏角点是否有裕量',
    'SIG-T04': '{circuit}（{refs}）的 TX/RX、P/N、Host/Device、Source/Sink 按两端官方语义是否对应，对端连接器视图与线缆针序是否一致',
    'SIG-D09': '{state} 时 {circuit}（{refs}）的 SPI 片选/时钟极性与串阻、SPI Flash 供电域、上拉与写保护是否正确',
    'SIG-D08': '{state} 时 {circuit}（{refs}）收发器的供电与 VIO、STBY/EN 默认态、端接策略、空闲偏置、隔离与防护是否满足总线要求',
    'SIG-C03': '{state} 时 {circuit}（{refs}）按实际端点和节点数算出的端接等效负载、空闲偏置是否满足接收保证差分门限',
    'SIG-C04': '{state} 时 {circuit}（{refs}）收发器的 VIO/默认态、总线共模范围、地偏差与未供电负载是否在限值内',
    'SIG-D07': '{circuit}（{refs}）的 REXT、DP/DM 串阻、VBUS 检测、ID 与 ESD 是否按 USB 要求接在活线上',
    'SIG-D04': '{circuit}（{refs}）按 Source/Sink/DRP 角色及 PD 模式，CC/Rp/Rd、方向检测、线缆 VCONN 是否正确',
    'SIG-C05': '{state} 时 {circuit}（{refs}）的 VBUS 供电资格、电压档位、放电、反灌、过流及端口未供电状态是否满足要求',
    'SIG-D11': '{state} 时 {circuit}（{refs}）的 MDI 对应、中心抽头与共模端接、MDIO、复位及 strap 是否符合实际 PHY、网变和接口模式的要求',
    'SIG-D02': '{state} 时 {circuit}（{refs}）的 ZQ/校准脚端接与精度是否符合控制器与 DRAM 各自型号的要求',
    'SIG-D03': '{state} 时 {circuit}（{refs}）各数据/地址/时钟/VREF/VTT 电源域的拓扑、端接、基准及上电条件是否正确',
    'SIG-D10': '{state} 时 {circuit}（{refs}）的 IO 电平、CMD 上拉、CLK/STROBE 串阻与测试节点电气预留是否满足 eMMC/SD 要求',
    'SIG-D12': '{state} 时 {circuit}（{refs}）的天线路径默认通断、供电电容、开关机/复位及 SIM 接口保护是否满足模组要求',
    'SIG-D14': '{state} 时 {circuit}（{refs}）链路的交流耦合电容位置与容值、极性与通道映射、参考时钟与边带信号是否按规范连接',
    'SIG-T01': '{state} 时 {circuit}（{refs}）差分对 P/N 两端语义、耦合/端接拓扑和全链路连通是否正确',
    'SIG-D15': '{state} 时 {circuit}（{refs}）的通道映射、热插拔/DDC/CEC 电平与上拉、MCLK/帧时钟来源、模拟音频供电与地是否按规范连接',
    'PRO-D02': '{state} 时 {circuit}（{refs}）跨隔离带器件与网络的归属及跨接用途是否明确',
    'PRO-C03': '{state} 时 {circuit}（{refs}）每个跨隔离器件的实际工作电压、重复峰值/频率、绝缘类别是否在厂家资格适用条件内',
    'SIG-D06': '{state} 时 {circuit}（{refs}）的 UART/JTAG/SWD 信号电气引出、串阻与 ESD 是否满足调试/烧录要求',
}

# 功能框架的问题：每个 intent 电路一句，由该检查项问题归纳；审查员可改写。
# 答案不随工作态变化的电路检查项（导通方向、接口语义、USB 物理层与角色、传感器接法）：计划每电路只问一次，
# 检查项的 object 不带 state，问题模板也不带“{state} 时”。纹波预算（PWR-C14）和变换器各条随负载/模式变化，仍逐状态。
STATE_INVARIANT = frozenset({'PWR-T05', 'ANA-D01', 'SIG-T04', 'SIG-D07', 'SIG-D04'})

# 系统功能（功能树设计 §3.4）：这些规则问的是全板的电源树、地、监控、时序和主控引脚，检查项归该系统功能。
# 按电路展开的检查项仍归电路（RST-T03 到第 5 步才移到 SYS-SEQUENCE）。
SYSTEM_FUNCTIONS = {
    'SYS-POWER': ('PWR-T01', 'PWR-C01', 'PWR-C16', 'PWR-A01', 'PWR-A04'),
    'SYS-GROUND': ('PWR-T06',),
    'SYS-MONITOR': ('PWR-A06', 'PWR-T04'),
    'SYS-SEQUENCE': ('RST-T03',),
    'SYS-PINMAP': ('SIG-D13',),
}
SYSTEM_OF_RULE = {rule: sid for sid, rules in SYSTEM_FUNCTIONS.items() for rule in rules}

# 接口检查项（功能树设计 §3.3，第 4 步）：计划按 interfaces 逐接口展开，检查项归接口。电路对问方向语义和电平，
# 链路问两端电平，连接器问对端定义、载流和对外防护，供电轨在敏感功能电路取电时问纹波与噪声。
# 两端 IC 的供电轨或参考地分区不同的接口网络另问一项掉电与跨域注入（SIG-C08）。
# 声明的总线电路（I2C、SPI 等）内部的链路仍由电路检查项问，接口只问不同所属对象之间的网络。
INTERFACE_SUBJECTS = {
    'CIRCUIT_PAIR': ('SIG-T04', 'SIG-C07'),
    'LINK': ('SIG-C07',),
    'EXTERNAL': ('DEV-D03', 'DEV-C04', 'PRO-D03'),
    'SUPPLY': ('PWR-C14',),
}
INTERFACE_NET_SUBJECTS = {'CIRCUIT_PAIR': ('SIG-C08',), 'LINK': ('SIG-C08',)}
NOISE_SENSITIVE_TYPES = ('ANALOG', 'CLOCK', 'RF')
# 归接口的规则（设计稿附录 A）：按电路展开的检查项仍归电路；其余检查项的网络都落在同一个接口上时归该接口。
INTERFACE_RULES = frozenset({
    'DEV-C04', 'DEV-D03', 'PRO-D03', 'PWR-C14', 'RST-A04', 'RST-A06', 'RST-T01', 'RST-T02',
    'SIG-A01', 'SIG-A02', 'SIG-E02', 'SIG-T01', 'SIG-T03', 'SIG-T04', 'SIG-C07', 'SIG-C08', 'SIG-C09'})
INTERFACE_QUESTIONS = {
    'SIG-T04': '{interface}（{nets}）两端的 TX/RX、P/N、Host/Device、Source/Sink 按两端官方语义是否对应',
    'SIG-C07': '{interface}（{nets}）每条网络驱动端 VOH/VOL 与接收端 VIH/VIL（含负载电流与温度角）、驱动能力与接收端耐压是否匹配',
    'SIG-C08': '{interface} 的 {nets} 两端供电或参考地分区不同：一端掉电或外设先上电时，Ioff、输入耐压与注入电流是否在限值内',
    'DEV-D03': '{interface}（{refs}）每针本端定义与对端定义是否逐针相容',
    'DEV-C04': '{interface}（{refs}）按实际系列的并针降额、接触电阻和故障电流核算的载流是否够',
    'PRO-D03': '{interface}（{refs}）每个对外针是否有防护、防护器件是否挂在活线上、泄放路径是否接到对应的地',
    'PWR-C14': '{interface} 供给敏感电路 {loads} 的纹波与噪声（含开关频率、后级滤波与去耦）是否满足其噪声/PSRR 要求',
}
INTERFACE_FRAME_QUESTIONS = {
    'CIRCUIT_PAIR': '{interface}（{owners}）之间的网络 {nets}，方向、电平与跨域注入是否都成立',
    'LINK': '链路 {interface}（{refs}）两端网络 {nets} 的电平与跨域注入是否成立',
    'EXTERNAL': '连接器 {interface} 的针定义、载流与对外防护是否成立',
}


# 系统功能框架的问题（功能树设计 §3.4，第 5 步）；对象是轨、地网或主控。
SYSTEM_FRAME_QUESTIONS = {
    'SYS-POWER': '电源树（{nets}）每条轨的源、负载、电压窗口与功率预算是否成立，有没有无驱动或同基名混淆的轨',
    'SYS-GROUND': '地网 {nets} 的划分与连接点（直连、0Ω、磁珠、RC/电容）是否符合器件与平台要求',
    'SYS-MONITOR': '需求要求监测的电源域（{nets}）是否都有监测点、阈值与动作',
    'SYS-SEQUENCE': '各轨（{nets}）在慢爬升、棕断、单域掉电、外部先供电与重试下的上电先后与恢复是否成立',
    'SYS-PINMAP': '主控（{refs}）的引脚复用、功能分配与电平域是否符合平台约束并与固件配置一致',
}
# 逐电路自有器件的检查项（第 5 步）：每块电路对它拥有的器件问一项，未归属的器件全板一项；按器件类别取对象。
OWNED_PART_RULES = ('DEV-C01', 'DEV-C02', 'DEV-C03')


def system_frame_question(system_id, nets=(), refs=()):
    return SYSTEM_FRAME_QUESTIONS[system_id].format(nets='、'.join(nets) or '无', refs='、'.join(refs) or '待定')


def interface_question(rule_id, interface, nets=(), refs=(), loads=()):
    return INTERFACE_QUESTIONS[rule_id].format(interface=interface, nets='、'.join(nets) or '无信号网络',
                                               refs='、'.join(refs), loads='、'.join(loads))


def interface_frame_question(kind, interface, owners=(), nets=(), refs=()):
    return INTERFACE_FRAME_QUESTIONS[kind].format(interface=interface, owners='、'.join(owners),
                                                  nets='、'.join(nets) or '无信号网络', refs='、'.join(refs))

# 电路候选的基础工作态（scripts/circuit_candidates.py）：按类型固定，审查员增减一个态要引用手册里的模式名。
# 控制器的 LL/HL、突发、掉电等模式是在这个基础清单上按资料补充的，候选一致不等于工作态覆盖完整。
CANDIDATE_STATES = {
    'POWER_CONVERTER': ('startup', 'run', 'fault'),
    'POWER_PROTECTION': ('startup', 'run', 'fault'),
    'USB': ('unattached', 'attached', 'fault'),
    'ANALOG': ('run', 'fault'),
    'ISOLATION': ('run',),
    'STARTUP': ('power-on', 'restart'),
    'DEBUG': ('run',),       # 调试口的答案不随工作态变化，仍要一个态来展开检查项
}

# A state a decision adds (states_add) must be named by a requirement (R7 acceptance 2026-10-25, user: B1 a): the
# decision maps each added state to a requirement id whose original text uses one of these words (or the state's own
# name when it is not listed). One generic citation gave every circuit six states on one R7 record (+130 rows).
STATE_WORDS = {
    'standby': ('待机', '空载', 'standby', 'no-load', 'no load', 'idle'),
    'off': ('关机', '关断', 'shutdown', 'switched off', 'power off', 'off state'),
    'power_down': ('掉电', '断电', '停电', 'power down', 'power-down', 'brown-out', 'loss of mains', 'hold-up'),
    'power-down': ('掉电', '断电', '停电', 'power down', 'power-down', 'brown-out', 'loss of mains', 'hold-up'),
    'hotplug': ('热插拔', '插拔', 'hot plug', 'hot-plug', 'hotplug', 'attach', 'detach'),
    'short_circuit': ('短路', 'short circuit', 'short-circuit', 'shorted'),
    'short-circuit': ('短路', 'short circuit', 'short-circuit', 'shorted'),
    'burst': ('突发', '轻载', 'burst', 'light load', 'light-load'),
    'overload': ('过载', 'overload'),
    'sleep': ('休眠', '睡眠', 'sleep', 'low power'),
}


def state_named_by(state, original_text):
    """Whether a requirement's original text names the state: one of STATE_WORDS[state], or the state's own name."""
    low = str(original_text or '').lower()
    name = str(state).lower()
    words = STATE_WORDS.get(name, ()) + (name, name.replace('_', ' ').replace('-', ' '))
    return any(w.lower() in low for w in words)


FRAME_QUESTIONS = {
    'POWER_CONVERTER': '输出是否落在负载要求的窗口内（{window}），电流应力、时序/电容条件、损耗和反馈环路是否都在保证范围内',
    'POWER_PROTECTION': '保护门限、功率管 SOA、防护器件协调、浪涌与防反接是否都成立',
    'ANALOG': '检测链的直流误差、动态、基准与保护、噪声预算是否满足测量要求',
    'STARTUP': '采样窗口电平、复位时序、上电顺序、IO 默认态与救砖通道是否成立',
    'CLOCK': '晶体/有源时钟/RTC 是否按料号条件起振并满足负载与噪声要求',
    'I2C': '上拉与上升时间、电平匹配、掉电注入和地址/装配组合是否成立',
    'LEVEL_SHIFT': '两侧电平匹配、掉电注入、时序裕量和方向语义是否成立',
    'SPI': 'SPI 片选/极性/串阻、电平匹配和时序裕量是否成立',
    'UART': '收发器供电与默认态、方向语义和电平匹配是否成立',
    'CAN': '端接与偏置、共模与未供电负载、收发器配置和防护协调是否成立',
    'RS485': '端接与偏置、共模与未供电负载、收发器配置、方向语义和防护协调是否成立',
    'USB': 'USB 物理层、Type-C 角色与 CC、VBUS 供电与保护、方向语义是否成立',
    'ETHERNET': 'PHY 与网变配置、时序裕量与防护协调是否成立',
    'DDR': '校准端接、各电源域端接与基准、时序裕量是否成立',
    'STORAGE': 'eMMC/SD 接口、电平匹配与时序裕量是否成立',
    'RF': '天线路径、供电与噪声预算是否满足模组要求',
    'HSSERIAL': '高速链路的耦合、映射、边带与差分连通是否按规范',
    'AV': '音视频接口的通道映射、电平与时钟来源、电平匹配是否成立',
    'ISOLATION': '隔离带跨接归属、防护协调与隔离器件工作资格是否成立',
    'DEBUG': '调试接口电气引出、串阻与 ESD 是否满足烧录/调试要求',
}
FRAME_PREFIX = '{circuit}（{refs}）在 {states} 各状态下，'
# The rails named come from the circuit's connecting nets, input and output alike: the reviewer says which is the output.
WINDOW = '电路连接网络上已声明的轨：%s；哪条是输出由审查员按拓扑认定'
NO_WINDOW = '电路连接网络上没有声明窗口的轨'

# 判“证据不足”之前的五步（原文见 evidence-proportionality.md），随功能框架交给审查员。
BOUNDING_STEPS = (
    '先用手册里已有的界限。',
    '算出了余量就下结论。',
    '本设计自己要定的量不向厂家要。',
    '没有保证值就按公开资料界限判断。',
    '只有走完 1–4 仍判不了，才记证据不足，并在缺口里写明查过手册哪几条、为什么都不够。',
)


# -- 工作点定界表（定界表方案 2026-10-23；用户：“必须按表”）--------------------------------
# 每格：哪类器件的哪个参数，随什么变、往哪个方向单调，允许的推法（G 编号 → bound_formulas 里的公式）按顺序，
# 推法用完仍推不出时落到哪一档。门禁按格核对：判“定不出界”的缺厂家数据写 monotonic_tried.cell，
# 余量依据写 basis.cell/method/formula 时按公式重算。
BoundMethod = namedtuple('BoundMethod', 'code name basis')
# 判决边界（2026-10-26 用户："判决的边界按器件类型来"）：每格另写厂家通常保证到哪（availability）、典型值估算能不能判通过及
# 倍数（estimates，空表示不估算）、参数超出时的物理后果（consequence）、估算判通过时移交的样机实测能不能做（prototype）、
# 一句话边界（boundary）。估算判 PASS 由 格 × 后果类 决定，规则 id 清单只在 cell 为 NONE 时作默认。
Bound = namedtuple('Bound', 'id kinds parameter side varies_with direction methods fallback source '
                            'availability estimates consequence prototype boundary')
# 一条允许的估算：factor 是把估算值再按不利方向打的折（电流增益 ÷2、阻值 ×1.2 都写 2 / 1.2），applies 是它适用的后果类，
# floor 是余量本身的下限（值, 单位；None 不限），how 写估算怎么做。
Estimate = namedtuple('Estimate', 'factor applies floor how')

BOUND_METHODS = OrderedDict((m.code, m) for m in (
    BoundMethod('G1', '保证限值直接覆盖：工作点在限值的测试条件内', '保证最坏值'),
    BoundMethod('G2', '单调有利侧：参数随 x 单调，工作点在测试点的有利一侧', '保证最坏值'),
    BoundMethod('G3', '两测试点之间的斜率界：取区间内斜率最大一端的保证上限', '保证最坏值'),
    BoundMethod('G4', '温度系数：P(T) = P(T₀) + S·(T − T₀)，S 取不利一端', '保证最坏值'),
    BoundMethod('G5', '公开特性表：表内插值，公差取表给的上下限', '保证最坏值'),
    BoundMethod('G6', '物理约束：节点电压不超过供电轨或钳位保证值，电流不超过上游限流', '保证最坏值'),
    BoundMethod('G7', '同一测试点比例外推：典型曲线 × 保证值 / 同点典型值', '估算'),
    BoundMethod('G8', '典型曲线覆盖工作点：按曲线取值；典型值已不够判失败（可达的反例）', '估算'),
    BoundMethod('G9', '只有典型值：同类参数 min/max 比例、同系列保证范围或典型 ±30%', '估算'),
    BoundMethod('G10', '厂家参考电路同接法：接法相同、本板负载不重于参考电路，引图号', '可判通过'),
    BoundMethod('SOA', '按持续时间选 25 °C 曲线，按开始壳温降额，恒功率段留 100%、热不稳定段留 80%', '保证最坏值'),
    BoundMethod('FORCED_BETA', '饱和开关按强制 β：IB ≥ IC /（hFE_min / 2）', '保证最坏值'),
))
BOUND_FALLBACKS = OrderedDict((
    ('VENDOR_DATUM', '缺厂家数据（第三档），按后果定级'),
    ('OUTSIDE_SPECIFIED', '超出规定区（第四档），记失败项'),
    ('BOUNDED', '总能定界，不开“定不出界”的项'),
))
BOUND_DIRECTIONS = ('INCREASING', 'DECREASING', 'NONMONOTONIC')
# 可得性：厂家手册对这个参数通常保证到哪
BOUND_AVAILABILITY = OrderedDict((
    ('GUARANTEED', '全保证：工作范围内有 min/max'),
    ('TEST_POINT', '测试点保证：只在标称测试条件保证，别处靠单调性或斜率推'),
    ('INDUSTRY_NONE', '行业不给：全温、寿命、低电流等只给典型曲线，索取也拿不到'),
    ('TYPICAL_BY_DEFINITION', '定义即典型：参数定义本身就是典型值'),
))
# 样机能否验证估算
BOUND_PROTOTYPE = OrderedDict((
    ('MEASURABLE', '可测（常温或高低温箱）'),
    ('TYPE_TEST', '型式试验（浪涌、ESD、破坏性，样机阶段不做）'),
    ('NOT_VERIFIABLE', '不可（寿命衰减）'),
))
# 后果类沿用 electrical_contract.IMPACT_CLASSES：功能 / 性能寿命 / 器件损坏 / 安全危害
FUNCTIONAL = frozenset(('REQUIRED_FUNCTION', 'PERFORMANCE_OR_LIFE', 'LOCAL_OR_DATA', 'OPTIMIZATION'))
DAMAGE = frozenset(('COMPONENT_DAMAGE',))
ESTIMATE_NEVER = frozenset(('DAMAGE_OR_HAZARD', 'CORE_LINK_LOSS'))   # 安全危害、核心链路：任何格都不估算
CONSEQUENCE_WORDS = OrderedDict((('REQUIRED_FUNCTION', '功能'), ('PERFORMANCE_OR_LIFE', '性能/寿命'),
                                 ('COMPONENT_DAMAGE', '损坏'), ('DAMAGE_OR_HAZARD', '安全')))

_EP = 'evidence-proportionality.md'
_CB = 'docs/2026-10-26-cell-boundary.md'
_IC_ROLES = tuple(DEVICE_ROLES)      # 器件角色登记表的全部角色，含泛称 ic
_M = ('MEASURABLE',)
_T = ('TYPE_TEST',)
def _e(factor, applies, how, floor=None):
    return Estimate(factor, applies, floor, how)
BOUNDS = OrderedDict((b.id, b) for b in (
    # 3.1 齐纳管、电压基准
    Bound('ZENER-VZ-UPPER', ('zener',), 'VZ 上界', 'UPPER', '工作电流 IZ', 'INCREASING', (('G1', ()), ('G2', ()), ('G9', ())),
          'VENDOR_DATUM', _EP + '“齐纳管低电流”',
          'TEST_POINT', (_e(1.5, FUNCTIONAL, '只有典型 rdif 时：典型 rdif ×1.5'),), ('REQUIRED_FUNCTION', 'COMPONENT_DAMAGE'), _M,
          '偏置用途允许估算；作钳位保护（下游过压→损坏）时不估算'),
    Bound('ZENER-VZ-LOWER', ('zener',), 'VZ 下界', 'LOWER', '工作电流 IZ', 'INCREASING',
          (('G1', ()), ('G2', ()), ('G3', ('slope_bound',)), ('G8', ())), 'OUTSIDE_SPECIFIED', _EP + '“齐纳管低电流”；本表“几条口径”齐纳管 VZ 下界',
          'INDUSTRY_NONE', (_e(1.2, FUNCTIONAL, '典型曲线 G8 在工作电流取值，再 ÷1.2（≈×0.85）'),), ('REQUIRED_FUNCTION',), _M,
          '典型曲线覆盖工作点时允许估算判 PASS；两测试点之间 G3 是保证值；最低测试点以下又没有覆盖它的曲线，是用在手册未规定的区间，'
          '记失败项（改法：把工作电流提到最低测试点以上），不向厂家索取（2026-10-26 定）'),
    Bound('ZENER-VZ-TEMP', ('zener', 'shunt_reference'), 'VZ / 基准电压随温度', None, '温度', 'NONMONOTONIC',
          (('G1', ()), ('G4', ('tempco_bound',)), ('G9', ())), 'VENDOR_DATUM', _EP + '第 4 步“温度系数的 min/max”',
          'TEST_POINT', (_e(2, FUNCTIONAL, '典型温漂 ×2'),), ('REQUIRED_FUNCTION', 'PERFORMANCE_OR_LIFE'), _M,
          '并联基准多给 max 温漂（G4 保证）；普通齐纳只给典型温漂，允许估算（×2）'),
    Bound('REF-IKA-MIN', ('shunt_reference',), '最小阴极电流 Ika', 'LOWER', '工作态', None, (('G1', ()),),
          'OUTSIDE_SPECIFIED', '定界表决定（architecture.md 2026-10-23）',
          'GUARANTEED', (), ('REQUIRED_FUNCTION',), _M, '不估算：规格地板，低于 Ika(min) 即超出规定区，记失败'),
    # 3.2 TVS
    Bound('TVS-STANDOFF', ('tvs',), '正常最大值不超过 VRWM', 'UPPER', '工作电压', None, (('G1', ()),),
          'OUTSIDE_SPECIFIED', 'wca-formulas.md TVS 行',
          'GUARANTEED', (), ('COMPONENT_DAMAGE',), _M, '不估算'),
    Bound('TVS-VC', ('tvs',), '钳位电压上界', 'UPPER', '冲击电流 Ipp（同一波形）', 'INCREASING', (('G1', ()), ('G2', ())),
          'VENDOR_DATUM', 'wca-formulas.md TVS 行',
          'TEST_POINT', (), ('COMPONENT_DAMAGE',), _T, '不估算；缺波形对应的保证值时按最坏（Ipp 处 VC max）判'),
    Bound('TVS-LEAK-HOT', ('tvs',), '高温漏电', 'UPPER', '温度', 'INCREASING', (('G1', ()), ('G2', ()), ('G7', ('ratio_extrapolation',))),
          'VENDOR_DATUM', '定界表决定（architecture.md 2026-10-23）',
          'INDUSTRY_NONE', (_e(2, FUNCTIONAL, '典型温度曲线比例外推 G7，再 ×2'),), ('REQUIRED_FUNCTION', 'PERFORMANCE_OR_LIFE'), _M,
          '允许估算（×2）：25 °C max 保证，高温只有典型曲线'),
    # 3.3 二极管、整流桥
    Bound('DIODE-VF', ('diode', 'bridge_rectifier'), 'VF 上界随电流', 'UPPER', '正向电流 IF', 'INCREASING',
          (('G1', ()), ('G2', ()), ('G8', ())), 'VENDOR_DATUM', _EP + '“单调外推”',
          'TEST_POINT', (_e(1.15, FUNCTIONAL, '超出测试点需要典型曲线时 ×1.15'),
                         _e(1.15, DAMAGE, '同上；用它判温升损坏时结温余量 ≥ 20 °C', (20, '°C'))), ('PERFORMANCE_OR_LIFE', 'COMPONENT_DAMAGE'), _M,
          '允许估算（×1.15）；判温升损坏时另要结温余量 ≥ 20 °C'),
    Bound('DIODE-VF-COLD', ('diode', 'bridge_rectifier'), 'VF 上界随温度（冷态最差）', 'UPPER', '温度', 'DECREASING',
          (('G1', ()), ('G2', ()), ('G4', ('tempco_bound',)), ('G7', ('ratio_extrapolation',))), 'VENDOR_DATUM', _EP + '“单调外推”',
          'INDUSTRY_NONE', (_e(1.15, FUNCTIONAL, '典型温度曲线 ×1.15；物理温漂上界（约 −2 mV/°C）可作 G4 保证推法'),), ('REQUIRED_FUNCTION',), _M,
          '允许估算（×1.15）'),
    Bound('DIODE-IR-HOT', ('diode', 'bridge_rectifier', 'zener'), '高温反向漏电', 'UPPER', '温度', 'INCREASING',
          (('G1', ()), ('G2', ()), ('G7', ('ratio_extrapolation',))), 'VENDOR_DATUM', _EP + '“二极管反向漏电”',
          'TEST_POINT', (_e(2, FUNCTIONAL, '比例外推 G7，再 ×2'),
                         _e(2, DAMAGE, '同上，结温余量 ≥ 20 °C', (20, '°C'))), ('REQUIRED_FUNCTION', 'COMPONENT_DAMAGE'), _M,
          '允许估算（×2）；判反向功耗热失控（损坏）另要结温余量 ≥ 20 °C，记应力风险'),
    Bound('DIODE-SURGE', ('diode', 'bridge_rectifier'), '浪涌 IFSM 换算到其他脉宽', 'UPPER', '脉宽', 'DECREASING',
          (('G1', ()), ('G2', ()), ('G5', ('half_sine_i2t', 'surge_current_at_width'))), 'OUTSIDE_SPECIFIED', _EP + '“脉冲与浪涌”',
          'TEST_POINT', (), ('COMPONENT_DAMAGE', 'DAMAGE_OR_HAZARD'), _T,
          '不估算：I²t（√t）换算已是保守推法；手册没给 IFSM 的器件承受浪涌是用在规定区之外，记失败项（2026-10-26 定）'),
    # 3.4 MOSFET、BJT
    Bound('MOS-VGS-ON', ('mosfet',), '导通所需 VGS', 'UPPER', '漏极电流 ID', 'INCREASING', (('G1', ()), ('G2', ()), ('G7', ())),
          'VENDOR_DATUM', 'wca-formulas.md VGS 三档',
          'TEST_POINT', (_e(2, FUNCTIONAL, '小信号 / 电平转换：典型传输曲线的 RDS ×2'),
                         _e(2, DAMAGE, '功率开关：典型曲线 RDS ×2 算导通损耗，结温余量 ≥ 20 °C', (20, '°C'))),
          ('REQUIRED_FUNCTION', 'COMPONENT_DAMAGE'), _M,
          '允许估算（×2）；功率开关（损坏）另要结温余量 ≥ 20 °C，记应力风险'),
    Bound('MOS-RDS-HOT', ('mosfet',), '高温 RDS(on)', 'UPPER', '结温', 'INCREASING',
          (('G1', ()), ('G2', ()), ('G7', ('ratio_extrapolation',))), 'VENDOR_DATUM', _EP + '“MOS 热态 RDS”',
          'INDUSTRY_NONE', (_e(1.2, FUNCTIONAL | DAMAGE, '25 °C max × 典型温度比（G7），再 ×1.2；判损坏时结温余量 ≥ 20 °C', (20, '°C')),),
          ('PERFORMANCE_OR_LIFE', 'COMPONENT_DAMAGE'), _M,
          '允许估算判 PASS（×1.2 且结温余量 ≥ 20 °C）：全行业做法，hot max 行业不给'),
    Bound('MOS-SOA-HOT', ('mosfet',), '高温 SOA', 'UPPER', '开始壳温', 'DECREASING',
          (('SOA', ('soa_allowed_power', 'soa_case_temperature', 'heatsink_requirement', 'zth_junction_temperature')),),
          'BOUNDED', '本表“几条口径”MOS 高温 SOA',
          'GUARANTEED', (), ('COMPONENT_DAMAGE',), _T, '按 SOA 推法降额后视作保证；不另估算'),
    Bound('MOS-LINEAR', ('mosfet',), '线性工作点的 VGS（源跟随、线性稳压）', None, '漏极电流与温度', 'NONMONOTONIC',
          (('G1', ()), ('G7', ('ratio_extrapolation',)), ('G8', ())), 'VENDOR_DATUM', _EP + '“按实际用途选模型”',
          'TEST_POINT', (_e(1.4, FUNCTIONAL, '典型传输曲线 gm ÷1.4（≈×0.7）；VGS(th) 的 min/max 是保证值'),), ('REQUIRED_FUNCTION',), _M,
          '允许估算（÷1.4）；功耗/结温部分走 MOS-SOA-HOT'),
    Bound('BJT-SAT', ('bjt',), '饱和导通所需基极电流', 'LOWER', '集电极电流 IC', None,
          (('FORCED_BETA', ('forced_beta_base_current',)),), 'BOUNDED', '本表“几条口径”BJT 饱和开关',
          'GUARANTEED', (), ('COMPONENT_DAMAGE',), _M, '按 FORCED_BETA，不估算'),
    Bound('BJT-HFE', ('bjt',), '线性区 hFE', 'LOWER', '集电极电流与温度', 'NONMONOTONIC',
          (('G1', ()), ('G7', ('ratio_extrapolation',))), 'VENDOR_DATUM', '定界表决定（architecture.md 2026-10-23）',
          'TEST_POINT', (_e(1.5, FUNCTIONAL, '比例外推 G7，再 ÷1.5'),), ('REQUIRED_FUNCTION',), _M,
          '允许估算（÷1.5）；饱和开关走 BJT-SAT'),
    # 3.5 光耦
    Bound('OPTO-CTR', ('opto',), 'CTR 随 IF 和温度', 'LOWER', '输入电流 IF 与温度', 'NONMONOTONIC',
          (('G1', ()), ('G7', ('ratio_extrapolation',))), 'VENDOR_DATUM', _EP + '“身份冲突与身份分支”（取最低档）',
          'INDUSTRY_NONE', (_e(2, FUNCTIONAL, '25 °C 分档下限 × 典型温度曲线最低点（G7），再 ÷2（含寿命衰减）'),),
          ('REQUIRED_FUNCTION',), ('MEASURABLE', 'NOT_VERIFIABLE'),
          '允许估算判 PASS（÷2）；在保护环里也是阈值偏移，不是器件损坏。“索取全温 CTR”要提示'),
    # 3.6 NTC
    Bound('NTC-SENSE', ('ntc',), '检测用 NTC 的 R(T)', None, '温度', 'DECREASING',
          (('G5', ('ntc_table_bound', 'ntc_beta_bound')),), 'BOUNDED', '本表“几条口径”检测用 NTC；datasheets.md“公开曲线表先于索取”',
          'GUARANTEED', (), ('REQUIRED_FUNCTION',), _M, '按表推法，不估算'),
    Bound('NTC-INRUSH-HOT', ('ntc',), '浪涌限制 NTC 热态重新接入', 'LOWER', '热态', None,
          (('G6', ('inrush_peak_current', 'inrush_i2t')),), 'BOUNDED', '本表“几条口径”浪涌限制 NTC',
          'TYPICAL_BY_DEFINITION', (), ('COMPONENT_DAMAGE', 'DAMAGE_OR_HAZARD'), _T, '不估算；热态阻值按 0 Ω（“按 0 Ω 定结论”）'),
    # 3.6b 压敏电阻（2026-10-26 扩表：R7 板 RV101 词表认不出）
    Bound('VAR-UC', ('varistor',), '最大持续工作电压 Uc', 'LOWER', '环境温度（额定温度以上降额）', 'DECREASING', (('G1', ()), ('G2', ())),
          'VENDOR_DATUM', 'docs/2026-10-26-cell-boundary.md 扩表记录',
          'GUARANTEED', (), ('DAMAGE_OR_HAZARD',), _M, '不估算：母线最高持续电压（含容差、过压）不超过 Uc 保证值，超额定温度按降额曲线；长期超 Uc 是热失控的安全后果'),
    Bound('VAR-VC', ('varistor',), '钳位（残）电压上界', 'UPPER', '浪涌电流（8/20 µs 同一波形）', 'INCREASING', (('G1', ()), ('G2', ())),
          'VENDOR_DATUM', 'docs/2026-10-26-cell-boundary.md 扩表记录',
          'TEST_POINT', (), ('COMPONENT_DAMAGE',), _T, '不估算；缺本板浪涌电流对应的保证值时按额定电流处 Vc max 判下游耐受'),
    Bound('VAR-SURGE', ('varistor',), '最大浪涌电流 / 能量（按次数降额）', 'LOWER', '脉冲次数与波形', 'DECREASING', (('G1', ()), ('G2', ())),
          'VENDOR_DATUM', 'docs/2026-10-26-cell-boundary.md 扩表记录',
          'GUARANTEED', (), ('DAMAGE_OR_HAZARD',), _T, '不估算：需求浪涌等级与次数对降额曲线取保证值；寿命走 DEV-C06 VARISTOR'),
    # 3.7 无源件
    Bound('RES-POWER', ('resistor',), '电阻功率、脉冲、TCR 与耐压', 'UPPER', '温度与脉宽', None, (('G1', ()), ('G5', ())),
          'VENDOR_DATUM', 'commodity-floors.md 片式电阻',
          'GUARANTEED', (), ('COMPONENT_DAMAGE',), _M, '不估算：额定、降额与脉冲曲线按保证；商品地板见 commodity-floors.md'),
    Bound('MLCC-EFFECTIVE-C', ('capacitor',), 'MLCC 有效容量（偏压、温度、老化）', 'LOWER', '直流偏压与温度', 'DECREASING',
          (('G1', ()), ('G2', ()), ('G5', ('table_interpolate',)), ('G8', ())), 'VENDOR_DATUM', 'commodity-floors.md MLCC；wca-formulas.md',
          'TYPICAL_BY_DEFINITION', (_e(1.25, FUNCTIONAL, '典型偏压曲线 × (1 − 公差) × 老化 0.9，再 ÷1.25（≈×0.8）；补偿网络 ÷1.4'),),
          ('REQUIRED_FUNCTION', 'PERFORMANCE_OR_LIFE'), _M, '允许估算判 PASS（÷1.25）'),
    Bound('ECAP-ESR-RIPPLE', ('electrolytic',), '电解 ESR 与纹波电流（温度、频率系数表）', None, '温度与频率', 'NONMONOTONIC',
          (('G1', ()), ('G5', ('table_interpolate',)), ('G9', ())), 'VENDOR_DATUM', 'commodity-floors.md 电解',
          'TEST_POINT', (_e(1.3, FUNCTIONAL, '系数表外的频率：ESR ×1.3'),
                         _e(1.3, DAMAGE, '同上，芯温余量 ≥ 10 °C', (10, '°C'))),
          ('PERFORMANCE_OR_LIFE', 'COMPONENT_DAMAGE'), _M,
          '表内按 G5（保证）；表外允许估算（×1.3），判纹波发热（损坏）另要芯温余量 ≥ 10 °C，记应力风险；寿命走 DEV-C02。'
          '“资料已读只剩折算”不是厂家数据缺口'),
    Bound('IND-ISAT', ('inductor', 'transformer', 'coupled_inductor', 'common_mode_choke'), '电感 Isat（按资料定义取温度最坏值）', 'LOWER', '温度', 'DECREASING',
          (('G1', ()), ('G2', ()), ('G5', ('table_interpolate',)), ('G9', ('typical_band',))), 'VENDOR_DATUM', 'commodity-floors.md 电感',
          'TYPICAL_BY_DEFINITION', (_e(1.3, FUNCTIONAL | DAMAGE, '典型 Isat 热态值 ÷1.3（峰流 ≤ Isat/1.3）'),), ('COMPONENT_DAMAGE',), _M,
          '允许估算判 PASS（÷1.3）：损坏类但行业别无他法；不满足 1.3 倍就开放或失败'),
    Bound('FUSE-I2T', ('fuse',), '保险丝 I²t 与温度降额', None, '脉宽与温度', 'NONMONOTONIC',
          (('G1', ()), ('G5', ('table_interpolate',))), 'VENDOR_DATUM', 'commodity-floors.md',
          'GUARANTEED', (), ('DAMAGE_OR_HAZARD', 'REQUIRED_FUNCTION'), _T,
          '不估算：保护判 max 曲线，误动作判 min 曲线；缺的若是本板冷/热态 NTC 阻值，是原理图该写没写的值（失败项，改法写算出的阻值）'),
    # 3.8 IC 通用参数
    Bound('IC-THRESHOLD', _IC_ROLES, '门限、基准', None, '温度', 'NONMONOTONIC',
          (('G1', ()), ('G4', ('tempco_bound',)), ('G7', ('ratio_extrapolation',))), 'VENDOR_DATUM', '定界表决定（architecture.md 2026-10-23）',
          'GUARANTEED', (_e(2, FUNCTIONAL, '只给 25 °C 加典型温漂时：典型温漂 ×2'),), ('REQUIRED_FUNCTION', 'COMPONENT_DAMAGE'), _M,
          '功能用途允许（×2）；用门限判保护覆盖（OVP 上限对下游绝限，损坏）时要全温 min/max'),
    Bound('IC-QUIESCENT', _IC_ROLES, '静态电流、按模式的功耗', 'UPPER', '模式与温度', None,
          (('G1', ()), ('G9', ('typical_band',))), 'VENDOR_DATUM', _EP + '“只有典型值的参数”',
          'TYPICAL_BY_DEFINITION', (_e(1.3, FUNCTIONAL, '典型 ×1.3（现行 G9）'), _e(1.5, DAMAGE, '用它判偏置电阻功耗损坏时 ×1.5')),
          ('REQUIRED_FUNCTION', 'PERFORMANCE_OR_LIFE'), _M, '允许（功能 ×1.3，损坏用途 ×1.5）'),
    Bound('IC-TIMING', _IC_ROLES, '时序参数（最小导通、延时、消隐）', None, '温度', 'NONMONOTONIC',
          (('G1', ()), ('G7', ('ratio_extrapolation',))), 'VENDOR_DATUM', '定界表决定（architecture.md 2026-10-23）',
          'GUARANTEED', (_e(2, FUNCTIONAL, '只给典型的延时：典型 ×2，取不利方向'),), ('REQUIRED_FUNCTION', 'COMPONENT_DAMAGE'), _M,
          '功能时序允许（×2）；用延时判过冲过压损坏时要 max，没有则不估算'),
    Bound('IC-IO-LEVEL', _IC_ROLES, 'IO 的 VOH/VOL', None, '负载电流与 VDD', 'INCREASING', (('G1', ()), ('G2', ()), ('G9', ())),
          'VENDOR_DATUM', '定界表决定（architecture.md 2026-10-23）',
          'TEST_POINT', (_e(1.5, FUNCTIONAL, '超测试电流：输出阻抗典型 ×1.5'),), ('REQUIRED_FUNCTION',), _M, '允许估算（×1.5）'),
    Bound('IC-IO-CURRENT', _IC_ROLES, 'IO 灌/拉电流超出规定', 'UPPER', '负载电流', None, (('G1', ()), ('G10', ())),
          'OUTSIDE_SPECIFIED', _EP + '“手册的情况按四档判”',
          'GUARANTEED', (), ('COMPONENT_DAMAGE',), _M, '不估算：超出手册给的灌/拉电流即超出规定区，记失败项（2026-10-26 定）'),
    Bound('IC-PIN-ABSMAX', _IC_ROLES, '引脚瞬态电压/注入电流对绝对最大额定', 'UPPER', '瞬态源与串联阻抗', None, (('G1', ()),),
          'OUTSIDE_SPECIFIED', '钳位规则（architecture.md 2026-10-25，B3 a）',
          'GUARANTEED', (), ('COMPONENT_DAMAGE',), _M,
          '不估算：脚上电压超绝对最大额定、手册又没给允许注入电流即超出规定区，记失败项；有串联阻抗时按算出的注入电流对手册允许值判'
          '（2026-10-26 定）'),
    Bound('IC-RECOMMENDED', _IC_ROLES, '推荐工作条件（绝对最大额定只算损坏边界）', None, '工作条件', None, (('G1', ()),),
          'OUTSIDE_SPECIFIED', 'DEV-C05',
          'GUARANTEED', (), ('REQUIRED_FUNCTION', 'COMPONENT_DAMAGE'), _M, '不估算：超出即 OUTSIDE_SPECIFIED'),
    # 3.9 R7 碰到、原来没有格的量（2026-10-26 决定 5）
    Bound('CAP-SURGE-V', ('capacitor', 'electrolytic'), '浪涌/瞬态时电容电压对额定电压', 'UPPER', '浪涌电荷与回路阻抗', 'INCREASING',
          (('G1', ()), ('G2', ()), ('G5', ()), ('G6', ())), 'OUTSIDE_SPECIFIED', _CB,
          'GUARANTEED', (), ('COMPONENT_DAMAGE', 'DAMAGE_OR_HAZARD'), _T,
          '不估算：瞬态比瞬态额定——电解按手册浪涌电压额定；MLCC 手册没给浪涌额定时，可靠性试验表的耐电压试验'
          '（如额定 ×1.5–2.5、规定秒数）作非重复瞬态的保证额定，瞬态不超过试验电压、持续不长于试验时间即可'
          '（2026-10-27，用户：A2 也改）；每个开关周期都出现的重复尖峰仍对额定电压；缺的是浪涌源与回路（设计量或标准条款）；'
          '两种额定都没给而超过额定电压即超出规定区，记失败项（2026-10-26 定）；电容爆裂是安全后果'),
    Bound('MOS-DISCHARGE-I2T', ('mosfet',), '短路放电峰流与 I²t 对脉冲能力', 'UPPER', '回路阻抗', 'DECREASING',
          (('G2', ()), ('G5', ()), ('G6', ())), 'OUTSIDE_SPECIFIED', _CB,
          'TEST_POINT', (), ('COMPONENT_DAMAGE',), _M,
          '不估算：脉冲能力按手册单脉冲曲线（保证）判，工作点超出曲线范围或 IDM 即超出规定区，记失败项（2026-10-26 定）；'
          '回路阻抗按写明的最小值，交给后续环节'),
    Bound('IC-GATE-DRIVE-I', ('mosfet',), '栅极驱动平均电流 Qg·f 对偏置供给', 'UPPER', '开关频率与 VGS', 'INCREASING',
          (('G1', ()), ('G2', ()), ('G9', ('typical_band',))), 'VENDOR_DATUM', _CB,
          'TEST_POINT', (_e(1.3, FUNCTIONAL, 'Qg 只有典型时 ×1.3'),), ('PERFORMANCE_OR_LIFE',), _M,
          '允许估算（×1.3）：Qg max 多数手册给（G1），只有典型时 ×1.3'),
))


# 风险类型（2026-10-26，用户：按方案改：三档结论加四类风险标签，只靠估算过关的角点标风险，风险不限制定稿只单列，关键参数表在
# 定界表上扩）：一个角点只能靠估算过关时，结论是“合格，但有风险”，风险按这个角点随什么变来分；降额不足但仍在额定内是应力风险。
RISK_TYPES = OrderedDict((
    ('ENVIRONMENT', '环境适应性'),   # 温度、海拔、湿度的极限角点只能按典型曲线估算
    ('LIFETIME', '寿命'),            # 设计寿命末期、累计次数后的参数（衰减、老化）只能估算
    ('CONSISTENCY', '一致性'),       # 批次、分档、超出测试点的工作点只有典型值
    ('STRESS', '应力'),              # 保证值下仍在额定内，但没满足降额规则
))
ESTIMATE_RISKS = ('ENVIRONMENT', 'LIFETIME', 'CONSISTENCY')   # cell NONE: an estimate may stand for any of these
# 每格估算代表的风险：格的“随什么变”是温度的落环境适应性，是工作点、分档的落一致性，含寿命衰减或老化的落寿命。
CELL_RISKS = OrderedDict((
    ('ZENER-VZ-UPPER', ('CONSISTENCY',)),
    ('ZENER-VZ-LOWER', ('CONSISTENCY',)),
    ('ZENER-VZ-TEMP', ('ENVIRONMENT',)),
    ('TVS-LEAK-HOT', ('ENVIRONMENT',)),
    ('DIODE-VF', ('CONSISTENCY',)),
    ('DIODE-VF-COLD', ('ENVIRONMENT',)),
    ('DIODE-IR-HOT', ('ENVIRONMENT',)),
    ('MOS-VGS-ON', ('CONSISTENCY',)),
    ('MOS-RDS-HOT', ('ENVIRONMENT',)),
    ('MOS-LINEAR', ('CONSISTENCY', 'ENVIRONMENT')),
    ('BJT-HFE', ('CONSISTENCY', 'ENVIRONMENT')),
    ('OPTO-CTR', ('ENVIRONMENT', 'LIFETIME', 'CONSISTENCY')),
    ('MLCC-EFFECTIVE-C', ('CONSISTENCY', 'ENVIRONMENT', 'LIFETIME')),
    ('ECAP-ESR-RIPPLE', ('ENVIRONMENT', 'CONSISTENCY')),
    ('IND-ISAT', ('ENVIRONMENT',)),
    ('IC-THRESHOLD', ('ENVIRONMENT',)),
    ('IC-QUIESCENT', ('CONSISTENCY', 'ENVIRONMENT')),
    ('IC-TIMING', ('ENVIRONMENT', 'CONSISTENCY')),
    ('IC-IO-LEVEL', ('CONSISTENCY',)),
    ('IC-GATE-DRIVE-I', ('CONSISTENCY',)),
))


def cell_risks(cell_id):
    """The risk types an estimate in this cell stands for (cell NONE: any estimate risk)."""
    return CELL_RISKS.get(cell_id, ESTIMATE_RISKS if cell_id == NO_CELL else ())


def estimate_rule(cell_id, consequence_class):
    """The table's estimate rule for this consequence class in this cell, or None (no estimate passes)."""
    bound = BOUNDS.get(cell_id)
    if bound is None or consequence_class in ESTIMATE_NEVER:
        return None
    for e in bound.estimates:
        if consequence_class in e.applies:
            return e
    return None


NO_CELL = 'NONE'   # a decisive margin whose parameter has no cell in the table says so

# Words that name a cell's parameter in a margin's against / aspect or its limit's says: a decisive margin written with
# cell NONE while one of these matches is a hint (BOUNDING_CELL_AVAILABLE). On a vendor-datum gap they are a check
# (review_functions._gap_cell_errors, 2026-10-26): a gap whose words name a cell names that cell or says why not.
CELL_WORDS = OrderedDict((
    ('ZENER-VZ-UPPER', r'\bV_?Z\b|齐纳电压|击穿电压|稳压值'),
    ('ZENER-VZ-LOWER', r'\bV_?Z\b|齐纳电压|击穿电压|稳压值'),
    ('ZENER-VZ-TEMP', r'温度系数|tempco|\bS_?Z\b|温漂'),
    ('REF-IKA-MIN', r'\bI_?KA\b|最小阴极电流'),
    ('TVS-STANDOFF', r'\bV_?RWM\b|截止电压|stand-?off'),
    ('TVS-VC', r'钳位电压|\bV_?C\b(?!C)|clamping voltage'),
    ('TVS-LEAK-HOT', r'高温漏电|\bI_?R\b.{0,12}(?:85|105|125|150)\s?°?C'),
    ('DIODE-VF', r'\bV_?F\b|正向(?:压降|电压)|forward voltage'),
    ('DIODE-VF-COLD', r'冷态|\bV_?F\b.{0,12}[−-]\s?\d+\s?°?C'),
    ('DIODE-IR-HOT', r'反向漏电|\bI_?R\b|leakage'),
    ('DIODE-SURGE', r'\bI_?FSM\b|浪涌电流|surge current'),
    ('MOS-VGS-ON', r'V_?GS\s?\(?(?:th|on)\)?|导通.{0,6}V_?GS|V_?GS.{0,6}导通|plateau'),
    ('MOS-RDS-HOT', r'R_?DS\s?\(?on\)?'),
    ('MOS-SOA-HOT', r'\bSOA\b|安全工作区|脉冲功率'),
    ('MOS-LINEAR', r'源跟随|线性稳压|跨导|\bg_?fs\b'),
    ('BJT-SAT', r'饱和|\bI_?B\b|强制 ?β|forced beta'),
    ('BJT-HFE', r'\bh_?FE\b|电流增益'),
    ('OPTO-CTR', r'\bCTR\b|电流传输比'),
    ('NTC-SENSE', r'\bR_?25\b|\bB_?25\b|R\(T\)'),
    ('NTC-INRUSH-HOT', r'浪涌限制|热态.{0,6}(?:NTC|阻值)|inrush'),
    ('VAR-UC', r'持续工作电压|\bU_?c\b|continuous operating voltage|压敏.{0,8}(?:额定|工作)电压'),
    ('VAR-VC', r'压敏.{0,10}(?:钳位|残压)|残压|varistor.{0,12}clamp'),
    ('VAR-SURGE', r'压敏.{0,10}(?:浪涌|能量|次数)|\bW_?max\b|8/20'),
    ('RES-POWER', r'电阻.{0,10}额定功率|\bP_?rated\b|电阻.{0,6}耐压'),
    ('MLCC-EFFECTIVE-C', r'有效容量|直流偏压|DC ?bias|容量.{0,6}(?:偏压|老化)'),
    ('ECAP-ESR-RIPPLE', r'\bESR\b|纹波电流|ripple current'),
    ('IND-ISAT', r'\bI_?sat\b|饱和电流'),
    ('FUSE-I2T', r'I\s?[²2]\s?t|熔断'),
    ('IC-THRESHOLD', r'门限|阈值|threshold|\bUVLO\b|\bV_?REF\b|基准电压'),
    ('IC-QUIESCENT', r'静态电流|\bI_?Q\b|quiescent|待机电流'),
    ('IC-TIMING', r'最小导通|消隐|延时|blank|delay|\bt_?(?:ON|OFF)(?:_?M(?:IN|AX))?\b|\bt[A-Za-z_]*\('),
    ('IC-IO-LEVEL', r'\bV_?O[HL]\b|\bV_?I[HL]\b|输出电平|输入电平'),
    ('IC-IO-CURRENT', r'\bI_?O[HL]\b|灌电流|拉电流|sink current|source current'),
    ('IC-PIN-ABSMAX', r'绝对最大|绝限|abs(?:olute)?[ .-]?max|注入|injection'),
    ('IC-RECOMMENDED', r'推荐工作|recommended operating'),
    ('CAP-SURGE-V', r'浪涌.{0,8}(?:电压|抬升)|surge voltage|电容.{0,6}瞬态电压|BULK.{0,6}抬升'),
    ('MOS-DISCHARGE-I2T', r'短路放电|放电峰流|放电.{0,4}I\s?[²2]\s?t|discharge'),
    ('IC-GATE-DRIVE-I', r'\bQ_?g\b|栅极电荷|驱动电流|gate charge'),
))
_CELL_WORDS_RE = {cell: re.compile(words, re.I) for cell, words in CELL_WORDS.items()}


def cells_named_by(text_):
    """The table cells whose parameter words appear in this text, in table order."""
    if not isinstance(text_, str) or not text_:
        return []
    return [cell for cell in BOUNDS if cell in _CELL_WORDS_RE and _CELL_WORDS_RE[cell].search(text_)]


def bounds_for(kinds):
    """The table cells for these device kinds, in table order."""
    kinds = set(kinds)
    return [b for b in BOUNDS.values() if kinds & set(b.kinds)]


def render_bounds_markdown():
    """references/bounding-table.md 的标记区间：推法、档位和逐格表。"""
    out = ['### 推法', '', '| 编号 | 推法 | 得到的依据 |', '|---|---|---|']
    out += ['| %s | %s | %s |' % (m.code, _cell(m.name), m.basis) for m in BOUND_METHODS.values()]
    out += ['', '### 推不出时', '', '| 写法 | 意思 |', '|---|---|']
    out += ['| `%s` | %s |' % item for item in BOUND_FALLBACKS.items()]
    out += ['', '### 逐格', '', '| 格 | 器件类别 | 参数 | 开着的一侧 | 随什么变 / 方向 | 推法（公式） | 推不出时 | 出处 |',
            '|---|---|---|---|---|---|---|---|']
    for b in BOUNDS.values():
        methods = '；'.join(code + ('（%s）' % '、'.join('`%s`' % f for f in formulas) if formulas else '')
                           for code, formulas in b.methods)
        kinds = '、'.join(b.kinds) if b.kinds != _IC_ROLES else 'ic 及各 IC 角色'
        out.append('| `%s` | %s | %s | %s | %s / %s | %s | `%s` | %s |' % (
            b.id, kinds, _cell(b.parameter), b.side or '—', _cell(b.varies_with), b.direction or '—', methods,
            b.fallback, _cell(b.source)))
    out += ['', '### 判决边界', '',
            '可得性：' + '；'.join('`%s` %s' % kv for kv in BOUND_AVAILABILITY.items()) + '。',
            '样机能否验：' + '；'.join('`%s` %s' % kv for kv in BOUND_PROTOTYPE.items()) + '。',
            '后果类：' + '、'.join('`%s` %s' % kv for kv in CONSEQUENCE_WORDS.items()) + '；`%s` 任何格都不估算。' % '`、`'.join(sorted(ESTIMATE_NEVER)),
            '倍数的意思：把估算值再按不利方向打这个折（电流增益 ÷2、阻值 ×1.2 都写 2 / 1.2）之后结论仍成立；“余量下限”是余量本身至少多少。', '',
            '“估算对应的风险”见上文“风险标签”。', '',
            '| 格 | 可得性 | 允许的估算（倍数 · 适用后果 · 余量下限） | 估算对应的风险 | 失效后果 | 样机能否验 | 边界 |', '|---|---|---|---|---|---|---|']
    for b in BOUNDS.values():
        if b.estimates:
            est = '<br>'.join('×%g · %s%s：%s' % (
                e.factor, '/'.join(CONSEQUENCE_WORDS.get(c, c) for c in CONSEQUENCE_WORDS if c in e.applies) or '/'.join(sorted(e.applies)),
                (' · 余量 ≥ %g %s' % e.floor) if e.floor else '', _cell(e.how)) for e in b.estimates)
        else:
            est = '不估算'
        out.append('| `%s` | `%s` | %s | %s | %s | %s | %s |' % (
            b.id, b.availability, est, '、'.join(RISK_TYPES[r] for r in CELL_RISKS.get(b.id, ())) or '—',
            '/'.join(CONSEQUENCE_WORDS.get(c, c) for c in b.consequence),
            '、'.join(BOUND_PROTOTYPE[p].split('（')[0] for p in b.prototype), _cell(b.boundary)))
    return '\n'.join(out) + '\n'

QUESTION_BAN_RE = re.compile(r'禁止|严禁|勿|不(得|能|可|准|要|把|以|强加|默认|另|自动|单|统一|套|据此|强制|推翻|代替|归|随|再|必|需)')


def question(rule_id, state, circuit, refs, window=None):
    """电路检查项的问题，按电路填空；没有模板的规则返回 None。"""
    template = QUESTIONS.get(rule_id)
    if template is None:
        return None
    return template.format(state=state, circuit=circuit, refs='、'.join(refs), window=WINDOW % window if window else NO_WINDOW)


def frame_question(type_name, circuit, refs, states, window=None):
    body = FRAME_QUESTIONS.get(type_name) or '电路检查项的问题是否都成立'
    return (FRAME_PREFIX + body).format(circuit=circuit, refs='、'.join(refs), states='/'.join(states),
                                        window=WINDOW % window if window else NO_WINDOW)


def question_errors(plan):
    """计划里每个问题（检查项的 question、功能框架的 question）都不含禁止句；审查员补加的检查项同样受限。"""
    errors = []
    for item in plan.get('checks') or []:
        if isinstance(item, dict) and isinstance(item.get('question'), str) and QUESTION_BAN_RE.search(item['question']):
            errors.append('%s: question 含禁止句，改写成要算什么、对照什么' % item.get('id'))
    for frame in plan.get('functions') or []:
        if isinstance(frame, dict) and isinstance(frame.get('question'), str) and QUESTION_BAN_RE.search(frame['question']):
            errors.append('functions.%s: question 含禁止句，改写成要算什么、对照什么' % frame.get('id'))
    return errors


# 审查过程的六个覆盖维度及其审计规则。
COVERAGE_RULES = {
    'input_consistency': 'DOC-Q01',
    'requirements': 'REQ-Q01',
    'chains': 'REQ-Q02',
    'states': 'REQ-Q03',
    'datasheets': 'DEV-Q01',
    'history': 'REQ-Q04',
}

# Requirement categories and aspects (fixed requirements, step 2; decomposition by parameter, 2026-10-24). A
# requirement is decomposed into aspects, each with a fixed criterion template, so two reviewers ask the same REQ-D01
# rows. A numeric aspect names the requirement parameters that ask it: it is asked when the requirement states one of
# them, whatever categories the reviewer chose. A qualitative aspect (no parameters) is asked by its category. A
# requirement that states no parameters falls back to every aspect of its categories, and the planner lists the
# unit-bearing numbers of its text that were not read.
REQUIREMENT_ASPECTS = OrderedDict([
    ('INPUT_STAGE_RATING', RequirementAspect('输入级器件额定覆盖', '需求输入范围的持续上下限下，输入级器件的持续电压、电流额定覆盖并有降额余量；需求的瞬态（一次一个）'
                                             '对瞬态额定或绝对最大额定，不另要降额余量',
                                             ('input_voltage', 'surge_voltage'))),
    ('INPUT_THRESHOLDS', RequirementAspect('启动与欠压门限覆盖', '启动、欠压与过压门限落在需求输入范围之外或边界上，范围内不误动作',
                                           ('input_voltage',))),
    ('CONVERTER_INPUT_RANGE', RequirementAspect('变换级工作范围覆盖', '变换级控制器与功率器件的工作输入范围覆盖需求输入范围',
                                                ('input_voltage', 'input_frequency'))),
    ('OUTPUT_LEVELS', RequirementAspect('各档输出可达', '需求的每个输出电压档或范围由反馈与设定网络算得可达，并留调节余量', ('output_voltage',))),
    ('OUTPUT_LIMITS', RequirementAspect('电流与功率限制', '需求的电流与功率限值有采样与限制通路，限值按元件值算得落在需求窗口内',
                                        ('output_current', 'output_power'))),
    ('OUTPUT_ACCURACY', RequirementAspect('精度与纹波', '输出精度与纹波按基准、分压公差与输出滤波算得在需求窗口内', ('ripple', 'accuracy'))),
    ('FUNCTION_PRESENT', RequirementAspect('功能与接口存在且数量达标', '需求的每个功能、接口由实际器件与连接落实，路数、端口数与需求一致')),
    ('PROTOCOL_ROLE', RequirementAspect('协议角色与能力', '所选控制器手册声明的协议角色与能力覆盖需求，外围连接与之相符；本机配置表不在原理图审查之内')),
    ('PORT_DETECTION', RequirementAspect('端口识别通路', '需求依赖的对端、线缆或附件识别有完整信号通路')),
    ('EXTERNAL_PINOUT', RequirementAspect('对外引脚定义', '对外连接器的每个引脚定义与需求一致，未用引脚的处理有依据')),
    ('POWER_SEQUENCE', RequirementAspect('上电与掉电顺序', '需求的供电建立顺序、掉电顺序与恢复由使能、监控或时序链保证')),
    ('STARTUP_TIMING', RequirementAspect('启动、复位与保持时间', '启动时间、复位脉宽与掉电保持时间按元件值与器件参数算得在需求窗口内',
                                         ('startup_time', 'hold_up_time', 'reset_time'))),
    ('FAULT_DETECTION', RequirementAspect('检测通路存在', '需求的每种故障有检测通路接到能动作的器件')),
    ('FAULT_THRESHOLD', RequirementAspect('动作门限', '检测门限按元件值与器件阈值算得落在需求窗口内，正常工作范围内不误动作',
                                          ('trip_current', 'trip_voltage', 'surge_voltage', 'esd_voltage'))),
    ('FAULT_RESPONSE', RequirementAspect('动作后状态与恢复', '故障动作后的输出状态、锁定或自动恢复方式与需求一致')),
    ('MEASUREMENT_CHAIN', RequirementAspect('检测链完整', '需求的每个被测量有取样、返回地与判决链，取样点与被测量一致')),
    ('MEASUREMENT_ACCURACY', RequirementAspect('测量精度', '测量误差按传感器、偏置、采样链与 ADC 的误差和温漂合计在需求窗口内',
                                               ('measurement_accuracy',))),
    ('TEMPERATURE_GRADE', RequirementAspect('器件温度等级覆盖', '器件温度等级覆盖需求环境温度加内部温升', ('ambient_temperature', 'storage_temperature'))),
    ('TEMPERATURE_DERATING', RequirementAspect('按温度降额', '器件额定按需求温度降额后仍有余量；需求要求随温度降额输出时，有温度检测与降额通路',
                                               ('ambient_temperature',))),
    ('TEMPERATURE_DRIFT', RequirementAspect('敏感参数温漂', '基准、门限、采样等敏感参数在需求温度范围的漂移计入窗口', ('ambient_temperature',))),
    ('ALTITUDE_HUMIDITY', RequirementAspect('海拔与湿度影响额定', '需求的海拔、湿度、气候条件对器件额定与绝缘等级的影响已计入', ('humidity', 'altitude'))),
    ('ISOLATION_PARTS', RequirementAspect('跨隔离器件资格', '跨隔离边界的每个器件绝缘等级与资格满足需求的绝缘类别', ('isolation_voltage',))),
    ('ISOLATION_PATHS', RequirementAspect('隔离路径唯一', '隔离边界两侧之间只经有资格的跨隔离器件相连，没有别的电气路径')),
    ('DOWNSTREAM_HANDOFF', RequirementAspect('原理图外部分移交', '原理图判不了的部分（爬电与电气间隙、整机试验、认证）列为移交项并写复验条件')),
    ('LIFETIME_BASIS', RequirementAspect('寿命计算依据', '寿命关键件有按需求工作条件算的寿命依据', ('lifetime',))),
    ('MISSION_PROFILE', RequirementAspect('按任务剖面复算', '寿命按需求任务剖面（工作时间、温度、负载）复算，实测温度后复算的条件写明', ('lifetime',))),
    ('STANDBY_POWER', RequirementAspect('待机与静态功耗上界', '待机或静态功耗按各轨空载电流与器件静态电流算得上界在需求窗口内',
                                        ('standby_power', 'quiescent_current'))),
    ('EFFICIENCY', RequirementAspect('效率', '效率只能样机实测：原理图核拓扑与主要损耗上界是否允许达到需求值，实测列为移交', ('efficiency',))),
    ('CLOCK_ACCURACY', RequirementAspect('时钟频率精度', '晶体或振荡器的频率精度、负载电容偏差与温漂合计在需求 ppm 窗口内', ('clock_accuracy',))),
    ('TEST_ACCESS', RequirementAspect('测试点与烧录调试口', '需求的测试点、烧录与调试接口在原理图上电气预留；可触达性与夹具交移交')),
    ('INDICATOR_PRESENT', RequirementAspect('指示功能存在', '需求的每个指示有驱动通路，指示的状态与需求一致')),
    ('INDICATOR_SUPPLY', RequirementAspect('指示供电独立', '指示的供电与被指示对象的关断或故障互不影响，与需求一致')),
    ('NO_SCHEMATIC_CRITERION', RequirementAspect('没有原理图判据', '优化目标或取舍原则在原理图上没有判据：记不适用（NA）并引原文')),
    ('SCHEMATIC_COMPLIANCE', RequirementAspect('原理图可核部分', '标准或认证中原理图能核的器件资格与电路要求逐条核')),
    ('EXCLUDED_FUNCTION', RequirementAspect('明确排除', '需求明确排除的功能或认证：记排除原文，相应检查记不适用（NA）')),
])
REQUIREMENT_CATEGORIES = OrderedDict([
    ('INPUT_RANGE', RequirementCategory('输入电气范围', ('INPUT_STAGE_RATING', 'INPUT_THRESHOLDS', 'CONVERTER_INPUT_RANGE'),
                                        '系统 SYS-POWER，输入相关电路', '原文说板子从外面接什么电：输入电压、频率、瞬态、热插拔')),
    ('OUTPUT_SPEC', RequirementCategory('输出电气规格', ('OUTPUT_LEVELS', 'OUTPUT_LIMITS', 'OUTPUT_ACCURACY'),
                                        '输出相关电路、供电接口', '原文给输出的电压、电流、功率、精度或纹波的数')),
    ('FUNCTION', RequirementCategory('功能与数量', ('FUNCTION_PRESENT',), '落实该功能的电路、接口',
                                     '原文要求有某个功能或接口，或给出路数、端口数、通道数（“4 路 RS-485”“2 个 USB”）')),
    ('PROTOCOL', RequirementCategory('协议与接口功能', ('PROTOCOL_ROLE', 'PORT_DETECTION', 'EXTERNAL_PINOUT'), '接口、主控电路',
                                     '原文点名协议、角色（主/从、Host/Device、PD 角色）、识别或对外引脚定义')),
    ('TIMING', RequirementCategory('时序与启动', ('POWER_SEQUENCE', 'STARTUP_TIMING'), '系统 SYS-SEQUENCE、启动与复位电路',
                                   '原文说上电/掉电顺序、启动时间、复位、保持时间、看门狗')),
    ('PROTECTION', RequirementCategory('保护与故障响应', ('FAULT_DETECTION', 'FAULT_THRESHOLD', 'FAULT_RESPONSE'),
                                       '保护电路、监控 SYS-MONITOR', '原文说过流、过压、短路、反接、浪涌、ESD 等故障要怎样检测、在哪动作、动作后怎样')),
    ('MEASUREMENT', RequirementCategory('测量与监测', ('MEASUREMENT_CHAIN', 'MEASUREMENT_ACCURACY'), '模拟与检测电路',
                                        '原文要求测量或监测某个量（温度、电流、电压）并给范围或精度')),
    ('ENVIRONMENT', RequirementCategory('环境条件', ('TEMPERATURE_GRADE', 'TEMPERATURE_DERATING', 'TEMPERATURE_DRIFT',
                                                 'ALTITUDE_HUMIDITY'), '全板器件应力，各电路', '原文给工作或储存温度、湿度、海拔、气候条件')),
    ('SAFETY_ISOLATION', RequirementCategory('安规与隔离', ('ISOLATION_PARTS', 'ISOLATION_PATHS', 'DOWNSTREAM_HANDOFF'),
                                             '隔离接口、链路', '原文说隔离、绝缘电压、安规类别、爬电与电气间隙')),
    ('LIFETIME', RequirementCategory('寿命与可靠性', ('LIFETIME_BASIS', 'MISSION_PROFILE'), '相关电路器件检查项',
                                     '原文给设计寿命、MTBF、工作时长或循环次数')),
    ('POWER_BUDGET', RequirementCategory('功耗与效率', ('STANDBY_POWER', 'EFFICIENCY'), '电源树、变换器电路',
                                         '原文给待机功耗、静态电流或效率的数')),
    ('INDICATION', RequirementCategory('指示与人机', ('INDICATOR_PRESENT', 'INDICATOR_SUPPLY'), '相关电路',
                                       '原文要求指示灯、蜂鸣器、按键等人机部件及其状态')),
    ('TESTABILITY', RequirementCategory('测试与生产', ('TEST_ACCESS',), '全板', '原文要求测试点、烧录口、调试口或生产测试方式')),
    ('CLOCK', RequirementCategory('时钟精度', ('CLOCK_ACCURACY',), '时钟电路', '原文给时钟或 RTC 的频率精度（ppm）或走时误差')),
    ('OPTIMIZATION', RequirementCategory('优化目标', ('NO_SCHEMATIC_CRITERION',), '全板', '原文是成本、体积、取舍优先级这类没有原理图判据的目标')),
    ('COMPLIANCE', RequirementCategory('合规与认证', ('SCHEMATIC_COMPLIANCE', 'DOWNSTREAM_HANDOFF'), '全板，移交',
                                       '原文点名标准、认证或 EMC 等级')),
    ('EXCLUSION', RequirementCategory('明确排除', ('EXCLUDED_FUNCTION',), '被排除功能对应的检查项', '原文明确不要求某功能、模式或认证')),
])

# Requirement parameters (fixed requirements, step 3): the numbers a reviewer reads from a requirement's original text,
# by name; `units` maps each accepted spelling to its factor into the canonical unit.
_VOLTS = {'V': 1, 'mV': 1e-3, 'kV': 1e3, 'Vac': 1, 'VAC': 1, 'Vdc': 1, 'VDC': 1}
_CELSIUS = {'°C': 1, '℃': 1}
_SECONDS = {'s': 1, 'ms': 1e-3, 'µs': 1e-6, 'us': 1e-6}
REQUIREMENT_PARAMETERS = OrderedDict([
    ('input_voltage', RequirementParameter('输入电压', 'V', _VOLTS)),
    ('input_frequency', RequirementParameter('输入频率', 'Hz', {'Hz': 1, 'kHz': 1e3})),
    ('output_voltage', RequirementParameter('输出电压', 'V', _VOLTS)),
    ('output_current', RequirementParameter('输出电流', 'A', {'A': 1, 'mA': 1e-3})),
    ('output_power', RequirementParameter('输出功率', 'W', {'W': 1, 'mW': 1e-3, 'kW': 1e3})),
    ('ripple', RequirementParameter('纹波', 'V', {'V': 1, 'mV': 1e-3, 'Vpp': 1, 'mVpp': 1e-3})),
    ('accuracy', RequirementParameter('精度', '%', {'%': 1})),
    ('surge_voltage', RequirementParameter('浪涌或瞬态电压', 'V', _VOLTS)),
    ('esd_voltage', RequirementParameter('静电放电电压', 'V', _VOLTS)),
    ('ambient_temperature', RequirementParameter('工作环境温度', '°C', _CELSIUS)),
    ('storage_temperature', RequirementParameter('储存温度', '°C', _CELSIUS)),
    ('humidity', RequirementParameter('相对湿度', '%RH', {'%RH': 1, '%': 1})),
    ('altitude', RequirementParameter('海拔', 'm', {'m': 1, 'km': 1e3})),
    ('lifetime', RequirementParameter('设计寿命', '年', {'年': 1, 'year': 1, 'h': 1 / 8760})),
    ('trip_current', RequirementParameter('保护动作电流', 'A', {'A': 1, 'mA': 1e-3})),
    ('trip_voltage', RequirementParameter('保护动作电压', 'V', _VOLTS)),
    ('isolation_voltage', RequirementParameter('绝缘电压', 'V', dict(_VOLTS, Vrms=1, kVrms=1e3))),
    ('startup_time', RequirementParameter('启动时间', 's', _SECONDS)),
    ('hold_up_time', RequirementParameter('掉电保持时间', 's', _SECONDS)),
    ('reset_time', RequirementParameter('复位时间', 's', _SECONDS)),
    ('standby_power', RequirementParameter('待机功耗', 'W', {'W': 1, 'mW': 1e-3})),
    ('quiescent_current', RequirementParameter('静态电流', 'A', {'A': 1, 'mA': 1e-3, 'µA': 1e-6, 'uA': 1e-6})),
    ('efficiency', RequirementParameter('效率', '%', {'%': 1})),
    ('measurement_accuracy', RequirementParameter('测量精度', '%', {'%': 1})),
    ('clock_accuracy', RequirementParameter('时钟精度', 'ppm', {'ppm': 1})),
])
PARAMETER_ASPECTS = OrderedDict((name, tuple(a for a, aspect in REQUIREMENT_ASPECTS.items() if name in aspect.parameters))
                                for name in REQUIREMENT_PARAMETERS)

# The tree rules that carry an aspect (fixed requirements, step 4): a requirement row is bound to their rows and
# takes its result from them. An aspect not listed is judged on the requirement row. A board aspect binds every row
# of its rules when the requirement names no owners.
ASPECT_RULES = OrderedDict([
    ('INPUT_STAGE_RATING', ('DEV-C01', 'PWR-C02', 'PWR-C13')),
    ('INPUT_THRESHOLDS', ('PWR-C06', 'PRO-C02')),
    ('CONVERTER_INPUT_RANGE', ('PWR-C02', 'DEV-C05')),
    ('OUTPUT_LEVELS', ('PWR-E01', 'PWR-C15')),
    ('OUTPUT_LIMITS', ('PWR-C01', 'PWR-C03', 'PWR-C06')),
    ('OUTPUT_ACCURACY', ('PWR-C14', 'DEV-C03', 'ANA-C01')),
    ('PROTOCOL_ROLE', ('SIG-T04', 'SIG-D04')),
    ('PORT_DETECTION', ('SIG-D04', 'SIG-C05')),
    ('EXTERNAL_PINOUT', ('DEV-D03',)),
    ('FAULT_DETECTION', ('ANA-T01', 'ANA-C04', 'PWR-T04')),
    ('FAULT_THRESHOLD', ('PWR-C06', 'PRO-C02')),
    ('FAULT_RESPONSE', ('PRO-C01', 'PRO-D03', 'RST-T03')),
    ('TEMPERATURE_GRADE', ('DEV-C05',)),
    ('TEMPERATURE_DERATING', ('DEV-C01',)),
    ('TEMPERATURE_DRIFT', ('ANA-C01', 'DEV-C03')),
    ('ISOLATION_PARTS', ('PRO-C03', 'PRO-D01')),
    ('ISOLATION_PATHS', ('PRO-D02',)),
    ('LIFETIME_BASIS', ('DEV-C02', 'DEV-C06')),
    ('MISSION_PROFILE', ('DEV-C02', 'DEV-C06')),
    ('STANDBY_POWER', ('PWR-C16',)),
    ('POWER_SEQUENCE', ('RST-T03',)),
    ('STARTUP_TIMING', ('RST-C02',)),
    ('MEASUREMENT_CHAIN', ('ANA-T01',)),
    ('MEASUREMENT_ACCURACY', ('ANA-C01',)),
    ('CLOCK_ACCURACY', ('CLK-C01',)),
    ('TEST_ACCESS', ('DOC-D02',)),
])
BOARD_ASPECTS = ('TEMPERATURE_GRADE', 'TEMPERATURE_DERATING', 'LIFETIME_BASIS', 'MISSION_PROFILE', 'ISOLATION_PARTS',
                 'ISOLATION_PATHS', 'TEST_ACCESS')
# Aspects whose whole question is work after the schematic: their requirement row may be stage NA as a whole
# (NA / OUTSIDE_SCHEMATIC_STAGE with the downstream handoff), the design obligations of the same requirement being
# the other aspects' rows (R6 acceptance 2026-10-24, codex2 SR-02 / claude1).
STAGE_ASPECTS = ('DOWNSTREAM_HANDOFF',)

# The circuit types that usually carry an aspect (requirement owners, 2026-10-24; in Chinese 承接电路, the circuits
# that realise the requirement, and 可承接的电路 for the ones the plan finds). A requirement row's candidate owners are
# the circuits of these types, and every system function and interface, that own an applicable row of the aspect's
# rules; with a candidate the requirement must name its owners (or `owners: []` with a located reason). Board aspects
# bind every row and have no candidates.
# Each cell lists the circuit types, the system functions and the interface kinds that may carry the aspect; an owner
# of another type, function or kind is not a candidate even when it owns a row of the aspect's rules (user, 2026-10-24:
# 系统功能和接口也按方面白名单过滤).
AspectOwners = namedtuple('AspectOwners', 'circuits systems interfaces')
_INPUT_TYPES = ('POWER_PROTECTION', 'POWER_CONVERTER')
_FAULT_TYPES = ('POWER_PROTECTION', 'POWER_CONVERTER', 'ANALOG')
_BUS_TYPES = ('USB', 'CAN', 'RS485', 'UART', 'SPI', 'I2C', 'ETHERNET', 'HSSERIAL', 'AV', 'STORAGE', 'DDR')
_INPUT = AspectOwners(_INPUT_TYPES, ('SYS-POWER',), ())
_OUTPUT = AspectOwners(('POWER_CONVERTER',), (), ('SUPPLY',))
_PROTOCOL = AspectOwners(_BUS_TYPES, (), ('CIRCUIT_PAIR', 'LINK'))
_FAULT = AspectOwners(_FAULT_TYPES, ('SYS-MONITOR', 'SYS-SEQUENCE'), ())
_MEASUREMENT = AspectOwners(('ANALOG',), ('SYS-MONITOR',), ())
_TIMING = AspectOwners(('STARTUP',), ('SYS-SEQUENCE',), ())
ASPECT_OWNER_TYPES = OrderedDict([
    ('INPUT_STAGE_RATING', _INPUT), ('INPUT_THRESHOLDS', _INPUT), ('CONVERTER_INPUT_RANGE', _INPUT),
    ('OUTPUT_LEVELS', _OUTPUT), ('OUTPUT_LIMITS', _OUTPUT), ('OUTPUT_ACCURACY', _OUTPUT),
    ('PROTOCOL_ROLE', _PROTOCOL), ('PORT_DETECTION', _PROTOCOL), ('EXTERNAL_PINOUT', AspectOwners((), (), ('EXTERNAL',))),
    ('FAULT_DETECTION', _FAULT), ('FAULT_THRESHOLD', _FAULT), ('FAULT_RESPONSE', _FAULT),
    ('MEASUREMENT_CHAIN', _MEASUREMENT), ('MEASUREMENT_ACCURACY', _MEASUREMENT),
    ('POWER_SEQUENCE', _TIMING), ('STARTUP_TIMING', _TIMING),
    ('CLOCK_ACCURACY', AspectOwners(('CLOCK',), (), ())),
])


def requirement_aspects(categories, parameters=None):
    """The aspects a requirement asks, in table order: the qualitative aspects of its categories plus the numeric
    aspects its stated parameters ask (whatever the categories); with no parameters stated, every aspect of its
    categories."""
    names = {p['name'] if isinstance(p, dict) else p for p in parameters or ()}
    wanted = set()
    for category in categories:
        for aspect in REQUIREMENT_CATEGORIES[category].aspects:
            if not names or not REQUIREMENT_ASPECTS[aspect].parameters:
                wanted.add(aspect)
    for name in names:
        wanted.update(PARAMETER_ASPECTS.get(name, ()))
    return [aspect for aspect in REQUIREMENT_ASPECTS if aspect in wanted]


def requirement_criterion(aspect):
    entry = REQUIREMENT_ASPECTS[aspect]
    return '%s：%s' % (entry.name, entry.template)


ID_RE = re.compile(r'^([A-Z]{3})-([A-Z])(\d{2})$')
METHOD_ORDER = ''.join(m.code for m in METHODS)
DOMAIN_BY_CODE = {d.code: d for d in DOMAINS}
METHOD_BY_CODE = {m.code: m for m in METHODS}

# -- 输入依赖与执行阶段 ---------------------------------------------------
# 方式字母同时编码了“谁来做”和“要什么输入”。这里把输入依赖单列，网表扫描、审查与复审阶段由它推出；
# 规则编号不变。
INPUTS = OrderedDict([
    ('netlist', '网表'),
    ('export_log', '导出日志'),
    ('intent', '审查意图声明'),
    ('assembly', '装配与状态表'),
    ('datasheet', '规格书数值'),
    ('requirement', '需求'),
    ('drawing', '图面'),
    ('ledger', '计划与结果台账'),
    ('history', '上一版网表与意见'),
])
METHOD_INPUTS = {
    'A': ('netlist',),
    'E': ('netlist', 'datasheet'),
    'T': ('netlist', 'assembly', 'drawing'),
    'C': ('netlist', 'datasheet', 'requirement'),
    'D': ('netlist', 'datasheet', 'requirement'),
    'V': ('drawing',),
    'Q': ('ledger',),
    'H': ('netlist', 'history'),
}
INPUT_OVERRIDES = {
    'DOC-A01': ('netlist', 'export_log'),
    'DOC-A02': ('netlist', 'export_log'),
    'REQ-A01': ('netlist', 'intent'),
}
COLD_INPUTS = {'netlist', 'export_log', 'intent'}
STAGES = OrderedDict([('cold', '网表扫描'), ('review', '审查员'), ('revision', '复审')])

# 每条规则的检查说明（第 2 版）。风险描述是检查理由，不是本次缺陷或自动严重度；
# inputs 中的规则只是复用方向，只有同一实际对象/状态的证据才构成项目依赖。
#   risk_if_omitted 盲区：朴素检查会漏掉什么（必填）
#   closes_when     关闭条件及不归本项的边界（必填）
#   inputs          复用哪个检查的哪个已核事实（只写上游，可空）
#   false_alarms    会合法触发本规则的结构（自动扫描 A 类必填）
EXPLANATION_VERSION = 2
EXPLANATION_FIELDS = ('risk_if_omitted', 'closes_when', 'inputs', 'false_alarms')
REQUIRED_EXPLANATION_FIELDS = ('risk_if_omitted', 'closes_when')
EXPLANATION_LIMITS = {'risk_if_omitted': 40, 'closes_when': 50, 'inputs': 40, 'false_alarms': 50}


def _x(risk, closes, inputs='', false_alarms=''):
    """一条第 2 版说明；空的可选字段不写入。"""
    values = dict(zip(EXPLANATION_FIELDS, (risk, closes, inputs, false_alarms)))
    return {key: value for key, value in values.items() if value}


EXPLANATIONS = {
    'DOC-A01': _x('残留的旧网表仍能被解析，看似完整却不是本版电路', '导出日志无 ERROR/中止，且网表与本版图纸同源即关闭', false_alarms='日志里的 Warning 或缺字段提示本身不等于导出中止'),
    'DOC-A02': _x('被导出器强行连网的 NC 脚在网表里像正常连接，不会再报错', '每条告警对应的脚已在实际网络中确认允许连接或已改正即关闭', inputs='NET-A04 的伪网判别', false_alarms='手册允许该脚接网（如内部无连接的 NC 脚）时不是缺陷'),
    'DOC-A03': _x('首尾空白肉眼看不出，却让同一物料在 BOM 和改版比对中变成两项', '字段已去空白或确认不影响 BOM 合并即关闭；通常不单独构成电气阻断', false_alarms='不进入 BOM 的模板占位字段可以忽略'),
    'DOC-A04': _x('带 ? 的位号无法与 BOM、整改意见和复审对应到实物', '全部实物位号唯一且无 ? 即关闭；通常不单独构成电气阻断', false_alarms='电源符号、图框等非实物符号的 # 位号不在此列'),
    'DOC-T01': _x('默认配置通过，另一种贴装组合仍可能互斥件同贴或通路断开', '每种声明的装配配置各自走通供电、信号和配置通路，且无互斥件同贴', inputs='intent.assemblies 的逐件贴装表'),
    'DOC-D01': _x('4.7F 一类笔误会被采购照抄，计算时又被按想当然的值读入', '每个值字段的数值、单位与器件类型相符即关闭'),
    'DOC-D02': _x('关键轨和 strap 点没有可接入的节点，样机出问题时无法定位', '需求或调试所需节点在电气上可接入即关闭；可触达性与夹具交 PCB'),
    'DOC-V01': _x('网表连对了，图面极性、pin1 或跨页标识错仍会误导装配和改图', '极性、pin1、跨页端口和关键标注逐页可辨且与网表一致即关闭', false_alarms='符号相邻或边框相交本身不是可读性缺陷，用局部原图核实'),
    'DOC-V02': _x('网名或注释沿用旧方案（如 _3V3 实为 1.8V），读图者会按错的电平处理', '注释、网名与实贴 BOM 和实际电平一致即关闭；通常不单独构成电气阻断'),
    'DOC-Q01': _x('各文件单独看都对，拼在一起可能来自不同版本', '图纸、BOM 与网表的版本和哈希对上，已证矛盾已判定即关闭', inputs='DOC-A01 的导出完整性'),
    'DEV-A01': _x('值字段写明的耐压低于轨压最容易漏看，但网名推断的轨压本身不可靠', '按 PWR-T01 确认的轨压复核候选即关闭；真实应力和降额交 DEV-C01', false_alarms='网名带电压却是分压后的低压网，或电容只跨在局部低压节点'),
    'DEV-A02': _x('极性电容反接在网表里只是普通连接，上电初期还可能看似正常', '+ 脚接较高电位即关闭；没有极性脚名的按图面确认', false_alarms='负压轨上 + 脚接地、- 脚接负轨是正确接法'),
    'DEV-A03': _x('LED 直接跨轨在低压下也能亮，实际电流只受内阻限制', '通路上有串阻或经证实的恒流驱动即关闭；电流和功耗交 DEV-C01', false_alarms='恒流驱动器、带限流的驱动脚或内置电阻的 LED'),
    'DEV-E01': _x('连接器符号编号与焊盘或对端习惯不同，按编号推测排针会错位', '每个触点按焊盘坐标或官方针图对上本端定义即关闭', inputs='DEV-D01 确认的连接器系列'),
    'DEV-C01': _x('标称值看似够用，最坏工况的电压、功耗或脉冲仍可能超过额定', '应力上界不超过适用额定的降额线即关闭；欠压归 DEV-C05，温升交下游', inputs='各电路计算得到的电压、电流上界'),
    'DEV-C02': _x('陶瓷电容直流偏压、电解电容高温下的有效容量可能远低于标称', '只有用途依赖有效容量或 ESR 时才索取边界；按用途核完耐压和容量即关闭'),
    'DEV-C03': _x('默认用 1% 器件，输出或测量仍可能超出允许误差窗口', '按实际误差传递，公差与温漂合计落在允许窗口内即关闭', inputs='需求给出的误差目标'),
    'DEV-C04': _x('单针额定乘针数会高估并联载流，接触电阻不均会让个别针过载', '按实际采购系列的并针降额和故障电流核完即关闭；走线载流交 PCB', inputs='PWR-C01 的电流预算'),
    'DEV-C06': _x('电解电容之外，光耦、保险丝、继电器、连接器等也会随时间或次数耗损', '按任务剖面算出的寿命或次数在器件能力内，或需求与剖面都没给次数时记 NA 即关闭', inputs='intent.mission_profile'),
    'DEV-C05': _x('在绝对最大额定内，仍可能不满足推荐条件而功能不受保证', '供电、输入、负载、频率和温度等级逐项落在保证条件内即关闭', inputs='DEV-D01 的身份、PWR-T01 的电源路径'),
    'DEV-D01': _x('同系列不同后缀的门限、封装或额定不同，可能拿错手册证明本器件', '实例 MPN、后缀和封装与所引用手册的订货信息一致即关闭'),
    'DEV-D02': _x('漏画的 EP、隐藏电源脚或错脚号会让后续计算建立在错的脚上', '官方脚与符号脚双向差集为空，或每处差异都有依据即关闭', inputs='DEV-D01 确认的器件身份'),
    'DEV-D03': _x('板内自洽的针序到了对端，电源、地或收发方向仍可能冲突', '每针本端定义与对端定义逐针相容即关闭；防护归 PRO-D03', inputs='DEV-E01 的触点映射'),
    'DEV-D04': _x('库字段或 MPN 与原厂订货组合不一致，会把错的物料送去采购', '实例采购字段与原厂订货组合一致，最低额定已写成 BOM 约束即关闭', false_alarms='符号缓存来源名不同本身不是物料冲突'),
    'DEV-D05': _x('未用不等于可悬空；悬空输入或乱接的 NC/DNU 脚可能误动作', '按官方脚表逐脚处置都有依据即关闭', inputs='DEV-D02 的官方脚表'),
    'DEV-Q01': _x('关键器件可能在没有适用手册章节时被默认通过', '每个关键器件的适用章节、errata 和脚差集都有可定位出处即关闭'),
    'NET-A01': _x('网名两处相同不等于连通；单节点网说明本该相连的信号实际断开', '按 DEV-D05 确认该脚允许悬空，或补上连接即关闭', false_alarms='测试点、被删外设留下的 SoC 脚、按引脚自动生成的未用网'),
    'NET-A02': _x('只差一个下划线或后缀的两张网在网表里互不相连，读图时却像同一张', '确认两网本应分开，或已合并即关闭；端点意图由 PWR-T01/SIG-T04 核', false_alarms='同族总线、差分对、序号/字母序兄弟、RX/TX 收发对、同名双路和工具自动生成的网名'),
    'NET-A03': _x('只挂无源件的自动编号网可能是断开的中间节点，滤波或终端实际不起作用', '确认该节点属于某个功能电路（如 RC 中点、分压中点）即关闭', false_alarms='RC/LC 中点、分压中点、反馈网络内部节点本来就只接无源件'),
    'NET-A04': _x('名为 NC 的网可能是设计者画出的真实短接，误当伪网会漏掉短路', '按判别式区分真实短接和导出器汇集网，并有图面或属性证据即关闭', inputs='DOC-A02 的导出告警', false_alarms='导出器的 No-Connect 汇集网；继电器 NC 常闭触点各自独立成网'),
    'NET-A07': _x('声明为输入的脚悬空时状态不确定，上电或干扰下可能随机翻转', '确认有有效偏置、片内上下拉或手册允许悬空即关闭', inputs='DEV-D05 的引脚处置', false_alarms='已标 NC 的无源连接器未用针；片内带上下拉且手册允许悬空的输入'),
    'NET-A06': _x('多个推挽输出直连会争用，单看各自连接都正常', '逐条确认是开漏、三态或互斥使能等合法结构，或已改正即关闭', inputs='DEV-D02 的真实脚义', false_alarms='开漏线与、三态总线、库把无源脚标成输出'),
    'PWR-A01': _x('电源轨可能只靠信号脚反灌供电，看起来有电其实没有真正的源', '沿已装配通路追到输出脚或声明的外部来源即关闭', false_alarms='由连接器从板外供电的轨；经已贴跳线或开关接入的轨'),
    'PWR-A02': _x('供电脚接在无来源的轨上或直接接地，器件可能经 IO 寄生取电而似乎能工作', '供电脚所在轨能追到有效来源即关闭；电压窗口交 DEV-C05', inputs='DEV-D02 的脚义', false_alarms='片内 LDO 输出脚（如 VCAP）被命名为 VDD；板外供电的轨；VSS/VEE 等负电源脚接地'),
    'PWR-A03': _x('地名网看似接地，经电容或未贴件隔开后器件实际没有回流', '确认地脚经已装配直流通路到参考地，或隔离设计有依据即关闭', false_alarms='隔离器两侧的独立地；同一 IC 的 AGND/PGND 片内相连'),
    'PWR-A04': _x('名字几乎相同的两条轨可能是不同电压域，监测或供电可能接错对象', '确认每条轨的来源与负载，监测对象未张冠李戴即关闭', false_alarms='经开关或滤波分出的子轨本来就该分开命名'),
    'PWR-A05': _x('输入 LC 滤波与开关稳压器负阻抗可能谐振，单独看两者都稳定', '有阻尼支路、体电容 ESR 或器件条款证明无需阻尼即关闭；计算归 PWR-E03', false_alarms='体电容 ESR 已提供阻尼；磁珠在谐振频率下本身是有损电阻'),
    'PWR-A06': _x('有一颗监控器不代表所有需要监测的轨都被监测到', '按 PWR-T04 确认需求要求的轨已监测或有不监测的依据即关闭', false_alarms='IC 自带欠压锁定已满足需求；需求不要求监测的辅助轨'),
    'PWR-E01': _x('标称输出正确，电阻与基准公差叠加后的极限电压可能越出负载窗口', '按电阻与 Vref 公差算出的窗口落在负载允许范围内即关闭', inputs='DEV-C03 的器件公差'),
    'PWR-E02': _x('典型压差够用，最低输入、最大负载和最坏温度下输出仍可能跌出窗口', '用保证最大压差核输出下限满足负载即关闭', inputs='PWR-T01 的最低输入电压'),
    'PWR-E03': _x('滤波器与变换器各自稳定，组合后的负输入阻抗可能引起振荡', '按最低输入与最大功率核阻尼判据和项目规定的电容比值即关闭', inputs='PWR-C11 的滤波元件参数'),
    'PWR-T01': _x('只核局部电压会漏掉错供、反灌和依赖未建立电源的启动路径', '每条轨的来源、负载、域电压和反灌路径都追清即关闭', false_alarms='VOUT_N 一类回流、VOUT_FBACK 一类反馈线名字像电源但不是轨'),
    'PWR-T03': _x('图上有电容不等于给对了脚：可能接在串联磁珠另一侧或返回错地', '每个电源脚找到接到正确返回网的直接电容即关闭；容量归 PWR-C09', inputs='DEV-D02 的电源脚表'),
    'PWR-T04': _x('监测信号可能漏掉需要的电压域，或检测到了却触发不了关断/复位', '需求要求监测的每个域都有监测点、门限和动作路径即关闭', inputs='PWR-T01 的电源树'),
    'PWR-T05': _x('防反接管方向画对了，体二极管朝向或栅极钳位错仍会失去保护', '正接导通、反接截止的通路和栅极钳位都核实即关闭；损耗归 PWR-C05'),
    'PWR-T06': _x('名称相近的地网不一定相连；也可能把隔离地意外接在一起', '每个地网的连接点和方式符合器件与平台要求即关闭；跨隔离归 PRO-D02'),
    'PWR-C01': _x('逐个负载都在额定内，组合起来仍可能超过电源能力', '按最重工作模式的负载合计不超过来源能力并留裕量即关闭', inputs='PWR-T01 的来源与负载'),
    'PWR-C16': _x('满载效率达标，空载下固定损耗、偏置与泄放电阻仍可能超过待机功耗要求', '按需求的待机状态算出的输入功耗上界在需求窗口内即关闭', inputs='PWR-T01 的电源树与各变换器手册的空载数据', false_alarms='需求没给待机功耗或静态电流的板子不生成本检查项'),
    'PWR-C02': _x('反馈设定正确，占空比、压差或拓扑能力不够时输出仍达不到', '要求调节的输入、负载和温度角点下输出都在窗口内即关闭', inputs='PWR-E01/PWR-E02 的窗口'),
    'PWR-C03': _x('平均电流在额定内，峰值仍可能使电感饱和或误触发限流', '峰值、RMS 对 Isat、限流和器件额定都有裕量即关闭', inputs='PWR-C01/PWR-C02 的工况'),
    'PWR-C04': _x('静态工作点都对，最小导通时间或输出电容条件仍可能不适用', '按实际拓扑核完最小导通/关断与输出电容条件；反馈模型与补偿另核PWR-C15', inputs='PWR-C02 的工作点'),
    'PWR-C15': _x('峰流或RCD应力通过不能证明闭环稳定；内部补偿不等于任意输出电容都可用', '分别核反馈模型、实际补偿配置与全部规定角点的稳定性/动态边界；无反馈环凭拓扑排除，实物测试另验', inputs='PWR-C02工作点、实际反馈路径与原厂补偿条件'),
    'PWR-C05': _x('效率估算只看稳态，掉电和预偏置时的反向电流可能损坏器件', '损耗边界和反向电流路径都有界即关闭；实际结温交下游', inputs='PWR-T05 的反流路径'),
    'PWR-C06': _x('门限中心值合理，容差叠加后可能正常工作时误动作或故障时动作过晚', '门限容差带与正常工作窗口不重叠且有裕量即关闭；协同归 PRO-C01', inputs='PWR-C01/PWR-C02 的工作范围'),
    'PWR-C09': _x('标称总容量够，串联边界另一侧的电容或降额后的容量并不算数', '直接供电段的数量、容量组合满足器件条款即关闭', inputs='PWR-T03 的分组、DEV-C02 的有效容量'),
    'PWR-C10': _x('容量够用的去耦电容可能耐压降额不足或纹波电流超额', '耐压降额和条款要求的 ESR/纹波都满足即关闭', inputs='PWR-T03 的分组与轨电压'),
    'PWR-C11': _x('有磁珠或电感不等于滤波合格：可能饱和、压降过大或温升超标', '饱和、RMS、压降和衰减量按测试条件核完即关闭；实际温升交下游'),
    'PWR-C13': _x('稳态正常的输入电容在上电瞬间可能让连接器或上游电源过流', '按实际接口算出的浪涌在源端和器件能力内即关闭', inputs='DEV-C02 的容量'),
    'PWR-C14': _x('电源纹波满足一般要求，对 PLL、ADC、RF 等敏感负载仍可能超标', '有适用噪声要求的负载逐项满足即关闭；没有适用要求不强造指标', inputs='PWR-C04/PWR-C09 的结论'),
    'PWR-D01': _x('没有名字命中的电源脚会整组漏掉，不进入任何去耦检查', '每组实际供电脚都已进入去耦清单即关闭', inputs='DEV-D02 的完整脚表'),
    'PWR-D02': _x('普通旁路接法可能被误用于飞跨、补偿或专用稳压电容', '本组按准确器件条款核完接法即关闭；容量归 PWR-C09', inputs='PWR-T03 的实际连接'),
    'PWR-D03': _x('冷启动正常，输出已有电压时同步变换器可能反向放电或卡住', '资料明确支持预偏置，软启动与浪涌、限流配合即关闭', inputs='PWR-C05 的反流结论'),
    'RST-A01': _x('上下拉画了不等于默认态对：有效极性或片内偏置相反时会反着开关', '按 RST-E01 核有效极性、默认态和脚耐压后关闭', false_alarms='片内已有同向上下拉的冗余外部电阻；双向配置脚的有意偏置'),
    'RST-A02': _x('使能与供电同网时，电源未稳就已被允许运行，平时上电却看似正常', '器件条款允许使能随电源建立，或已有 UVLO/延时满足顺序即关闭', false_alarms='器件内置 UVLO/上电复位，手册推荐 EN 直连 VIN'),
    'RST-A03': _x('使能直连输入轨，输入还没到可用电压时就可能反复启停', '器件自带 UVLO 满足需求，或已加分压/延时即关闭；顺序归 RST-T03', false_alarms='稳压器内置 UVLO 且手册推荐 EN 接 VIN'),
    'RST-A04': _x('使能网没有驱动也没有偏置时，开或关取决于漏电和噪声', '使能来源或确定的偏置有资料证据即关闭', false_alarms='器件内部上/下拉有手册保证；由板外连接器驱动的使能'),
    'RST-A05': _x('喂狗输入固定或悬空可能是有意禁用看门狗，也可能让监控失效', '确认需求允许禁用，或喂狗来源已接上即关闭', false_alarms='手册规定悬空或接固定电平即禁用看门狗，且需求不要求看门狗'),
    'RST-A06': _x('复位器件存在不等于复位能送达：输出可能接到了非复位输入', '每个应复位的输入都由已确认的复位输出驱动即关闭；时序归 RST-C02', false_alarms='复位输出先送到主控 GPIO 再由固件转发，且需求允许'),
    'RST-E01': _x('EN 有效极性弄反或上拉轨超过脚耐压，静态检查连通时不会暴露', '有效/无效电平都满足门限且脚电压不超绝限即关闭', inputs='RST-T01 的使能来源'),
    'RST-E02': _x('strap 静态电平正确，采样时被外设拉偏仍会进错启动模式', '每个 strap 的强制态在采样窗口内满足门限即关闭；时间归 RST-C01', inputs='RST-T04 的默认态'),
    'RST-E03': _x('复位器件典型脉宽够，保证最小值仍可能短于目标输入要求', '保证最小脉宽不短于接收端要求，开漏有正确域的上拉即关闭', inputs='RST-T02 的复位路径'),
    'RST-T01': _x('使能来源在正常上电下确定，掉电或故障恢复时可能依赖还没建立的电源', '上电、掉电和恢复下使能来源、UVLO 窗口和延时都确定即关闭', inputs='PWR-T01 的电源树'),
    'RST-T02': _x('有复位器件和看门狗，链路某一跳断开或电源域不对时故障仍无法恢复', '复位链逐跳连通、极性和上拉域正确，喂狗来源行为明确即关闭', inputs='PWR-T04 的监测范围'),
    'RST-T03': _x('正常上电顺序没问题，慢爬升、短暂掉电或单域掉电时仍可能死锁', '需求适用的上电、掉电和恢复状态逐一核过即关闭', inputs='PWR-T01、RST-T01/T02 的结论'),
    'RST-T04': _x('复位和断电期间 IO 高阻或内部偏置未建立，可能误开继电器或电源', '关键控制线在各适用状态都有保证的安全默认态即关闭'),
    'RST-C01': _x('strap 静态分压正确，采样瞬间电容未充好或 LED 漏电会读错', '每个采样窗口内的保证电压满足门限即关闭', inputs='RST-T03/T04 的顺序与默认态'),
    'RST-C02': _x('用 RC 时间常数估复位释放会漏掉门限容差和电源爬升速率', '按 V(t) 穿越门限的时刻核复位与 setup/hold 都满足即关闭', inputs='RST-T02/T03、CLK-C01 的建立条件'),
    'RST-D01': _x('平时能烧录的板子，固件或配置损坏后可能没有进入恢复的通道', '需求要求的恢复通道硬件可进入、电平匹配即关闭；烧录回执交上电集成'),
    'CLK-C01': _x('照手册配了负载电容，杂散电容和负阻裕量不足时仍可能低温不起振', '按准确料号核完 CL、ESR、驱动功率和起振裕量即关闭；实测交下游', inputs='DEV-D01 的晶体料号'),
    'CLK-D01': _x('时钟频率对了，输出电平、电源域或使能默认态不对，接收端仍收不到', '输出制式与接收端匹配、使能默认态和上电有效时间满足即关闭', inputs='SIG-C07 的电平判据'),
    'CLK-D03': _x('主电源在时 RTC 正常，掉电后可能停钟、丢时或反向耗电', '晶体条件满足，备份充电电压电流与反向电流在器件限值内即关闭', inputs='PWR-C05 的掉电路径'),
    'SIG-A01': _x('交流耦合发送端缺直流通路时工作点不成立，链路看似连通却无输出', '按实际制式确认发送端有直流偏置通路，或器件内部已提供即关闭', false_alarms='CML 等内部自带端接的输出；名称线索误判的非 PECL 信号'),
    'SIG-A02': _x('交流耦合后接收端没有偏置，共模漂移会让接收器无法判别', '接收端有偏置或端接，或器件内部自偏置有资料即关闭', false_alarms='接收器内部自偏置/内置端接，手册允许直接交流耦合'),
    'SIG-A03': _x('同一段 SDA/SCL 没有上拉，在其他段或片内可能有，也可能真的没有', '在主机侧、片内或其他段找到有资料的上拉即关闭；阻值归 SIG-C01', false_alarms='主控或电平转换器片内上拉；上拉在另一块板或另一段；只接测试点的配置口由夹具上拉'),
    'SIG-E01': _x('接口要求的上拉或串阻缺失时，静态连通检查发现不了', '指定两网间有已装配电阻且等效阻值在要求范围即关闭', inputs='SIG-T04 的方向'),
    'SIG-E02': _x('差分对连通了，共模或摆幅不在接收范围时仍收不到或损伤输入', '两端保证范围下共模、摆幅和阈值都兼容即关闭；时序归 SIG-C09', inputs='SIG-T01/T03 的连接与端接'),
    'SIG-T01': _x('差分对两根都连通，P/N 互换或配错对时仍无法工作', '每对 P/N 两端语义一致、全链路连通即关闭；电平归 SIG-E02', inputs='DEV-D02 的脚义', false_alarms='CS_P/CS_N 等电流电压采样对是模拟测量，按 ANA 检查'),
    'SIG-T02': _x('局部连通可能掩盖断段、错误电源域的上拉或经电平转换器的旁路', '本状态每段的端点、上拉和电源域都列清即关闭；电气计算归 SIG-C01'),
    'SIG-T03': _x('端接电阻存在，放错位置或接错电源域会建立错误共模', '端接与偏置的位置、阻值、电源域和未用通道处置都核实即关闭', inputs='SIG-T01 的连通'),
    'SIG-T04': _x('同名 TX/RX 连在一起可能是输出对输出；连通只证明有导线', '按两端官方语义复述方向并核对端视图与线缆针序即关闭', inputs='DEV-D02/D03 的脚义与对端定义'),
    'SIG-C01': _x('有上拉不等于合格：太强拉不低，太弱达不到速率，片内上拉可能没启用', '逐电气段 Rp 在灌电流下限和上升时间上限之间即关闭', inputs='SIG-T02 的分段、电容和电源域'),
    'SIG-C03': _x('端接电阻都在，节点数和偏置不对时空闲电平仍可能误触发', '等效负载在驱动能力内、空闲差分电压超过接收门限即关闭', inputs='SIG-T04 的总线端点'),
    'SIG-C04': _x('总线正常时没问题，某节点掉电或地偏移时可能拖垮整条总线', '共模范围、地差和未供电节点负载都在收发器限值内即关闭', inputs='PWR-T06 的地网关系'),
    'SIG-C05': _x('VBUS 有电不代表正确：可能未经许可供电、反灌或拔出后残压', '供电资格、档位、放电、反灌和过流按端口角色核完即关闭', inputs='SIG-D04 的端口角色'),
    'SIG-C07': _x('静态电压看似相近，带负载和温度角后可能拉不动或越过脚上限', '每条实际链路的 VOH/VOL 对 VIH/VIL 和耐压都满足即关闭', inputs='SIG-T04 的方向、DEV-C05 的工作条件'),
    'SIG-C08': _x('上电时都正常，一个域掉电后信号可能经上拉或 ESD 二极管反向供电', '每个域掉电和外设先上电时注入电流和脚电压都在限值内即关闭', inputs='PWR-T01/T06 的状态、RST-T04 的默认态'),
    'SIG-C09': _x('连接和电平都对，在规定速率下仍可能建立/保持时间不足而误码', '最坏角点下建立/保持裕量为正即关闭；布线延迟交 SI', inputs='SIG-C07 的电平、CLK-C01 的时钟'),
    'SIG-D01': _x('单看每颗器件地址都对，不同装配组合下仍可能地址冲突', '每种装配组合下地址唯一，复位态与上拉组合明确即关闭', inputs='SIG-T02 的连通、RST-E02 的配置态'),
    'SIG-D02': _x('ZQ 电阻照别的器件套用，精度或阻值不符时校准会失败', '控制器与 DRAM 各自按准确型号核 ZQ 阻值与精度即关闭'),
    'SIG-D03': _x('DDR 连通都对，VREF/VTT 或端接不匹配时训练仍会失败', '各数据/地址/时钟组的拓扑、端接、基准和上电条件匹配平台即关闭', inputs='DEV-C05 的电压条件'),
    'SIG-D04': _x('CC 电阻接了，角色或 VCONN 配错时可能误判连接或越权供电', '按实际角色核 Rp/Rd、方向检测和 VCONN 都符合规范即关闭', inputs='DEV-D03 的接口脚义'),
    'SIG-D06': _x('调试口引出了，电平、串阻或 ESD 不当时工具一接就冲突或损坏', '调试信号电气引出、电平和防护满足实际工具即关闭；可触达性交下游', inputs='SIG-C07 的电平判据'),
    'SIG-D07': _x('USB 差分线连通，REXT、VBUS 检测或 ESD 位置不对时仍不能枚举', 'REXT、串阻、VBUS 检测、ID 和挂在活线上的 ESD 都按手册即关闭', inputs='SIG-T01 的连通、SIG-C05 的 VBUS'),
    'SIG-D08': _x('收发器接通了，VIO、默认使能或端接策略不对时通信仍不成立', '供电/VIO、默认态、端接（本端或对端书面明确）和偏置都核实即关闭', inputs='SIG-C03/C04 的总线计算'),
    'SIG-D09': _x('SPI 能通信，写保护或片选默认态不对时启动 Flash 可能被误写或读不到', '片选、模式、供电域、上拉与写保护都按手册即关闭', inputs='SIG-C07 的电平'),
    'SIG-D10': _x('eMMC/SD 能识别，电压切换或 CMD 上拉不当时高速模式会失效', 'IO 电平、CMD 上拉和 CLK 串阻按手册即关闭；stub 限制交下游', inputs='SIG-C07 的电平'),
    'SIG-D11': _x('PHY 与网变接上了，中心抽头或共模端接套错固定参数时链路不稳', '按实际 PHY、网变与模式核 MDI、中心抽头和端接即关闭；隔离归 PRO-D02'),
    'SIG-D12': _x('照参考设计连了模组，偏离处的供电电容或天线默认通断可能不成立', '模组要求的供电、开关机、复位和天线默认态都满足即关闭；布局交下游', inputs='PWR-C14 的噪声结论'),
    'SIG-D13': _x('功能都分到了脚，同一脚被两个功能占用或该脚不支持该功能时才暴露', '每个功能的脚复用、电平域与平台约束和固件配置表一致即关闭', inputs='DEV-D02 的脚表'),
    'SIG-D14': _x('主数据线连对了，耦合电容位置或边带信号错时链路仍建立不起来', '耦合电容位置与容值、极性映射、参考时钟和边带信号按规范即关闭', inputs='SIG-T01/T03 的连通与端接'),
    'SIG-D15': _x('音视频线都连了，热插拔、DDC 上拉或时钟来源错时仍无声无图', '通道映射、控制线电平与上拉、时钟来源和模拟供电按规范即关闭', inputs='SIG-C07 的电平'),
    'ANA-T01': _x('有检测器件不等于检测有效：可能测错对象、参考错地或检测到了无法动作', '被测量、取样点、参考地、判决和控制端都追清即关闭'),
    'ANA-C01': _x('典型条件下量程够，供电或温度极限时可能饱和、超量程或误差超标', '输入共模、输出摆幅和误差在供电与温度极限下都在要求内即关闭', inputs='ANA-T01 的路径、DEV-C03 的公差'),
    'ANA-C02': _x('静态量程正确，容性负载或 ADC 采样建立不足仍会振荡或读数偏差', 'GBW、压摆率、容性负载和采样建立误差都满足即关闭', inputs='ANA-C01 的工作点'),
    'ANA-C03': _x('正常工作时基准和输入都对，输入异常或掉电时注入电流可能损坏前端', '基准误差与驱动、满量程和钳位注入电流（含掉电）都在限值内即关闭', inputs='ANA-T01 的路径'),
    'ANA-C04': _x('传感器开路、短路的读数可能落进正常区间，故障被当成正常', '全温和公差下正常区间与开路、短路读数不重叠并有裕量即关闭', inputs='ANA-T01 的路径、ANA-D01 的传感器参数', false_alarms='传感器接电源轨的一端只是偏置，轨上 IC 的供电脚不是检测脚'),
    'ANA-D01': _x('传感器连接正确，量程、接口或供电条件不符时读数仍无效', '电气连接、量程和接口按准确型号核实即关闭；摆放与热路径交热设计'),
    'PRO-A01': _x('图上有 ESD/TVS，挂在残留网上时外部能量会绕过它', '防护器件所在网含真实信号端点并接到端口即关闭', false_alarms='多路 ESD 阵列的未用通道；板内互连不需要防护的网'),
    'PRO-E02': _x('钳位电压高于被保护脚绝限时，ESD 事件先打坏芯片再被钳住', 'VRWM 不低于持续最高电压，到达本节点的瞬态下钳位电压不高于同网最低耐受，脉冲能量在额定内即关闭', inputs='钳位件 VRWM/VBR/VC 与脉冲额定；需求波形；同网器件耐受', false_alarms='防护是否挂在活线上、泄放路径归 PRO-D03；型号与轨名只能作线索'),
    'PRO-A03': _x('光耦 LED 没有限流时，驱动端与 LED 都可能过流，隔离信号仍可能偶尔能传', '回路有串阻或经证实的恒流驱动即关闭；电流归 PRO-E01', false_alarms='恒流驱动或驱动脚自带限流；串阻画在另一条腿上'),
    'PRO-A04': _x('光耦输出没有上拉时，高电平靠漏电建立，输出状态不确定', '接收端有外部上拉或经证实的内部上拉即关闭；能力归 PRO-E01', false_alarms='接收端 MCU 内部上拉已启用；推挽输出的光耦'),
    'PRO-E01': _x('光耦能传信号，CTR 随寿命衰减后输出电流可能不足以拉低负载', '最小正向电流乘保证 CTR 初始值后满足负载，最大电流不超额即关闭', inputs='PRO-D01 的两侧电平'),
    'PRO-C01': _x('单个保护器件合格，整条链的动作电压、时序和能量仍可能配合不上', '按实际保护链逐段核动作电压、时序与能量配合即关闭；缺工况不定判', inputs='PRO-C02 的门限、DRV-C01/C02 的耐受'),
    'PRO-C02': _x('只核一侧窗口：可能正常工作时误触发，或故障时触发不了', '两侧保证值或有据上界按同一温度角点与门限比较不越限即关闭，最坏取值时零余量即可', inputs='ANA-T01 的检测路径', false_alarms='跨网与地的防护钳位归 PRO-E02；栅源稳压管正常限幅属允许用途；跨开关 TVS 是能量钳位'),
    'PRO-D01': _x('光耦能传信号，隔离等级、工作电压或参考地归属仍可能不满足要求', '两侧网络归属、参考地、跨接器件和耐压都核实即关闭；爬电距离交版图', inputs='DEV-D01 的器件身份'),
    'PRO-D02': _x('跨隔离带的 Y 电容或误连网络可能绕过加强绝缘', '每个跨隔离器件与网络归属核实；不能代替PRO-C03工作资格，实际爬电另验', inputs='PWR-T06 的参考地分区'),
    'PRO-C03': _x('短时耐压测试值、绝缘目标或无直流跨接被错当成实际工作条件下的元件资格', '每个跨隔离器件均有工作应力与资格条件的对照，未满足前提不得移作阶段NA', inputs='隔离器件清单、实际波形/工作电压及准确订货变体资格'),
    'PRO-D03': _x('有 ESD 器件不等于端口受保护：可能挂在非活线上或泄放路径不通', '每个对外针的防护与泄放路径都核实即关闭；钳位数值归 PRO-E02', inputs='DEV-D03 的端口定义', false_alarms='板内互连连接器可按依据判不适用'),
    'DRV-A01': _x('被开关的线圈没有释放路径时，关断尖峰会击穿开关管', '找到续流、钳位、RC 或有据的集成钳位路径即关闭；额定归 DRV-C01', false_alarms='驱动器内部钳位（需资料）；反激变压器的能量经次级送出'),
    'DRV-A02': _x('续流二极管反接时，开关导通即短路电源，关断时也不续流', '二极管阳极在开关节点、阴极在电源轨即关闭', false_alarms='升压二极管阴极接输出母线是正确接法，不是续流管'),
    'DRV-A03': _x('栅极没有驱动也没有偏置时，上电瞬间功率管可能误导通', '有驱动源或确定的栅极偏置即关闭；驱动窗口归 DRV-E01', false_alarms='驱动器输出在欠压时有保证的拉低；栅极由连接器外部驱动；下拉在串联栅极电阻之后'),
    'DRV-A04': _x('开关节点没有释放感性能量的路径时，管子可能承受过压', '确认吸收/钳位或低边 Boost 正向主整流路径；寄生尖峰和耐压另核', false_alarms='Boost 主整流二极管把电感能量送往输出；同步整流对管或体二极管已钳位；TVS 跨开关也是吸收路径'),
    'DRV-E01': _x('栅极接到驱动了，实际 VGS 可能不足导通或超过栅源绝限', '实际最小栅压下所需导通能力有保证（测试 VGS 或有据曲线）且最大值不超绝限即关闭', inputs='源极返回路径（含采样电阻压降）'),
    'DRV-T01': _x('只认 RCD 会把 TVS 钳位误报为缺失；方向或贴装错又会无处泄能', '各开关状态的储能、送能和吸收路径存在且方向正确即关闭', false_alarms='无 RCD 时跨开关或跨初级的 TVS/齐纳也是漏感钳位'),
    'DRV-C01': _x('吸收器件在额定内，钳位电压加电源电压仍可能超过开关管耐压', '钳位电压、峰值/重复电流和耗散都在额定内即关闭；峰压交 DRV-C02', inputs='DRV-T01 的吸收拓扑、PWR-C03 的电流'),
    'DRV-C02': _x('静态耐压或额定电流够用，实际开关过程仍可能失效或达不到功率要求', '按实际驱动与工作方式核完应力和适用 SOA 即关闭；热路径交下游', inputs='DRV-E01 的驱动、DRV-C01 的峰压'),
    'DRV-D01': _x('驱动接对了，死区、自举欠压或负压等条款仍可能被遗漏', '实际拓扑适用的驱动器条款逐项满足即关闭；计算归 DRV-C01/C02', inputs='DRV-T01 的拓扑'),
    'REQ-A01': _x('数量对了不等于功能实现；该有的器件也可能被换成别的料号', '按意图清单数量一致即关闭；功能实现归 REQ-D01', false_alarms='意图清单把同一功能的替代料分开计数'),
    'REQ-A02': _x('名称没命中不等于功能缺失；命中了也不等于真实现', '按真实连接确认功能存在或缺失即关闭', false_alarms='功能由非典型命名或片内模块实现'),
    'REQ-D01': _x('局部电路都能工作，产品仍可能漏掉需求要求的功能或边界', '每条需求的要求条款都落到电路与检查并有结论即关闭'),
    'REQ-D02': _x('各模块各自正确，可能按不同的电流、电压口径设计', '同一参数在需求、计算和图面中只有一个数字来源即关闭', inputs='DOC-Q01 的版本一致性'),
    'REQ-Q01': _x('需求可能只在说明里提到，没有任何检查去验证', '每条需求都有检查去向，检查也能追回需求即关闭'),
    'REQ-Q02': _x('只查到局部引脚时，会漏掉链路另一端或中间转换', '每条接口、电源、检测、使能、复位和时钟链路都追到终点和返回即关闭'),
    'REQ-Q03': _x('正常状态通过，可能掩盖启动、掉电或故障时的错误', '每个关键电路的需求内状态都已覆盖即关闭；不新增需求之外的工况', inputs='RST-T03 的顺序结论'),
    'REQ-Q04': _x('历史意见可能因换版或改位号而无声消失', '每条历史意见都有复验结论：修复、保留或有依据撤回即关闭', inputs='REQ-H01 的复验结果'),
    'REQ-Q05': _x('只复验修改点，会漏掉改动对其他电路的连带影响', '改动影响的供电、控制和保护范围都用本轮证据复验即关闭', inputs='REQ-H01 的差异与依赖'),
    'REQ-Q07': _x('整类电路一次性通过可能掩盖某个子电路或状态没查', '功能电路的全部电路检查项逐电路、逐状态完成即关闭'),
    'REQ-Q08': _x('命名或符号不典型的电路可能被自动计划漏掉', '未检出的功能电路都有不适用依据或已补检查，未归属器件都有去处或原因即关闭'),
    'REQ-H01': _x('只改说明或换位号可能被误当成修复', '历史意见对应的器件字段、换网和网络成员变化都用新版证据核过即关闭', inputs='DOC-Q01 绑定的新旧输入'),
    'REQ-H02': _x('旧检查对象消失可能被误当成问题已关闭', '每个消失项都确认是删除、替代还是遗漏即关闭', inputs='REQ-H01 的差异'),
}


# Which rows an open item may block, by kind (R7 acceptance 2026-10-25, user: B2 a): the same T301 drawing gap blocked
# 62 / 16 / 29 / 14 rows on four records. A calculation (C) or electrical-window (E) row and the requirement row can wait
# for a vendor datum or a design value; document and identity rows (D), topology (T), hints (A) and coverage (Q/H/V)
# cannot. What another stage owes (a custom part's drawing, a firmware capability) is no gap since 2026-10-26 (user: 并入乙):
# it is a design constraint handed on. A configuration table is no gap (2026-10-26, user: 手册已有声明、配置表没有……判断为功能可达):
# a capability the datasheet declares is reachable, and the settings the hardware relies on are handed on.
def _rule_class(rule_id):
    return rule_id.split('-', 1)[1][0] if '-' in rule_id else ''


def _rules_of_class(*classes):
    return frozenset(r.id for r in RULES if _rule_class(r.id) in classes)


COMPUTED_RULES = _rules_of_class('C', 'E') | {'REQ-D01'}
OPEN_ITEM_RULES = {
    'VENDOR_DATUM': COMPUTED_RULES,
}


def blockable_rules(kind):
    """The rule ids an open item of this kind may block, or None when the table has no row for it."""
    return OPEN_ITEM_RULES.get(kind)


def rules_titled(aspect):
    """The rule ids whose title is `aspect` (frame members carry the rule title as aspect); empty for other text."""
    return frozenset(r.id for r in RULES if r.title == aspect)


def explanations_for(rule_ids):
    """计划级规则说明：每条出现的规则一份，按编号排序。"""
    return {rule: explanation(rule) for rule in sorted(set(rule_ids))}


def plan_explanation_errors(plan):
    """计划级说明须覆盖每个检查的规则，并与现检查项规则说明逐字一致；旧版本计划不兼容，重新生成。
    没有该字段的计划只出现在手工合成的夹具里：真实计划的说明由校验按保存的输入重建核对。"""
    saved = plan.get('check_explanations')
    if saved is None:
        return []
    if not isinstance(saved, dict):
        return ['check_explanations must be an object keyed by rule']
    if plan.get('check_explanations_version') != EXPLANATION_VERSION:
        return ['check_explanations_version is not %d; regenerate the plan (earlier plans are not read)' % EXPLANATION_VERSION]
    errors = []
    for rule in sorted({c.get('rule') for c in plan.get('checks') or [] if isinstance(c, dict)} - {None}):
        if rule not in saved:
            errors.append('check_explanations 缺少规则 %s' % rule)
        elif saved[rule] != explanation(rule):
            errors.extend(explanation_errors(saved[rule]) or
                          ['计划 check_explanations.%s 与规则说明不同；对象化说明写入结果检查项' % rule])
    return errors


def explanation(rule_id):
    """Return an independent snapshot for plans; never infer a verdict."""
    return dict(EXPLANATIONS[rule_id])


def explanation_errors(value, partial=False):
    """结构检查。partial=True 用于结果检查项的对象化覆盖：只写需要改的字段。"""
    if not isinstance(value, dict):
        return ["check_explanation must be an object"]
    fields, required = EXPLANATION_FIELDS, REQUIRED_EXPLANATION_FIELDS
    errors = ["check_explanation has unknown field " + key for key in sorted(set(value) - set(fields))]
    errors += ["check_explanation needs non-empty " + key for key in fields
               if (key in value or (key in required and not partial))
               and (not isinstance(value.get(key), str) or not value[key].strip())]
    if partial and not value:
        errors.append("check_explanation override needs at least one field")
    return errors


def catalog_explanation_errors(rule_id):
    """目录条目的写法约束：必填项、A 类常见误报、长度上限与引用规则存在。"""
    value = EXPLANATIONS[rule_id]
    if not isinstance(value, dict) or set(value) - set(EXPLANATION_FIELDS):
        return ['目录说明须为第 2 版字段']
    errors = explanation_errors(value)
    if method_of(rule_id) == 'A' and not value.get('false_alarms'):
        errors.append('自动扫描规则须写 false_alarms')
    errors += ['%s 超过 %d 字' % (k, n) for k, n in EXPLANATION_LIMITS.items() if len(value.get(k, '')) > n]
    return errors


BY_ID = {}
CIRCUIT_TYPE_BY_NAME = {}
OBJECTIVE_BY_RULE = {}


def _check_id(rule_id):
    match = ID_RE.match(rule_id)
    if not match or match.group(1) not in DOMAIN_BY_CODE or match.group(2) not in METHOD_BY_CODE:
        raise ValueError('规则编号格式错误: ' + rule_id)


def _build_index():
    for rule in RULES:
        _check_id(rule.id)
        if rule.id in BY_ID:
            raise ValueError('规则编号重复: ' + rule.id)
        if (rule.source not in SOURCES or rule.scope not in SCOPES
                or not rule.title.strip() or not rule.criterion.strip()):
            raise ValueError('规则定义不完整: ' + rule.id)
        BY_ID[rule.id] = rule
    if set(EXPLANATIONS) != set(BY_ID):
        raise ValueError('检查目的说明有遗漏或过期规则: ' + str(set(EXPLANATIONS) ^ set(BY_ID)))
    for rule_id in EXPLANATIONS:
        if catalog_explanation_errors(rule_id):
            raise ValueError('检查说明不合要求: %s %s' % (rule_id, catalog_explanation_errors(rule_id)))
        linked = set(re.findall(r'\b[A-Z]{3}-[A-Z]\d{2}\b', ' '.join(explanation(rule_id).values())))
        if linked - set(BY_ID):
            raise ValueError('检查说明引用未知规则: ' + rule_id)
    OBJECTIVE_BY_RULE.update(build_objective_index(BY_ID, OBJECTIVE_RULES))
    for kind in CIRCUIT_TYPES:
        if kind.name in CIRCUIT_TYPE_BY_NAME or kind.domain not in DOMAIN_BY_CODE:
            raise ValueError('功能电路定义错误: ' + kind.name)
        re.compile(kind.pattern)
        CIRCUIT_TYPE_BY_NAME[kind.name] = kind
    for (name, rule), requires in SUBJECT_REQUIRES.items():
        if name not in CIRCUIT_TYPE_BY_NAME or rule not in CIRCUIT_TYPE_BY_NAME[name].subjects \
                or requires not in SUBJECT_PRECONDITIONS:
            raise ValueError('电路规则前提定义错误: %s %s' % (name, rule))
    referenced = [rule for p in CIRCUIT_TYPES for rule in p.subjects] + list(COVERAGE_RULES.values())
    for rule in referenced:
        if rule not in BY_ID:
            raise ValueError('映射引用了未登记的规则: ' + rule)
    for rule_id, needs in INPUT_OVERRIDES.items():
        if rule_id not in BY_ID or not set(needs) <= set(INPUTS):
            raise ValueError('输入依赖定义错误: ' + rule_id)
    for kind in CIRCUIT_TYPES:
        if not kind.subjects or any(rule[4] in 'AEHQ' for rule in kind.subjects):
            raise ValueError('电路检查项须为审查者逐项执行的规则: ' + kind.name)
    for rule in RULES:
        if rule.source == 'subject' and not circuit_types_of(rule.id):
            raise ValueError('电路检查项未编入任何功能电路: ' + rule.id)


def known(rule_id):
    return isinstance(rule_id, str) and rule_id in BY_ID


def get(rule_id):
    try:
        return BY_ID[rule_id]
    except (KeyError, TypeError):
        raise KeyError('规则总表中没有该编号: %r' % (rule_id,)) from None


def domain_of(rule_id):
    return get(rule_id).id[:3]


def method_of(rule_id):
    return get(rule_id).id[4]


def inputs_of(rule_id):
    """判这条规则需要的输入（INPUTS 的键）。"""
    rule_id = get(rule_id).id
    return INPUT_OVERRIDES.get(rule_id) or METHOD_INPUTS[rule_id[4]]


def stage_of(rule_id):
    """cold：脚本只用网表/日志/意图；review：审查员；revision：复审比对。"""
    rule_id = get(rule_id).id
    inputs = set(inputs_of(rule_id))
    if 'history' in inputs:
        return 'revision'
    if METHOD_BY_CODE[rule_id[4]].executor == '脚本':
        return 'cold'
    return 'review'


def title(rule_id):
    return get(rule_id).title


def criterion(rule_id):
    return get(rule_id).criterion


def rules(method=None, domain=None, source=None, stage=None, needs=None):
    """stage 按输入依赖推出的执行阶段筛选；needs 筛出需要某种输入的规则。"""
    return [rule for rule in RULES
            if (method is None or rule.id[4] == method)
            and (domain is None or rule.id[:3] == domain)
            and (source is None or rule.source == source)
            and (stage is None or stage_of(rule.id) == stage)
            and (needs is None or needs in inputs_of(rule.id))]


def titles(method=None, domain=None, source=None, stage=None):
    return {rule.id: rule.title for rule in rules(method, domain, source, stage)}


def circuit_type(name):
    return CIRCUIT_TYPE_BY_NAME[name]


def circuit_types_of(rule_id):
    return [p.name for p in CIRCUIT_TYPES if rule_id in p.subjects]


def circuit_type_criterion(name):
    """功能电路汇总项的判据：列出本类型电路检查项；项目自定义功能没有电路检查项，由审查者补充。"""
    item = CIRCUIT_TYPE_BY_NAME.get(name)
    if item is None:
        return '执行项目自定义功能 %s 的原理图检查；电路检查项由审查者按需求逐项补充' % name
    members = '、'.join('%s %s' % (rule, title(rule)) for rule in item.subjects)
    return '执行%s功能电路：%s；电路检查项全部完成后汇总，禁止整类电路一次性 PASS' % (item.title, members)


def order(rule_id):
    """文档顺序：内容域 → 方式 → 序号；未登记的编号排最后。"""
    if not ID_RE.match(str(rule_id)) or str(rule_id)[:3] not in DOMAIN_BY_CODE:
        return (len(DOMAINS), len(METHODS), 0, str(rule_id))
    codes = [d.code for d in DOMAINS]
    return (codes.index(rule_id[:3]), METHOD_ORDER.index(rule_id[4]), int(rule_id[5:]), rule_id)


def spec_errors(item):
    """计划项的规则、方式、内容域与编号前缀必须和本表一致。"""
    rule = item.get('rule') if isinstance(item, dict) else None
    if not known(rule):
        return ['规则编号未登记: %r' % (rule,)]
    errors = []
    if item.get('method') != method_of(rule) or item.get('domain') != domain_of(rule):
        errors.append('method/domain 与规则 %s 不一致' % rule)
    if not str(item.get('id', '')).startswith(rule + '.'):
        errors.append('检查 ID 必须以 %s. 开头' % rule)
    if 'check_explanation' in item:  # 旧版逐项说明：只核结构
        errors.extend(explanation_errors(item['check_explanation']))
    return errors


_build_index()


# -- 文档 ----------------------------------------------------------------
DOC_BEGIN = '<!-- catalog:begin（由 scripts/catalog.py --write-doc 生成，勿手改） -->'
DOC_END = '<!-- catalog:end -->'


def _cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def _vocabulary_lines():
    """The three name tables a reviewer writes into intent.json (references/review-vocabulary.md): circuit
    types, device roles, requirement categories, aspects and parameters. The rule table carries them too."""
    lines = []
    lines += ['', '## 功能电路', '',
              '电路由电路候选与 `intent.circuit_decisions` 推出；名称命中只生成 UNDETERMINED 候选。推出的电路或已确认拓扑'
              '使功能电路适用，再生成 REQ-Q07 覆盖项与电路检查项，逐项再核实际用途。未检出的功能电路汇总到一项 REQ-Q08 确认；'
              '`features` 里的 NOT_APPLICABLE 声明不生成检查项，只作 REQ-Q08 那一项的依据。'
              '分立 MOSFET 电平转换器没有名称线索，候选没检出时写 add 决定（在 I²C 等总线上则并入该总线电路），'
              '转换管在 `intent.power_switches` 中声明为 `role: "level_shifter"`，见 [计划格式](plan-format.md)。', '',
              '| 功能电路 | 名称 | 内容域 | 电路检查项 | 必需资料 | 检出特征（正则） |',
              '|---|---|---|---|---|---|']
    for p in CIRCUIT_TYPES:
        lines.append('| %s | %s | %s | %s | %s | `%s` |' % (
            p.name, p.title, p.domain, '、'.join(p.subjects), '、'.join(p.materials), _cell(p.pattern)))
    lines += ['', '下表的电路检查项只在网表上有它问的机制时生成，检查项对象取前提找到的器件；前提不成立的规则记在功能框架的 '
              '`not_asked`，报告在功能下列“未问”。网表说不清（器件类别未知、IC 没有脚名）时照问；漏问的可经 '
              '`intent.rule_gaps` 补回。', '',
              '| 功能电路 | 电路检查项 | 前提 | 不成立时 |', '|---|---|---|---|']
    for (name, rule), requires in SUBJECT_REQUIRES.items():
        lines.append('| %s | %s | %s | %s |' % (name, rule, requires, SUBJECT_PRECONDITIONS[requires]))
    lines += ['', '## 器件角色', '',
              '集成电路在 `intent.device_kinds` 声明手册标题给出的角色（`audit_datasheets.py --intent` 用标题词核验原文），'
              '角色决定它作核心器件时生成哪些电路候选；泛称 `ic` 只在标题不含任何角色词时可写，计划把每个 `ic` 列成 '
              '`DEVICE_KIND_GENERIC` 诊断（不生成电路候选），这张清单是下一批角色的来源。加角色只改 `catalog.DEVICE_ROLES` 一行：'
              '标题词、靶的电路类型、走哪些脚。', '',
              '| 角色 | 名称 | 手册标题词（去空格小写的子串，3 个字母以内按整词） | 作核心器件生成的电路 | ANALOG 走线从哪些脚出发 |', '|---|---|---|---|---|']
    for name, role in DEVICE_ROLES.items():
        lines.append('| `%s` | %s | %s | %s | %s |' % (
            name, role.title, '、'.join(role.cues) or '—', '、'.join(role.circuits) or '不作核心器件',
            {'sense': '检测脚', 'all': '全部信号脚'}[role.pins] if 'ANALOG' in role.circuits else '—'))
    lines += ['', '接口电路（%s）的走线总是从核心器件的全部信号脚出发走两跳，到达的网上的连接器作成员。' % '、'.join(INTERFACE_TYPES)]
    lines += ['', '一个角色能靶多种接口电路（上表 transceiver、memory）时，按下表从手册标题挑第一个命中的类型，都不命中记候选缺口 '
              '`role-bus`，由审查员写 `circuit_decisions` add。', '',
              '| 接口电路 | 标题里的词（正则） |', '|---|---|']
    for name, pattern in BUS_CUES.items():
        lines.append('| %s | `%s` |' % (name, _cell(pattern.pattern)))
    lines += ['', '## 需求类别与审查方面', '',
              '每条需求分解成审查方面，计划按（需求，方面）各生成一项 REQ-D01，判据取方面模板。分解的单位是需求里的量：'
              '带参数的方面由 `requirements[].parameters` 里有没有这个参数决定，有就问，不管选了哪些类别；'
              '不带参数的方面由类别决定。一条需求一个参数都没写时，才按类别问全部方面，计划同时列出原文里没读进参数的带单位数字'
              '（`REQUIREMENT_NUMBERS_UNREAD`）。类别拿不准就多选：多出的不带参数的方面判 NA 要写依据，少选是漏查。', '',
              '| 类别 | 名称 | 怎么选 | 审查方面 | 落到 |', '|---|---|---|---|---|']
    for key, category in REQUIREMENT_CATEGORIES.items():
        lines.append('| %s | %s | %s | %s | %s |' % (key, category.name, category.when, '、'.join(
            '%s %s' % (a, REQUIREMENT_ASPECTS[a].name) for a in category.aspects), category.targets))
    lines += ['', '方面有树上的检查承担时，需求检查项绑定这些规则的检查项（需求 `owners` 点名的电路、接口、系统功能拥有的检查项；'
              '没写 `owners` 时，全板方面绑定全板这些规则的检查项），结论取绑定检查项中最差者，需求检查项不再另判；'
              '没有检查承担的方面由需求检查项自己判。', '',
              '需求的承接电路写在 `owners`（落实这条需求的功能电路；系统功能和接口也可以承接）。计划替每条需求找出可承接的电路：'
              '下表“可承接的电路”列出的电路类型、系统功能和接口种类里，拥有承担该方面的检查项的那些；表外的所属不算。'
              '有可承接的电路而没写 owners 的需求，计划拒绝生成并打印它们；审查员认定没有承接电路时写 `owners: []` 加能定位的 `no_owner_reason`，需求检查项自判。', '',
              '| 审查方面 | 何时问 | 判据模板 | 承担的检查 | 可承接的电路 |', '|---|---|---|---|---|']
    for key, aspect in REQUIREMENT_ASPECTS.items():
        carried = '、'.join(ASPECT_RULES.get(key, ())) or '需求检查项自判'
        asked = '原文有 ' + ' / '.join(aspect.parameters) if aspect.parameters else '类别选中'
        if key in BOARD_ASPECTS:
            owners = '全板，不要求 owners'
        elif key in ASPECT_OWNER_TYPES:
            cell = ASPECT_OWNER_TYPES[key]
            owners = '；'.join(part for part in (
                '电路 ' + '、'.join(cell.circuits) if cell.circuits else '',
                '系统功能 ' + '、'.join(cell.systems) if cell.systems else '',
                '接口 ' + '、'.join(cell.interfaces) if cell.interfaces else '') if part)
        else:
            owners = '—'
        lines.append('| %s %s | %s | %s | %s%s | %s |' % (key, aspect.name, asked, _cell(aspect.template), carried,
                                                          '（全板）' if key in BOARD_ASPECTS else '', owners))
    lines += ['', '需求里的数字读进 `requirements[].parameters`（`name`、`min`/`max`、`unit`、`condition`）；'
              '每个数字须在该条原文里出现，条件须是原文里的一段，数值按下表换算到规范单位。', '',
              '| 参数 | 名称 | 规范单位 | 可写单位 | 问的方面 |', '|---|---|---|---|---|']
    for key, parameter in REQUIREMENT_PARAMETERS.items():
        lines.append('| %s | %s | %s | %s | %s |' % (key, parameter.title, parameter.unit, '、'.join(parameter.units),
                                                   '、'.join(PARAMETER_ASPECTS[key])))
    return lines


def render_vocabulary_markdown():
    return '\n'.join(_vocabulary_lines()).lstrip('\n') + '\n'


def render_markdown():
    lines = ['## 审查要点与规则归属', '',
             '目的与取舍见 [审查要点](review-charter.md)。每条在用规则有一个主审查要点，跨域约束仍按判据与 HANDOFF 处理。',
             '这是维护映射，不增加项目检查或填写字段；映射齐全不等于实际审查正确。', '',
             '| 审查要点 | 要回答的问题 | 主归属规则数 |', '|---|---|---|']
    for goal, (name, question) in OBJECTIVES.items():
        lines.append('| %s %s | %s | %d |' % (goal, name, question, len(OBJECTIVE_RULES[goal])))
    lines += ['', '## 检查方式', '',
             '| 代码 | 方式 | 执行者 | 输入 | 输出 | 何时执行 |',
             '|---|---|---|---|---|---|']
    for m in METHODS:
        lines.append('| %s | %s | %s | %s | %s | %s |' % tuple(_cell(x) for x in m))
    lines += ['', '## 输入依赖与执行阶段', '',
              '方式字母说明谁来做；下表说明判这条规则要什么输入。网表扫描与审查阶段由输入依赖推出，'
              '规则编号不随自动化程度改变。', '',
              '| 阶段 | 条件 | 规则数 |', '|---|---|---|',
              '| 网表扫描 | 脚本执行，只用网表、导出日志或审查意图声明 | %d |' % len(rules(stage='cold')),
              '| 审查员 | 审查员对照资料、需求和图面判 | %d |' % len(rules(stage='review')),
              '| 复审 | 需要上一版网表与意见 | %d |' % len(rules(stage='revision'))]
    lines += ['', '## 内容域', '',
              '| 代码 | 内容域 | 范围 | 在用规则 | 移交事项（HANDOFF） |',
              '|---|---|---|---|---|']
    for d in DOMAINS:
        lines.append('| %s | %s | %s | %d | %s |' % (
            d.code, d.name, _cell(d.scope), len(rules(domain=d.code)), _cell(d.handoff or '—')))
    lines += ['', '## 来源与展开粒度', '',
              '| 来源 | 何时生成计划项 |', '|---|---|',
              '| Lint 内置 / 检查器 | 自动扫描随网表扫描执行；保证值核对项与检查器项按识别到的对象生成 |',
              '| 计划逐对象生成 | 按“粒度”列逐对象生成（页、器件、电源轨、链路、需求等） |',
              '| 电路检查项 | 所属功能电路适用时生成：声明了电路则逐电路×工况，否则按功能电路生成一次 |',
              '| 全板通用 | 每块板各生成一项，审查者给出适用性与结果 |',
              '| 改版比对 | 复审时由改版影响与历史意见断言生成 |', '',
              '| 粒度代码 | 含义 |', '|---|---|']
    for code, name in SCOPES.items():
        lines.append('| %s | %s |' % (code, name))
    lines += ['', '## 总览（内容域 × 方式）', '',
              '单元格为该组在用规则的序号。', '',
              '| 内容域 | ' + ' | '.join('%s %s' % (m.code, m.name) for m in METHODS) + ' |',
              '|---|' + '---|' * len(METHODS)]
    for d in DOMAINS:
        cells = []
        for m in METHODS:
            numbers = sorted(int(r.id[5:]) for r in rules(method=m.code, domain=d.code))
            cells.append(' '.join('%02d' % n for n in numbers) or '·')
        lines.append('| %s %s | %s |' % (d.code, d.name, ' | '.join(cells)))
    for d in DOMAINS:
        lines += ['', '## %s %s' % (d.code, d.name), '',
                  '| 编号 | 审查要点 | 方式 | 输入 | 检查内容 | 判据要点 | 粒度 | 来源 | 功能电路 |', '|---|---|---|---|---|---|---|---|---|']
        for rule in sorted(rules(domain=d.code), key=lambda r: order(r.id)):
            lines.append('| %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
                rule.id, OBJECTIVE_BY_RULE[rule.id], METHOD_BY_CODE[rule.id[4]].name,
                '、'.join(INPUTS[x] for x in inputs_of(rule.id)), _cell(rule.title),
                _cell(rule.criterion), SCOPES[rule.scope], SOURCES[rule.source],
                '、'.join(circuit_types_of(rule.id)) or '—'))
    lines += ['', '## 每项检查的盲区、关闭条件与常见误报', '',
              '“不查会漏掉什么”是检查的理由，不表示本设计已存在这些问题，也不预设 P0–P3。',
              '关闭条件写明证据到什么程度可以结束本项，以及哪些事不归本项；复用的事实只是方向，',
              '不自动构成项目依赖。实际对象不同的，在结果检查项只改需要改的那个字段。', '']
    for domain in DOMAINS:
        lines += ['### ' + domain.code + ' ' + domain.name, '',
                  '| 编号 | 不查会漏掉什么 | 关闭条件 | 复用的事实 | 常见误报/合法结构 |',
                  '|---|---|---|---|---|']
        for rule in sorted(rules(domain=domain.code), key=lambda r: order(r.id)):
            value = explanation(rule.id)
            cells = (rule.id, value['risk_if_omitted'], value['closes_when'],
                     value.get('inputs') or '—', value.get('false_alarms') or '—')
            lines.append('| ' + ' | '.join(_cell(v) for v in cells) + ' |')
        lines.append('')
    lines += _vocabulary_lines()
    lines += ['', '## 覆盖维度', '', '| 维度（results.scope_checks 键） | 规则 |', '|---|---|']
    for name, rule in COVERAGE_RULES.items():
        lines.append('| %s | %s %s |' % (name, rule, title(rule)))
    return '\n'.join(lines) + '\n'


BOUNDS_BEGIN = '<!-- bounds:begin（由 scripts/catalog.py --write-doc 生成，勿手改） -->'
BOUNDS_END = '<!-- bounds:end -->'
VOCAB_BEGIN = '<!-- vocabulary:begin（由 scripts/catalog.py --write-doc 生成，勿手改） -->'
VOCAB_END = '<!-- vocabulary:end -->'


def render_doc(text):
    """The marked region of a document: the rule table, the bounding table (references/bounding-table.md) or the
    reviewer's vocabulary (references/review-vocabulary.md)."""
    begin, end, body = ((BOUNDS_BEGIN, BOUNDS_END, render_bounds_markdown) if BOUNDS_BEGIN in text
                        else (VOCAB_BEGIN, VOCAB_END, render_vocabulary_markdown) if VOCAB_BEGIN in text
                        else (DOC_BEGIN, DOC_END, render_markdown))
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError('文档缺少唯一的规则总表标记')
    head, rest = text.split(begin)
    _, tail = rest.split(end)
    return head + begin + '\n\n' + body() + '\n' + end + tail


def main():
    parser = argparse.ArgumentParser(description='检查规则总表')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--write-doc', metavar='PATH', help='重写文档中标记区间内的规则总表')
    group.add_argument('--check-doc', metavar='PATH', help='文档与规则总表不一致时退出 1')
    args = parser.parse_args()
    if args.write_doc or args.check_doc:
        path = args.write_doc or args.check_doc
        with open(path, encoding='utf-8') as stream:
            text = stream.read()
        expected = render_doc(text)
        if args.check_doc:
            if expected != text:
                sys.exit(path + ' 与 scripts/catalog.py 不一致；运行 --write-doc 更新')
            return
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(expected)
        return
    sys.stdout.write(render_markdown())


if __name__ == '__main__':
    main()
