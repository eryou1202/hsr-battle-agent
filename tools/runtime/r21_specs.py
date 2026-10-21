"""Executable POLICY-ONLY arithmetic/serialization specifications, not a battle engine.

Insertion/interrupt transcripts are contract-state traces, not executed R15
interrupts. The separate R15 compatibility probe exercises its real guard/drain.
"""
from __future__ import annotations
import copy
from fractions import Fraction
import json
import math
import sys
import unittest

from r21_checks import ROOT, AUDIT, read, write
from r21_contract import schemas, policy, contract, CATEGORIES, BOUNDARIES
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from hsr_battle_agent.battle_ir.behavior import stable_hash, canonical_json
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime

def q(value):
    f=Fraction(value)
    return {'n':f.numerator,'d':f.denominator}
def fq(value): return Fraction(value['n'],value['d'])
def interval(speed, distance=10000):
    if isinstance(speed,bool) or not isinstance(speed,(int,Fraction)) or speed<=0:
        raise ValueError('SPEED_PROVIDER_MISSING')
    return Fraction(distance)/speed
def rebase(now,due,old_speed,new_speed):
    interval(old_speed);interval(new_speed)
    return Fraction(now)+max(Fraction(0),Fraction(due)-now)*old_speed/new_speed
def adjust(now,due,speed,fraction,kind):
    if Fraction(fraction)<0 or kind not in ('ADVANCE','DELAY'):raise ValueError('SEMANTIC_GAP')
    delta=Fraction(fraction)*interval(speed)
    return max(Fraction(now),Fraction(due)+(-delta if kind=='ADVANCE' else delta))
def order(entries):
    return sorted(entries,key=lambda e:(fq(e['due_at']),-e['priority'],e['registration_ordinal'],
            e['enqueue_ordinal'],e['entry_id'].encode('utf-8')))

def authority():
    return {'kind':'EXPLICIT_SCENARIO_INPUT','source_version':None,'artifact':'R21 POLICY-ONLY fixture',
            'sha256':stable_hash({'fixture':'R21'}),'pointer':''}

def sample_state():
    p=policy();h=stable_hash(p)
    s={'schema':'generic_battle_turn_state/1','policy_id':p['identity'],'policy_hash':h,
       'clock':{'now':q(0),'unit':'REFERENCE_AV','advance_count':0,'transition_count':0},
       'participants':[],'initiative':{},'normal_queue':[],'active_stack':[],
       'pending_insertions':[],'pending_interrupts':[],'permissions':[],'boundary_work':[],
       'decision':None,'terminal':{'status':'RUNNING','reason':None,'stage_policy_hash':h},
       'stage':{'stage_id':'fixture-stage','wave_index':0,'provider_id':'explicit-stage-fixture-v1',
                'pending_request_id':None,'generation':0,'policy_hash':h},'revision':0,
       'normal_turn_count':0,'action_count':0,'command_journal':[],'failure':None}
    for name in ['turn','entry','insertion','decision','permission','event','command']:
        s['next_'+name+'_id']=0
    s['next_enqueue_ordinal']=2;s['next_registration_ordinal']=2
    for ordinal,(actor,speed) in enumerate([('a',100),('b',200)]):
        entry='entry:'+str(ordinal)
        s['participants'].append({'actor_id':actor,'entity_ref':actor,'generation':0,'registration_ordinal':ordinal,
          'controller':'PLAYER' if actor=='a' else 'MONSTER_AI','speed_ref':{'base_property_key':'speed',
          'effective_provider_id':'r19-explicit-speed-fixture','provider_policy_hash':h,'authority':authority()},
          'participation':'ENABLED','entity_revision':0,'summon_parent_actor':None,
          'availability_provider_id':p['availability_provider_id'],'authority':authority()})
        s['initiative'][actor]={'actor_id':actor,'generation':0,'due_at':q(interval(speed)),
          'effective_speed_sample':{'value':q(speed),'provider_revision':0,'observed_at':q(0),'input_state_hash':h},
          'cycle_index':0,'normal_entry_id':entry,'disabled_remaining':None,'disabled_since':None,
          'revision':0,'authority':'REFERENCE_MODEL'}
        s['normal_queue'].append({'entry_id':entry,'actor_id':actor,'generation':0,'category':'NORMAL_TURN',
          'due_at':q(interval(speed)),'priority':0,'registration_ordinal':ordinal,'enqueue_ordinal':ordinal,
          'initiative_revision':0,'insertion_id':None})
    s['next_entry_id']=2;s['normal_queue']=order(s['normal_queue'])
    return s

