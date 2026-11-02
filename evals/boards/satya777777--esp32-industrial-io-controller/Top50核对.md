# Top 50 逐条对照

状态为本条局部范围：`local_pass`不代表整板通过；`coverage_miss`比较补查前369项计划，`needs_human`不得作为物理缺陷。

|序号|准则|状态|实际证据|
|---:|---|---|---|
|01|G01-018|not_applicable|本板无−48V电源输入，不把+24V标签替代−48V接口。| 
|02|G01-019|not_applicable|本板无−48V电源输入，不把+24V标签替代−48V接口。| 
|03|G01-020|not_applicable|本板无−48V电源输入，不把+24V标签替代−48V接口。| 
|04|G01-021|not_applicable|本板无−48V电源输入，不把+24V标签替代−48V接口。| 
|05|G01-022|not_applicable|本板无−48V电源输入，不把+24V标签替代−48V接口。| 
|06|G01-023|not_applicable|本板无−48V电源输入，不把+24V标签替代−48V接口。| 
|07|G01-024|not_applicable|本板无交流整流输入和一周期保持合同。| 
|08|G01-025|not_applicable|本板无交流输入；24V恢复问题独立保留。| 
|09|G01-026|needs_human|USB J2→R6/D2支路高阻已确认；线缆最低输入/SYS_5V/TLV压差窗口仍未闭。| 
|10|G01-027|needs_human|R7/R8仅Rd下拉，未检测公告电流；USB默认/枚举/ESP32负载表未给，不假定3A。| 
|11|G01-029|needs_human|USB原始VBUS无直接体电容；R6之后D2接C1=10u、C8=.1u及LDO输出36.9uF，须按实际受电模式/充电路径/公差核；不能跨R6直接加成220uF。| 
|12|G01-030|needs_human|U2.8在R6/R9分压，且被U2.7/D2加载；断开门限/40ms处理和模式尚未闭。| 
|13|G01-031|not_applicable|J2由两个Rd下拉声明Sink，无Source VBUS开关/Source角色；不套未连接Source带电要求。| 
|14|G03-003|needs_human|TLV输出36.9uF标称、手册p5有效≥0.5uF；LM输出220uF。缺用途相关Ceff而非机械判无电容。| 
|15|G03-004|needs_human|TLV p5 ESR2–500mohm；LM p25等ESR条件，源树无准确电容规格。| 
|16|G03-016|needs_human|Q3入口充Cin680uF；源阻抗、启动轨迹/温度与真实错脚修复后的SOA未闭。| 
|17|G03-018|needs_human|Buck ON/OFF接GND、TLV EN接IN；均有内部UVLO需按真实输入最低值核，不编外部分压。| 
|18|G03-019|needs_human|无源/线阻与最大负载表，不能只用24V名义点证明不打嗝。| 
|19|G03-021|needs_human|TLV internal soft-start typical500us，真实启动负载与限流下界未闭；LM未见外部SS配置。| 
|20|G03-025|needs_human|U1 EN RC及内建欠压复位；准确变体/配置、掉电斜率与复位阈值未闭。| 
|21|G03-028|needs_human|TLV EN=SYS_5V，U1 EN=R1/C3；须按各轨/阈值时刻核，10ms RC不是极值时序。| 
|22|G03-032|needs_human|D2/D3只在LDO输入OR；U2.VDD同+3V3且VREGIN在检测网；TLV p19–20反向条件与完整状态未闭。| 
|23|G03-037|local_pass|Cin1/Cout1原生C_Polarized物理1接正轨、2接GND；C1为非极性符号/电解封装，实际采购仍须明确，未声称所有选项反压已排除。| 
|24|G03-038|needs_human|Cin/Cout只有680uF/220uF，没有耐压/纹波/寿命字段；输入范围也只标称24V，不能判超压或降额已满足。| 
|25|G03-040|not_applicable|未发现串联电解链；Cin1/Cout1分别跨独立电源轨。| 
|26|G04-005|needs_human|RO经10k/20k衰减；ADC两路 nominal2.5/3V，未证明故障/断电注入在U1容忍范围。| 
|27|G04-007|needs_human|J5/J6可在板失电时仍有信号，RS485外部带电、USB独立供入均需分别核。| 
|28|G04-009|needs_human|D7直并IO35、信号可抬未供电轨；未给芯片注入与泄放预算，R串阻存在不自动安全。| 
|29|G04-010|related_true_defect|Q4真实G/S/D与符号错配，R12下拉落在真实S而非G；PINMAP已确认。RS485_DIR没有外部下拉，是否安全还要实际复位状态合同，未再添真缺陷。| 
|30|G04-017|not_applicable|本图无I2C SDA/SCL链及上拉。| 
|31|G04-018|not_applicable|本图无I2C SDA/SCL链及上拉。| 
|32|G04-032|not_applicable|本图为RS485 MAX485E，无CAN收发器；R15=120ohm不能冒充整条CAN端接。| 
|33|G04-040|coverage_miss|K1线圈/触点不同网络，未见直流桥接，但原生PRO-D02对象缺失；M04补查，隔离类别/负载仍待定。| 
|34|G04-041|not_applicable|无外置运放；直接片内ADC前端已按35核，不套双运放共模。| 
|35|G04-054|coverage_miss|IO34/IO35 ADC未触发ANALOG，M01；2.5V/3V超2.45V校准有效区不等于已证明绝对满量程/绝限越界。| 
|36|G04-078|not_applicable|无板级无源晶体/负载电容；U1模组/U2片内时钟不拆假晶体。| 
|37|G04-079|not_applicable|无可更换板级晶体/振荡器，模组内部起振为器件能力边界。| 
|38|G04-082|not_applicable|无一颗晶体并接两个振荡器拓扑。| 
|39|G05-019|coverage_miss|原PRO-C04只有J5/J6信号TVS，漏J1/Q3/F1分支与USB供入边界；M02，源保护是否缺失未定。| 
|40|G05-022|needs_human|F1=500mA额定，不是动作上限；串行通路/连接器/导线故障耐受未定。| 
|41|G05-025|needs_human|F1厂家/时流/I2t和源短路电流未知，不能由500mA单值证明切断及时。| 
|42|G05-030|needs_human|D6 VRWM10V对应0–10V输入、D7 VRWM5V对应0.6–3V；含实际公差、单向极性/采购分支仍需锁定。| 
|43|G05-031|needs_human|ST SMAJ5V VBR6.4..6.74V、VC9.2V指定波形明显高于3.3V ADC工作域；缺实际厂商、故障源/波形、GPIO注入限制，不把指定脉冲当本板已发生。| 
|44|G05-032|needs_human|400W是特定10/1000us与温度条件；本板ESD/浪涌合同和实际厂商不定。| 
|45|G05-040|needs_human|Q3/F1在入口，短路启动的源阻抗、F1动作/通路温度未定义；先修PINMAP再核SOA。| 
|46|G05-041|needs_human|与冷启动分开：开始壳温、重试次数与故障时间未给，不能沿用25°C SOA。| 
|47|G05-048|needs_human|F1只有500mA，无直流分断能力和安装点预期短路电流；不能用额定电流代替分断。| 
|48|G05-054|needs_human|Q3错脚并且按符号S在输入/D在下游不能证反接；PRO-D04.J1有一般入口问题，实际反接条件/完整修订仍需核。| 
|49|G05-057|not_applicable|D4跨栅源而非入口对GND TVS；D6/D7分别是模拟口，未发现J1反接阻断前单向TVS跨源。| 
|50|G05-087|coverage_miss|入口Q3没有原生PWR-T05，M03；真实物理映射错已归PINMAP，不双计真缺陷。| 
