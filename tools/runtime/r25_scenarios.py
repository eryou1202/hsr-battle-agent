"""Execute asserted E01-E18 and store snapshots, command replays and receipts."""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'tools/runtime')]
from r25_checks import write
from tests.battle_runtime.test_behavior_r25 import R25Scenarios

def branches():
    from r25_reference_fixtures import setup, complete
    from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
    r, _, _ = setup(waves=1)
    first = r.run_until_encounter_boundary({'decision_transitions': 1, 'scheduler_work': 1})
    assert first.kind == 'BUDGET_YIELD'
    start = r.stable_hash()
    rows = []
    for i, branch in enumerate((r.clone(), r.clone(), BehaviorRuntime.from_snapshot(r.snapshot()))):
        boundary = complete(branch)
        assert boundary.kind == 'BATTLE_TERMINAL'
        rows.append({'branch': i, 'result': branch.encounter_result()['result'], 'hash': branch.stable_hash(),
            'stage_events': len(branch.current_encounter()['events']),
            'actions': branch.state.mechanics['battle_turn_v1']['action_count']})
    assert len({row['hash'] for row in rows}) == 1 and r.stable_hash() == start
    write('independent_budgeted_branches.json', {'status': 'PASS', 'branches': rows,
        'initial_boundary': first.kind, 'initial_hash': start, 'parent_unchanged': True})
    return rows

def listener():
    from r25_reference_fixtures import setup, complete
    from r18_reference_fixtures import reference_listener
    from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID as DAMAGE
    from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
    from tests.battle_runtime import test_behavior_r15 as ir
    r, _, _ = setup()
    r.policies[DAMAGE] = {'tasks': {}}
    callback = ir.TaskSequenceIR('r25-stage-listener', 'immediate_sequence', ir.A,
        {'tasks': [ir.wait('owned-stage-wait'), ir.write('owned-stage-write', 17)]})
    reference_listener(r, callback, event_id='reference.encounter.before_wave_transition', identity='r25-stage-listener')
    R25Scenarios().submit(r)
    for _ in range(240):
        b = r.run_until_encounter_boundary({'decision_transitions': 1, 'scheduler_work': 1})
        assert b.kind != 'SEMANTIC_GAP', b
        if any(x['status'] not in ('CALLBACK_COMPLETE', 'CALLBACK_CANCELLED_REFERENCE')
               for x in r.state.scheduler.action_execution.get('callbacks', {}).values()): break
    else: raise AssertionError('pending R17 stage callback not reached')
    assert r.state.properties['a']['x'] == 0 and r.state.mechanics['battle_turn_v1']['stage']['wave_index'] == 0
    assert not r.state.entities['b']['alive']  # Listener survives defeat of its original owner.
    checkpoint = r.snapshot(); restored = BehaviorRuntime.from_snapshot(checkpoint)
    assert complete(r).kind == complete(restored).kind == 'BATTLE_TERMINAL'
    assert r.snapshot() == restored.snapshot() and r.state.properties['a']['x'] == 34
    event = next(x for x in r.current_encounter()['events'] if x['kind'] == 'BEFORE_WAVE_TRANSITION')
    assert event['listener_ids'] == ['r25-stage-listener/registration']
    write('r17_pending_stage_callback.json', checkpoint)
    write('r17_stage_callback_receipt.json', {'status': 'PASS', 'final_hash': r.stable_hash(),
        'callback_value': 34, 'listener_owner_defeated_before_callback': True, 'snapshot_suffix_equal': True,
        'listener_ids': event['listener_ids'], 'wave_index': r.state.mechanics['battle_turn_v1']['stage']['wave_index']})

def main(only=None):
    from r21_checks import read
    from r25_checks import AUDIT
    previous = read(AUDIT/'functional_scenarios.json')['scenarios'] if only else []
    rows = [r for r in previous if r['id'] not in (only or [])]
    for name in unittest.defaultTestLoader.getTestCaseNames(R25Scenarios):
        if only and name.split('_')[1] not in only: continue
        case = R25Scenarios(name); result = unittest.TestResult(); case.run(result)
        identity = name.split('_')[1]
        observation = getattr(case, 'observation', None)
        row = {'id': identity, 'test': name, 'PASS': result.wasSuccessful(),
            'failures': [text for _, text in result.failures+result.errors]}
        if observation:
            write(identity+'/final_runtime.json', observation.pop('snapshot'))
            write(identity+'/receipt.json', observation)
            row.update({k: observation[k] for k in ('cohort', 'state_hash', 'actions', 'waves_completed', 'phase')})
            row['terminal_result'] = observation['terminal_receipt']['result'] if observation['terminal_receipt'] else None
        if hasattr(case, 'command_receipts'):
            write(identity+'/commands.json', case.command_receipts)
            write(identity+'/initial_runtime.json', case.initial_snapshot)
        rows.append(row)
        rows.sort(key=lambda x: x['id'])
        write('functional_scenarios.json', {'required': 18, 'passed': sum(x['PASS'] for x in rows), 'scenarios': rows})
        print(identity, 'PASS' if row['PASS'] else 'FAIL', flush=True)
    assert len(rows) == 18 and all(x['PASS'] for x in rows), [x for x in rows if not x['PASS']]
    write('execution_summary.json', {'required': 18, 'passed': 18,
        'actions': sum(x['actions'] for x in rows), 'waves_completed': sum(x['waves_completed'] for x in rows),
        'terminal_outcomes': {k: sum(x['terminal_result'] == k for x in rows) for k in ('VICTORY', 'DEFEAT', 'ABORTED')},
        'cohorts': {k: sum(x['cohort'] == k for x in rows) for k in ('PURE_REFERENCE_ENCOUNTER', 'REAL_PRIMITIVE_REFERENCE_ENCOUNTER')},
        'count_basis': 'Required E01-E18 only; checkpoint/gap scenarios can intentionally stop before terminal',
        'source_closed_joined_skills': 0, 'native_equivalence': 'NOT_CLAIMED'})

if __name__ == '__main__':
    if '--branches-only' in sys.argv: branches()
    elif '--listener-only' in sys.argv: listener()
    elif '--only' in sys.argv: main(sys.argv[sys.argv.index('--only')+1:])
    else:
        main()
        branches()
        listener()
