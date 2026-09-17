#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""去耦覆盖检查器（清单引擎仍在 scripts/decoupling.py）。"""
from copy import deepcopy

from decoupling import build_decoupling_inventory, validate_decoupling_intent

from .base import Checker
from .planutil import handoff, slug

# 器件条款的三类要求各对应一条规则；缺条款时用规则总表里的默认判据。
REQUIREMENT_RULES = (('connection', 'PWR-D02'), ('capacitance', 'PWR-C09'), ('rating', 'PWR-C10'))
PLAN_RULES = frozenset({'PWR-D01', 'PWR-T03'} | {rule for _, rule in REQUIREMENT_RULES})


class DecouplingChecker(Checker):
    id = 'decoupling'
    title = '去耦覆盖'
    plan_key = 'decoupling'
    version_key = 'decoupling_version'
    version = 1
    intent_key = 'decoupling'

    missing_inventory_message = 'decoupling checks require their inventory'
    inventory_type_message = 'decoupling inventory must be an object'
    requires_db_message = 'decoupling inventory validation requires --db'
    stale_message = 'decoupling inventory/binding is stale or modified'
    invalid_message = 'invalid decoupling inventory: '
    allow_manual_bound_objects = False
    generated_fields = ('rule', 'method', 'domain', 'object', 'criterion',
                        'readiness', 'required_inputs', 'trigger', 'inventory_gaps',
                        'required_material_refs', 'handoff')

    def incomplete_message(self, key):
        return key + ': incomplete decoupling planned coverage'

    def changed_message(self, key):
        return key + ': decoupling generated criterion/object changed'

    def manual_addition_message(self, key):
        return key + ': use an independent object for manual decoupling additions'

    def validate_intent(self, intent, db):
        return validate_decoupling_intent(intent, db)

    def build(self, db, intent):
        return build_decoupling_inventory(db, intent)

    def plan(self, planner, inventory):
        """Direct-net inventory and separate, source-bound engineering criteria."""
        obj = {'feature': 'DECOUPLING-INVENTORY', 'decoupling_scope': 'inventory',
               'decoupling_inventory_digest': inventory['digest']}
        item = planner.add_check('PWR-D01', obj,
            readiness='WAITING_EVIDENCE' if inventory['discovery_gaps'] else 'READY',
            required_inputs=inventory['discovery_gaps'], trigger=['decoupling-inventory'])
        item['inventory_gaps'] = inventory['discovery_gaps']
        for state in inventory['states']:
            for group in state['groups']:
                obj = {'ref': group['ref'], 'nodes': group['supply_nodes'], 'return_nodes': group['return_nodes'],
                       'nets': group['supply_nets'], 'return_nets': group['return_nets'], 'state': state['id'],
                       'decoupling_group': group['id'], 'decoupling_inventory_digest': inventory['digest']}
                if len(group['supply_nets']) == 1:
                    obj['net'] = group['supply_nets'][0]
                item = planner.add_check('PWR-T03', deepcopy(obj), key=group['id'],
                    readiness='WAITING_EVIDENCE' if group['gaps'] else 'READY',
                    required_inputs=group['gaps'], trigger=['decoupling-group:' + group['id']])
                item['inventory_gaps'] = group['gaps']
                for kind, rule in REQUIREMENT_RULES:
                    requirements = [r for r in group['requirements'] if r['kind'] == kind]
                    for req in requirements or [None]:
                        gaps = group['gaps'] + (group['capacitance_gaps'] if kind == 'capacitance' else [])
                        if req is None:
                            gaps = gaps + ['datasheet-requirement:' + kind]
                        key = group['id'] + ('-' + slug(req['id']) if req else '')
                        item = planner.add_check(rule, deepcopy(obj), key=key,
                            criterion=req['criterion'] if req else None,
                            readiness='WAITING_EVIDENCE',
                            required_inputs=gaps + ['state-specific engineering evidence: ' + kind],
                            trigger=['decoupling-group:' + group['id']] + ([req['citation']] if req else []),
                            handoff=handoff({'required': kind == 'connection', 'receivers': ['PCB Layout'],
                                'constraint': '按本组实际器件条款落实去耦位置、回流与环路；同网共享电容不证明各器件本地去耦充分',
                                'verification': '核对本组各供电脚、实际电容与返回路径的 PCB 摆放和回路'}, 'APPLICABLE'))
                        item['inventory_gaps'] = sorted(set(gaps))
                        item['analysis_required'] = True
                        item['required_material_refs'] = sorted(set([group['ref']] + group['fitted_capacitors']))

    def binds(self, item):
        obj = item.get('object')
        if item.get('rule') in PLAN_RULES:
            return True
        return isinstance(obj, dict) and ('decoupling_group' in obj or 'decoupling_scope' in obj)

    def extra_presence_trigger(self, plan):
        return self.version_key in plan

    def object_errors(self, key, obj, inventory):
        if 'decoupling_group' not in obj and 'decoupling_scope' not in obj:
            return []
        if obj.get('decoupling_inventory_digest') != inventory['digest']:
            return [key + ': stale decoupling object binding']
        return []

    def pass_blockers(self, key, planned, generated, inventory):
        if generated and generated.get('inventory_gaps'):
            return [key + ': decoupling gaps must be resolved in a regenerated plan before PASS']
        return []
