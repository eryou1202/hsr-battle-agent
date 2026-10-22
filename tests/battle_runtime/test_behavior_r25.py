"""Executable E01-E18 reference encounters; no native stage equivalence claim."""
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/runtime')]
from hsr_battle_agent.battle_ir.behavior import stable_hash, walk_nodes, IRNode
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.battle_turn import KEY as TURN, ADAPTER, TurnError
from hsr_battle_agent.battle_runtime.encounter_runtime import KEY, EncounterDefinition, reference_policy, _evaluate
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.defense_break import POLICY_ID as DEFENSE
from r25_reference_fixtures import setup, complete, provenance, flag
from tests.battle_runtime import test_behavior_r15 as ir


class R25Scenarios(unittest.TestCase):
    def traced_encounter(self, **options):
        r, args, real = setup(initialize=False, **options)
        self.initial_snapshot = r.snapshot(); self.command_receipts = []
        def command(kind, **arguments):
            receipt, result = r.record_encounter_command(kind, arguments)
            self.command_receipts.append(receipt)
            return result
        command('initialize', **args)
        boundary = complete(r, command=command)
        replay, _ = BehaviorRuntime.from_snapshot(self.initial_snapshot).replay_encounter_commands(self.command_receipts)
        self.assertEqual(replay.snapshot(), r.snapshot())
        return r, boundary, real

    def capture(self, r, cohort='PURE_REFERENCE_ENCOUNTER'):
        c = r.current_encounter()
        self.observation = {'cohort': cohort, 'snapshot': r.snapshot(), 'state_hash': r.stable_hash(),
            'terminal_receipt': r.encounter_result(), 'actions': r.state.mechanics[TURN]['action_count'],
            'waves_completed': len([e for e in c['events'] if e['kind'] == 'WAVE_CLEAR' and e['status'] == 'COMMITTED']),
            'event_order': [e['kind'] for e in c['events']], 'phase': c['phase']}

    def submit(self, r, b=None):
        b = b or r.run_until_encounter_boundary()
        p = r.legal_action_candidates(b['decision_id'])[0]
        return r.submit_action(p, p['target_ids'], b['state_revision'])

    def until(self, r, condition, bound=80):
        for _ in range(bound):
            if condition(r): return
            b = r.run_until_encounter_boundary({'decision_transitions': 1, 'scheduler_work': 10000})
            self.assertNotEqual(b.kind, 'SEMANTIC_GAP', str(b))
        self.fail('checkpoint bound exhausted')

    def victory(self, r):
        b = complete(r)
        self.assertEqual(b.kind, 'BATTLE_TERMINAL', str(b))
        self.assertEqual(r.encounter_result()['result'], 'VICTORY')
        self.assertFalse(r.state.mechanics[TURN]['permissions'])
        return b

    def test_E01_one_wave_committed_damage_victory(self):
        r, _, _ = self.traced_encounter(waves=1, player_damage=10)
        self.victory(r)
        self.assertEqual(r.state.properties['b']['hp'], 0)
        self.assertEqual(len(r.current_encounter()['life_receipts']), 1)
        self.assertEqual(r.state.mechanics[TURN]['action_count'], 1)
        receipt = r.encounter_result()
        state = r.state.clone(); state.mechanics[KEY]['terminal_receipt'] = None
        self.assertEqual(receipt['final_state_hash'], state.stable_hash())
        self.capture(r)

    def test_E02_two_wave_automatic_victory(self):
        r, _, _ = self.traced_encounter()
        self.victory(r)
        self.assertEqual(r.state.mechanics[TURN]['stage']['wave_index'], 1)
        self.assertEqual(len(r.state.mechanics[TURN]['participants']), 3)
        self.assertEqual(r.state.properties['c']['hp'], 0)
        self.assertEqual(len([e for e in r.current_encounter()['events'] if e['kind'] == 'WAVE_CLEAR']), 2)
        self.capture(r)

    def test_E03_persistent_player_hp_resources(self):
        r, _, _ = setup(player_hp=80, player_damage=10)
        b = r.run_until_encounter_boundary(); self.submit(r, b)
        b = r.run_until_encounter_boundary()
        self.assertEqual(r.state.mechanics[TURN]['stage']['wave_index'], 1)
        self.assertEqual(r.state.properties['a']['hp'], 80*SCALE)
        self.assertEqual(r.state.actor_resources['a']['reference_actor_counter'], 5*SCALE)
        self.assertEqual(r.current_encounter()['counters']['wave_transitions'], 1)
        self.victory(r)
        self.assertGreaterEqual(r.state.actor_resources['a']['reference_actor_counter'], 6*SCALE)
        self.capture(r)

    def test_E04_enemy_action_defeat(self):
        r, b, _ = self.traced_encounter(waves=1, player_damage=1, enemy_damage=100)
        self.assertEqual(b.kind, 'BATTLE_TERMINAL', str(b))
        self.assertEqual(r.encounter_result()['result'], 'DEFEAT')
        self.assertEqual(r.state.properties['a']['hp'], 0)
        self.assertGreaterEqual(r.state.mechanics[TURN]['action_count'], 2)
        self.capture(r)

    def test_E05_zero_hp_waits_for_owned_callbacks(self):
        suffix = (ir.event('mandatory-after-hit', 'r25.required'),)
        r, _, _ = setup(waves=1, player_damage=10, player_suffix=suffix)
        r.events['r25.required'] = [ir.wait('required-wait'), ir.write('required-write', 11)]
        self.submit(r)
        observed = False
        for _ in range(150):
            r.run_until_encounter_boundary({'decision_transitions': 1, 'scheduler_work': 1})
            c = r.current_encounter()
            if c['life_candidates'] and r.state.properties['a']['x'] == 0:
                self.assertTrue(r.state.entities['b']['alive'])
                self.assertFalse(c['life_receipts']); self.assertFalse(r.is_terminal())
                observed = True; break
        self.assertTrue(observed)
        restored = BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))
        self.victory(r); self.victory(restored)
        self.assertEqual(r.stable_hash(), restored.stable_hash())
        self.assertEqual(r.state.properties['a']['x'], 22)
        self.capture(r)

    def test_E06_action_gap_blocks_objective_transition(self):
        r, args, _ = setup(waves=1, player_damage=10,
            player_suffix=(ir.task('unknown-after-hit', 'r25.unsupported_mandatory_task'),), initialize=False)
        # Explicit R18 settlement may set alive, but the coordinator still waits for the root.
        raw = r.actions['player:b'].to_dict()
        raw['payload']['tasks']['payload']['tasks'][0]['payload']['hp_settlement']['life_state'] = 'SET_ALIVE_FROM_HP_REFERENCE'
        root = r.actions['player:b'] = IRNode.from_dict(raw)
        args['provider_contracts']['availability']['actors']['a']['actions'][0]['ir_hash'] = root.stable_hash()
        args['definition']['waves'][0]['availability']['a']['actions'][0]['ir_hash'] = root.stable_hash()
        provenance(args['definition'])
        r.initialize_encounter(**args)
        self.submit(r)
        b = r.run_until_encounter_boundary()
        self.assertEqual(b.kind, 'SEMANTIC_GAP')
        self.assertTrue(r.evaluate_encounter_objectives()['wave']['satisfied'])
        self.assertEqual(r.current_encounter()['phase'], 'WAVE_ACTIVE')
        self.assertFalse(r.current_encounter()['life_receipts'])
        self.assertIsNone(r.encounter_result())
        self.capture(r)

    def test_E07_wave_pending_is_not_terminal(self):
        r, _, _ = setup(player_damage=10)
        self.submit(r)
        self.until(r, lambda x: x.state.mechanics[ADAPTER]['stage_status'] == 'WAVE_PENDING')
        self.assertFalse(r.is_terminal()); self.assertIsNone(r.encounter_result())
        self.assertEqual(r.state.mechanics[TURN]['stage']['wave_index'], 0)
        self.assertNotIn('c', r.state.entities)
        self.capture(r)

    def test_E08_retries_do_not_duplicate_wave_or_callbacks(self):
        r, args, _ = setup(player_damage=10)
        before = r.stable_hash(); r.initialize_encounter(**args)
        self.assertEqual(before, r.stable_hash())
        self.victory(r)
        before = r.stable_hash(); events = r.current_encounter()['events']
        for _ in range(3):
            r.run_until_encounter_boundary(); r.encounter_result(); r.initialize_encounter(**args)
        self.assertEqual(before, r.stable_hash()); self.assertEqual(events, r.current_encounter()['events'])
        self.assertEqual(r.current_encounter()['counters']['actor_registrations'], 3)
        self.capture(r)

    def test_E09_defeat_invalidates_stale_queue_permissions(self):
        r, _, _ = setup()
        b = r.run_until_encounter_boundary()
        p = r.legal_action_candidates(b['decision_id'])[0]
        r.turn_lifecycle('a', 'DEFEAT', source_ref={'authority': 'EXPLICIT_SCENARIO_INPUT', 'source': 'E09 explicit defeat'})
        self.assertFalse(any(x['actor_id'] == 'a' for x in r.state.mechanics[TURN]['normal_queue']))
        before = r.stable_hash()
        with self.assertRaises(TurnError): r.submit_action(p, p['target_ids'], b['state_revision'])
        self.assertEqual(before, r.stable_hash())
        self.assertEqual(r.state.mechanics[TURN]['initiative']['a']['generation'], 1)
        self.capture(r)

    def test_E10_revive_new_generation_restores_eligibility(self):
        r, _, _ = setup()
        r.turn_lifecycle('b', 'DEFEAT', source_ref={'authority': 'EXPLICIT_SCENARIO_INPUT', 'source': 'E10 defeat'})
        r.turn_lifecycle('b', 'REVIVE', source_ref={'authority': 'EXPLICIT_SCENARIO_INPUT', 'source': 'E10 revive'},
            binding={'generation': 2, 'content_version': '4.6.51', 'hp_raw': 10*SCALE})
        self.assertTrue(r.state.entities['b']['alive'])
        self.assertEqual(r.state.mechanics[TURN]['initiative']['b']['generation'], 2)
        self.assertEqual([x['generation'] for x in r.state.mechanics[TURN]['normal_queue'] if x['actor_id'] == 'b'], [2])
        self.victory(r); self.capture(r)

    def test_E11_shield_break_modifier_carryover(self):
        r, _, _ = setup(player_damage=10)
        from r18_reference_fixtures import reference_listener
        from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID as DAMAGE
        r.policies[DAMAGE] = {'tasks': {}}
        reference_listener(r, ir.write('persistent-listener', 1), event_id='reference.unused', identity='persistent-modifier')
        m = r.state.modifiers['persistent-modifier']; m.owner = m.target = 'a'
        state = r.state.mechanics[DEFENSE]['actors']['a']
        from tests.battle_runtime.test_behavior_r24 import shield
        state['shields']['value'] = [shield('persistent-shield', 13, owner='a')]
        state['break_state']['value'] = {'active': True, 'generation': 2}
        before = copy.deepcopy(state)
        modifier = copy.deepcopy(vars(m)); rng = copy.deepcopy(vars(r.state.rng))
        self.submit(r); r.run_until_encounter_boundary()
        self.assertEqual(r.state.mechanics[TURN]['stage']['wave_index'], 1)
        self.assertEqual(before, r.state.mechanics[DEFENSE]['actors']['a'])
        self.assertEqual(modifier, vars(r.state.modifiers['persistent-modifier']))
        self.assertEqual(rng, vars(r.state.rng))
        self.capture(r)

    def test_E12_prepare_failure_atomic_then_corrected_input(self):
        r, args, _ = setup(player_damage=10)
        self.submit(r)
        self.until(r, lambda x: x.current_encounter()['phase'] == 'WAVE_READY')
        before = r.stable_hash()
        bad = copy.deepcopy(args['actor_inputs']); bad['c']['content_version'] = '4.4.54'
        with self.assertRaises(TurnError): r.prepare_next_wave(bad)
        self.assertEqual(before, r.stable_hash()); self.assertNotIn('c', r.state.entities)
        prepared = r.prepare_next_wave(args['actor_inputs'])
        self.assertEqual(prepared['wave_index'], 1); self.assertEqual(before, r.stable_hash())
        self.victory(r); self.capture(r)

    def test_E13_terminal_rejects_further_action(self):
        r, _, _ = setup(waves=1, player_damage=10)
        b = r.run_until_encounter_boundary(); p = r.legal_action_candidates(b['decision_id'])[0]
        self.submit(r, b); self.victory(r)
        before = r.stable_hash()
        with self.assertRaises(TurnError): r.submit_action(p, p['target_ids'], b['state_revision'])
        with self.assertRaises(ValueError): r.start_action('player:b')
        with self.assertRaises(TurnError): r.turn_stage_transition('RUNNING', source_ref={})
        self.assertEqual(before, r.stable_hash()); self.assertEqual(r.legal_actions(), ())
        self.capture(r)

    def test_E14_deterministic_monster_provider_full_encounter(self):
        r, _, _ = setup(waves=1, player_damage=6)
        self.victory(r)
        self.assertTrue(any(x['actor_id'] == 'b' for x in r.state.mechanics[ADAPTER]['action_history']))
        self.assertLess(r.state.properties['a']['hp'], 100*SCALE)
        self.capture(r)

    def test_E15_unchanged_real_damage_primitive(self):
        r, _, original = self.traced_encounter(waves=1, real=True)
        self.victory(r)
        source = next(n for n in walk_nodes(r.actions['player:b']) if n.op.startswith('RPG.GameCore.DamageByAttackProperty'))
        self.assertEqual(source.stable_hash(), original)
        self.assertTrue(r.state.damage_history)
        self.capture(r, 'REAL_PRIMITIVE_REFERENCE_ENCOUNTER')

    def test_E16_full_command_clone_snapshot_replay(self):
        r, args, _ = setup(initialize=False, player_damage=10)
        original = r.clone(); receipts = []
        def command(kind, **kwargs):
            receipt, output = r.record_encounter_command(kind, kwargs)
            receipts.append(receipt)
            return output
        command('initialize', **args)
        b = command('advance'); p = r.legal_action_candidates(b['decision_id'])[0]
        command('submit', permission=p, targets=p['target_ids'], expected_revision=b['state_revision'])
        restored = BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))
        self.assertEqual(restored.stable_hash(), r.stable_hash())
        self.assertEqual(complete(r, command=command).kind, 'BATTLE_TERMINAL')
        self.victory(restored)
        replay, _ = original.replay_encounter_commands(receipts)
        self.assertEqual(r.snapshot(), replay.snapshot()); self.assertEqual(r.stable_hash(), restored.stable_hash())
        self.command_receipts = receipts; self.initial_snapshot = original.snapshot()
        self.capture(r)

    def test_E17_stage_callback_budget_resume_exactly_once(self):
        r, _, _ = setup(waves=1, player_damage=10)
        r.events['reference.encounter.encounter_start'] = [ir.wait('stage-wait'), ir.write('stage-write', 9)]
        b = r.run_until_encounter_boundary({'decision_transitions': 1, 'scheduler_work': 1})
        self.assertEqual(b.kind, 'BUDGET_YIELD')
        self.assertTrue(any(x['status'] == 'DISPATCHED' for x in r.current_encounter()['events']))
        restored = BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))
        self.victory(r); self.victory(restored)
        self.assertEqual(r.stable_hash(), restored.stable_hash())
        self.assertEqual(r.state.properties['a']['x'], 18)
        self.assertEqual(len([x for x in r.current_encounter()['events'] if x['kind'] == 'ENCOUNTER_START']), 1)
        self.capture(r)

    def test_E18_conflict_and_unknown_life_fail_closed(self):
        r, args, _ = setup(initialize=False)
        bad = copy.deepcopy(args)
        del bad['actor_inputs']['b']['actor_binding']['fields']['entity_state']
        bad['definition']['actors']['b']['binding_hash'] = stable_hash(bad['actor_inputs']['b'])
        provenance(bad['definition'])
        before = r.stable_hash()
        with self.assertRaises(TurnError): r.initialize_encounter(**bad)
        self.assertEqual(before, r.stable_hash())
        args['definition']['waves'][0]['objective'] = flag('abort', False)
        args['definition']['terminal_rules']['defeat'] = flag('abort', False)
        provenance(args['definition']); r.initialize_encounter(**args)
        b = r.run_until_encounter_boundary()
        self.assertEqual(b.kind, 'SEMANTIC_GAP'); self.assertIn('OBJECTIVE_RESULTS_CONFLICT', b.reason)
        self.assertFalse(r.is_terminal()); self.assertIsNone(r.encounter_result())
        self.capture(r)


