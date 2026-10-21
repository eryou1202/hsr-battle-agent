"""Executable R21 acceptance tests against the public persistent battle loop."""
from __future__ import annotations
import copy
import itertools
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools/runtime')]
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.battle_turn import (KEY, ADAPTER, PROVIDERS, CONTRACT,
    Rational, TurnBudget, TurnError, validate_runtime, validate_schema)
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_ir.behavior import stable_hash
from r22_reference_fixtures import runtime, inputs, submit, source_ref, insertion
from tests.battle_runtime.test_behavior_r15 import ability, finish, wait, task, write, call, expr


class R22Tests(unittest.TestCase):
    def state(self, r): return r.state.mechanics[KEY]
    def assert_atomic(self, r, operation):
        before = r.stable_hash()
        with self.assertRaises((TurnError, ValueError)):
            operation()
        self.assertEqual(before, r.stable_hash())

    def test_AT01_initialize_atomic_and_mode0(self):
        r, bindings, p, providers = runtime(initialize=False)
        for mutate in [lambda b: b[0].pop('provider_revision'),
                       lambda b: b[0]['participant'].update(actor_id='missing'),
                       lambda b: b[0].update(content_version='4.4.54'),
                       lambda b: b.append(copy.deepcopy(b[0])),
                       lambda b: b[0]['actor_binding']['fields']['base_properties']['value'].update(speed=0),
                       lambda b: b[0]['actor_binding']['fields']['base_properties']['value'].update(speed=100*SCALE+1)]:
            bad = copy.deepcopy(bindings); mutate(bad)
            self.assert_atomic(r, lambda: r.initialize_turns(bad, p, providers))
        r.initialize_turns(bindings, p, providers)
        self.assertEqual(self.state(r)['initiative']['a']['due_at'], {'n': 100, 'd': 1})
        self.assert_atomic(r, lambda: r.initialize_turns(bindings, p, providers))

    def test_AT02_multiple_successive_turns_public_api(self):
        r, *_ = runtime()
        actors, clocks = [], []
        for _ in range(4):
            b = r.run_until_decision()
            actors.append(b['actor_id']); clocks.append(copy.deepcopy(self.state(r)['clock']['now']))
            submit(r, b)
            b = r.run_until_next_turn()
            self.assertEqual(b.kind, 'PLAYER_NORMAL_TURN')
        self.assertEqual(actors, ['b', 'a', 'b', 'b'])
        self.assertEqual(clocks, [{'n': n, 'd': 1} for n in [50, 100, 100, 150]])
        self.assertEqual(self.state(r)['normal_turn_count'], 4)
        self.assertEqual(r.state.actor_resources['a']['reference_actor_counter'], 8*SCALE)
        self.assertEqual(len(r.state.mechanics[ADAPTER]['completion_receipts']), 4)

    def test_AT02_three_way_and_permutations(self):
        r, bindings, p, providers = runtime(speeds=(('a', 100), ('b', 125), ('c', 200)), initialize=False)
        hashes = []
        for perm in itertools.permutations(bindings):
            clone = r.clone(); clone.initialize_turns(list(perm), p, providers)
            self.assertEqual([x['actor_id'] for x in clone.next_actor_preview()], ['c', 'b', 'a'])
            order = []
            for _ in range(3):
                b = clone.run_until_decision(); order.append(b['actor_id']); submit(clone, b); clone.run_until_next_turn()
            self.assertEqual(order, ['c', 'b', 'a'])
            hashes.append(clone.stable_hash())
        self.assertEqual(len(set(hashes)), 1)

    def test_AT02_equal_readiness_stability(self):
        r, bindings, p, providers = runtime(speeds=(('a', 100), ('b', 100)), initialize=False)
        for perm in itertools.permutations(bindings):
            c = r.clone(); c.initialize_turns(list(perm), p, providers)
            self.assertEqual(c.run_until_decision()['actor_id'], 'a')
            submit(c); self.assertEqual(c.run_until_next_turn()['actor_id'], 'b')

    def test_AT03_waiting_speed_rebase_and_active_defer(self):
        r, *_ = runtime()
        b = r.run_until_decision()
        r.state.properties['a']['speed'] = 200*SCALE
        r.notify_speed_change('a', 1)
        self.assertEqual(self.state(r)['initiative']['a']['due_at'], {'n': 75, 'd': 1})
        self.assert_atomic(r, lambda: r.notify_speed_change('a', 1))
        r.state.properties['b']['speed'] = 100*SCALE
        r.notify_speed_change('b', 1)
        self.assertIsNone(self.state(r)['initiative']['b']['normal_entry_id'])
        submit(r, r.run_until_decision()); r.run_until_next_turn()
        self.assertEqual(self.state(r)['initiative']['b']['due_at'], {'n': 150, 'd': 1})

    def test_AT04_advance_delay_clamp_mapping_overflow(self):
        r, _, _, providers = runtime()
        ref = source_ref(providers)
        self.assertEqual(r.adjust_readiness('a', 'ADVANCE', {'n': 1, 'd': 2}, ref), {'n': 50, 'd': 1})
        self.assertEqual(r.adjust_readiness('a', 'DELAY', {'n': 1, 'd': 4}, ref), {'n': 75, 'd': 1})
        self.assertEqual(r.adjust_readiness('a', 'ADVANCE', {'n': 2, 'd': 1}, ref), {'n': 0, 'd': 1})
        for fraction, source in [({'n': -1, 'd': 1}, ref), ({'n': 2**257, 'd': 1}, ref), ({'n': 1, 'd': 1}, {})]:
            self.assert_atomic(r, lambda: r.adjust_readiness('a', 'ADVANCE', fraction, source))

    def test_AT05_gap_owner_av_frozen(self):
        r, *_ = runtime(root=ability('unfinished-gap', task('opaque', 'unsupported-turn-fixture'), finish()))
        b = r.run_until_decision(); submit(r, b)
        gap = r.run_until_decision()
        self.assertEqual(gap.kind, 'SEMANTIC_GAP')
        self.assertEqual(r.current_turn_owner(), 'b')
        self.assertEqual(self.state(r)['clock']['now'], {'n': 50, 'd': 1})
        self.assertEqual(self.state(r)['normal_turn_count'], 0)
        before = r.stable_hash(); self.assertEqual(r.run_until_decision().kind, 'SEMANTIC_GAP'); self.assertEqual(before, r.stable_hash())
        self.assert_atomic(r, lambda: r.start_action('root'))

    def test_AT06_original_finish_suffix_wait_and_child_drain(self):
        r, *_ = runtime(root=ability('finished-with-owned-work', finish(), wait(), write('suffix', 7)))
        submit(r)
        c = r.clone(); restored = BehaviorRuntime.from_snapshot(r.snapshot())
        for x in [r, c, restored]:
            b = x.run_until_next_turn()
            self.assertEqual(b['actor_id'], 'a')
            self.assertEqual(x.state.properties['a']['x'], 14)
            self.assertEqual(self.state(x)['clock']['now'], {'n': 100, 'd': 1})
            self.assertEqual(x.state.scheduler.action_execution['logical_time'], 14)
        self.assertEqual(r.stable_hash(), c.stable_hash()); self.assertEqual(r.stable_hash(), restored.stable_hash())

    def test_AT10_interrupt_rejected_atomic(self):
        r, *_ = runtime(root=ability('wait-action', task('interrupt-parent-input','barrier',key='parent-input'), finish()))
        submit(r)
        self.assertEqual(r.run_until_decision().kind,'SUSPENDED_ACTION_INPUT')
        execution=r.state.scheduler.action_execution
        self.assertNotEqual(execution['roots'][execution['current_root']]['status'],'ACTION_REFERENCE_COMPLETE')
        before = r.stable_hash()
        with self.assertRaisesRegex(TurnError, 'INTERRUPT_POLICY_MISSING'):
            r.request_insertion(insertion(r, category='ULTIMATE_INTERRUPT'))
        self.assertEqual(before, r.stable_hash())

    def test_AT12_previews_and_repeated_decision_are_pure(self):
        r, *_ = runtime()
        b = r.run_until_decision(); before = r.stable_hash()
        for _ in range(3):
            r.next_actor_preview(); r.current_turn_owner(); r.legal_action_candidates(b['decision_id']); r.is_terminal()
            self.assertEqual(r.run_until_decision(), b)
        self.assertEqual(before, r.stable_hash())

    def test_AT13_stale_altered_targets_consumed(self):
        r, *_ = runtime()
        b = r.run_until_decision(); p = r.legal_action_candidates(b['decision_id'])[0]
        self.assert_atomic(r, lambda: r.submit_action(p, ['unknown'], b['state_revision']))
        bad = copy.deepcopy(p); bad['action_ir_hash'] = '0'*64
        self.assert_atomic(r, lambda: r.submit_action(bad, p['target_ids'], b['state_revision']))
        r.submit_action(p, p['target_ids'], b['state_revision'])
        self.assert_atomic(r, lambda: r.submit_action(p, p['target_ids'], b['state_revision']))

    def test_AT16_exact_r21_schemas_policy_identity(self):
        r, _, p, _ = runtime()
        original = json.loads((ROOT/'data/control/generic_runtime_turn_contract_v1_20261011_001.json').read_text())
        self.assertEqual(CONTRACT['state_json_schema'], original['state_json_schema'])
        self.assertEqual(CONTRACT['policy_json_schema'], original['policy_json_schema'])
        validate_runtime(r, strict_queue=True)
        s = r.snapshot(); s['policies'][p['identity']]['numeric']['distance'] = {'n': 20000, 'd': 1}
        with self.assertRaisesRegex(TurnError, 'policy'):
            BehaviorRuntime.from_snapshot(s)

    def test_AT17_budget_yield_resumes(self):
        r, *_ = runtime()
        self.assertEqual(r.run_until_decision(0).kind, 'BUDGET_YIELD')
        self.assertFalse(r.is_terminal())
        self.assertEqual(r.run_until_decision().kind, 'PLAYER_NORMAL_TURN')
        submit(r)
        self.assertEqual(r.run_until_decision(TurnBudget(scheduler_work=1)).kind, 'BUDGET_YIELD')
        self.assertIsNotNone(r.current_turn_owner())
        self.assertEqual(r.run_until_next_turn().kind, 'PLAYER_NORMAL_TURN')

    def test_numeric_exactness_intermediates(self):
        self.assertEqual(Rational(0, -9).to_dict(), {'n': 0, 'd': 1})
        self.assertEqual(Rational(10000).div(123).to_dict(), {'n': 10000, 'd': 123})
        for value in [True, 1.0, {'n': 0, 'd': 2}, {'n': 1, 'd': -1}]:
            with self.assertRaises(TurnError): Rational.read(value)
        with self.assertRaises(TurnError): Rational(2**130).compare(Rational(1, 2**130))

    def test_AT07_AT08_modifier_turn_end_expiry_and_snapshot_every_transition(self):
        from tests.battle_runtime.test_behavior_r20 import R20Tests
        from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE, reference_policy
        from r20_reference_fixtures import resource_spec
        r, bindings, p, providers = runtime(root=ability('plain', finish()), initialize=False,
            durations={'initial': {'units': 'OWNER_NORMAL_TURN_END_REFERENCE', 'creation': 'SKIP_CREATION_TURN_REFERENCE',
                                  'expiry_event': 'explicit.expiry', 'pending_callbacks': 'RETAIN_ENQUEUED_REFERENCE'}})
        r.policies[RESOURCE] = reference_policy(); r.policies[RESOURCE]['bindings']['counter'] = resource_spec()
        m = R20Tests().listener(r, task('turn-end-add', 'property_write', owner='a', key='x', operation='add',
                                     value=expr(2, True)),
                                event=p['boundary_event_keys']['TURN_END'], owner='b')
        m.duration['remaining'] = 1
        expiry = copy.deepcopy(m.event_registrations[0]); expiry['registration_id'] = 'initial/expiry'
        expiry['event_id'] = 'explicit.expiry'; expiry['callback'] = write('expiry-write', 9).to_dict()
        m.event_registrations.append(expiry)
        r.initialize_turns(bindings, p, providers)
        submit(r)
        snapshots = set()
        for _ in range(160):
            c = r.clone(); restored = BehaviorRuntime.from_snapshot(r.snapshot())
            outcomes = [x.run_until_decision(TurnBudget(scheduler_work=1, decision_transitions=1)) for x in (r, c, restored)]
            self.assertEqual([x.kind for x in outcomes], [outcomes[0].kind]*3)
            self.assertEqual(len({x.stable_hash() for x in (r, c, restored)}), 1)
            snapshots.update(x['status'] for x in self.state(r)['boundary_work'])
            if outcomes[0].kind == 'PLAYER_NORMAL_TURN':
                break
            self.assertEqual(outcomes[0].kind, 'BUDGET_YIELD')
        else: self.fail('boundary loop failed to terminate')
        self.assertEqual(self.state(r)['normal_turn_count'], 1)
        self.assertNotIn('initial', r.state.modifiers)
        self.assertEqual(r.state.properties['a']['x'], 18)
        history = r.state.modifier_history
        self.assertEqual(sum(x['boundary'] == 'OWNER_NORMAL_DURATION_PROGRESS_REFERENCE' for x in history), 1)
        self.assertEqual(sum(x['boundary'] == 'REFERENCE_CALLBACK_EXECUTED' for x in history), 2)
        self.assertIn('COMMITTED', snapshots)

    def test_AT08_persistent_manual_modifier_survives_multiple_actions(self):
        from tests.battle_runtime.test_behavior_r20 import R20Tests
        from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE, reference_policy
        from r20_reference_fixtures import resource_spec
        r, bindings, p, providers = runtime(root=ability('plain', finish()), initialize=False)
        r.policies[RESOURCE] = reference_policy(); r.policies[RESOURCE]['bindings']['counter'] = resource_spec()
        R20Tests().listener(r, write('persistent-callback', 3), event=p['boundary_event_keys']['TURN_END'])
        r.initialize_turns(bindings, p, providers)
        for _ in range(2): submit(r); r.run_until_next_turn()
        self.assertIn('initial', r.state.modifiers)
        self.assertEqual(r.state.modifiers['initial'].duration['remaining'], 10)

    def test_AT09_all_safe_categories_order_owner_and_due(self):
        r, *_ = runtime(root=ability('plain', finish()))
        b = r.run_until_decision(); submit(r, b)
        for category in ['EXTRA_TURN', 'INSERTED_ACTION', 'FOLLOW_UP_ACTION', 'FORCED_ACTION']:
            r.request_insertion(insertion(r, actor='a', category=category))
        original_due = copy.deepcopy(self.state(r)['initiative']['a']['due_at'])
        order = []
        for _ in range(4):
            b = r.run_until_next_turn()
            top = self.state(r)['active_stack'][-1]
            order.append(top['category'])
            self.assertEqual(r.current_turn_owner(), 'b')
            self.assertEqual(self.state(r)['initiative']['a']['due_at'], original_due)
            submit(r, b)
        b = r.run_until_next_turn()
        self.assertEqual(order, ['FORCED_ACTION', 'FOLLOW_UP_ACTION', 'INSERTED_ACTION', 'EXTRA_TURN'])
        self.assertEqual(self.state(r)['normal_turn_count'], 1)
        self.assertEqual(self.state(r)['action_count'], 5)
        self.assertEqual(b['actor_id'], 'a')

    def test_AT11_defeat_revive_disable_and_summon_generations(self):
        r, bindings, p, providers = runtime(speeds=(('a', 100), ('b', 200), ('c', 125)), initialize=False)
        r.initialize_turns(bindings[:2], p, providers)
        source = {'authority': 'EXPLICIT_SCENARIO_INPUT', 'source': 'fixture lifecycle output'}
        r.turn_lifecycle('b', 'DEFEAT', source_ref=source)
        self.assertEqual(r.run_until_decision()['actor_id'], 'a')
        r.turn_lifecycle('b', 'REVIVE', source_ref=source, binding={'generation': 2, 'content_version': '4.6.51', 'hp_raw': 40*SCALE})
        self.assertEqual(self.state(r)['initiative']['b']['due_at'], {'n': 150, 'd': 1})
        self.assertEqual(self.state(r)['initiative']['b']['generation'], 2)
        r.turn_lifecycle('b', 'DISABLE', source_ref=source)
        self.assert_atomic(r, lambda: r.notify_speed_change('b', 1))
        r.turn_lifecycle('b', 'ENABLE', source_ref=source)
        r.turn_lifecycle('c', 'REGISTER_ENTITY', source_ref=source, binding=bindings[2])
        self.assertEqual(self.state(r)['initiative']['c']['due_at'], {'n': 180, 'd': 1})
        submit(r); self.assertEqual(r.run_until_next_turn()['actor_id'], 'b')

    def test_AT13_R20_resource_cost_atomic_and_actual_settlement(self):
        from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE, reference_policy
        from r20_reference_fixtures import resource_spec
        r, bindings, p, providers = runtime(root=ability('costed-original', finish()), initialize=False)
        cost = task('explicit-cost', 'resource_cost_reference', binding='admission-cost')
        r.policies[RESOURCE] = reference_policy()
        spec = resource_spec(amount=2*SCALE, operation='SUBTRACT')
        spec.update(cost_authority='EXPLICIT_SCENARIO_INPUT', cost_source='explicit reference counter cost')
        r.policies[RESOURCE]['bindings']['admission-cost'] = spec
        for actor in providers['availability']['actors'].values():
            actor['actions'][0]['cost'] = {'mode': 'R20_COST_TASKS_REFERENCE', 'authority': 'EXPLICIT_SCENARIO_INPUT',
                                         'tasks': [cost.to_dict()]}
        r.initialize_turns(bindings, p, providers)
        for _ in range(2): submit(r); r.run_until_next_turn()
        self.assertEqual(r.state.actor_resources['a']['reference_actor_counter'], 0)
        self.assertEqual(len(r.state.mechanics[RESOURCE]['history']), 2)
        b = r.run_until_decision()
        self.assertEqual(r.legal_action_candidates(b['decision_id']), [])

    def test_AT14_enemy_provider_receives_snapshot_and_validates_output(self):
        r, bindings, p, providers = runtime(controllers={'b': 'MONSTER_AI'}, initialize=False)
        identity = {'provider_id': 'reference-monster-fixture', 'version': '1', 'authority': 'REFERENCE_MODEL',
                    'mode': 'FIRST_PERMISSION_REFERENCE'}
        providers['monster_decision'] = identity
        r.initialize_turns(bindings, p, providers)
        b = r.run_until_decision(); self.assertEqual(b.kind, 'ENEMY_AI_DECISION')
        observed = []
        class Provider:
            def choose(self, **kwargs):
                observed.append(kwargs)
                kwargs['snapshot']['state']['properties'].clear()  # Read-only copy cannot mutate live state.
                permission = kwargs['permissions'][0]
                return {'permission': permission, 'targets': permission['target_ids']}
        provider = Provider(); provider.identity = identity
        r.request_enemy_decision(provider)
        self.assertEqual(observed[0]['actor_id'], 'b')
        self.assertIn('policy_identity', observed[0]); self.assertIn('rng_context', observed[0])
        self.assertTrue(r.state.properties)
        self.assertEqual(r.run_until_next_turn()['actor_id'], 'a')

    def test_AT14_pending_wave_and_terminal_after_settlement(self):
        r, _, _, providers = runtime()
        source = {'provider_id': providers['stage']['provider_id'], 'policy_hash': stable_hash(providers['stage'])}
        submit(r)
        r.turn_stage_transition('WAVE_PENDING', source_ref=source, reason='await explicit next wave')
        b = r.run_until_next_turn()
        self.assertEqual(b.kind, 'SEMANTIC_GAP'); self.assertIn('WAVE_PENDING', b['failure']['message'])
        self.assertFalse(r.is_terminal()); self.assertFalse(r.state.terminal)
        r.turn_stage_transition('RUNNING', source_ref=source)
        self.assertEqual(r.run_until_decision().kind, 'PLAYER_NORMAL_TURN')
        submit(r); r.turn_stage_transition('VICTORY', source_ref=source, reason='explicit fixture terminal predicate')
        self.assertFalse(r.is_terminal())
        b = r.run_until_next_turn(); self.assertEqual(b.kind, 'BATTLE_TERMINAL'); self.assertTrue(r.is_terminal())

    def test_AT15_full_public_command_replay_external_event_speed_and_adjust(self):
        from tests.battle_runtime.test_behavior_r20 import R20Tests
        from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE, reference_policy
        from r20_reference_fixtures import resource_spec
        r, bindings, p, providers = runtime(initialize=False)
        providers['external_events']['explicit.speed.effect'] = {'authority': 'EXPLICIT_SCENARIO_INPUT', 'source': 'caller event'}
        r.events['explicit.speed.effect'] = [task('actual-speed-effect', 'property_write', owner='a', key='speed',
                                              operation='set', value=expr(200*SCALE, True))]
        r.policies[RESOURCE] = reference_policy(); r.policies[RESOURCE]['bindings']['counter'] = resource_spec()
        R20Tests().listener(r, task('actual-event-listener','property_write',owner='a',key='x',operation='add',
                                  value=expr(2,True)),event='explicit.speed.effect')
        initial = r.clone(); receipts = []
        def command(kind, arguments):
            receipt, result = r.record_turn_command(kind, arguments); receipts.append(receipt); return result
        command('initialize', {'participant_bindings': bindings, 'policy': p, 'provider_contracts': providers})
        b = command('advance', {'budget': 10000})
        command('modifier_event', {'event_key': 'explicit.speed.effect', 'payload': {'source': 'fixture'}})
        b = command('advance', {'budget': 10000})
        command('speed_change', {'actor_id': 'a', 'provider_revision': 1})
        command('adjust', {'actor_id': 'a', 'kind': 'DELAY', 'fraction': {'n': 1, 'd': 4}, 'source_ref': source_ref(providers)})
        b = command('advance', {'budget': 10000})
        permission = r.legal_action_candidates(b['decision_id'])[0]
        command('submit', {'permission': permission, 'targets': permission['target_ids'], 'expected_revision': b['state_revision']})
        command('complete', {'budget': 10000})
        replay, outputs = initial.replay_turn_commands(receipts)
        self.assertEqual(r.stable_hash(), replay.stable_hash()); self.assertEqual(r.snapshot(), replay.snapshot())
        self.assertEqual(r.state.mechanics[ADAPTER]['event_history'], replay.state.mechanics[ADAPTER]['event_history'])
        self.assertEqual(r.state.rng.draws, replay.state.rng.draws)
        self.assertEqual(self.state(r)['normal_turn_count'], 1)
        self.assertEqual(r.state.properties['a']['x'],2)
        self.assertEqual(sum(x['boundary']=='REFERENCE_CALLBACK_EXECUTED' for x in r.state.modifier_history),1)

    def test_AT17_zero_time_insertion_limits_and_stale_queue(self):
        r, *_ = runtime(root=ability('plain', finish()))
        for _ in range(3): r.request_insertion(insertion(r))
        self.assertEqual(r.run_until_decision(TurnBudget(zero_time_insertions=0)).kind, 'BUDGET_YIELD')
        b = r.run_until_decision(); self.assertEqual(b.kind, 'OUT_OF_TURN_WINDOW')
        submit(r, b); self.assertEqual(r.run_until_next_turn().kind, 'OUT_OF_TURN_WINDOW')
        # Stale queue entries are non-authoritative indices and never selected.
        r2, *_ = runtime()
        stale = copy.deepcopy(self.state(r2)['normal_queue'][0]); stale['entry_id'] = 'stale'; stale['generation'] += 1
        self.state(r2)['normal_queue'].insert(0, stale)
        self.assertEqual(r2.run_until_decision()['actor_id'], 'b')
        self.assertNotIn('stale', [x['entry_id'] for x in self.state(r2)['normal_queue']])

    def test_LevelB_original_decoded_ability_and_full_hash_replay(self):
        from r22_real_fixtures import real_runtime
        r, graph, *_ = real_runtime()
        original_ir = r.actions['real'].stable_hash()
        b = r.run_until_decision(); self.assertEqual(b['actor_id'], 'a')
        submit(r, b)
        c = r.clone(); restored = BehaviorRuntime.from_snapshot(r.snapshot())
        for x in [r, c, restored]:
            b = x.run_until_next_turn()
            self.assertEqual(b.kind, 'PLAYER_NORMAL_TURN')
            self.assertEqual(self.state(x)['normal_turn_count'], 1)
            self.assertTrue(x.state.damage_history)
            self.assertEqual(x.state.actor_resources['a']['reference_actor_counter'], 2*SCALE)
            self.assertEqual(x.actions['real'].stable_hash(), original_ir)
        self.assertEqual(len({x.stable_hash() for x in (r,c,restored)}), 1)
        self.assertFalse(graph['skill_joined'])

    def test_AT07_listener_removal_does_not_double_fire(self):
        from tests.battle_runtime.test_behavior_r20 import R20Tests
        from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE, reference_policy
        from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID as MODIFIER
        from r20_reference_fixtures import resource_spec
        r, bindings, p, providers = runtime(root=ability('plain', finish()), initialize=False, speeds=(('a',100),))
        remove = task('remove-self', 'modifier_remove_reference')
        r.policies[RESOURCE] = reference_policy(); r.policies[RESOURCE]['bindings']['counter'] = resource_spec()
        R20Tests().listener(r, remove, event=p['boundary_event_keys']['TURN_END'])
        r.policies[MODIFIER]['removals'][remove.stable_hash()] = {'selection': 'INSTANCE_REFERENCE', 'instance_id': 'initial',
            'reason': 'explicit turn-end self removal', 'pending_callbacks': 'RETAIN_ENQUEUED_REFERENCE'}
        r.initialize_turns(bindings, p, providers)
        for _ in range(2): submit(r); r.run_until_next_turn()
        self.assertNotIn('initial', r.state.modifiers)
        self.assertEqual(sum(x['boundary']=='REFERENCE_CALLBACK_EXECUTED' for x in r.state.modifier_history), 1)

    def test_AT08_new_modifier_skips_creation_turn(self):
        from dataclasses import asdict
        from hsr_battle_agent.battle_runtime.behavior_state import ModifierInstance
        fresh = ModifierInstance('fresh', 'reference', 'a', 'a', 'a', 1, 1,
            {'units': 'EXPLICIT_REFERENCE_UNITS', 'remaining': 1, 'expiry': 'MANUAL_REFERENCE'},
            activation_state='REFERENCE_INSTANCE_ACTIVE', provider_binding={'definition_policy': {'pending_callbacks': 'RETAIN_ENQUEUED_REFERENCE'}})
        r, *_ = runtime(root=ability('create-fresh', task('create', 'modifier_apply', instance=asdict(fresh)), finish()), initialize=False)
        r.actions['plain'] = ability('plain', finish())
        bindings, p, providers = inputs(r, (('a',100),), durations={'fresh': {'units':'OWNER_NORMAL_TURN_END_REFERENCE',
            'creation':'SKIP_CREATION_TURN_REFERENCE', 'expiry_event':None, 'pending_callbacks':'RETAIN_ENQUEUED_REFERENCE'}})
        r.initialize_turns(bindings,p,providers)
        b = r.run_until_decision(); permission = next(x for x in r.legal_action_candidates(b['decision_id']) if x['action_id']=='root')
        r.submit_action(permission,permission['target_ids'],b['state_revision']); b=r.run_until_next_turn()
        self.assertEqual(r.state.modifiers['fresh'].duration['remaining'],1)
        permission = next(x for x in r.legal_action_candidates(b['decision_id']) if x['action_id']=='plain')
        r.submit_action(permission,permission['target_ids'],b['state_revision']);r.run_until_next_turn()
        self.assertNotIn('fresh',r.state.modifiers)

    def test_AT05_suspended_barrier_restore_and_release(self):
        r, *_ = runtime(root=ability('barrier-action', task('external','barrier',key='explicit-input'), finish()))
        submit(r); b=r.run_until_decision()
        self.assertEqual(b.kind,'SUSPENDED_ACTION_INPUT')
        self.assertEqual(r.current_turn_owner(),'b')
        self.assertEqual(self.state(r)['clock']['now'],{'n':50,'d':1})
        copies=[r,r.clone(),BehaviorRuntime.from_snapshot(r.snapshot())]
        barrier=b['input_request']['barriers'][0]['frame_id']
        for x in copies:
            x.release_action_barrier(barrier)
            self.assertEqual(x.run_until_next_turn()['actor_id'],'a')
        self.assertEqual(len({x.stable_hash() for x in copies}),1)

    def test_AT03_final_turn_callback_speed_sample_and_missing_notification(self):
        from tests.battle_runtime.test_behavior_r15 import expr
        r, bindings, p, providers=runtime(root=ability('plain',finish()),initialize=False)
        r.events[p['boundary_event_keys']['TURN_END']]=[task('owner-final-speed','property_write',owner='b',key='speed',
            operation='set',value=expr(100*SCALE,True))]
        r.initialize_turns(bindings,p,providers)
        submit(r);r.run_until_next_turn()
        self.assertEqual(self.state(r)['initiative']['b']['due_at'],{'n':150,'d':1})
        r2,*_=runtime();r2.state.properties['b']['speed']=100*SCALE
        b=r2.run_until_decision()
        self.assertEqual(b.kind,'SEMANTIC_GAP');self.assertEqual(b['failure']['code'],'SPEED_PROVIDER_MISSING')
        self.assertIsNone(r2.current_turn_owner())

    def test_AT11_defeat_active_owner_drains_pending_action(self):
        r,*_=runtime(root=ability('active-defeat',wait(),finish()))
        submit(r)
        b=r.run_until_decision(TurnBudget(scheduler_work=30,decision_transitions=2))
        source={'authority':'EXPLICIT_SCENARIO_INPUT','source':'active owner defeat'}
        r.turn_lifecycle('b','DEFEAT',source_ref=source)
        self.assertEqual(r.current_turn_owner(),'b')
        self.assertEqual(r.run_until_next_turn()['actor_id'],'a')
        self.assertIsNone(self.state(r)['initiative']['b']['normal_entry_id'])

    def test_AT17_insertion_depth_guard_and_active_root_parent(self):
        r,bindings,p,providers=runtime(root=ability('running',wait(),finish()),initialize=False)
        p['max_insert_depth']=1;providers['policy_hash']=stable_hash(p)
        r.initialize_turns(bindings,p,providers);submit(r)
        r.run_until_decision(TurnBudget(scheduler_work=30,decision_transitions=2))
        top=self.state(r)['active_stack'][-1]
        self.assertIsNotNone(top['action_root_id'])
        request=insertion(r,actor='a');r.request_insertion(request)
        b=r.run_until_next_turn();self.assertEqual(b.kind,'OUT_OF_TURN_WINDOW')
        self.assertEqual(self.state(r)['active_stack'][-1]['parent_action_root_id'],request['parent_action_root_id'])
        self.assert_atomic(r,lambda:r.request_insertion(insertion(r,actor='b')))

    def test_AT06_finish_request_waits_owned_child_and_suffix(self):
        r,bindings,p,providers=runtime(root=ability('parent',finish(),call(),write('parent-suffix',8)),initialize=False)
        r.abilities['child']=ability('child',task('child-input','barrier',key='child-release'),write('child-write',4))
        r.initialize_turns(bindings,p,providers);submit(r)
        b=r.run_until_decision();self.assertEqual(b.kind,'SUSPENDED_ACTION_INPUT')
        d=r.state.scheduler.action_execution;root=d['roots'][d['current_root']]
        self.assertTrue(root['completion_requested']);self.assertNotEqual(root['status'],'ACTION_REFERENCE_COMPLETE')
        self.assertEqual(self.state(r)['normal_turn_count'],0)
        r.release_action_barrier(b['input_request']['barriers'][0]['frame_id'])
        self.assertEqual(r.run_until_next_turn()['actor_id'],'a')
        self.assertEqual(r.state.properties['a']['x'],16)
        self.assertEqual(self.state(r)['normal_turn_count'],1)

    def test_AT03_ready_actor_remains_ready_under_rebase(self):
        r,_,_,providers=runtime();r.run_until_decision()
        r.adjust_readiness('a','ADVANCE',{'n':1,'d':2},source_ref(providers))
        r.state.properties['a']['speed']=300*SCALE;r.notify_speed_change('a',1)
        self.assertEqual(self.state(r)['initiative']['a']['due_at'],{'n':50,'d':1})

    def test_AT11_defeat_during_start_boundary_drains_then_cancels(self):
        r,*_=runtime(root=ability('plain',finish()))
        self.assertEqual(r.run_until_decision(TurnBudget(scheduler_work=1)).kind,'BUDGET_YIELD')
        self.assertEqual(self.state(r)['active_stack'][-1]['phase'],'START_BOUNDARY')
        r.turn_lifecycle('b','DEFEAT',source_ref={'authority':'EXPLICIT_SCENARIO_INPUT','source':'defeat during start'})
        self.assertEqual(r.current_turn_owner(),'b')
        b=r.run_until_decision();self.assertEqual(b['actor_id'],'a')
        self.assertEqual(self.state(r)['normal_turn_count'],0)
        self.assertEqual(self.state(r)['action_count'],0)
        self.assertFalse(any(x['actor_id']=='b' and x['kind']=='PLAYER_NORMAL_TURN' for x in r.state.mechanics[ADAPTER]['decision_history']))

    def test_AT07_duration_visits_explicit_registration_order(self):
        from tests.battle_runtime.test_behavior_r20 import R20Tests
        from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE,reference_policy
        from r20_reference_fixtures import resource_spec
        durations={k:{'units':'OWNER_NORMAL_TURN_END_REFERENCE','creation':'SKIP_CREATION_TURN_REFERENCE',
            'expiry_event':None,'pending_callbacks':'RETAIN_ENQUEUED_REFERENCE'} for k in ['first','second']}
        r,bindings,p,providers=runtime(root=ability('plain',finish()),initialize=False,durations=durations)
        providers['duration_order']=['second','first']
        r.policies[RESOURCE]=reference_policy();r.policies[RESOURCE]['bindings']['counter']=resource_spec()
        for identity in ['first','second']:
            m=R20Tests().listener(r,write(identity,3),event=p['boundary_event_keys']['TURN_END'],identity=identity,owner='b')
            m.duration['remaining']=2
        r.initialize_turns(bindings,p,providers);submit(r);r.run_until_next_turn()
        actual=[x['instance_id'] for x in r.state.modifier_history if x['boundary']=='OWNER_NORMAL_DURATION_PROGRESS_REFERENCE']
        self.assertEqual(actual,['second','first'])

    def test_AT14_stage_pending_at_unsubmitted_decision_is_gap(self):
        r,_,_,providers=runtime();r.run_until_decision()
        source={'provider_id':providers['stage']['provider_id'],'policy_hash':stable_hash(providers['stage'])}
        r.turn_stage_transition('WAVE_PENDING',source_ref=source)
        b=r.run_until_decision();self.assertEqual(b.kind,'SEMANTIC_GAP');self.assertFalse(r.is_terminal())
        self.assertFalse(b['candidate_permission_ids'])
        r.turn_stage_transition('RUNNING',source_ref=source)
        self.assertEqual(r.run_until_decision().kind,'PLAYER_NORMAL_TURN')

    def test_AT09_typed_ActionInsertion_public_record(self):
        from hsr_battle_agent.battle_runtime.battle_turn import ActionInsertion
        r,*_=runtime(root=ability('plain',finish()))
        request=ActionInsertion.from_dict(insertion(r,category='FORCED_ACTION'))
        r.request_insertion(request)
        self.assertEqual(r.run_until_decision().kind,'PENDING_FORCED_ACTION')

    def test_AT15_positive_rng_draws_and_public_replay(self):
        r,bindings,p,providers=runtime(initialize=False,root=ability('random-finished',
            task('random-choice','random_choice',choices=[write('choice-one',1),write('choice-two',2)]),finish()))
        initial=r.clone();receipts=[]
        def command(kind,arguments):
            receipt,result=r.record_turn_command(kind,arguments);receipts.append(receipt);return result
        command('initialize',{'participant_bindings':bindings,'policy':p,'provider_contracts':providers})
        b=command('advance',{'budget':10000})
        for _ in range(2):
            permission=r.legal_action_candidates(b['decision_id'])[0]
            command('submit',{'permission':permission,'targets':permission['target_ids'],'expected_revision':b['state_revision']})
            b=command('complete',{'budget':10000})
        replay,_=initial.replay_turn_commands(receipts)
        self.assertEqual(r.state.rng.draws,2)
        self.assertEqual(r.stable_hash(),replay.stable_hash())
        self.assertEqual(r.state.properties,replay.state.properties)


if __name__ == '__main__': unittest.main()
