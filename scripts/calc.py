#!/usr/bin/env python3
"""条件性工程计算的命令行入口：参数以 JSON 关键字传入，结果以 JSON 输出。

用法：python3 scripts/calc.py fault_energy.packet_bound '{"inductance_h": 1e-3, ...}'
参数也可用 @文件 或 - （标准输入）。输入不合法时退出码 2，并输出错误原因；
缺输入不补 0。结果只是以调用者给定边界为条件的计算，不是审查结论。
"""
import argparse
import json
import sys

import boost_switch_loss
import fault_energy
import flyback_stop
import zener_fault

FUNCTIONS = {
    'boost_switch_loss.boost_cycle': boost_switch_loss.boost_cycle,
    'boost_switch_loss.conditional_losses': boost_switch_loss.conditional_losses,
    'fault_energy.packet_bound': fault_energy.packet_bound,
    'fault_energy.capacitor_energy_window': fault_energy.capacitor_energy_window,
    'flyback_stop.post_stop_capacitor_bound': flyback_stop.post_stop_capacitor_bound,
    'flyback_stop.primary_on_sr_platform': flyback_stop.primary_on_sr_platform,
    'zener_fault.trip_drive': zener_fault.trip_drive,
    'zener_fault.no_trip_budget': zener_fault.no_trip_budget,
    'zener_fault.hold_charge': zener_fault.hold_charge,
}


def run(name, kwargs):
    """调用登记的计算函数；返回 (退出码, 输出对象)。"""
    if name not in FUNCTIONS:
        return 2, {'error': 'unknown calculation: ' + name, 'available': sorted(FUNCTIONS)}
    if not isinstance(kwargs, dict):
        return 2, {'error': 'arguments must be a JSON object of keyword arguments'}
    try:
        return 0, {'calculation': name, 'inputs': kwargs, 'result': FUNCTIONS[name](**kwargs)}
    except (TypeError, ValueError, KeyError) as error:
        return 2, {'calculation': name, 'error': str(error)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('calculation', nargs='?', help='模块.函数，例如 zener_fault.trip_drive')
    parser.add_argument('arguments', nargs='?', default='{}', help='JSON 关键字参数、@文件或 -')
    parser.add_argument('--list', action='store_true', help='列出可用计算及说明')
    args = parser.parse_args(argv)
    if args.list or not args.calculation:
        for name, func in sorted(FUNCTIONS.items()):
            print(name + ': ' + ((func.__doc__ or '').strip().splitlines() or ['(无说明)'])[0])
        return 0
    raw = args.arguments
    try:
        if raw == '-':
            raw = sys.stdin.read()
        elif raw.startswith('@'):
            with open(raw[1:], encoding='utf-8') as handle:
                raw = handle.read()
        kwargs = json.loads(raw)
    except (OSError, ValueError) as error:
        code, out = 2, {'error': 'cannot read arguments: ' + str(error)}
    else:
        code, out = run(args.calculation, kwargs)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