class R25ContractTests(unittest.TestCase):
    def test_independent_budgeted_search_branches(self):
        from r25_scenarios import branches
        rows = branches()
        self.assertEqual(len(rows), 3)
        self.assertEqual({r['result'] for r in rows}, {'VICTORY'})

    def test_definition_provenance_and_versions(self):
        r, args, _ = setup(initialize=False)
        for change in ('provenance', 'version', 'duplicate'):
            bad = copy.deepcopy(args['definition'])
            if change == 'provenance': bad['provenance'] = {}
            elif change == 'version': bad['source_version'] = '4.4.54'
            else: bad['waves'][1]['wave_id'] = bad['waves'][0]['wave_id']
            with self.assertRaises(TurnError): EncounterDefinition.from_dict(bad)

    def test_all_generic_objectives_pure(self):
        r, _, _ = setup()
        before = r.stable_hash()
        self.assertFalse(_evaluate(r, {'kind': 'SPECIFIC_ACTOR_DEFEATED_REFERENCE', 'actor_id': 'a'})['satisfied'])
        self.assertFalse(_evaluate(r, {'kind': 'SURVIVE_N_NORMAL_TURNS_REFERENCE', 'side': 'players', 'count': 1})['satisfied'])
        children = [flag('abort', False), flag('abort', True)]
        self.assertTrue(_evaluate(r, {'kind': 'COMPOSITE_OR_REFERENCE', 'children': children})['satisfied'])
        self.assertFalse(_evaluate(r, {'kind': 'COMPOSITE_AND_REFERENCE', 'children': children})['satisfied'])
        r.current_encounter(); r.current_wave(); r.next_wave_preview(); r.evaluate_encounter_objectives(); r.encounter_result()
        self.assertEqual(before, r.stable_hash())
        with self.assertRaises(TurnError): _evaluate(r, flag('missing'))

    def test_missing_enemy_provider_retains_boundary(self):
        r, args, _ = setup(waves=1, player_damage=6, initialize=False)
        del args['provider_contracts']['monster_decision']
        r.initialize_encounter(**args)
        b = r.run_until_encounter_boundary(); R25Scenarios().submit(r, b)
        b = r.run_until_encounter_boundary(); self.assertEqual(b.kind, 'ENEMY_AI_DECISION')
        before = r.stable_hash(); self.assertEqual(r.request_enemy_decision(), b)
        self.assertEqual(before, r.stable_hash())

    def test_terminal_snapshot_tampering_rejected(self):
        r, _, _ = setup(waves=1, player_damage=10)
        complete(r)
        restored = BehaviorRuntime.from_snapshot(r.snapshot())
        self.assertEqual(restored.stable_hash(), r.stable_hash())
        bad = r.snapshot(); bad['state']['mechanics'][KEY]['terminal_receipt']['result'] = 'DEFEAT'
        with self.assertRaises(TurnError): BehaviorRuntime.from_snapshot(bad)

    def test_explicit_registration_budget_yields_without_partial_wave(self):
        r, args, _ = setup(initialize=False, player_damage=10)
        args['definition']['limits']['actor_registrations'] = 2; provenance(args['definition'])
        r.initialize_encounter(**args); R25Scenarios().submit(r)
        b = r.run_until_encounter_boundary()
        self.assertEqual(b.kind, 'BUDGET_YIELD'); self.assertNotIn('c', r.state.entities)
        self.assertIsNone(r.encounter_result())

    def test_stage_callback_objective_conflict_blocks_terminal(self):
        r, _, _ = setup(waves=1, player_damage=10)
        r.events['reference.encounter.wave_clear'] = [
            ir.task('explicit-player-zero', 'property_write', owner='a', key='hp', operation='set', value=ir.expr(0, True))]
        b = complete(r)
        self.assertEqual(b.kind, 'SEMANTIC_GAP')
        self.assertIn('OBJECTIVE_RESULTS_CONFLICT', b.reason)
        self.assertIsNone(r.encounter_result())

    def test_lifecycle_checkpoints_clone_and_prepared_input_invalidation(self):
        r, _, _ = setup(player_damage=10)
        R25Scenarios().submit(r)
        checkpoints = set()
        for _ in range(65):
            c = r.current_encounter()
            label = (c['phase'], bool(c['prepared']), r.state.mechanics[TURN]['stage']['wave_index'])
            if label not in checkpoints:
                clone = r.clone(); restored = BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))
                self.assertEqual(clone.snapshot(), restored.snapshot())
                left = clone.run_until_encounter_boundary({'decision_transitions': 1})
                right = restored.run_until_encounter_boundary({'decision_transitions': 1})
                self.assertEqual(left, right); self.assertEqual(clone.stable_hash(), restored.stable_hash())
                checkpoints.add(label)
            if c['phase'] == 'WAVE_READY' and c['prepared']:
                altered = r.clone()
                from r22_reference_fixtures import source_ref
                altered.adjust_readiness('a', 'DELAY', {'n': 1, 'd': 2},
                    source_ref(altered.policies['r22_turn_provider_contracts_v1']))
                b = altered.run_until_encounter_boundary()
                self.assertEqual(b.kind, 'SEMANTIC_GAP'); self.assertIn('WAVE_PREPARE_STALE', b.reason)
                self.assertNotIn('c', altered.state.entities)
            b = r.run_until_encounter_boundary({'decision_transitions': 1})
            self.assertNotEqual(b.kind, 'SEMANTIC_GAP', str(b))
            if r.state.mechanics[TURN]['stage']['wave_index'] == 1 and r.current_encounter()['phase'] == 'WAVE_ACTIVE': break
        self.assertTrue({'WAVE_CLEAR_PENDING', 'TRANSITION_DRAINING', 'WAVE_READY', 'WAVE_INITIALIZING'} <= {x[0] for x in checkpoints})


if __name__ == '__main__': unittest.main()
