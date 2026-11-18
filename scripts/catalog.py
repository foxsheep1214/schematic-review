"""器件角色与耗损类别：解析器按它识别 IC 的角色（part_words、device_kinds 读）。"""
from collections import OrderedDict, namedtuple


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
        'voltageregulator', 'linearregulator', 'lowdropout', 'ldoregulator', 'dcdcconverter', 'buckconverter', 'boostconverter',
        'switchingregulator', 'stepdownconverter', 'stepupconverter', 'powermanagementic', 'pmic', 'chargepump'),
        ('POWER_CONVERTER',))),
    ('supervisor', DeviceRole('电压监控与复位', ('supervisor', 'supervisory', 'voltagemonitor', 'resetcircuit', 'resetic', 'watchdog'),
                              ('ANALOG',), 'all')),   # every input is a monitored voltage (R8: TPS3700 INA+/INB−)
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
        'loadswitch', 'hotswap', 'efuse', 'idealdiode', 'powerdistributionswitch', 'currentlimitswitch', 'highsideswitch',
        'highsidesmartpower',
        'protectioncontroller', 'surgestopper'),   # p24 (Matrix R2 1.11): LTC4367 "... Protection Controller" drives a series FET
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

# 有寿命需求时派 DEV-C06 的耗损件类别：核什么、依据，以及按哪种次数核（None 按剖面时间核）。
# 电解、固态与超级电容由 DEV-C02 寿命检查项核（6a）。
WearoutClass = namedtuple('WearoutClass', 'title checks basis event')

WEAROUT_CLASSES = OrderedDict([
    ('BATTERY', WearoutClass('电池', '循环次数、容量保持、充电电压和温度', '手册循环寿命和日历寿命', None)),
    ('OPTO', WearoutClass('光耦', '按最小正向电流和保证 CTR 算出这条链寿命末所需的 CTR 保留比例，不高于 85% 即通过（降额规范 R10），写成选型或 bom_constraint；'
                                  '厂家给了 CTR 随时间的曲线才用曲线核对，SR 不自编衰减系数', '手册衰减曲线', None)),
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