def validate_state(value,p):
    import jsonschema
    state_schema,policy_schema=schemas()
    jsonschema.Draft202012Validator(state_schema).validate(value)
    jsonschema.Draft202012Validator(policy_schema).validate(p)
    def visit(v):
        if isinstance(v,dict):
            if set(v)=={'n','d'}:
                if isinstance(v['n'],bool) or isinstance(v['d'],bool) or math.gcd(v['n'],v['d'])!=1:
                    raise ValueError('noncanonical rational')
                if max(abs(v['n']).bit_length(),v['d'].bit_length())>p['numeric']['max_integer_bits']:
                    raise ValueError('SEMANTIC_GAP numeric bound')
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
        elif isinstance(v,float):raise ValueError('float forbidden')
    visit(value)
    if value['policy_hash']!=stable_hash(p) or value['policy_id']!=p['identity']:raise ValueError('policy mismatch')
    ids=[x['actor_id'] for x in value['participants']];ordinals=[x['registration_ordinal'] for x in value['participants']]
    if len(set(ids))!=len(ids) or len(set(ordinals))!=len(ordinals):raise ValueError('duplicate participant')
    if set(ids)!=set(value['initiative']):raise ValueError('initiative input missing')
    members={x['actor_id']:x for x in value['participants']}
    entries=value['normal_queue'];eids=[x['entry_id'] for x in entries]
    if len(set(eids))!=len(eids) or entries!=order(entries):raise ValueError('queue order/duplicate')
    active_normal={x['action_actor_id'] for x in value['active_stack'] if x['category']=='NORMAL_TURN'}
    for entry in entries:
        actor=entry['actor_id'];m=members[actor];i=value['initiative'][actor]
        if (m['generation']!=entry['generation'] or i['generation']!=entry['generation'] or
            i['revision']!=entry['initiative_revision'] or i['normal_entry_id']!=entry['entry_id'] or
            i['due_at']!=entry['due_at'] or m['participation']!='ENABLED' or actor in active_normal):
            raise ValueError('stale or foreign initiative entry')
    for actor,m in members.items():
        expected=1 if m['participation']=='ENABLED' and actor not in active_normal else 0
        if sum(x['actor_id']==actor for x in entries)!=expected:raise ValueError('normal entry cardinality')
    for turn in value['active_stack']:
        if turn['turn_owner_actor_id'] not in members or turn['action_actor_id'] not in members:raise ValueError('unknown owner')
    return True

