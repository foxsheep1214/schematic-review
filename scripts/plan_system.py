#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""系统功能（功能树设计 §3.4、§3.8）：电源树、地、监控、上电时序、主控引脚有对象才生成的行与每个系统功能的框架。
ReviewPlanner 混入这里的方法。"""
import board_intent
import catalog
from checkers.netgraph import IC, NetGraph

SYSTEM_MATERIALS = {'PWR-T06': ('datasheets', 'platform_checklist'), 'SIG-D13': ('datasheets', 'platform_checklist'),
                    'RST-T03': ('requirements', 'datasheets')}


class SystemPlanning:
    """系统功能的行与框架。"""

    def plan_system(self):
        """系统功能的行（功能树设计第 5 步），有对象才生成：两个以上地网问 PWR-T06，两条以上电源轨问 RST-T03（全板一次），
        有可能是主控的 IC（核验为 mcu 或通用 ic，或没核验）问 SIG-D13。电源树和监控的行由逐轨展开和监控检查器生成。"""
        graph = NetGraph(board_intent.graph_db(self.db, self.kind_intent))
        grounds = sorted(self.domains['grounds'])
        rails = sorted(c['object']['net'] for c in self.checks if c['rule'] == 'PWR-T01' and (c.get('object') or {}).get('net'))
        if len(grounds) >= 2:
            self._ready_check('PWR-T06', {'system': 'SYS-GROUND', 'nets': grounds},
                              self._materials_gap(SYSTEM_MATERIALS['PWR-T06']), [f'grounds:{len(grounds)}'])
        if len(rails) >= 2:
            self._ready_check('RST-T03', {'system': 'SYS-SEQUENCE', 'rails': rails},
                              self._materials_gap(SYSTEM_MATERIALS['RST-T03']), [f'rails:{len(rails)}'])
        controllers = sorted(ref for ref in graph.parts if graph.is_fitted(ref) and graph.kind(ref) == IC
                             and graph.role_kind(ref) in (None, 'mcu', 'ic'))
        if controllers:
            self._ready_check('SIG-D13', {'system': 'SYS-PINMAP', 'refs': controllers},
                              self._materials_gap(SYSTEM_MATERIALS['SIG-D13']), [f'controller-candidates:{len(controllers)}'])

    def plan_system_frames(self):
        """每个有行的系统功能一个框架；成员是归它的行（按电路或接口展开的不算）。行没有点名网络或器件的
        （如逐电源域监控覆盖），框架的对象取全板电源轨。"""
        rails = sorted(c['object']['net'] for c in self.checks if c['rule'] == 'PWR-T01' and (c.get('object') or {}).get('net'))
        for sid in catalog.SYSTEM_FUNCTIONS:
            members = [c for c in self.checks if catalog.SYSTEM_OF_RULE.get(c['rule']) == sid
                       and not (c.get('object') or {}).get('circuit') and not (c.get('object') or {}).get('interface')]
            if not members:
                continue
            nets, refs = set(), set()
            for row in members:
                obj = row.get('object') or {}
                nets.update(n for key in ('nets', 'rails') for n in obj.get(key) or [])
                nets.update([obj['net']] if obj.get('net') else [])
                refs.update(obj.get('refs') or [])
            if not nets and not refs:
                nets.update(rails)
            frame = {'id': 'FN-' + sid, 'system': sid,
                     'question': catalog.system_frame_question(sid, sorted(nets), sorted(refs)),
                     'objects': {'refs': sorted(refs), 'nets': sorted(nets)}, 'states': ['run'], 'members': [],
                     'blind_spots': {}, 'checklist': list(catalog.BOUNDING_STEPS)}
            for row in sorted(members, key=lambda c: c['id']):
                row['function_id'] = frame['id']
                row['aspect'] = catalog.title(row['rule'])
                frame['members'].append({'check_id': row['id'], 'rule': row['rule'], 'aspect': row['aspect'], 'state': None})
                frame['blind_spots'][row['rule']] = catalog.explanation(row['rule'])['risk_if_omitted']
            self.functions.append(frame)
