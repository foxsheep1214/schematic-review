#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查规则总表：编号、检查方式、内容域、展开粒度、功能包与判据的唯一来源。

编号格式为 <内容域>-<方式><序号>，例如 PWR-E01：前三个字母说明查什么，
短横后的字母说明怎么查。编号一经发布不再改变或复用：合并或删除的规则登记在
RETIRED，新规则接在所在组已发布的最大序号之后。计划、Lint、证据校验、结果校验
与文档规则表都从这里取规则，不另写副本。

    python3 catalog.py                     打印规则总表（Markdown）
    python3 catalog.py --write-doc PATH    重写文档标记区间内的规则总表
    python3 catalog.py --check-doc PATH    文档与本表不一致时退出 1
"""
import argparse
import re
import sys
from collections import namedtuple

Domain = namedtuple('Domain', 'code name scope handoff')
Method = namedtuple('Method', 'code name executor inputs output stage')
Rule = namedtuple('Rule', 'id title criterion source scope')
Retired = namedtuple('Retired', 'id title replaced_by note')
Package = namedtuple('Package', 'name title domain pattern rules materials handoff')

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
    Domain('REQ', '需求与闭环', '需求追溯、关键器件与功能存在性、功能包与覆盖审计、改版与历史意见闭环', ''),
)

METHODS = (
    Method('A', '自动扫描', '脚本', '网表；关键器件计数另需意图', '疑点 FINDING / 候选 CANDIDATE / 提示 INFO',
           '冷跑与热跑都执行'),
    Method('E', '证据计算', '脚本', '网表 + 结构化证据 + 资料审计', '逐项 PASS / FAIL / INSUFFICIENT',
           '热跑执行，缺任一保证值即 INSUFFICIENT'),
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
    'package': '功能包成员',
    'board': '全板通用',
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
    'package': '逐功能包',
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
    Rule('DOC-T01', '装配选项一致性',
         '逐装配配置核 0Ω/跳线/不贴选项：互斥件不同时贴装，每种配置的供电、信号与配置通路完整，'
         'BOM 选项表与图面标注一致', 'plan', 'assembly'),
    Rule('DOC-D01', 'BOM 值字段笔误',
         'BOM 值字段无异常字符串（如 4.7F），数值、单位与器件类型一致', 'board', 'board'),
    Rule('DOC-D02', '测试节点电气预留',
         '关键电源轨、strap 点与调试信号按需要电气预留测试节点；可触达性、邻近地与夹具另交 HANDOFF',
         'board', 'board'),
    Rule('DOC-V01', '页面图形目检',
         '目检极性、方向、pin1、Option/NC 表和图形语义；页间连接符与层次端口的名称、方向一致', 'plan', 'page'),
    Rule('DOC-V02', '图纸卫生',
         '页面注释与实贴 BOM 一致（注释是意图，BOM 是现实，两者都核），换方案残留的命名与注释已清理；'
         '网络命名与实际电平、功能一致（如 DBG_*_3V3 实为 1.8V 属误导）；图框信息与 PDF/网表版本一致',
         'board', 'board'),
    Rule('DOC-Q01', '输入一致性覆盖',
         '核对本轮输入版本、哈希、导出完整性与装配配置', 'plan', 'input'),

    # DEV 器件与引脚
    Rule('DEV-E01', '符号引脚映射',
         '逐脚核对连接器符号与官方/对端 pinout', 'lint', 'device'),
    Rule('DEV-C01', '器件应力与降额',
         '受应力的电阻、电容、开关与稳压器逐颗核功耗、连续/脉冲电压、电流与温度；降额取项目规则，缺规则标为假设',
         'board', 'board'),
    Rule('DEV-C02', '电容有效容量与寿命',
         '电容耐压降额与 MLCC 直流偏压后的有效容量；电解电容按高温满载核寿命', 'board', 'board'),
    Rule('DEV-C03', '精度器件选择',
         '分压、采样、ZQ 等精度要求由允许误差窗口与器件要求决定，不能默认 1% 即合格', 'board', 'board'),
    Rule('DEV-C04', '连接器载流',
         '按实际并针降额、接触电阻/均流、线缆与故障电流核连接器载流，不能按单针额定乘针数放行；'
         'PCB 走线载流另交 HANDOFF', 'board', 'board'),
    Rule('DEV-C05', '推荐工作条件覆盖',
         '逐颗核供电电压、输入电压、结温/环境温度、负载与频率等推荐工作条件覆盖本设计全部工况；'
         '绝对最大额定只作损坏边界，不当作工作范围', 'plan', 'device'),
    Rule('DEV-D01', '器件身份与封装',
         '核对 MPN、符号、引脚、封装字段、参数档位和替代兼容性', 'plan', 'device'),
    Rule('DEV-D02', '官方物理脚差集',
         '官方物理脚与符号声明/网表实有脚双向差集，含未连/EP/隐藏电源', 'plan', 'device'),
    Rule('DEV-D03', '连接器对端定义',
         'pinout 与对端定义逐针核对（板内自洽不等于对端正确）；防误插与 pin1 标识按平台规则', 'plan', 'device'),
    Rule('DEV-D04', '库与物料卫生',
         '符号名与实物 MPN 一致；沿用库须有同一 MPN/封装/符号版本的验证记录', 'board', 'board'),
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
         '相邻网络名相似度超过 90%（只差下划线或后缀），疑似拼写分裂；同族总线、差分对与序号兄弟除外',
         'lint', 'net'),
    Rule('NET-A03', '自动命名无源孤岛',
         '自动编号网络上只挂无源件（无 U/J/M/Y），疑似中间节点悬空', 'lint', 'net'),
    Rule('NET-A04', 'NC 网络判别',
         '名为 NC/NC_* 的多节点网络先按判别式区分：带层次路径的是设计者画出的真实短接（疑点）；'
         '导出器的 No-Connect 汇集网不构成短接（提示），准出前仍需图面或属性证据', 'lint', 'net'),
    Rule('NET-A06', '引脚类型冲突',
         '多个输出脚直连为疑点；全输入网络、GROUND 类型脚未接已知地网为候选；开漏/三态等合法结构逐条排除',
         'lint', 'net'),

    # PWR 电源
    Rule('PWR-A01', '电源轨无驱动',
         '命名电源轨沿已装配通路追不到输出脚或声明的外部来源', 'lint', 'rail'),
    Rule('PWR-A02', '电源脚无驱动',
         '含 VDD/VCC/AVDD/DVDD/VBAT 功能名的电源脚无网络，或所在轨无驱动来源', 'lint', 'pin'),
    Rule('PWR-A03', '地脚未入地',
         '功能名为 VSS/AVSS/DVSS 的脚不在已知地网', 'lint', 'pin'),
    Rule('PWR-A04', '同基名多轨',
         '同一基名对应多条电源轨（如 VCC_3V3 与 VCC_3V3_SOM），确认监测与供电对象没有张冠李戴', 'lint', 'rail'),
    Rule('PWR-A05', '输入串联滤波无阻尼元件',
         '开关稳压器输入经串联电感/磁珠滤波，但既无 RC 阻尼支路也无体电容候选', 'input_filter', 'device'),
    Rule('PWR-A06', '存在未被监测的电源轨',
         '已识别监控器时，给 IC 供电的轨既无 sense 脚也无到 sense 的分压', 'supervision', 'rail'),
    Rule('PWR-E01', '分压窗口验算',
         '按实际电阻与 Vref 公差验证反馈/监控分压窗口', 'lint', 'pin'),
    Rule('PWR-E02', '线性稳压最坏压差',
         '按最低输入电压与最坏压差（最低温度、最大负载）核输出是否仍高于负载要求下限', 'power_up', 'device'),
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
         '防反接电路（MOSFET 理想二极管/二极管）的导通方向、体二极管朝向与栅极钳位', 'package', 'circuit'),
    Rule('PWR-T06', '地网划分与连接',
         '列出全部地网（数字、模拟、功率、机壳/保护地、隔离地），核连接点位置与方式（直连、0Ω、磁珠、RC/电容）'
         '符合器件与平台要求；不同地网不因名称相近而视为同一网', 'board', 'board'),
    Rule('PWR-C01', '电源轨功率预算',
         '按最大负载、电压范围与器件能力验证功率预算和裕量', 'plan', 'rail'),
    Rule('PWR-C02', '变换器电压裕量',
         '按 Vin/负载/温度保证窗口核对输出电压，与负载推荐工作范围比较；线性稳压器的最坏压差由 PWR-E02 计算',
         'package', 'circuit'),
    Rule('PWR-C03', '变换器电流应力',
         '按拓扑计算电感峰值/RMS、Isat、开关限流最小值及器件降额', 'package', 'circuit'),
    Rule('PWR-C04', '变换器时序与稳定性',
         '核对最小导通/关断时间、Cout 有效容量/ESR、补偿和稳定工作条件', 'package', 'circuit'),
    Rule('PWR-C05', '损耗与反向电流',
         '核对损耗、反向电流、预偏置与放电路径；结温实现转 HANDOFF', 'package', 'circuit'),
    Rule('PWR-C06', '保护门限',
         '核对 UVLO/OVLO/限流容差与检测目的，明确保护前后采样点；开关的连续电流、限流值、快断时间与热保护分别核，'
         '不能互代', 'package', 'circuit'),
    Rule('PWR-C09', '去耦容量',
         '按本状态器件条款分别核对数量、容量组合及适用的有效容量要求；标称总量不能替代偏压/温度/公差后的保证容量',
         'decoupling', 'device'),
    Rule('PWR-C10', '去耦电容额定',
         '按具体电容料号与项目工况核对耐压/降额及适用 ESR 要求；不从封装或轨名猜参数', 'decoupling', 'device'),
    Rule('PWR-C11', '输入滤波元件',
         '核滤波元件的饱和电流、直流压降、温升与所需衰减量；'
         '截止频率与开关频率的关系按 EMC 需求确认，不以有磁珠即判合格', 'input_filter', 'device'),
    Rule('PWR-C13', '热插拔浪涌与输入电容',
         '热插拔浪涌电流 I=C·dV/dt 对照源端限制；输入电容总量对照平台限制（如 ≤500µF）', 'package', 'circuit'),
    Rule('PWR-C14', '纹波与噪声预算',
         '按敏感负载（PLL、ADC、RF、基准）的电源噪声/PSRR 要求核纹波与噪声预算，含开关频率、后级 LDO/滤波与去耦；'
         '实测另交 HANDOFF', 'package', 'circuit'),
    Rule('PWR-D01', '去耦清单完整性',
         '结合完整器件/官方物理脚清单核对供电脚与去耦分组覆盖；无名称命中不代表不适用', 'decoupling', 'board'),
    Rule('PWR-D02', '去耦接法',
         '按准确器件条款核对本组各电源脚与指定返回节点的去耦接法；同网存在电容不证明布局充分', 'decoupling', 'device'),
    Rule('PWR-D03', '预偏置与软启动',
         '核同步变换器的预偏置启动支持与软启动配置：资料是否明确支持预偏置、'
         '软启动时间与输入浪涌/限流的配合', 'power_up', 'device'),

    # RST 启动与复位
    Rule('RST-A01', '使能脚上下拉待核',
         '使能网（按网名或引脚名识别）上有上拉/下拉时列候选，核有效极性与脚耐压；已有对应证据的网络交证据计算',
         'lint', 'net'),
    Rule('RST-A02', '使能/复位与供电轨同时建立',
         '器件的使能/复位输入与其自身供电脚同网，随电源同时建立', 'power_up', 'device'),
    Rule('RST-A03', '使能直连输入轨无 UVLO/延时',
         '稳压器使能脚直连自身输入网，无分压或 RC', 'power_up', 'device'),
    Rule('RST-A04', '使能来源不确定',
         '稳压器使能网上既无驱动源，也无分压、RC 或上/下拉；器件内部上/下拉需资料证据', 'power_up', 'device'),
    Rule('RST-A05', '喂狗输入悬空或固定电平',
         '喂狗输入悬空或直接接电源/地，需确认是否有意禁用', 'supervision', 'device'),
    Rule('RST-A06', '复位/看门狗输出未到复位输入',
         '输出网不含任何复位输入脚；网上无其他器件为疑点，只接到其他脚为候选', 'supervision', 'device'),
    Rule('RST-E01', '使能极性与耐压',
         '核对 EN 有效极性、默认态、上拉轨与绝对最大额定', 'lint', 'pin'),
    Rule('RST-E02', 'strap 强制态',
         '核对 BOOT/strap/test 引脚的强制态与采样窗口', 'lint', 'pin'),
    Rule('RST-E03', '复位脉宽',
         '按保证值核复位输出最小脉宽不低于目标复位输入要求；开漏输出须有上拉且电源域正确', 'supervision', 'device'),
    Rule('RST-T01', '使能来源确定性',
         '核使能来源在上电、掉电与故障恢复下的确定性：来源形态、UVLO/迟滞窗口、'
         '延时与被供电器件的要求顺序；使能脚耐压与所接轨按绝限核', 'power_up', 'device'),
    Rule('RST-T02', '复位链与喂狗',
         '逐跳核复位链：输出类型与上拉电源域、极性、到每个复位输入的连通、'
         '喂狗来源在启动期与固件异常时的行为，以及手动复位/去抖接法', 'supervision', 'device'),
    Rule('RST-T03', '上电顺序与恢复',
         '检查慢爬升、棕断、短暂掉电、单域掉电、外部先供电、重试及恢复模式', 'package', 'circuit'),
    Rule('RST-T04', '复位期间 IO 默认态',
         '核主控与外设在断电、复位、启动配置采样与固件接管前的 IO 默认态（高阻、内部上下拉、默认输出）'
         '对继电器、电源使能、驱动器、LED 与外部总线的影响；关键控制线须有确定的外部默认电平',
         'package', 'circuit'),
    Rule('RST-C01', '采样窗口电平',
         '逐采样窗口计算 strap/EN 保证电压，含内部拉阻、LED、泄漏、电容和门限', 'package', 'circuit'),
    Rule('RST-C02', '复位时序',
         '按 V(t) 穿越门限时刻核对复位脉宽/释放与采样 setup/hold，不能以 RC 时间常数代替', 'package', 'circuit'),
    Rule('RST-D01', '救砖通道',
         'Recovery/Maskrom 等救砖通道存在，进入条件与默认电平确定', 'package', 'circuit'),

    # CLK 时钟
    Rule('CLK-C01', '晶体负载与起振',
         '按晶体准确料号核对 CL/ESR/驱动功率、振荡器适配和起振条件，反馈电阻、串联电阻按 datasheet/参考设计取值；'
         '寄生及实测裕量转 HANDOFF', 'package', 'circuit'),
    Rule('CLK-D01', '有源时钟输出与使能',
         '有源时钟输出幅度/电源域、使能态和上电有效时间', 'package', 'circuit'),
    Rule('CLK-D03', 'RTC 晶体与备份电源',
         'RTC 晶振为 32.768kHz（防丝印笔误为高频）；外部 RTC 备份电池/超级电容充电电压不超上限', 'package', 'circuit'),

    # SIG 接口与信号
    Rule('SIG-A01', '交流耦合发送端无直流通路',
         'LVPECL/PECL 类电平交流耦合，发送侧无到地/到轨的直流通路；声明依据出疑点，名称线索出候选',
         'diff_levels', 'link'),
    Rule('SIG-A02', '交流耦合接收端无偏置/端接',
         '交流耦合后的接收侧既无端接也无偏置', 'diff_levels', 'link'),
    Rule('SIG-E01', '必需上拉与串阻',
         '核对指定两网间电阻装配与等效阻值；电平/上升时间另行检查', 'lint', 'net'),
    Rule('SIG-E02', '差分电平兼容',
         '按两端保证范围核电平兼容：直流耦合时发送共模与摆幅落在接收端共模/差分输入'
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
         'package', 'circuit'),
    Rule('SIG-C01', 'I²C 灌电流与上升时间',
         '逐电气段合并全部上拉公差：Rp_min=(Vpullup_max-VOL_max)/IOL_guaranteed，'
         'Rp_max=tr_max/(0.8473*Cb_max)；核对串联压降', 'package', 'link'),
    Rule('SIG-C03', '总线端接与偏置',
         '按实际总线端点和节点数核对端接等效负载、空闲偏置及接收保证差分门限', 'package', 'circuit'),
    Rule('SIG-C04', '总线共模与未供电负载',
         '核对收发器 VIO/默认态、总线共模范围、地偏差与未供电负载', 'package', 'circuit'),
    Rule('SIG-C05', 'USB VBUS 供电与保护',
         '核对 VBUS 供电资格、电压档位、放电、反灌、过流及端口未供电状态', 'package', 'circuit'),
    Rule('SIG-C07', '逻辑电平与驱动匹配',
         '逐条链路核驱动端 VOH/VOL 与接收端 VIH/VIL（含负载电流与温度角）、驱动电流与扇出、上拉轨对所有接收端'
         '门限与耐压的满足情况；跨电压域须有转换器或书面确认同域，转换器方向与使能态明确', 'package', 'link'),
    Rule('SIG-C08', '掉电与跨域注入',
         '逐域掉电和外部设备先上电时核 Ioff、输入耐压与注入电流限值，找出经上拉、ESD 结构或保护二极管的反灌路径；'
         '跨轨上拉先列候选，再核掉电容忍', 'package', 'link'),
    Rule('SIG-C09', '时序裕量',
         '按两端保证值核传播延迟、建立/保持、时钟偏斜与电平转换器延迟，给出最坏角点裕量；布线延迟另交 SI HANDOFF',
         'package', 'link'),
    Rule('SIG-D01', 'I²C 地址与装配组合',
         '核对地址/复用/复位态和板载及外部可选上拉的装配组合', 'package', 'link'),
    Rule('SIG-D02', 'DDR 校准端接',
         '分别按控制器和 DRAM 的具体型号/代际核对 ZQ/校准脚端接与精度，禁止跨器件套用', 'package', 'circuit'),
    Rule('SIG-D03', 'DDR 端接与基准',
         '逐数据/地址/时钟/VREF/VTT 电源域核对拓扑、端接、基准及上电条件', 'package', 'circuit'),
    Rule('SIG-D04', 'USB-C 角色与 CC',
         '按 Source/Sink/DRP 角色及 PD 模式核对 CC/Rp/Rd、方向检测、线缆 VCONN', 'package', 'circuit'),
    Rule('SIG-D06', '调试接口',
         'UART/JTAG/SWD 调试口可达，串阻与 ESD 按需配置', 'package', 'circuit'),
    Rule('SIG-D07', 'USB 物理层',
         'REXT、DP/DM 串阻、VBUS 检测、ID 与 ESD 挂在活线上', 'package', 'circuit'),
    Rule('SIG-D08', '串口与现场总线',
         'UART/RS232/RS485/CAN 的收发器供电与 VIO、STBY/EN 默认态、端接策略（本端/对端书面明确）、空闲偏置、隔离与防护',
         'package', 'circuit'),
    Rule('SIG-D09', 'SPI 与 SPI Flash',
         'SPI 片选/时钟极性与串阻；SPI Flash 供电域、上拉与写保护', 'package', 'circuit'),
    Rule('SIG-D10', 'eMMC/SD 接口',
         'eMMC/SD 的 IO 电平、CMD 上拉、CLK/STROBE 串阻与测试节点电气预留；高速测试点与 stub 限制另交 HANDOFF',
         'package', 'circuit'),
    Rule('SIG-D11', '以太网 PHY 与网变',
         'MDI 差分对 P/N、变压器中心抽头端接、Bob Smith 75Ω+1nF/2kV、MDIO 上拉、PHY 复位与 strap',
         'package', 'circuit'),
    Rule('SIG-D12', '射频与模组',
         '天线路径默认通断、供电电容总量对照规格书最小值、开关机/复位驱动与参考设计一致、SIM 卡 ESD 与上拉',
         'package', 'circuit'),
    Rule('SIG-D13', '主控引脚复用与分配',
         '主控/SoC 引脚复用、功能分配与电平域符合平台约束（专用功能脚、启动相关脚、仅输入脚、5V 容忍），'
         '与固件配置表一致，无冲突与重复占用', 'board', 'board'),
    Rule('SIG-D14', '高速串行链路',
         'PCIe/SATA/USB3/SerDes 链路的交流耦合电容位置与容值、极性与通道映射、参考时钟与边带信号'
         '（PERST#/CLKREQ#/WAKE#）按规范连接', 'package', 'circuit'),
    Rule('SIG-D15', '音视频接口',
         'HDMI/MIPI/LVDS 显示与摄像接口、I²S/编解码器的通道映射，热插拔/DDC/CEC 电平与上拉，'
         'MCLK/帧时钟来源，模拟音频供电与地按规范连接', 'package', 'circuit'),

    # ANA 模拟与监测
    Rule('ANA-T01', '检测与监测链',
         '先定义被测量与保护目的，再核取样网络与取样侧、返回地、比较/判决、控制与反馈：检测输入存在可取源侧，'
         '验证输出有效或负载电压取保护后；首次使能不能依赖尚未使能的输出，检查循环启动', 'package', 'circuit'),
    Rule('ANA-C01', '直流范围与误差',
         '运放输入共模/输出摆幅及偏置/失调/增益误差，含供电和温度极限', 'package', 'circuit'),
    Rule('ANA-C02', '动态与负载',
         '运放 GBW/压摆率/容性负载；ADC 源阻抗、采样保持获取时间与建立误差', 'package', 'circuit'),
    Rule('ANA-C03', '基准与输入保护',
         'ADC 基准驱动/误差、输入满量程及钳位/注入电流，含掉电状态', 'package', 'circuit'),
    Rule('ANA-D01', '温度传感器',
         '温度传感器电气连接、量程和接口正确；传感器摆放与热路径另交 HANDOFF', 'package', 'circuit'),

    # PRO 防护与隔离
    Rule('PRO-A01', 'ESD/TVS 挂残网',
         'ESD/TVS 器件所在网络节点数少于 2，或不含真实信号端点', 'lint', 'device'),
    Rule('PRO-A02', '钳位器件窗口待核',
         '跨接轨与地的钳位器件按型号/轨名只给检索提示，逐项查 VRWM、VBR、VC、波形、温度与能量；型号不能证明导通或烧毁',
         'lint', 'device'),
    Rule('PRO-A03', '光耦 LED 回路无限流元件',
         '光耦 LED 两条腿上都没有串联电阻，且未声明恒流驱动', 'optocoupler', 'device'),
    Rule('PRO-A04', '光耦输出集电极无上拉',
         '光耦集电极网上无到电源轨的上拉电阻', 'optocoupler', 'device'),
    Rule('PRO-E01', '光耦传输能力',
         '按最小正向电流、保证 CTR 与项目规定的寿命衰减系数核输出可用电流是否满足'
         '上拉与负载要求；同时核最大正向电流不超额定', 'optocoupler', 'device'),
    Rule('PRO-C01', '防护器件协调',
         'TVS 的 VRWM/VBR/VC 按实际浪涌波形、电流与温度对照后级绝限；熔断器/PTC 的额定、时间电流与熔断能量按项目'
         '降额核对；浪涌（GDT/TSS）→ ESD → 端接 → 隔离逐段核动作电压与能量配合；缺工况不定判', 'package', 'circuit'),
    Rule('PRO-D01', '光耦隔离与耐压',
         '核隔离两侧的网络归属、参考地、跨接器件与耐压，以及输出侧速度/负载条件；'
         '爬电距离与实际隔离距离另交结构与版图', 'optocoupler', 'device'),
    Rule('PRO-D02', '隔离带跨接',
         '跨隔离带器件与网络归属、跨接电容耐压；实际爬电距离另交 HANDOFF', 'package', 'circuit'),
    Rule('PRO-D03', '对外连接器防护',
         '对外连接器逐针考虑防护，ESD 器件挂在活线上；板内互连器件可按依据判不适用', 'plan', 'device'),

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
         '按保证值核栅源驱动窗口：最小驱动不低于 RDS(on) 保证条件的 VGS，'
         '最大驱动不超栅源绝限；驱动源与下拉在上电、故障与高阻态下均确定', 'power_switch', 'device'),
    Rule('DRV-T01', '钳位拓扑与方向',
         '核对本状态该感性负载的续流/钳位路径是否存在、方向是否正确、钳位器件是否贴装；'
         '驱动器内部钳位须有资料证据，网名或型号不构成结论', 'inductive_load', 'device'),
    Rule('DRV-C01', '钳位器件额定',
         '按线圈关断瞬间电流与电源最高电压核钳位器件额定：反向耐压、峰值/重复电流、'
         '钳位电压加电源电压不超过开关器件耐压、重复频率下的耗散', 'inductive_load', 'device'),
    Rule('DRV-C02', '功率管 SOA 与降额',
         '按实际电流、电压、脉宽、换流速度与栅偏共同核安全工作区与降额；保护管另核限流/故障计时、热态降额与'
         '重复重试能量；不能只用 I²·RDS(on) 代替 SOA，重复脉冲与单次脉冲分别核', 'power_switch', 'device'),
    Rule('DRV-D01', '开关节点吸收与驱动条款',
         '核开关节点尖峰与振铃：吸收/钳位网络的存在、参数与耗散，'
         '死区、自举欠压、负压与短路软关断按驱动器条款逐项核', 'power_switch', 'device'),

    # REQ 需求与闭环
    Rule('REQ-A01', '关键器件计数',
         '按意图清单核对关键器件数量（该有的写 ≥1，该删的写 0）；缺意图时不执行并列入未执行', 'lint', 'board'),
    Rule('REQ-A02', '要求的功能未检出',
         '验证设计意图要求的功能是否已在原理图中实现', 'plan', 'package'),
    Rule('REQ-D01', '需求逐条追溯',
         '需求条款逐条落到实现电路与检查项，验收判据取需求原文', 'plan', 'requirement'),
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
    Rule('REQ-Q07', '功能包覆盖',
         '功能包的全部成员规则逐电路、逐工况完成后汇总；功能包只汇总覆盖，不能代替成员检查', 'plan', 'package'),
    Rule('REQ-Q08', '未检出功能确认',
         '网表未检出且未声明的功能包逐个确认不适用并给出依据；未检出特征不等于不适用', 'plan', 'board'),
    Rule('REQ-H01', '改版 Diff 与历史意见闭环',
         '按历史意见断言核对新旧器件字段、引脚换网与网络成员变化，防止假闭环', 'revision', 'history'),
    Rule('REQ-H02', '改版删除项复核',
         '核对旧项在本版冷/热阶段的消失、恢复或替代及连带影响，不能以清单增减证明修复。', 'revision', 'history'),
)

# 已发布但被合并或删除的编号：不再复用，旧计划与历史报告按此查找替代规则。
RETIRED = (
    Retired('NET-A05', 'NC 工具伪网络', ('NET-A04',), '并入 NC 网络判别，伪网络作为提示级结果'),
    Retired('PWR-T02', '检测点取样侧', ('ANA-T01',), '与监测链合并'),
    Retired('PWR-C07', '保护器件 SOA', ('DRV-C02',), '与开关管 SOA 合并'),
    Retired('PWR-C08', '保护器件协调', ('PRO-C01',), '与防护链配合合并'),
    Retired('PWR-C12', '输入保险丝与限流开关', ('PWR-C06', 'PRO-C01'), '开关限流并入保护门限，熔断特性并入防护器件协调'),
    Retired('PWR-D04', '未用电源脚处置', ('DEV-D05',), '并入引脚处置'),
    Retired('SIG-C02', 'I²C 电压域与掉电', ('SIG-C07', 'SIG-C08'), '拆为通用的电平匹配与掉电注入'),
    Retired('SIG-C06', '上拉轨与电平门限', ('SIG-C07',), '并入逻辑电平与驱动匹配'),
    Retired('SIG-D05', '跨电压域接口', ('SIG-C07',), '并入逻辑电平与驱动匹配'),
    Retired('DOC-V03', '网络命名与图框版本', ('DOC-V02',), '并入图纸卫生'),
    Retired('CLK-D02', '晶振外围电阻', ('CLK-C01',), '并入晶体负载与起振'),
    Retired('ANA-D02', '运放未用通道', ('DEV-D05',), '并入引脚处置'),
    Retired('SIG-Q01', 'DDR 功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('SIG-Q02', 'USB 功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('SIG-Q03', '以太网功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('SIG-Q04', 'CAN 功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('SIG-Q05', 'RS485 功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('SIG-Q06', 'I²C 功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('SIG-Q07', 'SPI 功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('SIG-Q08', 'UART 功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('SIG-Q09', '存储功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('SIG-Q10', '射频功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('CLK-Q01', '时钟功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('RST-Q01', '复位功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('PRO-Q01', '隔离功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
    Retired('REQ-Q06', '自定义功能覆盖', ('REQ-Q07',), '功能覆盖统一为功能包覆盖'),
)

_HANDOFF_NONE = {'required': False}

# 功能包：检出特征（对网名、引脚名与物料字段做正则匹配）或意图声明使其适用；适用后逐电路×工况
# （未声明电路时按包一次）生成全部成员规则。意图中 features 的键与 circuits[].type 取包名。
PACKAGES = (
    Package('POWER_CONVERTER', '变换器与稳压器', 'PWR',
            r'(^|[:_-])(FB|VFB|LX\d*|PGOOD|PWRGD|VOUT\d*)([:_-]|$)|LDO|BUCK|BOOST|DC-?DC|PMIC',
            ('PWR-C02', 'PWR-C03', 'PWR-C04', 'PWR-C05', 'PWR-C14'),
            ('requirements', 'datasheets'),
            {'required': True, 'receivers': ['PCB Layout', 'Thermal/Test'],
             'constraint': '功率回路面积、反馈走线、散热与输入/输出电容布局要求',
             'verification': '版图复核与温升、纹波实测'}),
    Package('POWER_PROTECTION', '电源输入保护', 'PWR',
            r'FUSE|HOT-?SWAP|SURGE|PART:F\d+:|(^|[:_-])(OVP|UVP|OCP|ILIM)([:_-]|$)|SMBJ|SMAJ|SMCJ',
            ('PWR-C06', 'DRV-C02', 'PRO-C01', 'PWR-C13', 'PWR-T05', 'ANA-T01'),
            ('requirements', 'datasheets'),
            {'required': True, 'receivers': ['PCB Layout', 'EMC/Test'],
             'constraint': '保护器件靠近入口、浪涌回路最短、功率器件散热',
             'verification': '版图复核与浪涌/短路测试'}),
    Package('ANALOG', '模拟前端与监测', 'ANA',
            r'(^|[:_-])(AIN\d*|ADC\w*|VREF\w*|REFIN|REFOUT|OPA\w*|INA\d*|ISENSE\w*|CSP|CSN|NTC\w*|THERM\w*)([:_-]|$)',
            ('ANA-C01', 'ANA-C02', 'ANA-C03', 'ANA-T01', 'ANA-D01'),
            ('requirements', 'datasheets'),
            {'required': True, 'receivers': ['PCB Layout'],
             'constraint': '模拟地与基准走线、敏感输入远离开关节点',
             'verification': '版图复核与噪声实测'}),
    Package('STARTUP', '上电、复位与启动', 'RST',
            r'RESET|(^|_)RST|POR(_|$)|(^|[:_-])(BOOT\w*|STRAP\w*|PWRON\w*)([:_-]|$)',
            ('RST-C01', 'RST-C02', 'RST-T03', 'RST-T04', 'RST-D01'),
            ('requirements', 'datasheets'), _HANDOFF_NONE),
    Package('CLOCK', '时钟', 'CLK',
            r'CLK|CLOCK|OSC|XTAL|XIN|XOUT|32K',
            ('CLK-C01', 'CLK-D01', 'CLK-D03'),
            ('datasheets',),
            {'required': True, 'receivers': ['PCB Layout'],
             'constraint': '晶振回路、时钟走线和噪声隔离布局要求', 'verification': '版图复核'}),
    Package('I2C', 'I²C', 'SIG',
            r'(^|[:_-])(I2C\w*|SCL\d*|SDA\d*)([:_-]|$)',
            ('SIG-C01', 'SIG-C07', 'SIG-C08', 'SIG-D01'),
            ('requirements', 'datasheets'), _HANDOFF_NONE),
    Package('SPI', 'SPI', 'SIG',
            r'\bSPI\w*|MOSI|MISO|SCLK',
            ('SIG-D09', 'SIG-C07', 'SIG-C09'),
            ('requirements', 'datasheets'), _HANDOFF_NONE),
    Package('UART', 'UART/RS232', 'SIG',
            r'UART|\bTXD\w*|\bRXD\w*',
            ('SIG-D08', 'SIG-T04', 'SIG-C07'),
            ('requirements', 'datasheets'), _HANDOFF_NONE),
    Package('CAN', 'CAN', 'SIG',
            r'CANH|CANL|CAN_TX|CAN_RX|\bCAN\d*\b',
            ('SIG-C03', 'SIG-C04', 'SIG-D08', 'PRO-C01'),
            ('requirements', 'datasheets'),
            {'required': True, 'receivers': ['PCB Layout', 'EMC/Test'],
             'constraint': '差分走线、防护器件顺序、隔离与端接布局', 'verification': '版图复核与接口测试'}),
    Package('RS485', 'RS485', 'SIG',
            r'RS485|485_TX|485_RX|485_A|485_B',
            ('SIG-C03', 'SIG-C04', 'SIG-D08', 'SIG-T04', 'PRO-C01'),
            ('requirements', 'datasheets'),
            {'required': True, 'receivers': ['PCB Layout', 'EMC/Test'],
             'constraint': '差分走线、防护顺序和隔离布局要求', 'verification': '版图复核与接口测试'}),
    Package('USB', 'USB/Type-C', 'SIG',
            r'USB|VBUS|TYPEC|TYPE_C',
            ('SIG-D07', 'SIG-D04', 'SIG-C05', 'SIG-T04'),
            ('requirements', 'datasheets'),
            {'required': True, 'receivers': ['PCB Layout'],
             'constraint': '差分阻抗、等长、回流、stub 和防护器件顺序', 'verification': 'PCB 规则与版图复核'}),
    Package('ETHERNET', '以太网', 'SIG',
            r'ETH|RGMII|RMII|SGMII|MDIO|\bMDI\d|PHY',
            ('SIG-D11', 'SIG-C09', 'PRO-C01'),
            ('requirements', 'datasheets', 'platform_checklist'),
            {'required': True, 'receivers': ['PCB Layout', 'SI'],
             'constraint': 'MDI/RGMII 阻抗、等长、回流及网变到接口布局规则',
             'verification': 'PCB 规则、版图复核与必要 SI 验证'}),
    Package('DDR', 'DDR', 'SIG',
            r'LPDDR|DDR[2345]?|SDRAM|DQS|\bZQ\b',
            ('SIG-D02', 'SIG-D03', 'SIG-C09'),
            ('requirements', 'datasheets', 'platform_checklist'),
            {'required': True, 'receivers': ['PCB Layout', 'SI'],
             'constraint': '阻抗、拓扑、等长、回流与布局规则按平台规范落实', 'verification': 'PCB 约束/DRC 与 SI 验证'}),
    Package('STORAGE', 'eMMC/SD', 'SIG',
            r'EMMC|SDIO|SDMMC|MICROSD|TF_CARD',
            ('SIG-D10', 'SIG-C07', 'SIG-C09'),
            ('requirements', 'datasheets', 'platform_checklist'),
            {'required': True, 'receivers': ['PCB Layout'],
             'constraint': '高速信号阻抗、等长、stub 与测试点规则', 'verification': 'PCB 规则与版图复核'}),
    Package('RF', '射频与模组', 'SIG',
            r'(^|[:_-])(RF|ANT|WIFI|WLAN|LTE|GNSS|SIM)([:_-]|$)',
            ('SIG-D12', 'PWR-C14'),
            ('requirements', 'datasheets'),
            {'required': True, 'receivers': ['RF/PCB Layout', 'EMC/Test'],
             'constraint': '射频阻抗、匹配、布局隔离与认证测试约束', 'verification': 'RF 版图复核、匹配和实测'}),
    Package('HSSERIAL', '高速串行', 'SIG',
            r'PCIE|PCI_E|SATA|SERDES|USB3|SSTX|SSRX|PERST|CLKREQ',
            ('SIG-D14', 'SIG-T01'),
            ('requirements', 'datasheets', 'platform_checklist'),
            {'required': True, 'receivers': ['PCB Layout', 'SI'],
             'constraint': '差分阻抗、耦合电容位置、等长与参考平面连续', 'verification': 'SI 仿真或链路测试'}),
    Package('AV', '音视频接口', 'SIG',
            r'HDMI|MIPI|(^|[:_-])(CSI|DSI|EDP|LCD)\w*|(^|[:_-])I2S|MCLK|LRCK|BCLK|CODEC|(^|[:_-])(SPK|MIC)([:_-]|\d|$)',
            ('SIG-D15', 'SIG-C07'),
            ('requirements', 'datasheets'),
            {'required': True, 'receivers': ['PCB Layout', 'EMC/Test'],
             'constraint': '高速差分阻抗与等长、音频模拟地与数字地分区', 'verification': '版图复核与接口测试'}),
    Package('ISOLATION', '隔离', 'PRO',
            r'ISOLAT|(^|_)ISO(_|$)|DIGITAL_ISO',
            ('PRO-D02', 'PRO-C01'),
            ('requirements', 'datasheets'),
            {'required': True, 'receivers': ['PCB Layout', 'Safety'],
             'constraint': '隔离分区、爬电/电气间隙和禁布要求', 'verification': 'PCB 实距与安规复核'}),
    Package('DEBUG', '调试与烧录', 'SIG',
            r'JTAG|SWDIO|SWCLK|(^|[:_-])(SWD|TCK|TMS|TDI|TDO|TRST\w*)([:_-]|$)|(^|[:_-])(DEBUG|DBG)',
            ('SIG-D06',),
            ('datasheets',), _HANDOFF_NONE),
)

# 审查过程的六个覆盖维度及其审计规则。
COVERAGE_RULES = {
    'input_consistency': 'DOC-Q01',
    'requirements': 'REQ-Q01',
    'chains': 'REQ-Q02',
    'states': 'REQ-Q03',
    'datasheets': 'DEV-Q01',
    'history': 'REQ-Q04',
}

ID_RE = re.compile(r'^([A-Z]{3})-([A-Z])(\d{2})$')
METHOD_ORDER = ''.join(m.code for m in METHODS)
DOMAIN_BY_CODE = {d.code: d for d in DOMAINS}
METHOD_BY_CODE = {m.code: m for m in METHODS}
BY_ID = {}
RETIRED_BY_ID = {}
PACKAGE_BY_NAME = {}


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
    for item in RETIRED:
        _check_id(item.id)
        if item.id in BY_ID or item.id in RETIRED_BY_ID:
            raise ValueError('废弃编号与在用或其他废弃编号重复: ' + item.id)
        if not item.replaced_by or any(x not in BY_ID for x in item.replaced_by):
            raise ValueError('废弃编号须指向在用规则: ' + item.id)
        RETIRED_BY_ID[item.id] = item
    for package in PACKAGES:
        if package.name in PACKAGE_BY_NAME or package.domain not in DOMAIN_BY_CODE:
            raise ValueError('功能包定义错误: ' + package.name)
        re.compile(package.pattern)
        PACKAGE_BY_NAME[package.name] = package
    referenced = [rule for p in PACKAGES for rule in p.rules] + list(COVERAGE_RULES.values())
    for rule in referenced:
        if rule not in BY_ID:
            raise ValueError('映射引用了未登记的规则: ' + rule)
    for package in PACKAGES:
        if not package.rules or any(rule[4] in 'AEHQ' for rule in package.rules):
            raise ValueError('功能包成员须为审查者逐项执行的规则: ' + package.name)
    for rule in RULES:
        if rule.source == 'package' and not packages_of(rule.id):
            raise ValueError('功能包成员规则未编入任何功能包: ' + rule.id)


def known(rule_id):
    return isinstance(rule_id, str) and rule_id in BY_ID


def retired(rule_id):
    return RETIRED_BY_ID.get(rule_id) if isinstance(rule_id, str) else None


def get(rule_id):
    try:
        return BY_ID[rule_id]
    except (KeyError, TypeError):
        old = retired(rule_id)
        if old:
            raise KeyError('规则 %s 已废弃，改用 %s' % (rule_id, '、'.join(old.replaced_by))) from None
        raise KeyError('规则总表中没有该编号: %r' % (rule_id,)) from None


def domain_of(rule_id):
    return get(rule_id).id[:3]


def method_of(rule_id):
    return get(rule_id).id[4]


def title(rule_id):
    return get(rule_id).title


def criterion(rule_id):
    return get(rule_id).criterion


def rules(method=None, domain=None, source=None):
    return [rule for rule in RULES
            if (method is None or rule.id[4] == method)
            and (domain is None or rule.id[:3] == domain)
            and (source is None or rule.source == source)]


def titles(method=None, domain=None, source=None):
    return {rule.id: rule.title for rule in rules(method, domain, source)}


def package(name):
    return PACKAGE_BY_NAME[name]


def packages_of(rule_id):
    return [p.name for p in PACKAGES if rule_id in p.rules]


def package_criterion(name):
    """功能包汇总项的判据：列出本包成员规则；项目自定义功能没有成员规则，由审查者补充。"""
    item = PACKAGE_BY_NAME.get(name)
    if item is None:
        return '执行项目自定义功能 %s 的原理图检查；成员检查由审查者按需求逐项补充' % name
    members = '、'.join('%s %s' % (rule, title(rule)) for rule in item.rules)
    return '执行%s功能包：%s；成员检查全部完成后汇总，禁止整包一次性 PASS' % (item.title, members)


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
        old = retired(rule)
        if old:
            return ['规则 %s 已废弃，改用 %s' % (rule, '、'.join(old.replaced_by))]
        return ['规则编号未登记: %r' % (rule,)]
    errors = []
    if item.get('method') != method_of(rule) or item.get('domain') != domain_of(rule):
        errors.append('method/domain 与规则 %s 不一致' % rule)
    if not str(item.get('id', '')).startswith(rule + '.'):
        errors.append('检查 ID 必须以 %s. 开头' % rule)
    return errors


_build_index()


# -- 文档 ----------------------------------------------------------------
DOC_BEGIN = '<!-- catalog:begin（由 scripts/catalog.py --write-doc 生成，勿手改） -->'
DOC_END = '<!-- catalog:end -->'


def _cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def _numbers(domain, method):
    active = [int(r.id[5:]) for r in rules(method=method, domain=domain)]
    old = [int(r.id[5:]) for r in RETIRED if r.id[:3] == domain and r.id[4] == method]
    return active, old


def render_markdown():
    lines = ['## 检查方式', '',
             '| 代码 | 方式 | 执行者 | 输入 | 输出 | 何时执行 |',
             '|---|---|---|---|---|---|']
    for m in METHODS:
        lines.append('| %s | %s | %s | %s | %s | %s |' % tuple(_cell(x) for x in m))
    lines += ['', '## 内容域', '',
              '| 代码 | 内容域 | 范围 | 在用规则 | 移交事项（HANDOFF） |',
              '|---|---|---|---|---|']
    for d in DOMAINS:
        lines.append('| %s | %s | %s | %d | %s |' % (
            d.code, d.name, _cell(d.scope), len(rules(domain=d.code)), _cell(d.handoff or '—')))
    lines += ['', '## 来源与展开粒度', '',
              '| 来源 | 何时生成计划项 |', '|---|---|',
              '| Lint 内置 / 检查器 | 自动扫描随冷跑、热跑执行；证据计算项与检查器项按识别到的对象生成 |',
              '| 计划逐对象生成 | 按“粒度”列逐对象生成（页、器件、电源轨、链路、需求等） |',
              '| 功能包成员 | 所属功能包适用时生成：声明了电路则逐电路×工况，否则按功能包生成一次 |',
              '| 全板通用 | 每块板各生成一项，审查者给出适用性与结果 |',
              '| 改版比对 | 复审时由改版影响与历史意见断言生成 |', '',
              '| 粒度代码 | 含义 |', '|---|---|']
    for code, name in SCOPES.items():
        lines.append('| %s | %s |' % (code, name))
    lines += ['', '## 总览（内容域 × 方式）', '',
              '单元格为该组在用规则的序号，括号内为已废弃序号（不再复用）。', '',
              '| 内容域 | ' + ' | '.join('%s %s' % (m.code, m.name) for m in METHODS) + ' |',
              '|---|' + '---|' * len(METHODS)]
    for d in DOMAINS:
        cells = []
        for m in METHODS:
            active, old = _numbers(d.code, m.code)
            text = ' '.join('%02d' % n for n in sorted(active))
            if old:
                text = (text + ' ' if text else '') + '(' + ' '.join('%02d' % n for n in sorted(old)) + ')'
            cells.append(text or '·')
        lines.append('| %s %s | %s |' % (d.code, d.name, ' | '.join(cells)))
    for d in DOMAINS:
        lines += ['', '## %s %s' % (d.code, d.name), '',
                  '| 编号 | 方式 | 检查项 | 判据要点 | 粒度 | 来源 | 功能包 |', '|---|---|---|---|---|---|---|']
        for rule in sorted(rules(domain=d.code), key=lambda r: order(r.id)):
            lines.append('| %s | %s | %s | %s | %s | %s | %s |' % (
                rule.id, METHOD_BY_CODE[rule.id[4]].name, _cell(rule.title),
                _cell(rule.criterion), SCOPES[rule.scope], SOURCES[rule.source],
                '、'.join(packages_of(rule.id)) or '—'))
    lines += ['', '## 功能包', '',
              '网表检出特征或意图声明（`features` 键、`circuits[].type` 取包名）使功能包适用；适用后生成 REQ-Q07 '
              '覆盖项与全部成员规则。未检出且未声明的功能包汇总到一项 REQ-Q08 确认。', '',
              '| 功能包 | 名称 | 内容域 | 成员规则 | 必需资料 | 检出特征（正则） |',
              '|---|---|---|---|---|---|']
    for p in PACKAGES:
        lines.append('| %s | %s | %s | %s | %s | `%s` |' % (
            p.name, p.title, p.domain, '、'.join(p.rules), '、'.join(p.materials), _cell(p.pattern)))
    lines += ['', '## 覆盖维度', '', '| 维度（results.scope_checks 键） | 规则 |', '|---|---|']
    for name, rule in COVERAGE_RULES.items():
        lines.append('| %s | %s %s |' % (name, rule, title(rule)))
    lines += ['', '## 已废弃编号', '',
              '废弃编号不再复用；使用它们的计划项会被拒绝，按“改用”列换成在用规则。', '',
              '| 编号 | 原名称 | 改用 | 说明 |', '|---|---|---|---|']
    for item in sorted(RETIRED, key=lambda r: order(r.id)):
        lines.append('| %s | %s | %s | %s |' % (
            item.id, _cell(item.title), '、'.join(item.replaced_by), _cell(item.note)))
    return '\n'.join(lines) + '\n'


def render_doc(text):
    if text.count(DOC_BEGIN) != 1 or text.count(DOC_END) != 1:
        raise ValueError('文档缺少唯一的规则总表标记')
    head, rest = text.split(DOC_BEGIN)
    _, tail = rest.split(DOC_END)
    return head + DOC_BEGIN + '\n\n' + render_markdown() + '\n' + DOC_END + tail


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
