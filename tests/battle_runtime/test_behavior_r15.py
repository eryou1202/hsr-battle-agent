"""R15 ownership, suspension, policies and replay regressions."""
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/runtime'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from r13_reference_fixtures import fixture
from hsr_battle_agent.battle_ir.behavior import (Authority, TaskIR, TaskSequenceIR, AbilityIR,
    ExpressionIR, TargetSelectorIR, UnsupportedSemanticIR)
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime, ExecutionStatus, GapError
from hsr_battle_agent.battle_runtime.action_scheduler import POLICY_ID, reference_policy, WorkBudget

A = Authority('REFERENCE_MODEL', 'r15', 'SYNTHETIC_R15_REGRESSION', '', semantic_status='REFERENCE_MODEL')

def expr(value, raw=False):
    return ExpressionIR('expr/' + str(value), 'literal', A, {'raw' if raw else 'value': value})

def task(name, op, **payload):
    return TaskIR(name, op, A, payload)

def ability(name, *nodes):
    return AbilityIR(name, 'ability', A, {'tasks': TaskSequenceIR(name + '/seq', 'immediate_sequence', A, {'tasks': list(nodes)})})

def finish(name='finish'):
    return task(name, 'RPG.GameCore.SkillPerformFinish')

def call(name='call', child='child'):
    return task(name, 'RPG.GameCore.TriggerAbility', fields={'AbilityName': expr(child),
        'TargetType': TargetSelectorIR(name + '/target', 'explicit', A, {'entities': ['b']})})

def write(name, value):
    return task(name, 'property_write', owner='a', key='x', operation='set', value=expr(value * 2, True))

def wait(name='wait', duration=7):
    return task(name, 'RPG.GameCore.WaitSecond', roles={'duration': expr(duration * 2, True)})

def event(name, kind):
    return task(name, 'event_dispatch', event_type=kind)

