"""Executable R22 A-L public API traces, clone checks and external replay receipts."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime'),str(ROOT)]
from hsr_battle_agent.battle_ir.behavior import stable_hash
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.battle_turn import KEY,ADAPTER,TurnBudget
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE,reference_policy as resource_policy
from r20_reference_fixtures import resource_spec
from r22_reference_fixtures import runtime,source_ref,insertion
from r22_real_fixtures import real_runtime,REAL_ROOTS
from tests.battle_runtime.test_behavior_r15 import ability,finish,task,expr,write
from tests.battle_runtime.test_behavior_r20 import R20Tests

AUDIT=ROOT/'tmp/audit/r22_global_turn_engine_20261011_001'

def write_json(name,value):
    path=AUDIT/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


class Trace:
    def __init__(self,name,r,bindings,p,providers):
        self.name,self.r=name,r
        self.initial=r.clone();self.receipts=[];self.observed=[];self.checkpoints=[]
        self.snapshot_check('idle_before_initialize')
        self.command('initialize',participant_bindings=bindings,policy=p,provider_contracts=providers)
        self.snapshot_check('ready_queue')

    def snapshot_check(self,label):
        clone=self.r.clone();restored=BehaviorRuntime.from_snapshot(json.loads(json.dumps(self.r.snapshot())))
        assert clone.stable_hash()==self.r.stable_hash()==restored.stable_hash()
        self.checkpoints.append({'label':label,'hash':self.r.stable_hash(),'clone_restore':'PASS'})

    def command(self,command_kind,**arguments):
        receipt,result=self.r.record_turn_command(command_kind,arguments)
        self.receipts.append(receipt)
        if hasattr(result,'kind'):
            self.observed.append({'kind':result.kind,'actor_id':result['actor_id'],'owner':self.r.current_turn_owner(),
                                  'clock':copy.deepcopy(self.r.state.mechanics[KEY]['clock']['now'])})
        return result

    def advance(self,**args):return self.command('advance',budget=args or 10000)
    def submit(self,boundary=None):
        boundary=boundary or self.r.run_until_decision()
        p=self.r.legal_action_candidates(boundary['decision_id'])[0]
        self.command('submit',permission=p,targets=p['target_ids'],expected_revision=boundary['state_revision'])
        self.snapshot_check('active_action_admitted')
    def complete(self):return self.command('complete',budget=10000)

    def finish(self,expected):
        replay,outputs=self.initial.replay_turn_commands(self.receipts)
        assert replay.stable_hash()==self.r.stable_hash() and replay.snapshot()==self.r.snapshot()
        self.snapshot_check('final_boundary')
        s=self.r.state.mechanics[KEY];adapter=self.r.state.mechanics[ADAPTER]
        row={'id':self.name,'authority':'REFERENCE_MODEL','native_validation':False,'PASS':True,
             'expected':expected,'observed_decisions':self.observed,'normal_turns_completed':s['normal_turn_count'],
             'actions_completed':s['action_count'],'decisions_produced':len(adapter['decision_history']),
             'clock':s['clock']['now'],'hp':{k:v.get('hp') for k,v in self.r.state.properties.items()},
             'actor_resources':self.r.state.actor_resources,'team_resources':self.r.state.team_resources,
             'modifier_state':{k:vars(v) for k,v in self.r.state.modifiers.items()},
             'event_order':[x['kind'] for x in adapter['event_history']],
             'rng_draws':self.r.state.rng.draws,'full_runtime_hash':self.r.stable_hash(),
             'full_hash_replay':'PASS','snapshots':self.checkpoints,'command_receipt_file':self.name+'/commands.json',
             'full_joined_skill_transitions':0}
        write_json(self.name+'/commands.json',self.receipts)
        write_json(self.name+'/initial_runtime.json',self.initial.snapshot())
        write_json(self.name+'/final_runtime.json',self.r.snapshot())
        write_json(self.name+'/receipt.json',row)
        print(self.name,'PASS',s['normal_turn_count'],'normal turns',flush=True)
        return row


def make(name,**kwargs):
    r,b,p,providers=runtime(initialize=False,**kwargs)
    return Trace(name,r,b,p,providers)


def main():
    rows=[]
    t=make('A_two_actors_two_actions');b=t.advance();assert b['actor_id']=='b'
    t.submit(b);b=t.complete();assert b['actor_id']=='a'
    t.submit(b);b=t.complete();assert b['actor_id']=='b'
    rows.append(t.finish({'actor_order':['b','a','b'],'clock':[50,100,100],'completed_actions':2}))
    t=make('B_three_actors',speeds=(('a',100),('b',125),('c',200)))
    order=[]
    for _ in range(3):
        b=t.advance();order.append(b['actor_id']);t.submit(b);t.complete()
    assert order==['c','b','a'];rows.append(t.finish({'first_actors':['c','b','a']}))
    t=make('C_equal_readiness',speeds=(('a',100),('b',100)))
    b=t.advance();assert b['actor_id']=='a';t.submit(b);b=t.complete();assert b['actor_id']=='b'
    t.submit(b);t.complete();rows.append(t.finish({'actor_order':['a','b','a'],'tie_break':'registration ordinal'}))
    r,bindings,p,providers=runtime(initialize=False,speeds=(('a',100),('b',400)))
    providers['external_events']['explicit.speed']={'authority':'EXPLICIT_SCENARIO_INPUT','source':'explicit speed effect'}
    r.events['explicit.speed']=[task('speed-effect','property_write',owner='a',key='speed',operation='set',value=expr(200*SCALE,True))]
    t=Trace('D_waiting_speed_rebase',r,bindings,p,providers);t.advance()
    t.command('modifier_event',event_key='explicit.speed',payload={'actor_id':'a'});t.advance()
    t.command('speed_change',actor_id='a',provider_revision=1)
    assert r.state.mechanics[KEY]['initiative']['a']['due_at']=={'n':125,'d':2}
    rows.append(t.finish({'now':{'n':25,'d':1},'a_due_after_rebase':{'n':125,'d':2}}))
    r,bindings,p,providers=runtime(initialize=False);t=Trace('E_advance_delay',r,bindings,p,providers);t.advance()
    ref=source_ref(providers);actual=[]
    for kind,fraction in [('ADVANCE',{'n':1,'d':2}),('DELAY',{'n':1,'d':4}),('ADVANCE',{'n':2,'d':1})]:
        actual.append(t.command('adjust',actor_id='a',kind=kind,fraction=fraction,source_ref=ref))
    assert actual==[{'n':n,'d':1} for n in [50,75,50]]
    rows.append(t.finish({'due_sequence':actual,'basis':'FULL_CURRENT_INTERVAL'}))
    t=make('F_post_settle_insertions',root=ability('explicit-finished',finish()));b=t.advance();t.submit(b)
    for category in ['EXTRA_TURN','FOLLOW_UP_ACTION']:
        t.command('insertion',insertion=insertion(t.r,actor='a',category=category))
    due=copy.deepcopy(t.r.state.mechanics[KEY]['initiative']['a']['due_at']);order=[]
    for _ in range(2):
        b=t.complete();assert b.kind=='OUT_OF_TURN_WINDOW'
        order.append(t.r.state.mechanics[KEY]['active_stack'][-1]['category'])
        assert t.r.current_turn_owner()=='b' and t.r.state.mechanics[KEY]['initiative']['a']['due_at']==due
        t.submit(b)
    t.complete();assert order==['FOLLOW_UP_ACTION','EXTRA_TURN']
    rows.append(t.finish({'inserted_order':order,'normal_AV_consumed':False,'normal_turn_count':1}))
    r,bindings,p,providers=runtime(initialize=False,root=ability('explicit-finished',finish()),durations={
        'initial':{'units':'OWNER_NORMAL_TURN_END_REFERENCE','creation':'SKIP_CREATION_TURN_REFERENCE',
                   'expiry_event':'explicit.expiry','pending_callbacks':'RETAIN_ENQUEUED_REFERENCE'}})
    r.policies[RESOURCE]=resource_policy();r.policies[RESOURCE]['bindings']['counter']=resource_spec()
    callback=task('turn-end-resource','resource_write',scope='actor',owner='b',key='reference_actor_counter',operation='add',value=expr(SCALE,True))
    m=R20Tests().listener(r,callback,event=p['boundary_event_keys']['TURN_END'],owner='b');m.duration['remaining']=1
    expiry=copy.deepcopy(m.event_registrations[0]);expiry.update(registration_id='initial/expiry',event_id='explicit.expiry',callback=write('expiry',9).to_dict())
    m.event_registrations.append(expiry)
    t=Trace('G_modifier_duration_callbacks',r,bindings,p,providers);t.advance();t.submit();t.complete()
    assert 'initial' not in r.state.modifiers and r.state.actor_resources['b']['reference_actor_counter']==5*SCALE
    assert r.state.properties['a']['x']==18
    rows.append(t.finish({'turn_end_callbacks':1,'expiry_callbacks':1,'resource_after':5*SCALE,'expiry':'drained before removal'}))
    t=make('H_defeated_before_due');t.command('lifecycle',actor_id='b',operation='DEFEAT',
        source_ref={'authority':'EXPLICIT_SCENARIO_INPUT','source':'explicit defeat provider output'})
    assert t.advance()['actor_id']=='a';rows.append(t.finish({'actor_selected':'a','defeated_actor':'b','stale_generation_skipped':True}))
    r,bindings,p,providers=runtime(initialize=False,controllers={'b':'MONSTER_AI'})
    providers['monster_decision']={'provider_id':'explicit-monster-selection','version':'1','authority':'REFERENCE_MODEL','mode':'FIRST_PERMISSION_REFERENCE'}
    t=Trace('I_enemy_provider',r,bindings,p,providers);assert t.advance().kind=='ENEMY_AI_DECISION'
    t.command('enemy');assert t.complete()['actor_id']=='a'
    rows.append(t.finish({'provider':'explicit-monster-selection','native_monster_AI':False}))
    r,bindings,p,providers=runtime(initialize=False,stage='WAVE_PENDING');t=Trace('J_pending_wave',r,bindings,p,providers)
    assert t.advance().kind=='SEMANTIC_GAP' and not r.is_terminal()
    t.command('stage',status='RUNNING',source_ref={'provider_id':providers['stage']['provider_id'],'policy_hash':stable_hash(providers['stage'])})
    assert t.advance().kind=='PLAYER_NORMAL_TURN'
    rows.append(t.finish({'wave_pending_is_terminal':False,'explicit_stage_transition':'required'}))
    t=make('K_active_R15_gap',root=ability('original-synthetic-gap',task('opaque','unimplemented-reference-source'),finish()))
    t.advance();t.submit();assert t.complete().kind=='SEMANTIC_GAP'
    assert t.r.current_turn_owner()=='b' and t.r.state.mechanics[KEY]['clock']['now']=={'n':50,'d':1}
    before=t.r.stable_hash();t.advance();assert before==t.r.stable_hash()
    rows.append(t.finish({'owner':'b','AV_frozen_at':{'n':50,'d':1},'normal_turns_completed':0}))
    for index,name in enumerate(REAL_ROOTS):
        r,graph,bindings,p,providers=real_runtime(name,initialize=False)
        t=Trace('L'+str(index+1)+'_real_ability',r,bindings,p,providers)
        original=r.actions['real'].stable_hash();hp_before=r.state.properties['b']['hp']
        for _ in range(2):
            b=t.advance();assert b['actor_id']=='a';t.submit(b);assert t.complete().kind=='PLAYER_NORMAL_TURN'
        assert r.actions['real'].stable_hash()==original and r.state.properties['b']['hp']<hp_before
        assert r.state.actor_resources['a']['reference_actor_counter']==4*SCALE
        row=t.finish({'root':name,'source_IR_hash':original,'original_finish_nodes_only':True,
                      'hp_changed':True,'resource_changed':True,'skill_joined':False,'completed_actions':2})
        row['real_content_root']=name;row['IR_artifact']=graph['IR_artifact'];row['source_IR_hash']=original
        rows.append(row)
    write_json('execution_traces.json',{'schema':'r22_public_api_execution_traces/1','traces':rows,
        'required_trace_groups':12,'passed_trace_groups':12,'real_ability_cases':3,'native_validation':False})
    write_json('execution_summary.json',{'normal_turns_completed':sum(x['normal_turns_completed'] for x in rows),
        'actions_completed':sum(x['actions_completed'] for x in rows),'decisions_produced':sum(x['decisions_produced'] for x in rows),
        'full_real_skill_transitions':0,'real_ability_action_completions':6,'executable_traces':len(rows),
        'required_groups':'12/12','determinism':'PASS','snapshot_replay':'PASS','native_equivalence':'NOT_CLAIMED'})


if __name__=='__main__':main()
