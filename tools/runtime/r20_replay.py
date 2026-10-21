"""Independent replay of every original graph resource prefix/completed action."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r20_checks import AUDIT,read,write
from r20_probes import R18
from r18_probes import load
from r19_probes import context
from r19_reference_fixtures import extend as r19_extend
from r20_reference_fixtures import extend
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState

def main():
    roots,_=load();nodes,aliases,abilities,templates=context(roots)
    bykey={tuple(g['source_identity']):(g,ir) for g,ir in roots}
    inputs=read(R18/'joined_explicit_inputs.json')
    state,policies=r19_extend(BehaviorBattleState.from_snapshot(inputs['state']),inputs['policies'],nodes)
    bindings={tuple(b['source_identity']):b['binding'] for b in read(AUDIT/'actor_cohort_inputs.json')}
    receipts=[]
    for row in read(AUDIT/'actor_cohort_results.json'):
        if not row['real_graph_resource_prefix'] and row['status']!='ACTION_REFERENCE_COMPLETE':continue
        g,ir=bykey[tuple(row['source_identity'])];b=bindings[tuple(row['source_identity'])];fields=b['fields']
        r=BehaviorRuntime(state,actions={'probe':ir},aliases=aliases,abilities=abilities,templates=templates,policies=policies)
        actual=extend(r,nodes,avatar_id=b['content']['identity'],level=fields['level']['value'],
                      promotion=fields['promotion']['value'],rank=fields['rank']['value'])
        assert actual.to_dict()==b
        r.state.target_context['current_ability']=g['record_identity'];initial=r.snapshot()
        r.start_action('probe');r.run_ready(7)
        engines=[r,r.clone(),BehaviorRuntime.from_snapshot(r.snapshot())]
        outcomes=[e.run_until_action_complete() for e in engines]
        assert outcomes[0]==outcomes[1]==outcomes[2]
        assert len({e.state.stable_hash() for e in engines})==1 and r.state.stable_hash()==row['final_battle_state_hash']
        replay,replayed=BehaviorRuntime.from_snapshot(initial).replay(['probe'])
        assert replayed[0].status==outcomes[0].status and replay.state.stable_hash()==r.state.stable_hash()
        if row['status']=='ACTION_REFERENCE_COMPLETE':
            assert any(t['node']['op']=='RPG.GameCore.SkillPerformFinish' and t['status']=='TASK_COMPLETE'
                       for t in r.state.scheduler.action_execution['tasks'].values())
        receipts.append({'root':row['root'],'source_identity':row['source_identity'],'status':row['status'],
            'real_graph_resource_prefix':row['real_graph_resource_prefix'],'full_joined_skill_transition':row['full_joined_skill_transition'],
            'snapshot_clone_resume':'PASS','independent_replay':'PASS','source_finish_inserted':False,
            'final_state_hash':r.state.stable_hash()})
        print('replay',row['root'],row['status'],flush=True)
    write('original_graph_replay.json',{'status':'PASS','roots':receipts})

if __name__=='__main__': main()