class R15Tests(unittest.TestCase):
    def runtime(self, root, *, children=None, events=None, mode='WAIT_CHILD_TREE_REFERENCE', policy=None):
        state, aliases, policies = fixture([])
        state.properties['a']['x'] = 0
        p = reference_policy()
        p['invocation']['parent_resume'] = mode
        p['waits'] = {'WaitSecond': {'classification': 'LOGICAL_DELAY_REFERENCE', 'duration_units': 'SERIALIZED_RAW_REFERENCE_UNITS'},
                      'WaitAnimState': {'classification': 'BARRIER_ONLY_REFERENCE'},
                      'WaitTimelineFinish': {'classification': 'BARRIER_ONLY_REFERENCE'}}
        if policy:
            policy(p)
        policies[POLICY_ID] = p
        return BehaviorRuntime(state, actions={'root': root}, abilities=children or {}, aliases=aliases, events=events or {}, policies=policies)

    def data(self, r):
        return r.state.scheduler.action_execution

    def completed_order(self, r):
        return [h['node'] for h in self.data(r)['history'] if h.get('status') == 'TASK_COMPLETE' and h['op'] != 'immediate_sequence']

    def assert_resume(self, r, operation='run_until_action_complete'):
        clone = r.clone()
        restored = BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())), registry=r.registry)
        self.assertEqual(r.stable_hash(), clone.stable_hash())
        self.assertEqual(r.stable_hash(), restored.stable_hash())
        outcomes = [getattr(x, operation)() for x in (r, clone, restored)]
        self.assertEqual(outcomes[0], outcomes[1]); self.assertEqual(outcomes[0], outcomes[2])
        self.assertEqual(r.stable_hash(), clone.stable_hash())
        self.assertEqual(r.stable_hash(), restored.stable_hash())
        return outcomes[0]

    def test_wait_child_lifecycle_and_context(self):
        r = self.runtime(ability('root', call(), write('parent', 2), finish()), children={'child': ability('child', wait(), write('child-write', 1))}, mode='WAIT_CHILD_REFERENCE')
        r.start_action('root')
        self.assertEqual(r.run_ready().status, ExecutionStatus.WAITING_SCHEDULER)
        self.assertEqual(r.state.properties['a']['x'] // 2, 0)
        d = self.data(r)
        child = next(a for a in d['abilities'].values() if a['parent_ability_id'])
        self.assertEqual(child['context']['ability_target'], 'b')
        self.assertEqual(child['context']['owner'], 'a')
        self.assertEqual(child['context']['skill_targets'], ['b', 'a'])
        self.assertEqual(child['context']['param_entity_stack'], ['a'])
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertLess(self.completed_order(r).index('child-write'), self.completed_order(r).index('parent'))

    def test_fire_and_continue_still_drains_child(self):
        r = self.runtime(ability('root', call(), write('parent', 2), finish()), children={'child': ability('child', wait(), write('child-write', 1))}, mode='FIRE_AND_CONTINUE_REFERENCE')
        r.start_action('root'); r.run_ready()
        d = self.data(r)
        self.assertTrue(d['roots'][d['current_root']]['completion_requested'])
        self.assertEqual(d['roots'][d['current_root']]['status'], 'RUNNING')
        self.assertEqual(r.state.properties['a']['x'] // 2, 2)
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(r.state.properties['a']['x'] // 2, 1)

    def test_direct_child_and_tree_relationship_differ(self):
        # Per task explicit policy is supplied by changing parent_resume only at a
        # checkpoint: root waits; child fires a grandchild; restore must preserve it.
        for mode, expected in [('WAIT_CHILD_REFERENCE', 4), ('WAIT_CHILD_TREE_REFERENCE', 0)]:
            r = self.runtime(ability('root', call(), write('after', 4), finish()), children={
                'child': ability('child', call('grand-call', 'grand')), 'grand': ability('grand', wait())}, mode=mode)
            r.start_action('root')
            # Activate root + sequence + invoke root child.
            r.run_ready(3)
            r.policies[POLICY_ID]['invocation']['parent_resume'] = 'FIRE_AND_CONTINUE_REFERENCE'
            r.run_ready()
            self.assertEqual(r.state.properties['a']['x'] // 2, expected)
            self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)

    def test_sequence_suspension_logical_time(self):
        r = self.runtime(ability('root', wait(duration=11), write('next', 3), finish()))
        r.start_action('root'); r.run_ready()
        self.assertEqual(self.data(r)['logical_time'], 0)
        self.assertEqual(r.state.properties['a']['x'] // 2, 0)
        self.assertEqual(r.advance_to_next_event().status, ExecutionStatus.WAITING_SCHEDULER)
        self.assertEqual(self.data(r)['logical_time'], 22)
        self.assertEqual(r.run_ready().status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)

    def test_external_barrier_release_and_restore(self):
        r = self.runtime(ability('root', task('anim', 'RPG.GameCore.WaitAnimState'), write('next', 8), finish()),
                         policy=lambda p: p['waits'].update(WaitAnimState={'classification': 'EXTERNAL_PRESENTATION_BARRIER', 'release_key': 'anim'}))
        r.start_action('root'); r.run_until_blocked()
        c = r.clone(); bid = next(iter(self.data(r)['barriers']))
        r.release_action_barrier(bid); c.release_action_barrier(bid)
        self.assertEqual(r.run_ready().status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        c.run_ready(); self.assertEqual(r.stable_hash(), c.stable_hash())

    def test_barrier_only_is_a_fence(self):
        r = self.runtime(ability('root', task('anim', 'RPG.GameCore.WaitAnimState'), finish()))
        r.start_action('root')
        self.assertEqual(r.run_ready().status, ExecutionStatus.WAITING_SCHEDULER)
        self.assertEqual(len(self.data(r)['barriers']), 1)
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)

    def test_timeline_delay(self):
        r = self.runtime(ability('root', task('timeline', 'RPG.GameCore.WaitTimelineFinish'), finish()),
                         policy=lambda p: p['waits'].update(WaitTimelineFinish={'classification': 'LOGICAL_DELAY_REFERENCE', 'duration_raw': 19}))
        self.assertEqual(r.step('root').status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(self.data(r)['logical_time'], 19)

    def test_unknown_wait_and_native_policy_are_gaps(self):
        for op in ['WaitSecond', 'WaitAnimState', 'WaitTimelineFinish']:
            r = self.runtime(ability('root', task('wait', 'RPG.GameCore.' + op), finish()), policy=lambda p: p.update(waits={}))
            self.assertEqual(r.step('root').status, ExecutionStatus.SEMANTIC_GAP)
            self.assertEqual(len(self.data(r)['barriers']), 0)

    def test_callback_fifo_nested_and_action_drain(self):
        r = self.runtime(ability('root', event('dispatch', 'one'), finish()), events={
            'one': [write('first', 1), event('nested', 'two'), write('third', 3)], 'two': [write('nested-write', 4)]})
        r.start_action('root')
        self.assertEqual(r.run_ready(6).status, ExecutionStatus.EXECUTION_BUDGET_EXHAUSTED)
        self.assertTrue(self.data(r)['roots'][self.data(r)['current_root']]['completion_requested'])
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(r.state.properties['a']['x'] // 2, 4)
        self.assertLess(self.completed_order(r).index('third'), self.completed_order(r).index('nested-write'))
        self.assertTrue(all(c['status'] == 'CALLBACK_COMPLETE' for c in self.data(r)['callbacks'].values()))
        self.assertTrue(all(c['source_event'] and c['callback_owner'] for c in self.data(r)['callbacks'].values()))

    def test_child_callback_drain_before_parent(self):
        r = self.runtime(ability('root', call(), write('parent', 9), finish()), children={'child': ability('child', event('e', 'child-event'))},
            events={'child-event': [TaskSequenceIR('child-callback', 'immediate_sequence', A, {'tasks': [wait(), write('callback-write', 5)]})]})
        r.start_action('root'); r.run_ready()
        self.assertEqual(r.state.properties['a']['x'] // 2, 0)
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(r.state.properties['a']['x'] // 2, 9)
        child = next(a for a in self.data(r)['abilities'].values() if a['parent_ability_id'])
        self.assertTrue(all(c['ability_instance_id'] == child['frame_id'] for c in self.data(r)['callbacks'].values()))

    def test_finish_is_request_and_does_not_skip_suffix(self):
        r = self.runtime(ability('root', finish(), wait(), write('suffix', 8)))
        r.start_action('root'); r.run_ready()
        self.assertEqual(len(self.data(r)['completion_requests']), 1)
        self.assertEqual(self.data(r)['roots'][self.data(r)['current_root']]['status'], 'RUNNING')
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(r.state.properties['a']['x'] // 2, 8)

    def test_no_finish_no_action_completion(self):
        r = self.runtime(ability('root', write('write', 1)))
        self.assertEqual(r.step('root').status, ExecutionStatus.WAITING_SCHEDULER)
        self.assertTrue(all(a['status'] == 'ABILITY_COMPLETE' for a in self.data(r)['abilities'].values()))
        self.assertEqual(r.legal_actions(), ())

    def test_child_finish_does_not_complete_root(self):
        r = self.runtime(ability('root', call()), children={'child': ability('child', finish())})
        self.assertEqual(r.step('root').status, ExecutionStatus.WAITING_SCHEDULER)
        self.assertFalse(self.data(r)['roots'][self.data(r)['current_root']]['completion_requested'])

    def test_semantic_gap_rolls_back_primitive_and_rng(self):
        bad = task('bad', 'mutate_then_gap')
        r = self.runtime(ability('root', write('prefix', 2), bad, finish()))
        def handler(engine, node, state):
            state.rng.next_u64(); state.properties['a']['x'] = 77
            raise GapError(node, 'unsupported primitive')
        r.registry.register('task', 'mutate_then_gap', handler)
        r.start_action('root')
        r.run_ready(3)
        before = r.stable_hash()
        outcome = r.run_ready()
        self.assertEqual(outcome.status, ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(r.stable_hash(), before)
        self.assertEqual(r.state.properties['a']['x'] // 2, 2)
        self.assertEqual(r.state.rng.draws, 0)
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.SEMANTIC_GAP)

    def test_budget_exhaustion_resumable(self):
        r = self.runtime(ability('root', wait(), finish()))
        r.start_action('root'); before = r.stable_hash()
        self.assertEqual(r.run_ready(0).status, ExecutionStatus.EXECUTION_BUDGET_EXHAUSTED)
        self.assertEqual(r.stable_hash(), before)
        self.assertEqual(r.run_ready(1).status, ExecutionStatus.EXECUTION_BUDGET_EXHAUSTED)
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)

    def test_separate_budget_limits(self):
        for budget in [WorkBudget(max_task_transitions=0), WorkBudget(max_child_invocations=0), WorkBudget(max_callbacks=0), WorkBudget(max_time_advances=0)]:
            r = self.runtime(ability('root', call(), event('e', 'event'), wait(), finish()), children={'child': ability('child')}, events={'event': [write('callback', 1)]})
            r.start_action('root')
            self.assertEqual(r.run_until_blocked(budget).status, ExecutionStatus.EXECUTION_BUDGET_EXHAUSTED)
            self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)

    def test_ability_cycle_protection(self):
        r = self.runtime(ability('root', call(child='root')), children={'root': ability('root', call(child='root'))})
        result = r.step('root')
        self.assertEqual(result.status, ExecutionStatus.SEMANTIC_GAP)
        self.assertIn('CYCLE', result.gap.required_capability)

    def test_callback_cycle_protection(self):
        r = self.runtime(ability('root', event('e', 'recursive'), finish()), events={'recursive': [event('again', 'recursive')]})
        result = r.step('root')
        self.assertEqual(result.status, ExecutionStatus.SEMANTIC_GAP)
        self.assertIn('CALLBACK_CYCLE', result.gap.required_capability)

    def test_zero_delay_schedule_cycle(self):
        r = self.runtime(ability('root', task('schedule', 'schedule', tick=0, tasks=[event('loop', 'event')]), finish()),
            events={'event': [task('schedule', 'schedule', tick=0, tasks=[event('loop', 'event')])]})
        result = r.step('root')
        self.assertEqual(result.status, ExecutionStatus.SEMANTIC_GAP)
        self.assertIn('CYCLE', result.gap.required_capability)

    def test_damage_remains_gap(self):
        for op in ['DamageByAttackProperty', 'DamagePerformFinish']:
            r = self.runtime(ability('root', task('damage', 'RPG.GameCore.' + op), finish()))
            self.assertEqual(r.step('root').status, ExecutionStatus.SEMANTIC_GAP)
            self.assertEqual(r.state.properties['a']['hp'], 5 * (1 << 33))

    def test_policy_is_hashed_and_invocation_unknown_gaps(self):
        r = self.runtime(ability('root', call(), finish()), children={'child': ability('child')})
        c = r.clone(); c.policies[POLICY_ID]['invocation']['rng'] = 'NATIVE_UNKNOWN'
        self.assertNotEqual(r.stable_hash(), c.stable_hash())
        self.assertEqual(c.step('root').status, ExecutionStatus.SEMANTIC_GAP)

    def test_replay_same_state_policy_rng_and_hash(self):
        choice = task('random', 'random_choice', choices=[write('one', 1), write('two', 2)])
        r = self.runtime(ability('root', choice, wait(), finish()))
        a, results = r.replay(['root', 'root'])
        b, results2 = r.replay(['root', 'root'])
        self.assertEqual(a.stable_hash(), b.stable_hash())
        self.assertEqual(a.state.rng.draws, 2)
        self.assertEqual([x.status for x in results], [ExecutionStatus.ACTION_REFERENCE_COMPLETE] * 2)
        self.assertEqual([x.status for x in results], [x.status for x in results2])

    def test_every_checkpoint_restores_same_suffix(self):
        root = ability('root', call(), event('e', 'event'), wait(), finish())
        for budget in range(1, 24):
            r = self.runtime(root, children={'child': ability('child', wait())}, events={'event': [wait('callback-wait', 3)]})
            r.start_action('root'); r.run_until_blocked(budget)
            self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)

    def test_persistent_modifier_does_not_keep_action_open(self):
        from hsr_battle_agent.battle_runtime.behavior_state import ModifierInstance
        r = self.runtime(ability('root', finish()))
        r.state.modifiers['persistent'] = ModifierInstance('persistent', 'config', 'a', 'a', 'a', 1, 1, {'future_turns': 100})
        self.assertEqual(r.step('root').status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertIn('persistent', r.state.modifiers)

    def test_movement_requires_position_and_is_transactional(self):
        node = task('move', 'RPG.GameCore.MoveToTargetList')
        r = self.runtime(ability('root', node, finish()), policy=lambda p: p['presentation'].update(MoveToTargetList={
            'classification': 'POSITION_RELEVANT_REFERENCE', 'positions': {'a': [1, 2], 'b': [3, 4]}, 'duration_raw': 4}))
        r.state.entities['a']['position'] = [0, 0]
        self.assertEqual(r.step('root').status, ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(r.state.entities['a']['position'], [0, 0])
        r.state.entities['b']['position'] = [0, 0]
        self.assertEqual(r.run_until_blocked().status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(r.state.entities['a']['position'], [1, 2])
        self.assertEqual(self.data(r)['logical_time'], 4)

    def test_explicit_bitmap_operand_binding(self):
        n = UnsupportedSemanticIR('wait', 'RPG.GameCore.WaitSecond', A, {'fields': {'unbound_bit_0': expr(10, True)},
            'reference_binding': {'unknown_slots': [{'field_index': 0, 'mask': 2}], 'roles': {}}, 'required_capability': 'wait'})
        r = self.runtime(ability('root', n, finish()), policy=lambda p: p['role_bindings'].update({n.op: {'slots': {'2': 'duration'}}}))
        self.assertEqual(r.step('root').status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(self.data(r)['logical_time'], 10)

    def test_modifier_listener_order_owner_and_nested_event(self):
        from hsr_battle_agent.battle_runtime.behavior_state import ModifierInstance
        r = self.runtime(ability('root', task('dispatch', 'modifier_event_dispatch', event_id=12), finish()),
                         events={'nested': [write('nested-result', 6)]})
        r.policies['r13_reference_v1']['event_callbacks'] = 'ORDERED_OWNER_CONTEXT_REFERENCE_V1'
        def registration(order, callback):
            return {'event_id': 12, 'order': order, 'callback': callback.to_dict(), 'mutation_result': 'NORMAL_GENERIC_TASK_EXECUTION'}
        r.state.modifiers['z'] = ModifierInstance('z', 'config-z', 'b', 'a', 'a', 1, 1, {},
            event_registrations=[registration(2, write('last', 4))])
        r.state.modifiers['a'] = ModifierInstance('a', 'config-a', 'a', 'b', 'b', 1, 1, {},
            event_registrations=[registration(1, event('nested-event', 'nested'))])
        self.assertEqual(r.step('root').status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        callbacks = sorted(self.data(r)['callbacks'].values(), key=lambda c: c['enqueue_order'])
        self.assertEqual(callbacks[0]['context']['modifier_owner'], 'a')
        self.assertEqual(callbacks[0]['context']['caster'], 'b')
        self.assertEqual(callbacks[1]['context']['modifier_owner'], 'b')
        self.assertEqual(r.state.properties['a']['x'] // 2, 6)
        self.assertTrue(all(c['action_root_id'] == self.data(r)['current_root'] for c in callbacks))

    def test_frame_value_contracts(self):
        from hsr_battle_agent.battle_runtime.action_scheduler import (TaskFrame, SequenceFrame,
            AbilityExecution, ChildAbilityFrame, Barrier, ScheduledContinuation, CallbackFrame,
            CompletionRequest, ActionExecutionRoot)
        for cls in (TaskFrame, SequenceFrame, AbilityExecution, ChildAbilityFrame, Barrier,
                    ScheduledContinuation, CallbackFrame, CompletionRequest):
            f = cls('frame', 'action', 'ability', 'task', None, None, 'ability')
            restored = cls.from_snapshot(json.loads(json.dumps(f.snapshot())))
            self.assertEqual(f.stable_hash(), restored.stable_hash())
            self.assertEqual(f.stable_hash(), f.clone().stable_hash())
        f = ActionExecutionRoot('action', 'planner-action', 'ability', POLICY_ID)
        self.assertEqual(f.stable_hash(), f.clone().stable_hash())

    def test_movement_cannot_be_discarded_by_instant_policy(self):
        r = self.runtime(ability('root', task('move', 'RPG.GameCore.MoveToTargetPosition'), finish()),
            policy=lambda p: p['presentation'].update(MoveToTargetPosition={'classification': 'PRESENTATION_INSTANT_REFERENCE'}))
        result = r.step('root')
        self.assertEqual(result.status, ExecutionStatus.SEMANTIC_GAP)
        self.assertIn('POSITION', result.gap.required_capability)

    def test_nested_callback_owns_fire_child_tree(self):
        r = self.runtime(ability('root', event('event', 'child-call'), finish()),
            children={'child': ability('child', wait(), write('child-effect', 6))},
            events={'child-call': [call()]}, mode='FIRE_AND_CONTINUE_REFERENCE')
        r.start_action('root'); r.run_ready()
        callback = next(iter(self.data(r)['callbacks'].values()))
        self.assertEqual(callback['status'], 'RUNNING')
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(r.state.properties['a']['x'] // 2, 6)

    def test_event_enqueue_budget_is_resumable(self):
        r = self.runtime(ability('root', event('dispatch', 'many'), finish()),
                         events={'many': [write('one', 2), write('two', 4), write('three', 6)]})
        r.start_action('root')
        result = r.run_until_blocked(WorkBudget(max_callbacks=1))
        self.assertEqual(result.status, ExecutionStatus.EXECUTION_BUDGET_EXHAUSTED)
        self.assertEqual(len(self.data(r)['callbacks']), 1)
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)

    def test_invalid_logical_durations_rollback(self):
        for duration in (-2, True, 1.5):
            r = self.runtime(ability('root', task('wait', 'RPG.GameCore.WaitSecond', roles={'duration': expr(duration, True)}), finish()))
            self.assertEqual(r.step('root').status, ExecutionStatus.SEMANTIC_GAP)
            self.assertFalse(self.data(r)['barriers'])

    def test_zero_child_budget_allows_linear_root(self):
        r = self.runtime(ability('root', finish()))
        r.start_action('root')
        self.assertEqual(r.run_until_blocked(WorkBudget(max_child_invocations=0)).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)

    def test_completion_is_scoped_to_action_ownership(self):
        r = self.runtime(ability('root', finish()))
        r.start_action('root')
        from hsr_battle_agent.battle_runtime.action_scheduler import CallbackFrame
        from dataclasses import asdict
        d = self.data(r)
        d['callbacks']['unrelated'] = asdict(CallbackFrame('unrelated', 'different-action', 'different-ability', None, None, None, 'different-ability'))
        d['callback_queue'].append('unrelated')
        self.assertEqual(r.run_until_blocked().status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(self.data(r)['callback_queue'], ['unrelated'])
        r.start_action('root')
        self.assertEqual(self.data(r)['callback_queue'], ['unrelated'])
        self.assertEqual(r.run_until_blocked().status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)

    def test_root_callback_finish_requests_owned_ability_completion(self):
        r = self.runtime(ability('root', event('dispatch', 'end-event')),
                         events={'end-event': [finish(), wait(), write('settlement', 6)]})
        r.start_action('root'); r.run_ready()
        d = self.data(r)
        self.assertTrue(d['roots'][d['current_root']]['completion_requested'])
        self.assertEqual(d['roots'][d['current_root']]['status'], 'RUNNING')
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(r.state.properties['a']['x'] // 2, 6)

    def test_step_accepts_work_budget_and_retains_pending_root(self):
        r = self.runtime(ability('root', finish()))
        self.assertEqual(r.step('root', budget=WorkBudget(max_total_transitions=0)).status, ExecutionStatus.EXECUTION_BUDGET_EXHAUSTED)
        self.assertEqual(self.assert_resume(r).status, ExecutionStatus.ACTION_REFERENCE_COMPLETE)

if __name__ == '__main__':
    unittest.main()
