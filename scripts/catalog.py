#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查规则总表：编号、检查方式、内容域与判据的唯一来源。

编号格式为 <内容域>-<方式><序号>，例如 PWR-E01：前三个字母说明查什么，
短横后的字母说明怎么查。计划、Lint、证据校验、结果校验与文档规则表都从
这里取规则，不另写副本。

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
Rule = namedtuple('Rule', 'id title criterion source')

DOMAINS = (
    Domain('DOC', '图纸与数据', '导出与解析完整性、BOM/库字段、页面图形与命名、测试节点、输入一致性',
           '测试点可触达性、邻近地、夹具与 ICT 覆盖'),
    Domain('DEV', '器件与引脚', '料号/封装/符号身份、引脚映射与物理脚、器件应力与降额、连接器定义与载流',
           '特殊封装/摆放要求；PCB 走线载流'),
    Domain('NET', '网络连接', '悬空网、网名分裂、无源孤岛、NC 网络、引脚类型冲突', ''),
    Domain('PWR', '电源', '电源树、电源脚与地脚、变换器/LDO、输入保护与滤波、去耦、监控覆盖、检测点',
           '去耦/储能位置与回路、大电流铜皮、PCB 压降与载流、散热与实测温升'),
    Domain('RST', '启动与复位', '使能、strap/启动配置、复位链与脉宽、看门狗、上电顺序与恢复',
           '上电/掉电单调性与台阶实测'),
    Domain('CLK', '时钟', '晶体负载与起振、有源时钟、RTC', '晶振回路寄生、起振裕量与时钟走线'),
    Domain('SIG', '接口与信号', 'I²C/SPI/UART/USB/CAN/RS485/以太网/存储/DDR/射频、差分电平、电平域、调试口',
           '阻抗、等长、间距、回流、过孔、stub 与防护器件摆放顺序'),
    Domain('ANA', '模拟与监测', '运放、ADC、基准、监测链、温度传感', '传感器摆放与热路径'),
    Domain('PRO', '防护与隔离', 'ESD/TVS/浪涌防护链、钳位窗口、隔离与光耦、对外连接器防护',
           '防护器件靠近连接器、实际爬电距离与电气间隙'),
    Domain('DRV', '功率驱动', '功率开关栅极驱动、SOA、开关节点吸收、感性负载续流钳位',
           '换流/钳位回路面积、结温与散热'),
    Domain('REQ', '需求与闭环', '需求追溯、关键器件与功能存在性、覆盖审计、改版与历史意见闭环', ''),
)

