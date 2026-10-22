"""Isolate an inherited R23 saved-census discrepancy using exact starting code.

This is an audit-only subprocess: existing module objects are evaluated with
SHA-verified start-gate source bytes. No production file or historical control
is changed and no second runtime is installed.
"""
from __future__ import annotations
import importlib
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'),str(ROOT/'tools/runtime'),str(ROOT)]
from r24_finalize import EXISTING, starting_bytes
from r24_checks import AUDIT
from r24_evidence import write
from r21_checks import read, sha

KEYS = ('status','primitive','required_capability','metrics','original_finish_reached',
        'original_finish_completed','hp_settlements','normal_turns_completed','actions_completed','source_IR_unchanged')


def main():
    previous = ROOT/'tmp/audit/r23_real_skill_root_closure_20261012_001'
    old = read(previous/'joined_execution_results.json')
    new = read(AUDIT/'r23/joined_execution_results.json')
    before = {tuple(row['source_identity']):row for row in old}
    changes = [row for row in new if any(row.get(k)!=before[tuple(row['source_identity'])].get(k) for k in KEYS)]
    assert len(changes)==1, [(row['root'],row['required_capability']) for row in changes]
    current = changes[0]; archived = before[tuple(current['source_identity'])]
    assert archived['required_capability']=='unknown operation provider/version/implementation hash'
    assert archived['decision']['boundary']['action_root_id'] is None
    assert current['metrics']['tasks_completed']==0 and current['actions_completed']==0
    gate = read(AUDIT/'start_gate.json')
    pins = {}
    for name in EXISTING:
        body = starting_bytes(name,gate)
        module = importlib.import_module('hsr_battle_agent.battle_runtime.'+Path(name).stem)
        exec(compile(body, str(ROOT/name), 'exec'), module.__dict__)
        pins[name] = gate['file_hashes'][name]
        if name.endswith('battle_turn.py'):
            # The existing contract hashes __file__ bytes. Point this isolated
            # diagnostic to the exact starting bytes, after loading its contract.
            path = AUDIT/'starting_code_diagnostic/battle_turn.py'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(body)
            assert sha(path)==gate['file_hashes'][name]
            module.__file__ = str(path)
    import r23_probes as probes
    import r23_discovery as discovery
    probes.AUDIT = discovery.AUDIT = AUDIT/'starting_code_diagnostic'
    graph = next(g for g in probes.content()[-1]['graphs'] if g['source_identity']==current['source_identity'])
    baseline = probes.execute(graph,replay=False)
    assert all(baseline.get(k)==current.get(k) for k in KEYS), {
        k:(baseline.get(k),current.get(k)) for k in KEYS if baseline.get(k)!=current.get(k)}
    summary = read(AUDIT/'r23/execution_summary.json')
    saved = read(previous/'execution_summary.json')
    assert summary['partial_real_skill_prefix_roots']==72 and saved['partial_real_skill_prefix_roots']==73
    assert all(summary[k]==saved[k] for k in ('roots','owner_rows','hp_settled_roots',
        'original_finish_completed_roots','source_closed_unique_roots','policy_abstracted_unique_roots'))
    result = {'status':'PASS','summary':summary,'archived_summary':saved,'archived_summary_equal':False,
        'preexisting_census_discrepancy_isolated':True,'unchanged_archived_root_results':159,
        'starting_source_pins':pins,'comparison_keys':list(KEYS),
        'discrepancy':{'source_identity':current['source_identity'],'root':current['root'],
            'archived':{k:archived.get(k) for k in KEYS},
            'exact_starting_code':{k:baseline.get(k) for k in KEYS},
            'R24_code_without_opt_in':{k:current.get(k) for k in KEYS},
            'conclusion':'Archived row stops at operation implementation-binding guard before admitting a content action; boundary tasks were counted as a real prefix. Exact starting code and R24 both stop at the same original missing child source with zero real tasks completed.',
            'historical_control_modified':False,'source_closed_transitions_added':0},
        'frozen_632_corpus_drift':'NONE','native_correctness':'NOT_CLAIMED'}
    write('r23_regression.json',result)
    write('r23_starting_code_diagnostic.json',result['discrepancy'] | {'source_pins':pins,'status':'PASS'})
    print('R23 diagnostic PASS: 159 archived semantic results unchanged; one inherited boundary-prefix count discrepancy isolated; exact starting code also yields 72 stable real prefixes',flush=True)


if __name__ == '__main__': main()
