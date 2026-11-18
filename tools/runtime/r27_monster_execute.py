"""Admit unchanged exact Monster roots through R20, R22 enemy provider and R15."""
import copy
from r27_checks import ROOT,AUDIT,write,read,sha
import sys
sys.path.insert(0,str(ROOT))
from r13_frozen_reader import SNAPSHOT,MANIFEST_SHA
from r13_reference_fixtures import fixture
from r19_reference_fixtures import extend as property_extend
from r20_reference_fixtures import actor_binding
from r22_reference_fixtures import inputs
from hsr_battle_agent.battle_ir.behavior import IRNode,walk_nodes
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState
from hsr_battle_agent.battle_runtime.actor_binding import ActorRuntimeBinding,source_reference,supplied,reference_policy
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE

def runtime(join):
    records=read(AUDIT/'monster/root_records.json')
    compiled={r['identity']:IRNode.from_dict(r['ir']) for r in records if r.get('ir')}
    ir=compiled[join['entry_ability']]
    original=read(ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001/joined_explicit_inputs.json')
    state=BehaviorBattleState.from_snapshot(original['state']);policies=copy.deepcopy(original['policies'])
    nodes=list({n.stable_hash():n for v in compiled.values() for n in walk_nodes(v)}.values())
    _,aliases,_=fixture({n.payload['alias'] for n in nodes if n.op=='RPG.GameCore.TargetAlias'})
    state,policies=property_extend(state,policies,nodes)
    state.target_context['current_ability']=join['entry_ability']
    r=BehaviorRuntime(state,actions={'original_monster':ir},abilities=compiled,aliases=aliases,policies=policies)
    actors=read(AUDIT/'monster/selected_actors.json')['actors']
    index=next(i for i,a in enumerate(actors) if a['monster_id']==join['monster_id'])
    actor=actors[index];path=AUDIT/'monster/selected_actors.json'
    content=source_reference(path,version='4.6.51',pointer_path='/actors/'+str(index),identity=join['monster_id'],
        kind='Monster',expected_sha256=sha(path))
    fi=next(i for i,f in enumerate(actor['graph']['fields']) if int(f['mask'])==16)
    content['identity_pointer']=f'/graph/fields/{fi}/values/0/value'
    content['version_evidence']=dict(artifact=str(SNAPSHOT/'SNAPSHOT_MANIFEST.json'),sha256=MANIFEST_SHA,
        version_pointer='/content_version',files_pointer='/files',record_shard_pointer='/source_shard',record_shard_hash_pointer='/source_shard_sha256')
    values=dict(level=1,promotion=0,rank=0,team='monsters',
        base_properties=dict(speed=200*SCALE,hp=100*SCALE,max_hp=100*SCALE,reference_atk=10*SCALE),
        actor_resources=dict(reference_actor_counter=0))
    binding=ActorRuntimeBinding('a','4.6.51',content,{k:supplied(v,'R27 explicit reference execution inputs; native effective state UNKNOWN') for k,v in values.items()}, {},reference_policy())
    r.bind_actor(binding)
    r.bind_actor(actor_binding('b',1001,base_properties=dict(speed=100*SCALE,hp=100*SCALE,max_hp=100*SCALE,reference_atk=10*SCALE)))
    participants,policy,providers=inputs(r,(('a',200),('b',100)),controllers={'a':'MONSTER_AI'})
    for p in participants:p['actor_binding']=None
    providers['availability']['actors']['a']['actions'][0]['target_ids']=['b']
    providers['availability']['actors']['b']['actions']=[]
    providers['monster_decision']=dict(provider_id='r27.exact_root_reference_permission',version='1',authority='REFERENCE_MODEL',mode='FIRST_PERMISSION_REFERENCE')
    r.initialize_turns(participants,policy,providers)
    return r,binding

def execute(join):
    r,binding=runtime(join);initial=r.clone();commands=[]
    def command(kind,**args):
        receipt,out=r.record_turn_command(kind,args);commands.append(receipt);return out
    decision=command('advance',budget=10000)
    assert decision.kind=='ENEMY_AI_DECISION'
    permission=r.legal_action_candidates(decision['decision_id'])[0]
    admitted=command('enemy')
    result=command('complete',budget=10000)
    replayed,_=initial.replay_turn_commands(commands)
    restored=BehaviorRuntime.from_snapshot(r.snapshot())
    assert replayed.snapshot()==r.snapshot()==r.clone().snapshot()==restored.snapshot()
    assert replayed.stable_hash()==r.stable_hash()==restored.stable_hash()
    execution=r.state.scheduler.action_execution
    diag=r.clone().run_until_blocked() if result.kind=='SEMANTIC_GAP' else None
    gap=diag.gap if diag else None
    name=str(join['monster_id'])+'_'+str(join['skill_id'])
    write('monster/execution/'+name+'/commands.json',commands)
    write('monster/execution/'+name+'/initial_runtime.json',initial.snapshot())
    write('monster/execution/'+name+'/final_runtime.json',r.snapshot())
    row=dict(monster_id=join['monster_id'],skill_id=join['skill_id'],root=join['entry_ability'],exact_join=join,
        actor_kind=r.state.entities['a']['content_kind'],actor_binding=binding.to_dict(),
        enemy_permission=permission,admission=admitted.to_dict() if hasattr(admitted,'to_dict') else admitted,boundary=result.to_dict(),
        action_reference_complete=r.state.mechanics['battle_turn_v1']['action_count']>0,
        executed_original_tasks=execution['metrics']['tasks_completed'],metrics=execution['metrics'],
        primitive=gap.task_type if gap else None,required_capability=gap.required_capability if gap else None,
        gap_node=gap.node if gap else None,source_IR_unchanged=r.actions['original_monster'].stable_hash()==join['canonical_IR_hash'],
        native_AI=False,decision_policy='FIRST_PERMISSION_REFERENCE; original AI not executed',
        full_runtime_hash=r.stable_hash(),state_hash=r.state.stable_hash(),turn_owner=r.current_turn_owner(),
        clone_snapshot_replay='PASS',native_correctness='NOT_CLAIMED')
    write('monster/execution/'+name+'/result.json',row)
    print('MONSTER',name,result.kind,'tasks',row['executed_original_tasks'],'next',row['required_capability'],flush=True)
    return row

def main():
    records=read(AUDIT/'monster/root_records.json')
    bykey={tuple((r['source_shard_sha256'],r['record_start'],r['record_end'])):r for r in records if r.get('ir')}
    rows=[]
    for join in read(AUDIT/'monster/exact_joins.json'):
        record=bykey.get(tuple(join['exact_root_identity'] or []))
        if record:
            join['canonical_IR_hash']=record['canonical_IR_hash']
            rows.append(execute(join))
    write('monster/execution_results.json',rows)

if __name__=='__main__':main()