def trace_specs():
    p=policy();h=stable_hash(p);traces=[]
    def add(name,inputs,commands,expected,actual,scope='ARITHMETIC_POLICY_SPEC'):
        assert actual==expected,(name,actual,expected)
        traces.append({'id':name,'authority':'REFERENCE_MODEL','native_validation':False,'policy_hash':h,
          'scope':scope,'inputs':inputs,'commands':commands,'expected':expected,'observed':actual,'PASS':True})
    add('two_speeds',{'a':100,'b':200},['initial full interval'],[['b',q(50)],['a',q(100)]],
        sorted([['a',q(interval(100))],['b',q(interval(200))]],key=lambda x:fq(x[1])))
    add('three_way',{'a':100,'b':125,'c':200},['initial full interval'],[['c',q(50)],['b',q(80)],['a',q(100)]],
        sorted([[a,q(interval(s))] for a,s in [('a',100),('b',125),('c',200)]],key=lambda x:fq(x[1])))
    entries=[{'entry_id':e,'actor_id':a,'due_at':q(100),'priority':0,'registration_ordinal':r,'enqueue_ordinal':k}
             for e,a,r,k in [('e2','b',1,0),('e1','a',0,1)]]
    add('equal_readiness',entries,['permute input queue'],['a','b'],[x['actor_id'] for x in order(entries)])
    add('speed_change_waiting',{'now':q(25),'due':q(100),'old':100,'new':200},['preserve remaining distance'],q(Fraction(125,2)),q(rebase(25,100,100,200)))
    add('advance_delay',{'now':q(20),'due':q(100),'speed':100},['advance 1/2 interval','delay 1/4 interval'],
        [q(50),q(75)], [q(adjust(20,100,100,Fraction(1,2),'ADVANCE')),
                       q(adjust(20,adjust(20,100,100,Fraction(1,2),'ADVANCE'),100,Fraction(1,4),'DELAY'))])
    # Explicit transcripts describe the proposed state protocol, not executed insertion support.
    after=['a:NORMAL@100','a:COMPLETE@100','b:FOLLOW_UP@100','b:COMPLETE@100','a:NEXT_DUE@200']
    add('inserted_action',{'parent_owner':'a','insert_owner':'b','a_due':q(100)},
        ['complete normal a','admit queued follow-up b after active settles','complete insertion'],
        {'transcript':after,'b_normal_av_consumed':False,'normal_turn_count_delta':1},
        {'transcript':after,'b_normal_av_consumed':p['category_rules']['FOLLOW_UP_ACTION']['consumes_normal_av'],
          'normal_turn_count_delta':int(p['category_rules']['NORMAL_TURN']['counts_normal_turn'])},'DECLARED_OWNERSHIP_TRANSCRIPT')
    interrupt=['a:RUNNING root:A@100','a:SUSPENDED root:A@100','b:INTERRUPT root:B@100',
               'b:COMPLETE root:B@100','a:RESUMED root:A@100','a:COMPLETE root:A@100']
    add('interrupted_action',{'safe_point':'explicit future adapter token','parent_root':'A','child_root':'B'},
        ['save root and context','child root settles','restore parent root and context'],
        {'transcript':interrupt,'initial_profile_result':'INTERRUPT_POLICY_MISSING','clock':q(100)},
        {'transcript':interrupt,'initial_profile_result':'INTERRUPT_POLICY_MISSING' if p['interrupts']=='GAP_UNTIL_SAFE_POINT_ADAPTER' else 'INVALID','clock':q(100)},
        'FUTURE_ADAPTER_SPEC_NOT_R15_EXECUTION')
    s=sample_state();s['participants'][1]['participation']='REMOVED';s['participants'][1]['generation']=1
    s['initiative']['b']['generation']=1;s['initiative']['b']['normal_entry_id']=None;s['initiative']['b']['due_at']=None
    s['normal_queue']=[e for e in s['normal_queue'] if e['actor_id']!='b'];validate_state(s,p)
    add('defeated_before_turn',{'a_due':q(100),'b_due':q(50)},['defeat b at AV 25; remove entry; new generation'],
        ['a'],[e['actor_id'] for e in s['normal_queue']],'ENTITY_STATE_TRANSCRIPT')
    # A real reference EventIR callback is separately verified below, not added to native evidence.
    ev=['AFTER_ACTION','TURN_END','turn-end resource callback','DURATION_PROGRESS','EXPIRY_CHECK','normal reset']
    add('turn_end_callback',{'resource':0,'explicit_callback_delta':3},ev,
        {'boundary_order':['AFTER_ACTION','TURN_END','DURATION_PROGRESS','EXPIRY_CHECK'],'resource_after':3,'new_due':q(200)},
        {'boundary_order':p['boundary_order'][2:],'resource_after':0+3,'new_due':q(100+interval(100))},
        'DECLARED_BOUNDARY_TRANSCRIPT')
    return traces

