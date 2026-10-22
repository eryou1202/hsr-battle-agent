"""Execute P01-P20 once, retain asserted observations and replays in R26 audit."""
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tools/runtime')]
from r26_checks import AUDIT
from tests.battle_runtime.test_behavior_r26 import R26Scenarios,R26Contracts,cached,comparison

def write(name,doc):
    p=AUDIT/name; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(doc,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')

def main(only=None):
    rows=json.loads((AUDIT/'functional_scenarios.json').read_text(encoding='utf-8'))['scenarios'] if only else []
    rows=[r for r in rows if r['id'] not in (only or [])]
    for name in unittest.defaultTestLoader.getTestCaseNames(R26Scenarios):
        if only and name.split('_')[1] not in only:continue
        case=R26Scenarios(name); result=unittest.TestResult(); case.run(result)
        identity=name.split('_')[1]; observation=getattr(case,'observation',{})
        row={'id':identity,'test':name,'PASS':result.wasSuccessful(),'failures':[s for _,s in result.errors+result.failures]}
        if observation:
            write(identity+'/observation.json',observation)
            if 'result' in observation:
                d=observation['result']; write(identity+'/result.json',d)
                row.update({'counts':d['counts'],'completed_rollouts':d['completed_rollouts'],
                    'incomplete_rollouts':d['incomplete_rollouts'],'truncated_rollouts':d['truncated_rollouts'],
                    'semantic_gap_branches':len(d['semantic_gaps']),'depth':d['search_depth'],
                    'chosen_action':d['chosen_action'],'status':d['status']})
        rows.append(row); rows.sort(key=lambda x:x['id'])
        write('functional_scenarios.json',{'required':20,'passed':sum(x['PASS'] for x in rows),'scenarios':rows})
        print(identity,'PASS' if row['PASS'] else 'FAIL',flush=True)
        if not result.wasSuccessful(): print('\n'.join(row['failures']),flush=True)
    extra=unittest.TestResult(); unittest.defaultTestLoader.loadTestsFromTestCase(R26Contracts).run(extra)
    write('contract_tests.json',{'tests':extra.testsRun,'PASS':extra.wasSuccessful(),'failures':[s for _,s in extra.failures+extra.errors]})
    assert len(rows)==20 and all(x['PASS'] for x in rows) and extra.wasSuccessful()
    # A second independent benchmark is required in addition to the P04 comparison.
    from hsr_battle_agent.battle_runtime.planner_bridge import replay_principal_variation
    for kind,identity in ([] if only else [('choice','P01'),('resource','P03')]):
        r,d,_=cached(kind)
        write(identity+'/initial_runtime.json',r.snapshot()); write(identity+'/result.json',d)
        write(identity+'/final_runtime.json',replay_principal_variation(r,d).snapshot())
    if not only:
        first=comparison('choice')
        second=json.loads((AUDIT/'P04/observation.json').read_text(encoding='utf-8'))['comparative_benchmarks']
        assert first[0]['terminal']['result']=='DEFEAT' and first[2]['terminal']['result']=='VICTORY'
        write('comparative_benchmarks.json',{'choice':first,'resource':second,'same_input_per_comparison':True,
            'evaluation_player_decision_cap':4,'one_step_greedy':'Replan one action at a time under identical scoring/opponent and evaluation cap'})
    count_keys=next(row['counts'] for row in rows if 'counts' in row)
    write('execution_summary.json',{'required':20,'passed':20,'aggregate_scope':'One recorded result per P scenario; shared cached searches can recur in scenario observations. Not unique executions.',
        'counts':{k:sum(row.get('counts',{}).get(k,0) for row in rows) for k in count_keys},
        'completed_rollouts':sum(row.get('completed_rollouts',0) for row in rows),
        'incomplete_rollouts':sum(row.get('incomplete_rollouts',0) for row in rows),
        'truncated_rollouts':sum(row.get('truncated_rollouts',0) for row in rows),
        'semantic_gap_branches':sum(row.get('semantic_gap_branches',0) for row in rows),
        'source_closed_joined_skills':0,'native_validated_planning':0})

if __name__=='__main__':main(sys.argv[2:] if sys.argv[1:2]==['--only'] else None)
