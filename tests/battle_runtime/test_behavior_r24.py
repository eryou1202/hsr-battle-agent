"""R24 explicit reference defense; real damage interoperability is a separate cohort."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/runtime')]
from hsr_battle_agent.battle_ir.behavior import IRNode
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime, ExecutionStatus, GapError
from hsr_battle_agent.battle_runtime.defense_break import (
    POLICY_ID, reference_policy, supplied, unknown, bind)
from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID as DAMAGE
from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID as MODIFIER, reference_policy as modifier_policy
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.battle_turn import KEY
from tests.battle_runtime import test_behavior_r15 as r15
from tests.battle_runtime.test_behavior_r15 import task, ability, finish, write, wait
from r18_reference_fixtures import make_runtime, reference_listener
from r22_reference_fixtures import runtime as turn_runtime, submit


def shield(identity='s', capacity=10, priority=0, **extra):
    return {'instance_id': identity, 'owner': 'b', 'caster': 'a', 'source': 'explicit scenario shield',
            'capacity': supplied(capacity*SCALE), 'priority': priority, 'elements': None,
            'expiry': 'MANUAL_REFERENCE', **extra}


def initial(shields=(), current=10, maximum=10, **extra):
    return {'current': supplied(current*SCALE), 'maximum': supplied(maximum*SCALE),
            'weaknesses': supplied(['fire']), 'eligible': supplied(True),
            'break_state': supplied({'active': False, 'generation': 0}),
            'shields': supplied(list(shields)), **extra}


def toughness(amount=4, element='fire', **extra):
    return {'base_reduction': supplied(amount*SCALE), 'element': element, 'modifiers': [],
            'ignore_weakness': False, 'source': 'explicit scenario toughness amount',
            'authority': 'EXPLICIT_SCENARIO_INPUT', **extra}


def settlement():
    return {'storage': 'MODE0_RAW_REFERENCE', 'clamp': 'ZERO_MAX_HP_REFERENCE',
            'hp_property': 'hp', 'max_hp_property': 'max_hp', 'life_state': 'PRESERVE_EXPLICIT_REFERENCE',
            'death_callbacks': 'NO_PROCESSING_EXPLICIT_SANDBOX', 'battle_end': 'NO_PROCESSING_EXPLICIT_SANDBOX'}


def request(name='hit', amount=0, **extra):
    return task(name, 'reference_defense_request', **{
        'authority': 'EXPLICIT_SCENARIO_INPUT', 'actor': 'a', 'target': 'b',
        'source': 'explicit reference request', 'amount_raw': amount*SCALE,
        'shield': 'APPLY_REFERENCE', 'toughness': None, 'hp_settlement': settlement(), **extra})


def setup(nodes, defense=None, policy=None):
    r = r15.R15Tests().runtime(ability('r24-reference', *nodes, finish()))
    r.policies[POLICY_ID] = policy or reference_policy()
    r.policies[MODIFIER] = modifier_policy()
    for eid in ('a', 'b'):
        r.state.properties[eid].update(hp=100*SCALE, max_hp=100*SCALE)
    bind(r, 'b', defense if defense is not None else initial(), nodes[0])
    return r


def actor(r, eid='b'):
    return r.state.mechanics[POLICY_ID]['actors'][eid]


def records(r):
    return list(r.state.mechanics[POLICY_ID]['requests'].values())


def execute(r, name='root'):
    r.start_action(name)
    return r.run_until_action_complete()


def effect(*nodes):
    return {'identity': 'explicit-break-effect', 'authority': 'EXPLICIT_SCENARIO_INPUT',
            'tasks': [n.to_dict() for n in nodes]}


class R24Scenarios(unittest.TestCase):
    def complete(self, r, name='root'):
        result = execute(r, name)
        self.assertEqual(result.status, ExecutionStatus.ACTION_REFERENCE_COMPLETE, str(result.gap))
        self.assertEqual(r.state.damage_transactions, [])
        self.assertEqual(r.state.rng.draws, 0)
        return result

    def capture(self, r, cohort='PURE_REFERENCE_MECHANIC'):
        self.observation = {'cohort': cohort, 'state_hash': r.stable_hash(),
            'hp': {k: v.get('hp') for k, v in r.state.properties.items()},
            'defense': copy.deepcopy(r.state.mechanics[POLICY_ID]), 'rng_draws': r.state.rng.draws}

    def test_scenario_01_full_absorption(self):
        r = setup([request(amount=4)], initial([shield()]))
        self.complete(r)
        self.assertEqual(r.state.properties['b']['hp'], 100*SCALE)
        self.assertEqual(actor(r)['shields']['value'][0]['capacity']['value'], 6*SCALE)
        self.assertEqual(actor(r)['shields']['value'][0]['capacity']['authority'], 'REFERENCE_MODEL')
        self.capture(r)

    def test_scenario_02_partial_absorption_hp_overflow(self):
        r = setup([request(amount=14)], initial([shield()]))
        self.complete(r)
        self.assertEqual(r.state.properties['b']['hp'], 96*SCALE)
        self.assertEqual(records(r)[0]['absorbed_raw'], 10*SCALE)
        self.capture(r)

    def test_scenario_03_multiple_shields_stable_order(self):
        r = setup([request(amount=8)], initial([shield('last', 6, 9), shield('first', 3, -1), shield('tie', 4, -1)]))
        self.complete(r)
        self.assertEqual([s['instance_id'] for s in records(r)[0]['shield_changes']], ['first', 'tie', 'last'])
        self.assertEqual(actor(r)['shields']['value'][0]['capacity']['value'], 5*SCALE)
        self.capture(r)

    def test_scenario_04_depletion_listener_cleanup(self):
        p = reference_policy(); p['events']['SHIELD_DEPLETED'] = ['r24.depleted']
        r = setup([request(amount=10)], initial([shield(modifier_instance_id=None)]), p)
        # A caller-provided R17 modifier, not a catalog definition, owns the shield.
        r.policies[DAMAGE] = {'tasks': {}}
        reference_listener(r, write('depleted-callback', 3), event_id='r24.depleted', identity='shield-listener')
        actor(r)['shields']['value'][0]['modifier_instance_id'] = 'shield-listener'
        self.complete(r)
        self.assertEqual(r.state.properties['a']['x'], 6)
        self.assertNotIn('shield-listener', r.state.modifiers)
        self.assertEqual(actor(r)['shields']['value'], [])
        self.assertTrue(r.state.modifier_history)
        self.capture(r)

    def test_scenario_05_known_empty_shields(self):
        r = setup([request(amount=7)])
        self.complete(r)
        self.assertEqual(r.state.properties['b']['hp'], 93*SCALE)
        self.capture(r)

    def test_scenario_06_unknown_shields_gap(self):
        data = initial(); data['shields'] = unknown()
        r = setup([request(amount=7)], data)
        result = execute(r)
        self.assertEqual(result.status, ExecutionStatus.SEMANTIC_GAP)
        self.assertIn('SHIELD_STATE_UNKNOWN', result.gap.required_capability)
        self.assertEqual(r.state.properties['b']['hp'], 100*SCALE)
        self.assertEqual(records(r), [])
        self.capture(r)

    def test_scenario_07_positive_toughness_reduction(self):
        r = setup([request(toughness=toughness())])
        self.complete(r)
        self.assertEqual(actor(r)['current']['value'], 6*SCALE)
        self.assertEqual(actor(r)['current']['authority'], 'REFERENCE_MODEL')
        self.assertFalse(actor(r)['break_state']['value']['active'])
        self.capture(r)

    def test_scenario_08_weakness_mismatch(self):
        r = setup([request(toughness=toughness(element='ice'))])
        self.complete(r)
        self.assertEqual(actor(r)['current']['value'], 10*SCALE)
        self.assertFalse(records(r)[0]['toughness_evaluation']['weakness_match'])
        self.capture(r)

    def test_scenario_09_exact_zero_break_once(self):
        r = setup([request(toughness=toughness(10))])
        self.complete(r)
        b = actor(r)['break_state']['value']
        self.assertEqual(actor(r)['current']['value'], 0)
        self.assertTrue(b['active']); self.assertEqual(b['generation'], 1)
        self.assertEqual(actor(r)['break_state']['authority'], 'REFERENCE_MODEL')
        self.assertEqual(b['effect_status'], 'BREAK_EFFECT_NOT_BOUND')
        self.assertEqual(b['recovery_status'], 'BREAK_RECOVERY_POLICY_MISSING')
        self.assertTrue(r.state.entities['b']['alive'])
        self.capture(r)

    def test_scenario_10_repeated_hits_no_double_break(self):
        r = setup([request('first', toughness=toughness(11)), request('later', toughness=toughness(6))])
        self.complete(r)
        self.assertEqual(actor(r)['break_state']['value']['generation'], 1)
        self.assertEqual([d['toughness_evaluation']['BREAK_TRIGGERED_REFERENCE'] for d in records(r)], [True, False])
        self.capture(r)

    def test_scenario_11_explicit_recovery(self):
        recovery = {'boundary': 'EXPLICIT_CALLBACK', 'remaining': 1, 'restore_raw': 8*SCALE,
                    'authority': 'EXPLICIT_SCENARIO_INPUT'}
        recover = task('recover', 'reference_break_recovery', actor='a', target='b', source='scenario callback')
        r = setup([request(toughness=toughness(10)), recover], initial(recovery=recovery))
        self.complete(r)
        self.assertEqual(actor(r)['current']['value'], 8*SCALE)
        self.assertFalse(actor(r)['break_state']['value']['active'])
        self.capture(r)

    def test_scenario_12_multi_hit_shield_break(self):
        r = setup([request('first', 7, toughness=toughness(10)), request('second', 7, toughness=toughness(10))],
                  initial([shield()]))
        self.complete(r)
        self.assertEqual([d['absorbed_raw'] for d in records(r)], [7*SCALE, 3*SCALE])
        self.assertEqual(r.state.properties['b']['hp'], 96*SCALE)
        self.assertEqual(actor(r)['break_state']['value']['generation'], 1)
        self.capture(r)

    def test_scenario_13_multi_target_independence(self):
        r = setup([request('b', 12, toughness=toughness(10)), request('c', 12, target='c', toughness=toughness(10))],
                  initial([shield()]))
        r.state.entities['c'] = {'alive': True}; r.state.properties['c'] = {'hp': 100*SCALE, 'max_hp': 100*SCALE}
        bind(r, 'c', initial(current=20, maximum=20), request())
        self.complete(r)
        self.assertEqual([d['target'] for d in records(r)], ['b', 'c'])
        self.assertEqual(actor(r, 'c')['current']['value'], 10*SCALE)
        self.assertEqual(r.state.properties['b']['hp'], 98*SCALE)
        self.assertEqual(r.state.properties['c']['hp'], 88*SCALE)
        self.capture(r)

    def replay(self, r):
        copies = [r, r.clone(), BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))]
        results = [x.run_until_action_complete() for x in copies]
        self.assertEqual(results[0].status, ExecutionStatus.ACTION_REFERENCE_COMPLETE, str(results[0].gap))
        self.assertEqual(results[0], results[1]); self.assertEqual(results[0], results[2])
        self.assertEqual(len({x.stable_hash() for x in copies}), 1)

    def checkpoint(self, r, condition):
        r.start_action('root')
        for _ in range(300):
            if condition(r): return
            result = r.run_ready(1)
            self.assertNotEqual(result.status, ExecutionStatus.SEMANTIC_GAP, str(result.gap))
        self.fail('checkpoint not reached')

    def test_scenario_14_absorption_clone_snapshot_replay(self):
        r = setup([request(amount=6)], initial([shield()]))
        self.checkpoint(r, lambda x: bool(records(x)) and bool(records(x)[0].get('shield_changes')))
        self.assertTrue(r.state.damage_transactions)
        self.replay(r)
        self.assertEqual(r.state.properties['b']['hp'], 100*SCALE)
        self.capture(r)

    def test_scenario_15_break_callback_clone_snapshot_replay(self):
        p = reference_policy(); p['events']['BREAK_TRIGGERED'] = ['r24.break']
        r = setup([request(toughness=toughness(10))], policy=p)
        r.policies[DAMAGE] = {'tasks': {}}
        reference_listener(r, write('break-callback', 7), event_id='r24.break', identity='break-listener')
        self.checkpoint(r, lambda x: bool(x.state.scheduler.action_execution.get('callbacks')))
        self.replay(r)
        self.assertEqual(r.state.properties['a']['x'], 14)
        callbacks = r.state.scheduler.action_execution['callbacks'].values()
        self.assertTrue(all(c['status'] == 'CALLBACK_COMPLETE' for c in callbacks))
        self.capture(r)

    def test_scenario_16_atomic_gap_rollback(self):
        bad = toughness(10); bad['base_reduction'] = unknown()
        r = setup([request('committed', 2), request('atomic', 14, toughness=bad)], initial([shield()]))
        result = execute(r)
        self.assertEqual(result.status, ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(actor(r)['shields']['value'][0]['capacity']['value'], 8*SCALE)
        self.assertEqual(actor(r)['current']['value'], 10*SCALE)
        self.assertEqual(r.state.properties['b']['hp'], 100*SCALE)
        self.assertEqual(len(records(r)), 1); self.assertEqual(r.state.damage_transactions, [])
        before = r.state.snapshot(); result2 = r.run_until_action_complete()
        self.assertEqual(result.gap, result2.gap); self.assertEqual(result.status, result2.status)
        self.assertEqual(before, r.state.snapshot())
        self.capture(r)

    def real(self, targets=('b',), nodes=None):
        rows = json.loads((ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001/real_damage_fixtures.json').read_text())
        nodes = nodes or [IRNode.from_dict(rows[0]['node'])]
        r = make_runtime(nodes, targets=targets)
        p = reference_policy()
        for node in nodes:
            s = r.policies[DAMAGE]['tasks'][node.stable_hash()]
            s['defense_reference'] = 'R24_EXPLICIT_SCENARIO_HOOK'
            for k in ('shield', 'toughness', 'break'): s['boundaries'][k] = 'R24_EXPLICIT_REFERENCE'
            p['damage_hooks'][node.stable_hash()] = {'authority': 'EXPLICIT_SCENARIO_INPUT',
                'shield': 'APPLY_REFERENCE', 'element': 'fire', 'toughness': toughness(10)}
        r.policies[POLICY_ID] = p
        for eid in set(targets): bind(r, eid, initial([shield(owner=eid)]), nodes[0])
        return r, nodes

    def test_scenario_17_real_decoded_damage_reference_defense(self):
        r, nodes = self.real()
        original = nodes[0].stable_hash()
        self.complete(r, 'probe')
        d = r.state.damage_history[0]
        self.assertEqual(d['evaluated_amount_raw'], 20*SCALE)
        self.assertEqual(d['hp_after_raw'], 90*SCALE)
        self.assertEqual(d['defense_authority'], 'SEPARATE_EXPLICIT_REFERENCE_INPUT_NOT_DECODED')
        self.assertEqual(nodes[0].stable_hash(), original)
        self.assertEqual(IRNode.from_dict(d['request']).payload['source_task'], nodes[0])
        self.assertEqual(r.state.scheduler.action_execution['metrics']['hp_mutations'], 1)
        self.assertTrue(actor(r)['break_state']['value']['active'])
        self.capture(r, 'REAL_DAMAGE_PLUS_REFERENCE_DEFENSE')

    def test_scenario_18_r22_turn_persistence_and_order(self):
        root = ability('defense-turn', request('turn-hit', 7, toughness=toughness(6), effect=effect(wait(), write('effect', 2))), finish())
        r, *_ = turn_runtime(root=root)
        r.policies[POLICY_ID] = reference_policy()
        bind(r, 'b', initial([shield(capacity=20)]), request())
        submit(r)
        out = r.run_until_next_turn()
        self.assertEqual(out.kind, 'PLAYER_NORMAL_TURN')
        self.assertEqual(actor(r)['current']['value'], 4*SCALE)
        self.assertEqual(actor(r)['shields']['value'][0]['capacity']['value'], 13*SCALE)
        submit(r, out)
        # The second action breaks b; logical callback wait retains normal turn owner.
        result = r.run_until_decision(budget=30)
        self.assertIn(result.kind, ('BUDGET_YIELD', 'PLAYER_NORMAL_TURN'), str(result))
        restored = BehaviorRuntime.from_snapshot(r.snapshot())
        out = r.run_until_next_turn(); other = restored.run_until_next_turn()
        self.assertEqual(out, other); self.assertEqual(r.stable_hash(), restored.stable_hash())
        self.assertGreaterEqual(r.state.mechanics[KEY]['normal_turn_count'], 2)
        self.assertEqual(actor(r)['break_state']['value']['generation'], 1)
        self.assertEqual(actor(r)['shields']['value'][0]['capacity']['value'], 6*SCALE)
        self.assertEqual(r.state.properties['a']['x'], 4)
        self.capture(r, 'PURE_REFERENCE_MECHANIC_R22')


class R24EdgeCases(unittest.TestCase):
    complete = R24Scenarios.complete
    real = R24Scenarios.real
    def test_refresh_replace_remove(self):
        def change(name, mode, instance=None):
            return task(name, 'reference_shield_lifecycle', actor='a', target='b', source='scenario lifecycle',
                        mode=mode, instance_id='s', instance=instance)
        r = setup([change('insert', 'INSERT_REFERENCE', shield()), request('first', 3),
            change('refresh', 'REFRESH_REFERENCE', shield(capacity=20)), request('second', 4),
            change('replace', 'REPLACE_REFERENCE', shield(capacity=5)), request('third', 2),
            change('remove', 'REMOVE_REFERENCE')])
        self.complete(r)
        self.assertEqual(actor(r)['shields']['value'], [])
        self.assertEqual(r.state.properties['b']['hp'], 100*SCALE)

    def test_element_override_temporary_weakness_modifiers(self):
        cases = [toughness(element='ice', match_override=supplied(True)),
                 toughness(element='ice', ignore_weakness=True), toughness(element='ice')]
        for req in cases:
            r = setup([request(toughness=req)], initial(temporary_weaknesses=[
                {'element': 'ice', 'operation': 'ADD_REFERENCE', 'evidence': 'scenario implant'}]))
            self.complete(r); self.assertEqual(actor(r)['current']['value'], 6*SCALE)
        req = toughness(); req['modifiers'] = [supplied(2*SCALE)]
        r = setup([request(toughness=req)]); self.complete(r)
        self.assertEqual(actor(r)['current']['value'], 2*SCALE)

    def test_unknown_values_negative_overcap_rejected_atomically(self):
        for field in ('current', 'maximum', 'weaknesses', 'eligible', 'break_state'):
            data = initial(); data[field] = unknown()
            r = setup([request(amount=12, toughness=toughness())], data)
            self.assertEqual(execute(r).status, ExecutionStatus.SEMANTIC_GAP)
            self.assertEqual(r.state.properties['b']['hp'], 100*SCALE)
        for req in (request(amount=-1), request(toughness=toughness(-1))):
            r = setup([req]); self.assertEqual(execute(r).status, ExecutionStatus.SEMANTIC_GAP)
        with self.assertRaisesRegex(GapError, 'current exceeds maximum'):
            setup([request()], initial(current=11))

    def test_missing_recovery_is_typed_gap(self):
        recover = task('recover', 'reference_break_recovery', actor='a', target='b', source='explicit recovery request')
        r = setup([request(toughness=toughness(10)), recover])
        result = execute(r)
        self.assertIn('BREAK_RECOVERY_POLICY_MISSING', result.gap.required_capability)
        self.assertEqual(actor(r)['break_state']['value']['generation'], 1)

    def test_r22_boundary_expiry_recovery(self):
        root = ability('turn', request(toughness=toughness(10)), finish())
        r, *_ = turn_runtime(root=root)
        r.policies[POLICY_ID] = reference_policy()
        expiry = {'boundary': 'TURN_END', 'remaining': 1, 'authority': 'EXPLICIT_SCENARIO_INPUT'}
        recovery = {'boundary': 'TURN_START', 'remaining': 1, 'restore_raw': 10*SCALE,
                    'authority': 'EXPLICIT_SCENARIO_INPUT'}
        bind(r, 'b', initial([shield(expiry=expiry)], recovery=recovery), request())
        submit(r); boundary = r.run_until_next_turn()
        self.assertEqual(actor(r)['shields']['value'], [])
        self.assertTrue(actor(r)['break_state']['value']['active'])
        submit(r, boundary); boundary = r.run_until_next_turn()
        self.assertEqual(boundary['actor_id'], 'b')
        self.assertEqual(actor(r)['current']['value'], 10*SCALE)
        self.assertFalse(actor(r)['break_state']['value']['active'])

    def test_real_multi_target_atomic_rollback_and_rounding(self):
        r, _ = self.real(targets=('c', 'b'))
        actor(r)['current'] = unknown()
        result = execute(r, 'probe')
        self.assertEqual(result.status, ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(r.state.damage_requests, {})
        self.assertEqual(actor(r, 'c')['current']['value'], 10*SCALE)
        self.assertEqual(r.state.properties['c']['hp'], 100*SCALE)
        self.assertEqual(actor(r, 'c')['shields']['value'][0]['capacity']['value'], 10*SCALE)
        self.assertEqual(r.state.damage_transactions, [])

    def test_policies_hash_and_unknown_shield_capacity(self):
        r = setup([request()]); original = r.stable_hash()
        actor(r)['shields'] = unknown('MISSING')
        self.assertNotEqual(r.stable_hash(), original)
        data = initial([shield(capacity=1)]); data['shields']['value'][0]['capacity'] = unknown()
        r = setup([request(amount=2)], data)
        self.assertIn('SHIELD_CAPACITY_UNKNOWN', execute(r).gap.required_capability)

    def test_explicit_shield_precedence_overflow_and_zero_policy(self):
        p = reference_policy(); p['precedence'] = 'FIRST_APPLICABLE_REFERENCE'
        r = setup([request(amount=12)], initial([shield('one', 3), shield('two', 8)]), p)
        self.complete(r); self.assertEqual(r.state.properties['b']['hp'], 91*SCALE)
        p = reference_policy(); p['overflow'] = 'DISCARD_REFERENCE'; p['zero_capacity'] = 'RETAIN_INACTIVE_REFERENCE'
        r = setup([request(amount=12)], initial([shield()]), p)
        self.complete(r); self.assertEqual(r.state.properties['b']['hp'], 100*SCALE)
        self.assertEqual(actor(r)['shields']['value'][0]['capacity']['value'], 0)

    def test_effect_failure_rolls_back_break_shield_and_hp(self):
        r = setup([request(amount=14, toughness=toughness(10), effect=effect(task('unknown-effect', 'not-supported')))],
                  initial([shield()]))
        result = execute(r)
        self.assertEqual(result.status, ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(actor(r)['shields']['value'][0]['capacity']['value'], 10*SCALE)
        self.assertEqual(actor(r)['current']['value'], 10*SCALE)
        self.assertFalse(actor(r)['break_state']['value']['active'])
        self.assertEqual(r.state.properties['b']['hp'], 100*SCALE)
        self.assertEqual(records(r), [])

    def test_actor_binding_defense_atomic_and_identity(self):
        from r20_reference_fixtures import actor_binding
        from hsr_battle_agent.battle_runtime.actor_binding import supplied as actor_input
        r = r15.R15Tests().runtime(ability('root', finish()))
        r.policies[POLICY_ID] = reference_policy()
        binding = actor_binding('b', 1001)
        document = binding.to_dict()
        document['fields']['defense'] = actor_input(initial([shield()]))
        binding = type(binding).from_dict(document)
        r.bind_actor(binding)
        self.assertEqual(actor(r)['identity']['content_identity'], 1001)
        self.assertEqual(actor(r)['identity']['content_version'], '4.6.51')
        r = r15.R15Tests().runtime(ability('root', finish()))
        r.policies[POLICY_ID] = reference_policy()
        document['fields']['defense']['value']['current'] = supplied(11*SCALE)
        before = r.stable_hash()
        with self.assertRaises(GapError): r.bind_actor(type(binding).from_dict(document))
        self.assertEqual(before, r.stable_hash())

    def test_break_eligibility_and_unknown_element_boundaries(self):
        r = setup([request(toughness=toughness(10))], initial(eligible=supplied(False)))
        self.complete(r)
        self.assertEqual(actor(r)['current']['value'], 0)
        self.assertFalse(actor(r)['break_state']['value']['active'])
        req = toughness(); req.pop('element')
        r = setup([request(toughness=req)])
        self.assertIn('WEAKNESS_MAPPING_UNKNOWN', execute(r).gap.required_capability)
        data = initial(); data['weaknesses'] = unknown()
        r = setup([request(toughness=toughness(ignore_weakness=True))], data)
        self.complete(r); self.assertEqual(actor(r)['current']['value'], 6*SCALE)

    def test_known_zero_unknown_and_missing_remain_distinct(self):
        data = initial(current=0); data['current'] = {'status':'KNOWN_ZERO', 'value':0, 'authority':'REFERENCE_MODEL'}
        r = setup([request(toughness=toughness(10))], data)
        self.complete(r)
        self.assertEqual(actor(r)['break_state']['value']['generation'], 0)
        hashes = []
        for status in ('MISSING','UNKNOWN_NATIVE_VALUE'):
            data = initial(); data['current'] = unknown(status)
            r = setup([request(toughness=toughness())], data)
            hashes.append(r.stable_hash())
            self.assertIn('TOUGHNESS_CURRENT_UNKNOWN', execute(r).gap.required_capability)
        self.assertNotEqual(*hashes)

    def test_post_hp_callback_failure_restores_complete_real_transaction(self):
        r, nodes = self.real()
        callback = task('unsupported-after-hp', 'unknown-callback')
        reference_listener(r, callback, event_id='after-hp', stage='AFTER_HP_MUTATION')
        out = execute(r, 'probe')
        self.assertEqual(out.status, ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(r.state.damage_requests, {})
        self.assertEqual(r.state.damage_history, [])
        self.assertEqual(records(r), [])
        self.assertEqual(actor(r)['current']['value'], 10*SCALE)
        self.assertEqual(actor(r)['shields']['value'][0]['capacity']['value'], 10*SCALE)
        self.assertEqual(r.state.properties['b']['hp'], 100*SCALE)
        self.assertEqual(r.state.damage_transactions, [])
        self.assertEqual(r.state.rng.draws, 0)

    def test_reference_events_owned_stable_order_and_single_callbacks(self):
        p = reference_policy()
        for stage in ('BEFORE_SHIELD_ABSORPTION','AFTER_SHIELD_ABSORPTION','SHIELD_DEPLETED',
                      'BEFORE_TOUGHNESS_CHANGE','AFTER_TOUGHNESS_CHANGE','BREAK_TRIGGERED'):
            p['events'][stage] = ['explicit.'+stage]
        r = setup([request(amount=11, toughness=toughness(10))], initial([shield()]), p)
        r.policies[DAMAGE] = {'tasks':{}}
        for ordinal, stage in enumerate(p['events']):
            if p['events'][stage]:
                reference_listener(r, write('callback-'+stage, ordinal), event_id='explicit.'+stage,
                                   identity='listener-'+stage)
        self.complete(r)
        d = r.state.scheduler.action_execution
        actual = [e['source_event']['payload']['defense_stage'] for e in d['events'].values()]
        self.assertEqual(actual, ['BEFORE_SHIELD_ABSORPTION','AFTER_SHIELD_ABSORPTION','SHIELD_DEPLETED',
                                 'BEFORE_TOUGHNESS_CHANGE','AFTER_TOUGHNESS_CHANGE','BREAK_TRIGGERED'])
        self.assertEqual(len(d['callbacks']), 6)
        root = d['current_root']
        self.assertTrue(all(e['action_root_id'] == root for e in d['events'].values()))
        self.assertTrue(all(e['action_root_id'] == root for e in d['callbacks'].values()))

    def test_recover_rebreak_increments_generation_once(self):
        recovery = {'boundary':'EXPLICIT_CALLBACK','remaining':2,'restore_raw':10*SCALE,
                    'authority':'EXPLICIT_SCENARIO_INPUT'}
        recover = task('recover','reference_break_recovery',actor='a',target='b',source='explicit recovery')
        r = setup([request('first',toughness=toughness(10)),recover,
                   request('second',toughness=toughness(10))], initial(recovery=recovery))
        self.complete(r)
        self.assertEqual(actor(r)['break_state']['value']['generation'], 2)

    def test_source_claims_do_not_admit_unbound_defense_operands(self):
        data = initial()
        data['current'] = {'status':'KNOWN_NONZERO','value':10*SCALE,'authority':'SOURCE_BACKED',
            'evidence':{'source_version':'4.6.51','body_sha256':'a'*64,'source_span':[1,2],
                        'operand_role':'candidate','uncertainty':'UNKNOWN'}}
        with self.assertRaisesRegex(GapError,'DEFENSE_SOURCE_OPERAND_NOT_BOUND'):
            setup([request()],data)


if __name__ == '__main__':
    unittest.main()