class Specs(unittest.TestCase):
    def test_handwritten_traces(self): self.assertEqual(len(trace_specs()),9)
    def test_rational_speed_rebase_after_multiple_changes(self):
        self.assertEqual(rebase(40,rebase(25,100,100,200),200,50),130)
    def test_ready_actor_stays_ready(self): self.assertEqual(rebase(100,100,100,300),100)
    def test_overadvance_clamps_to_current_clock(self): self.assertEqual(adjust(20,100,100,2,'ADVANCE'),20)
    def test_fractional_interval_no_rounding(self): self.assertEqual(interval(123),Fraction(10000,123))
    def test_bad_speed_has_typed_gap(self):
        for s in [0,-1,True,1.5]:
            with self.assertRaisesRegex(ValueError,'SPEED_PROVIDER_MISSING'):interval(s)
    def test_negative_fraction_rejects(self):
        with self.assertRaises(ValueError):adjust(0,100,100,-1,'ADVANCE')
    def test_permutations_keep_total_order(self):
        import itertools
        e=sample_state()['normal_queue']
        for perm in itertools.permutations(e):self.assertEqual(order(list(perm)),e)
    def test_duplicate_actor_rejected(self):
        s=sample_state();s['participants'].append(copy.deepcopy(s['participants'][0]))
        with self.assertRaises(ValueError):validate_state(s,policy())
    def test_stale_generation_rejected(self):
        s=sample_state();s['normal_queue'][0]['generation']=1
        with self.assertRaises(ValueError):validate_state(s,policy())
    def test_queue_revision_rejected(self):
        s=sample_state();s['normal_queue'][0]['initiative_revision']=1
        with self.assertRaises(ValueError):validate_state(s,policy())
    def test_queue_readiness_mirror_checked(self):
        s=sample_state();s['normal_queue'][0]['due_at']=q(51)
        with self.assertRaises(ValueError):validate_state(s,policy())
    def test_noncanonical_rational_rejected(self):
        s=sample_state();s['clock']['now']={'n':0,'d':2}
        with self.assertRaises(ValueError):validate_state(s,policy())
    def test_numeric_overflow_rejected(self):
        s=sample_state();s['clock']['now']={'n':2**257,'d':1}
        with self.assertRaises(ValueError):validate_state(s,policy())
    def test_bool_float_missing_extra_rejected_by_schema(self):
        import jsonschema
        for bad in [True,1.5]:
            s=sample_state();s['clock']['now']['n']=bad
            with self.assertRaises(jsonschema.ValidationError):validate_state(s,policy())
        for kind in ['missing','extra']:
            s=sample_state()
            if kind=='missing':del s['pending_interrupts']
            else:s['native_speed']=100
            with self.assertRaises(jsonschema.ValidationError):validate_state(s,policy())
    def test_policy_hash_mismatch_rejected(self):
        p=policy();p['numeric']['distance']=q(20000)
        with self.assertRaises(ValueError):validate_state(sample_state(),p)
    def test_existing_state_runtime_clone_snapshot_hash(self):
        p=policy();s=sample_state();validate_state(s,p)
        state=BehaviorBattleState(entities={'a':{},'b':{}},mechanics={'battle_turn_v1':s})
        r=BehaviorRuntime(state,policies={p['identity']:p});clone=r.clone();restore=BehaviorRuntime.from_snapshot(r.snapshot())
        self.assertEqual(r.snapshot(),clone.snapshot());self.assertEqual(r.stable_hash(),restore.stable_hash())
        clone.state.mechanics['battle_turn_v1']['clock']['now']=q(1)
        self.assertNotEqual(r.stable_hash(),clone.stable_hash());self.assertEqual(r.stable_hash(),restore.stable_hash())
        changed=r.clone();changed.policies[p['identity']]['max_insert_depth']=17
        self.assertNotEqual(r.stable_hash(),changed.stable_hash())
    def test_all_decision_kinds_and_active_phases_serialize(self):
        import jsonschema
        d=schemas()[0];schema={'$defs':d['$defs'],'$ref':'#/$defs/DecisionBoundary'}
        for k in BOUNDARIES:
            boundary={'decision_id':'decision:0','kind':k,'actor_id':None,'turn_id':None,'action_root_id':None,
                      'state_revision':0,'policy_hash':stable_hash(policy()),'candidate_permission_ids':[],
                      'input_request':None,'failure':None,'terminal_reason':None}
            jsonschema.Draft202012Validator(schema).validate(boundary)
        # Schema alone does not prove semantic validity of terminal/gap/input kinds.
        self.assertEqual(len(BOUNDARIES),8)
        phases=d['$defs']['ActiveTurn']['properties']['phase']['enum']
        for phase in phases:
            s=sample_state();s['normal_queue']=[e for e in s['normal_queue'] if e['actor_id']!='a']
            s['initiative']['a']['normal_entry_id']=None
            s['active_stack']=[{'turn_id':'turn:0','queue_entry_id':'entry:0','turn_owner_actor_id':'a',
              'action_actor_id':'a','category':'NORMAL_TURN','phase':phase,'selected_at':q(100),
              'normal_turn_index':0,'action_index':0,'parent_turn_id':None,'parent_action_root_id':None,
              'action_root_id':None,'saved_r15_current_root':None,'saved_target_context':None,
              'permission_id':None,'insertion_id':None,'completion_consumed':False}]
            validate_state(s,policy())
            state=BehaviorBattleState(mechanics={'battle_turn_v1':s})
            self.assertEqual(state.snapshot(),BehaviorBattleState.from_snapshot(state.snapshot()).snapshot())
    def test_reference_category_accounting_is_explicit(self):
        p=policy()
        self.assertEqual(set(p['category_rules']),set(CATEGORIES))
        self.assertEqual([k for k,v in p['category_rules'].items() if v['consumes_normal_av']],['NORMAL_TURN'])
        self.assertTrue(p['category_rules']['EXTRA_TURN']['emits_turn_start'])
        self.assertFalse(p['category_rules']['EXTRA_TURN']['counts_normal_turn'])
        self.assertEqual(p['category_rules']['ULTIMATE_INTERRUPT']['admission'],'TYPED_GAP')
    def test_r15_actual_guard_and_owned_callback_drain(self):
        from tests.battle_runtime.test_behavior_r15 import R15Tests,ability,wait,finish,event,write as property_write
        from hsr_battle_agent.battle_runtime.behavior import ExecutionStatus
        root=ability('policy-fixture',wait(duration=7),event('turn-end-ref','r21-explicit-end'),finish())
        r=R15Tests().runtime(root,events={'r21-explicit-end':[property_write('end-callback',3)]})
        r.state.mechanics['battle_turn_v1']=sample_state()
        r.start_action('root');r.run_ready()
        self.assertEqual(r.legal_actions(),())
        with self.assertRaises(ValueError):r.start_action('root')
        c=r.clone();restored=BehaviorRuntime.from_snapshot(r.snapshot())
        for runtime in [r,c,restored]:
            result=runtime.run_until_action_complete()
            self.assertEqual(result.status,ExecutionStatus.ACTION_REFERENCE_COMPLETE)
            self.assertEqual(runtime.state.properties['a']['x']//2,3)
            self.assertEqual(runtime.state.mechanics['battle_turn_v1']['clock']['now'],q(0))
            self.assertEqual(runtime.state.scheduler.action_execution['logical_time'],14)
        self.assertEqual(r.stable_hash(),c.stable_hash());self.assertEqual(r.stable_hash(),restored.stable_hash())
    def test_replay_receipt_external_prevents_self_reference(self):
        initial=sample_state();p=policy()
        def replay(s):
            before=stable_hash(s);s=copy.deepcopy(s)
            command={'command_id':'command:0','expected_revision':s['revision'],'expected_hash':before,
                     'policy_hash':s['policy_hash'],'kind':'SPEED_CHANGED','arguments':{'actor_id':'a','speed':200}}
            s['command_journal'].append(command);s['revision']+=1;s['next_command_id']+=1
            due=rebase(0,fq(s['initiative']['a']['due_at']),100,200)
            i=s['initiative']['a'];i['due_at']=q(due);i['revision']+=1;i['effective_speed_sample']['value']=q(200)
            i['effective_speed_sample']['provider_revision']+=1
            for e in s['normal_queue']:
                if e['actor_id']=='a':e['due_at']=q(due);e['initiative_revision']=i['revision']
            s['normal_queue']=order(s['normal_queue']);validate_state(s,p)
            return s,{'prehash':before,'posthash':stable_hash(s)}
        a,ra=replay(initial);b,rb=replay(json.loads(canonical_json(initial)))
        self.assertEqual(a,b);self.assertEqual(ra,rb);self.assertNotIn('posthash',str(a['command_journal']))

def main():
    import jsonschema
    state_schema,policy_schema=schemas()
    jsonschema.Draft202012Validator.check_schema(state_schema)
    jsonschema.Draft202012Validator.check_schema(policy_schema)
    validate_state(sample_state(),policy())
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Specs)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    receipt={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
             'pass':result.wasSuccessful(),'native_validation':False,'production_engine_implemented':False,
             'scope':'algebra and schema tests; clone/hash/replay specification; one existing R15 guard/drain compatibility probe'}
    write('policy_trace_fixtures.json',{'schema':'r21_policy_only_trace_fixtures/1','policy':policy(),
          'traces':trace_specs(),'native_validation':False,'integrated_turn_engine_test':False,
          'interrupt_trace_is_executed_native_or_R15_interrupt':False})
    write('sample_turn_state.json',sample_state());write('spec_tests.json',receipt)
    if not result.wasSuccessful():raise RuntimeError('R21 specifications failed')

if __name__=='__main__':main()