METHODS = (
    Method('A', '自动扫描', '脚本', '网表；关键器件计数另需意图', '疑点 FINDING / 候选 CANDIDATE',
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
    'plan': '计划生成',
    'revision': '改版比对',
    'manual': '人工补查',
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

RULES = (
    # DOC 图纸与数据
    Rule('DOC-A01', '网表导出错误或中止',
         '导出日志出现 ERROR 或中止记录；先隔离为输入阻断，残留文件不能证明当前版本有效', 'lint'),
    Rule('DOC-A02', 'No-Connect 属性被忽略',
         '导出日志中被忽略并强行连线的 No-Connect 属性，逐条核对实际网络', 'lint'),
    Rule('DOC-A03', 'BOM/库字段首尾空白',
         'PART/VALUE/JEDEC/primitive 字段含首尾空白，会破坏 BOM 与版本比对', 'lint'),
    Rule('DOC-D01', 'BOM 值字段笔误',
         'BOM 值字段无异常字符串（如 4.7F），数值、单位与器件类型一致', 'manual'),
    Rule('DOC-D02', '测试节点电气预留',
         '关键电源轨、strap 点与调试信号按需要电气预留测试节点；可触达性、邻近地与夹具另交 HANDOFF', 'manual'),
    Rule('DOC-V01', '页面图形目检',
         '目检极性、方向、pin1、Option/NC 表和图形语义', 'plan'),
    Rule('DOC-V02', '页面注释与遗留内容',
         '页面注释与实贴 BOM 一致（注释是意图，BOM 是现实，两者都核）；换方案残留的命名与注释已清理', 'manual'),
    Rule('DOC-V03', '网络命名与图框版本',
         '网络命名与实际电平、功能一致（如 DBG_*_3V3 实为 1.8V 属误导）；图框信息与 PDF/网表版本一致', 'manual'),
    Rule('DOC-Q01', '输入一致性覆盖',
         '核对本轮输入版本、哈希、导出完整性与装配配置', 'plan'),

    # DEV 器件与引脚
    Rule('DEV-E01', '符号引脚映射',
         '逐脚核对连接器符号与官方/对端 pinout', 'lint'),
    Rule('DEV-C01', '器件应力与降额',
         '受应力的电阻、电容、开关与稳压器逐颗核功耗、连续/脉冲电压、电流与温度；降额取项目规则，缺规则标为假设', 'manual'),
    Rule('DEV-C02', '电容有效容量与寿命',
         '电容耐压降额与 MLCC 直流偏压后的有效容量；电解电容按高温满载核寿命', 'manual'),
    Rule('DEV-C03', '精度器件选择',
         '分压、采样、ZQ 等精度要求由允许误差窗口与器件要求决定，不能默认 1% 即合格', 'manual'),
    Rule('DEV-C04', '连接器载流',
         '按实际并针降额、接触电阻/均流、线缆与故障电流核连接器载流，不能按单针额定乘针数放行；PCB 走线载流另交 HANDOFF',
         'manual'),
    Rule('DEV-D01', '器件身份与封装',
         '核对 MPN、符号、引脚、封装字段、参数档位和替代兼容性', 'plan'),
    Rule('DEV-D02', '官方物理脚差集',
         '官方物理脚与符号声明/网表实有脚双向差集，含未连/EP/隐藏电源', 'plan'),
    Rule('DEV-D03', '连接器对端定义',
         'pinout 与对端定义逐针核对（板内自洽不等于对端正确）；防误插、pin1 标识与未用针处置按平台规则', 'manual'),
    Rule('DEV-D04', '库与物料卫生',
         '符号名与实物 MPN 一致；沿用库须有同一 MPN/封装/符号版本的验证记录', 'manual'),
    Rule('DEV-Q01', '资料覆盖',
         '全部关键器件适用章节/errata及官方物理脚双向差集已审', 'plan'),

    # NET 网络连接
    Rule('NET-A01', '单节点悬空网',
         '网络只有一个节点且不在白名单（被删外设的 SoC 引脚、自动中间网）', 'lint'),
    Rule('NET-A02', '疑似网络名分裂',
         '相邻网络名相似度超过 90%（只差下划线或后缀），疑似拼写分裂；同族总线、差分对与序号兄弟除外', 'lint'),
    Rule('NET-A03', '自动命名无源孤岛',
         '自动编号网络上只挂无源件（无 U/J/M/Y），疑似中间节点悬空', 'lint'),
    Rule('NET-A04', 'NC 网络名造成短接',
         '名为 NC/NC_* 的多节点网络带层次路径，是设计者画出的真实短接；先按判别式排除工具伪网络', 'lint'),
    Rule('NET-A05', 'NC 工具伪网络',
         '名为 NC 的多节点网络是导出器的 No-Connect 汇集网，不构成电气短接；准出前仍需图面或属性证据', 'lint'),
    Rule('NET-A06', '引脚类型冲突',
         '多个输出脚直连为疑点；全输入网络、GROUND 类型脚未接已知地网为候选；开漏/三态等合法结构逐条排除', 'lint'),

    # PWR 电源
    Rule('PWR-A01', '电源轨无驱动',
         '命名电源轨沿已装配通路追不到输出脚或声明的外部来源', 'lint'),
    Rule('PWR-A02', '电源脚无驱动',
         '含 VDD/VCC/AVDD/DVDD/VBAT 功能名的电源脚无网络，或所在轨无驱动来源', 'lint'),
    Rule('PWR-A03', '地脚未入地',
         '功能名为 VSS/AVSS/DVSS 的脚不在已知地网', 'lint'),
    Rule('PWR-A04', '同基名多轨',
         '同一基名对应多条电源轨（如 VCC_3V3 与 VCC_3V3_SOM），确认监测与供电对象没有张冠李戴', 'lint'),
    Rule('PWR-A05', '输入串联滤波无阻尼元件',
         '开关稳压器输入经串联电感/磁珠滤波，但既无 RC 阻尼支路也无体电容候选', 'input_filter'),
    Rule('PWR-A06', '存在未被监测的电源轨',
         '已识别监控器时，给 IC 供电的轨既无 sense 脚也无到 sense 的分压', 'supervision'),
    Rule('PWR-E01', '分压窗口验算',
         '按实际电阻与 Vref 公差验证反馈/监控分压窗口', 'lint'),
    Rule('PWR-E02', '线性稳压最坏压差',
         '按最低输入电压与最坏压差（最低温度、最大负载）核输出是否仍高于负载要求下限', 'power_up'),
    Rule('PWR-E03', '输入滤波阻尼',
         '按最低输入电压与最大输入功率求负输入阻抗，核体电容 ESR 与滤波电感的一阶阻尼'
         '判据及体电容/输入电容比值（比值须由项目规定，不得默认）', 'input_filter'),
    Rule('PWR-T01', '电源轨拓扑',
         '确认电源轨驱动源、负载、域电压、时序与反灌路径', 'plan'),
    Rule('PWR-T02', '检测点取样侧',
         '先定义被测量和保护目的，再核取样网络、ADC/比较器终点及反馈控制：检测输入存在可取源侧，'
         '验证输出有效或负载电压取保护后；首次使能不能依赖尚未使能的输出', 'plan'),
    Rule('PWR-T03', '去耦连接覆盖',
         '逐物理脚核对本状态分组、返回节点、直接连接电容和装配；保留零电容/不贴/未知项，不跨串联边界，不判断电气合格',
         'decoupling'),
    Rule('PWR-T04', '逐电源域监控覆盖',
         '按需求确定哪些电源域必须监测，逐轨核监测点、阈值与动作；'
         '未监测的轨需给出书面依据，不能因为有一颗监控器就判全板覆盖', 'supervision'),
    Rule('PWR-T05', '防反接与理想二极管',
         '防反接电路（MOSFET 理想二极管/二极管）的导通方向、体二极管朝向与栅极钳位', 'manual'),
    Rule('PWR-C01', '电源轨功率预算',
         '按最大负载、电压范围与器件能力验证功率预算和裕量', 'plan'),
    Rule('PWR-C02', '变换器电压裕量',
         '按 Vin/负载/温度保证窗口核对输出及 LDO dropout；与负载推荐工作范围比较', 'plan'),
    Rule('PWR-C03', '变换器电流应力',
         '按拓扑计算电感峰值/RMS、Isat、开关限流最小值及器件降额', 'plan'),
    Rule('PWR-C04', '变换器时序与稳定性',
         '核对最小导通/关断时间、Cout 有效容量/ESR、补偿和稳定工作条件', 'plan'),
    Rule('PWR-C05', '损耗与反向电流',
         '核对损耗、反向电流、预偏置与放电路径；结温实现转 HANDOFF', 'plan'),
    Rule('PWR-C06', '保护门限',
         '核对 UVLO/OVLO/限流容差与检测目的，明确保护前后采样点', 'plan'),
    Rule('PWR-C07', '保护器件 SOA',
         '核对 MOS VDS-I-t SOA、限流/故障计时、热态降额与重复重试能量', 'plan'),
    Rule('PWR-C08', '保护器件协调',
         '核对 TVS VRWM/VBR/VC 对应波形及温度、熔断器时间电流/熔断能量与后级承受能力', 'plan'),
    Rule('PWR-C09', '去耦容量',
         '按本状态器件条款分别核对数量、容量组合及适用的有效容量要求；标称总量不能替代偏压/温度/公差后的保证容量',
         'decoupling'),
    Rule('PWR-C10', '去耦电容额定',
         '按具体电容料号与项目工况核对耐压/降额及适用 ESR 要求；不从封装或轨名猜参数', 'decoupling'),
    Rule('PWR-C11', '输入滤波元件',
         '核滤波元件的饱和电流、直流压降、温升与所需衰减量；'
         '截止频率与开关频率的关系按 EMC 需求确认，不以有磁珠即判合格', 'input_filter'),
    Rule('PWR-C12', '输入保险丝与限流开关',
         '输入保险丝/PTC 的额定与熔断特性按项目降额规范核对；开关的连续电流、限流值、快断时间与热保护分别核，不能互代',
         'manual'),
    Rule('PWR-C13', '热插拔浪涌与输入电容',
         '热插拔浪涌电流 I=C·dV/dt 对照源端限制；输入电容总量对照平台限制（如 ≤500µF）', 'manual'),
    Rule('PWR-D01', '去耦清单完整性',
         '结合完整器件/官方物理脚清单核对供电脚与去耦分组覆盖；无名称命中不代表不适用', 'decoupling'),
    Rule('PWR-D02', '去耦接法',
         '按准确器件条款核对本组各电源脚与指定返回节点的去耦接法；同网存在电容不证明布局充分', 'decoupling'),
    Rule('PWR-D03', '预偏置与软启动',
         '核同步变换器的预偏置启动支持与软启动配置：资料是否明确支持预偏置、'
         '软启动时间与输入浪涌/限流的配合', 'power_up'),
    Rule('PWR-D04', '未用电源脚处置',
         '未用 PHY/外设电源脚按平台规范处置（悬空/接地/关闭）；未用不等于所有引脚均可悬空', 'manual'),

    # RST 启动与复位
    Rule('RST-A01', '使能脚上下拉待核',
         '使能网（按网名或引脚名识别）上有上拉/下拉时列候选，核有效极性与脚耐压；已有对应证据的网络交证据计算', 'lint'),
    Rule('RST-A02', '使能/复位与供电轨同时建立',
         '器件的使能/复位输入与其自身供电脚同网，随电源同时建立', 'power_up'),
    Rule('RST-A03', '使能直连输入轨无 UVLO/延时',
         '稳压器使能脚直连自身输入网，无分压或 RC', 'power_up'),
    Rule('RST-A04', '使能来源不确定',
         '稳压器使能网上既无驱动源，也无分压、RC 或上/下拉；器件内部上/下拉需资料证据', 'power_up'),
    Rule('RST-A05', '喂狗输入悬空或固定电平',
         '喂狗输入悬空或直接接电源/地，需确认是否有意禁用', 'supervision'),
    Rule('RST-A06', '复位/看门狗输出未到复位输入',
         '输出网不含任何复位输入脚；网上无其他器件为疑点，只接到其他脚为候选', 'supervision'),
    Rule('RST-E01', '使能极性与耐压',
         '核对 EN 有效极性、默认态、上拉轨与绝对最大额定', 'lint'),
    Rule('RST-E02', 'strap 强制态',
         '核对 BOOT/strap/test 引脚的强制态与采样窗口', 'lint'),
    Rule('RST-E03', '复位脉宽',
         '按保证值核复位输出最小脉宽不低于目标复位输入要求；开漏输出须有上拉且电源域正确', 'supervision'),
    Rule('RST-T01', '使能来源确定性',
         '核使能来源在上电、掉电与故障恢复下的确定性：来源形态、UVLO/迟滞窗口、'
         '延时与被供电器件的要求顺序；使能脚耐压与所接轨按绝限核', 'power_up'),
    Rule('RST-T02', '复位链与喂狗',
         '逐跳核复位链：输出类型与上拉电源域、极性、到每个复位输入的连通、'
         '喂狗来源在启动期与固件异常时的行为，以及手动复位/去抖接法', 'supervision'),
    Rule('RST-T03', '上电顺序与恢复',
         '检查慢爬升、棕断、短暂掉电、单域掉电、外部先供电、重试及恢复模式', 'plan'),
    Rule('RST-C01', '采样窗口电平',
         '逐采样窗口计算 strap/EN 保证电压，含内部拉阻、LED、泄漏、电容和门限', 'plan'),
    Rule('RST-C02', '复位时序',
         '按 V(t) 穿越门限时刻核对复位脉宽/释放与采样 setup/hold，不能以 RC 时间常数代替', 'plan'),
    Rule('RST-D01', '救砖通道',
         'Recovery/Maskrom 等救砖通道存在，进入条件与默认电平确定', 'manual'),
    Rule('RST-Q01', '复位功能覆盖',
         '执行复位源、默认态、脉宽与全链路连通检查包', 'plan'),

    # CLK 时钟
    Rule('CLK-C01', '晶体负载与起振',
         '按晶体准确料号核对 CL/ESR/驱动功率、振荡器适配和起振条件；寄生及实测裕量转 HANDOFF', 'plan'),
    Rule('CLK-D01', '有源时钟输出与使能',
         '有源时钟输出幅度/电源域、使能态和上电有效时间', 'plan'),
    Rule('CLK-D02', '晶振外围电阻',
         '晶振反馈电阻、串联电阻按 datasheet/参考设计取值', 'manual'),
    Rule('CLK-D03', 'RTC 晶体与备份电源',
         'RTC 晶振为 32.768kHz（防丝印笔误为高频）；外部 RTC 备份电池/超级电容充电电压不超上限', 'manual'),
    Rule('CLK-Q01', '时钟功能覆盖',
         '执行晶振/时钟源、负载、使能和端点检查包', 'plan'),

    # SIG 接口与信号
    Rule('SIG-A01', '交流耦合发送端无直流通路',
         'LVPECL/PECL 类电平交流耦合，发送侧无到地/到轨的直流通路；声明依据出疑点，名称线索出候选', 'diff_levels'),
    Rule('SIG-A02', '交流耦合接收端无偏置/端接',
         '交流耦合后的接收侧既无端接也无偏置', 'diff_levels'),
    Rule('SIG-E01', '必需上拉与串阻',
         '核对指定两网间电阻装配与等效阻值；电平/上升时间另行检查', 'lint'),
    Rule('SIG-E02', '差分电平兼容',
         '按两端保证范围核电平兼容：直流耦合时发送共模与摆幅落在接收端共模/差分输入'
         '范围内；交流耦合时核接收端偏置共模、耦合电容与低频截止', 'diff_levels'),
    Rule('SIG-T01', '差分对连通',
         '核对差分 P/N 两端语义、耦合/端接拓扑和全链路连通', 'plan'),
    Rule('SIG-T02', 'I²C 连接覆盖',
         '核对本状态 SDA/SCL 物理端点、装配/跳线、全部上拉与电源域、串阻路径及隔离/外接边界；仅连接覆盖',
         'i2c_topology'),
    Rule('SIG-T03', '差分端接与偏置',
         '核端接与偏置网络的位置、阻值与电源域：差分端接、接收端偏置、'
         '发送端直流通路，以及未用通道与掉电状态的处置', 'diff_levels'),
    Rule('SIG-T04', '接口方向语义',
         'TX/RX、P/N、Host/Device、Source/Sink 按两端官方语义复述，核对对端连接器视图与线缆针序；连通只证明导电路径',
         'manual'),
    Rule('SIG-C01', 'I²C 灌电流与上升时间',
         '逐电气段合并全部上拉公差：Rp_min=(Vpullup_max-VOL_max)/IOL_guaranteed，'
         'Rp_max=tr_max/(0.8473*Cb_max)；核对串联压降', 'plan'),
    Rule('SIG-C02', 'I²C 电压域与掉电',
         '两端 VIH/VIL、VOL、耐压及 Ioff；逐域掉电和外部设备先上电的注入路径', 'plan'),
    Rule('SIG-C03', '总线端接与偏置',
         '按实际总线端点和节点数核对端接等效负载、空闲偏置及接收保证差分门限', 'plan'),
    Rule('SIG-C04', '总线共模与未供电负载',
         '核对收发器 VIO/默认态、总线共模范围、地偏差与未供电负载', 'plan'),
    Rule('SIG-C05', 'USB VBUS 供电与保护',
         '核对 VBUS 供电资格、电压档位、放电、反灌、过流及端口未供电状态', 'plan'),
    Rule('SIG-C06', '上拉轨与电平门限',
         '上拉轨须同时满足所有接收端门限、耐压、掉电容忍及转换器要求，不能固定取较高或较低域', 'manual'),
    Rule('SIG-D01', 'I²C 地址与装配组合',
         '核对地址/复用/复位态和板载及外部可选上拉的装配组合', 'plan'),
    Rule('SIG-D02', 'DDR 校准端接',
         '分别按控制器和 DRAM 的具体型号/代际核对 ZQ/校准脚端接与精度，禁止跨器件套用', 'plan'),
    Rule('SIG-D03', 'DDR 端接与基准',
         '逐数据/地址/时钟/VREF/VTT 电源域核对拓扑、端接、基准及上电条件', 'plan'),
    Rule('SIG-D04', 'USB-C 角色与 CC',
         '按 Source/Sink/DRP 角色及 PD 模式核对 CC/Rp/Rd、方向检测、线缆 VCONN', 'plan'),
    Rule('SIG-D05', '跨电压域接口',
         '跨电压接口（1.8V↔3.3V 等）有转换器或书面确认两端同域；各 IO 电源域实际电压与相连外设电平一致', 'manual'),
    Rule('SIG-D06', '调试接口',
         'UART/JTAG/SWD 调试口可达，串阻与 ESD 按需配置', 'manual'),
    Rule('SIG-D07', 'USB 物理层',
         'REXT、DP/DM 串阻、VBUS 检测、ID 与 ESD 挂在活线上', 'manual'),
    Rule('SIG-D08', '串口与现场总线',
         'UART/RS232/RS485/CAN 的收发器供电与 VIO、STBY/EN 默认态、端接策略（本端/对端书面明确）、空闲偏置、隔离与防护',
         'manual'),
    Rule('SIG-D09', 'SPI 与 SPI Flash',
         'SPI 片选/时钟极性与串阻；SPI Flash 供电域、上拉与写保护', 'manual'),
    Rule('SIG-D10', 'eMMC/SD 接口',
         'eMMC/SD 的 IO 电平、CMD 上拉、CLK/STROBE 串阻与测试节点电气预留；高速测试点与 stub 限制另交 HANDOFF', 'manual'),
    Rule('SIG-D11', '以太网 PHY 与网变',
         'MDI 差分对 P/N、变压器中心抽头端接、Bob Smith 75Ω+1nF/2kV、MDIO 上拉、PHY 复位与 strap', 'manual'),
    Rule('SIG-D12', '射频与模组',
         '天线路径默认通断、供电电容总量对照规格书最小值、开关机/复位驱动与参考设计一致、SIM 卡 ESD 与上拉', 'manual'),
    Rule('SIG-Q01', 'DDR 功能覆盖',
         '执行 DDR 供电、ZQ/ODT、时序拓扑和平台规则检查包', 'plan'),
    Rule('SIG-Q02', 'USB 功能覆盖',
         '执行 USB 方向、VBUS 检测、串阻、REXT 与 ESD 检查包', 'plan'),
    Rule('SIG-Q03', '以太网功能覆盖',
         '执行以太网 PHY、MDI、网变、时钟、strap 与管理口检查包', 'plan'),
    Rule('SIG-Q04', 'CAN 功能覆盖',
         '执行 CAN 收发器、端接、偏置、隔离和防护检查包', 'plan'),
    Rule('SIG-Q05', 'RS485 功能覆盖',
         '执行 RS485 方向、端接、偏置、隔离与防护检查包', 'plan'),
    Rule('SIG-Q06', 'I²C 功能覆盖',
         '执行 I2C 上拉、域电压、地址和总线连通检查包', 'plan'),
    Rule('SIG-Q07', 'SPI 功能覆盖',
         '执行 SPI 供电域、CS 默认态、时钟和串阻检查包', 'plan'),
    Rule('SIG-Q08', 'UART 功能覆盖',
         '执行 UART 方向、电平域、连接器与防护检查包', 'plan'),
    Rule('SIG-Q09', '存储功能覆盖',
         '执行 eMMC/SDIO 供电、上拉、串阻与启动检查包', 'plan'),
    Rule('SIG-Q10', '射频功能覆盖',
         '执行射频/模组供电、控制、默认通路、SIM 与防护检查包', 'plan'),

    # ANA 模拟与监测
    Rule('ANA-T01', '监测链完整',
         '监测量、取样侧、返回地、判决、控制与反馈完整，检查循环启动', 'manual'),
    Rule('ANA-C01', '直流范围与误差',
         '运放输入共模/输出摆幅及偏置/失调/增益误差，含供电和温度极限', 'plan'),
    Rule('ANA-C02', '动态与负载',
         '运放 GBW/压摆率/容性负载；ADC 源阻抗、采样保持获取时间与建立误差', 'plan'),
    Rule('ANA-C03', '基准与输入保护',
         'ADC 基准驱动/误差、输入满量程及钳位/注入电流，含掉电状态', 'plan'),
    Rule('ANA-D01', '温度传感器',
         '温度传感器电气连接、量程和接口正确；传感器摆放与热路径另交 HANDOFF', 'manual'),

    Rule('ANA-D02', '运放未用通道',
         '未用运放/比较器通道按具体料号推荐接法处置，输入钳定、输出不悬空也不短接到轨', 'manual'),

    # PRO 防护与隔离
    Rule('PRO-A01', 'ESD/TVS 挂残网',
         'ESD/TVS 器件所在网络节点数少于 2，或不含真实信号端点', 'lint'),
    Rule('PRO-A02', '钳位器件窗口待核',
         '跨接轨与地的钳位器件按型号/轨名只给检索提示，逐项查 VRWM、VBR、VC、波形、温度与能量；型号不能证明导通或烧毁',
         'lint'),
    Rule('PRO-A03', '光耦 LED 回路无限流元件',
         '光耦 LED 两条腿上都没有串联电阻，且未声明恒流驱动', 'optocoupler'),
    Rule('PRO-A04', '光耦输出集电极无上拉',
         '光耦集电极网上无到电源轨的上拉电阻', 'optocoupler'),
    Rule('PRO-E01', '光耦传输能力',
         '按最小正向电流、保证 CTR 与项目规定的寿命衰减系数核输出可用电流是否满足'
         '上拉与负载要求；同时核最大正向电流不超额定', 'optocoupler'),
    Rule('PRO-C01', '防护链配合',
         '浪涌（GDT/TSS）→ ESD → 端接 → 隔离逐段点名，核段间动作电压与能量配合；'
         'TVS 的 VRWM/VBR/VC 按实际浪涌波形、电流与温度对照后级绝限，缺工况不定判', 'manual'),
    Rule('PRO-D01', '光耦隔离与耐压',
         '核隔离两侧的网络归属、参考地、跨接器件与耐压，以及输出侧速度/负载条件；'
         '爬电距离与实际隔离距离另交结构与版图', 'optocoupler'),
    Rule('PRO-D02', '隔离带跨接',
         '跨隔离带器件与网络归属、跨接电容耐压；实际爬电距离另交 HANDOFF', 'manual'),
    Rule('PRO-D03', '对外连接器防护',
         '对外连接器逐针考虑防护，ESD 器件挂在活线上', 'manual'),
    Rule('PRO-Q01', '隔离功能覆盖',
         '执行隔离域、耐压、跨域器件与接地检查包', 'plan'),

    # DRV 功率驱动
    Rule('DRV-A01', '感性负载无续流/钳位路径',
         '开关驱动的线圈/绕组在该装配状态下无续流二极管、TVS/齐纳、RC 或有据的集成钳位', 'inductive_load'),
    Rule('DRV-A02', '续流二极管方向接反',
         '续流二极管阴极在开关节点、阳极在电源轨', 'inductive_load'),
    Rule('DRV-A03', '栅极无驱动源且无下拉',
         '分立开关管栅极网上既无驱动输出/外接驱动，也无下拉或上拉电阻', 'power_switch'),
    Rule('DRV-A04', '开关节点无吸收/钳位',
         '开关节点接感性元件或半桥对管，但无 RC/RCD/钳位', 'power_switch'),
    Rule('DRV-E01', '栅源驱动窗口',
         '按保证值核栅源驱动窗口：最小驱动不低于 RDS(on) 保证条件的 VGS，'
         '最大驱动不超栅源绝限；驱动源与下拉在上电、故障与高阻态下均确定', 'power_switch'),
    Rule('DRV-T01', '钳位拓扑与方向',
         '核对本状态该感性负载的续流/钳位路径是否存在、方向是否正确、钳位器件是否贴装；'
         '驱动器内部钳位须有资料证据，网名或型号不构成结论', 'inductive_load'),
    Rule('DRV-C01', '钳位器件额定',
         '按线圈关断瞬间电流与电源最高电压核钳位器件额定：反向耐压、峰值/重复电流、'
         '钳位电压加电源电压不超过开关器件耐压、重复频率下的耗散', 'inductive_load'),
    Rule('DRV-C02', '开关 SOA 与降额',
         '按实际电流、电压、脉宽、换流速度与栅偏共同核安全工作区与降额；'
         '不能只用 I²·RDS(on) 代替 SOA，重复脉冲与单次脉冲分别核', 'power_switch'),
    Rule('DRV-D01', '开关节点吸收与驱动条款',
         '核开关节点尖峰与振铃：吸收/钳位网络的存在、参数与耗散，'
         '死区、自举欠压、负压与短路软关断按驱动器条款逐项核', 'power_switch'),

    # REQ 需求与闭环
    Rule('REQ-A01', '关键器件计数',
         '按意图清单核对关键器件数量（该有的写 ≥1，该删的写 0）；缺意图时不执行并列入未执行', 'lint'),
    Rule('REQ-A02', '要求的功能未检出',
         '验证设计意图要求的功能是否已在原理图中实现', 'plan'),
    Rule('REQ-D01', '需求逐条追溯',
         '需求条款逐条落到实现电路与检查项，验收判据取需求原文', 'plan'),
    Rule('REQ-D02', '需求口径一致',
         '需求/规格书与原理图参数口径统一（电流/电压数字唯一来源）', 'manual'),
    Rule('REQ-Q01', '需求覆盖',
         '需求逐条拆解并与电路检查双向追溯，缺口不得隐藏', 'plan'),
    Rule('REQ-Q02', '链路覆盖',
         '全部接口/电源/检测/使能/复位/时钟逐路终点与返回路径覆盖', 'plan'),
    Rule('REQ-Q03', '工况状态覆盖',
         '逐关键电路覆盖启动、复位、运行、掉电、外部带电及需求内故障状态', 'plan'),
    Rule('REQ-Q04', '历史意见覆盖',
         '首审/复审已裁定，历史意见逐条复验并保留撤回/复发', 'plan'),
    Rule('REQ-Q05', '改版影响覆盖',
         '核对新旧基线、变化、依赖缺口及扩大复验范围；全部必需项使用本轮证据，不迁移旧结论。', 'revision'),
    Rule('REQ-Q06', '自定义功能覆盖',
         '执行项目自定义功能的原理图检查包', 'plan'),
    Rule('REQ-H01', '改版 Diff 与历史意见闭环',
         '按历史意见断言核对新旧器件字段、引脚换网与网络成员变化，防止假闭环', 'revision'),
    Rule('REQ-H02', '改版删除项复核',
         '核对旧项在本版冷/热阶段的消失、恢复或替代及连带影响，不能以清单增减证明修复。', 'revision'),
)

# 意图中声明的电路类型逐状态展开为这些规则（顺序即计划生成顺序）。
CIRCUIT_TYPES = {
    'POWER_CONVERTER': ('PWR-C02', 'PWR-C03', 'PWR-C04', 'PWR-C05'),
    'POWER_PROTECTION': ('PWR-C06', 'PWR-C07', 'PWR-C08'),
    'ANALOG': ('ANA-C01', 'ANA-C02', 'ANA-C03'),
    'I2C': ('SIG-C01', 'SIG-C02', 'SIG-D01'),
    'STARTUP': ('RST-C01', 'RST-C02', 'RST-T03'),
    'DDR': ('SIG-D02', 'SIG-D03'),
    'USB_C': ('SIG-D04', 'SIG-C05'),
    'CAN_RS485': ('SIG-C03', 'SIG-C04'),
    'CLOCK': ('CLK-C01', 'CLK-D01'),
}

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


def _build_index():
    for position, rule in enumerate(RULES):
        match = ID_RE.match(rule.id)
        if not match or match.group(1) not in DOMAIN_BY_CODE or match.group(2) not in METHOD_BY_CODE:
            raise ValueError('规则编号格式错误: ' + rule.id)
        if rule.id in BY_ID:
            raise ValueError('规则编号重复: ' + rule.id)
        if rule.source not in SOURCES or not rule.title.strip() or not rule.criterion.strip():
            raise ValueError('规则定义不完整: ' + rule.id)
        BY_ID[rule.id] = rule
    referenced = [rule for ids in CIRCUIT_TYPES.values() for rule in ids] + list(COVERAGE_RULES.values())
    for rule in referenced:
        if rule not in BY_ID:
            raise ValueError('映射引用了未登记的规则: ' + rule)


_build_index()


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


def order(rule_id):
    """文档顺序：内容域 → 方式 → 序号；未登记的编号排最后。"""
    if not known(rule_id):
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
    return errors


# -- 文档 ----------------------------------------------------------------
DOC_BEGIN = '<!-- catalog:begin（由 scripts/catalog.py --write-doc 生成，勿手改） -->'
DOC_END = '<!-- catalog:end -->'


def _cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def _span(numbers):
    numbers = sorted(numbers)
    if not numbers:
        return ''
    if len(numbers) == 1:
        return '%02d' % numbers[0]
    return '%02d–%02d' % (numbers[0], numbers[-1])


def render_markdown():
    lines = ['## 检查方式', '',
             '| 代码 | 方式 | 执行者 | 输入 | 输出 | 何时执行 |',
             '|---|---|---|---|---|---|']
    for m in METHODS:
        lines.append('| %s | %s | %s | %s | %s | %s |' % tuple(_cell(x) for x in m))
    lines += ['', '## 内容域', '',
              '| 代码 | 内容域 | 范围 | 规则数 | 移交事项（HANDOFF） |',
              '|---|---|---|---|---|']
    for d in DOMAINS:
        lines.append('| %s | %s | %s | %d | %s |' % (
            d.code, d.name, _cell(d.scope), len(rules(domain=d.code)), _cell(d.handoff or '—')))
    lines += ['', '## 总览（内容域 × 方式）', '',
              '单元格为该组规则的序号范围，编号即 `内容域-方式序号`。', '',
              '| 内容域 | ' + ' | '.join('%s %s' % (m.code, m.name) for m in METHODS) + ' |',
              '|---|' + '---|' * len(METHODS)]
    for d in DOMAINS:
        cells = []
        for m in METHODS:
            numbers = [int(r.id[5:]) for r in rules(method=m.code, domain=d.code)]
            cells.append(_span(numbers) or '·')
        lines.append('| %s %s | %s |' % (d.code, d.name, ' | '.join(cells)))
    for d in DOMAINS:
        lines += ['', '## %s %s' % (d.code, d.name), '',
                  '| 编号 | 方式 | 检查项 | 判据要点 | 来源 |', '|---|---|---|---|---|']
        for rule in sorted(rules(domain=d.code), key=lambda r: order(r.id)):
            lines.append('| %s | %s | %s | %s | %s |' % (
                rule.id, METHOD_BY_CODE[rule.id[4]].name, _cell(rule.title),
                _cell(rule.criterion), SOURCES[rule.source]))
    lines += ['', '## 电路类型展开', '',
              '意图中 `circuits[].type` 声明的电路逐状态展开为以下规则。', '',
              '| 电路类型 | 规则 |', '|---|---|']
    for name, ids in CIRCUIT_TYPES.items():
        lines.append('| %s | %s |' % (name, '、'.join(ids)))
    lines += ['', '## 覆盖维度', '', '| 维度（results.scope_checks 键） | 规则 |', '|---|---|']
    for name, rule in COVERAGE_RULES.items():
        lines.append('| %s | %s %s |' % (name, rule, title(rule)))
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
