"""R18 real decoded damage, explicit sandbox policies and R15/R17 transactions."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime')]
from hsr_battle_agent.battle_ir.behavior import IRNode,TaskIR,ExpressionIR,DamageRequestIR,walk_nodes,stable_hash
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime,ExecutionStatus
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE,fixed_binary
from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID,STAGES,source_expression,attack_fields
from hsr_battle_agent.battle_runtime.action_scheduler import POLICY_ID as SCHEDULER
from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID as MODIFIER
from r18_reference_fixtures import make_runtime,reference_listener,wrapper
from tests.battle_runtime.test_behavior_r15 import A,task,expr,ability,call,finish,write,wait

class R18Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads((ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001/real_damage_fixtures.json').read_text())
        cls.nodes=[IRNode.from_dict(row['node']) for row in cls.rows]
    def runtime(self,**kwargs): return make_runtime([self.nodes[0]],**kwargs)
    def binding(self,r,n=None): return r.policies[POLICY_ID]['tasks'][(n or self.nodes[0]).stable_hash()]
    def complete(self,r):
        result=r.step('probe');self.assertEqual(result.status,ExecutionStatus.ACTION_REFERENCE_COMPLETE,str(result.gap));return result
    def gap(self,r,kind):
        result=r.step('probe');self.assertEqual(result.status,ExecutionStatus.SEMANTIC_GAP);self.assertIn(kind,result.gap.required_capability)
        self.assertEqual(r.state.damage_history,[]);self.assertEqual(r.state.damage_requests,{})
        self.assertEqual(r.state.damage_transactions,[]);self.assertEqual(r.state.properties['b']['hp'],100*SCALE)
        return result
    def amount_callback(self,value=5*SCALE,name='amount_callback'):
        return task(name,'reference_damage_amount_modify',value=expr(value,True))
    def test_real_source_binding_and_typed_request(self):
        r=self.runtime();self.complete(r);record=r.state.damage_history[0];request=IRNode.from_dict(record['request'])
        self.assertIsInstance(request,DamageRequestIR);self.assertEqual(request.payload['source_task'],self.nodes[0])
        self.assertEqual(request.authority.source_version,'4.6.51');self.assertEqual(request.payload['unknown_roles']['native_formula'],'UNKNOWN')
    def test_raw_fields_spans_evidence_roundtrip(self):
        r=self.runtime();self.complete(r);request=IRNode.from_dict(r.state.damage_history[0]['request'])
        self.assertEqual(request.payload['raw_operands'],self.nodes[0].payload['decoded'])
        self.assertEqual(request.authority,self.nodes[0].authority)
        self.assertEqual(request,IRNode.from_dict(request.to_dict()))
    def test_non_natasha_real_fixtures(self):
        for row,node in zip(self.rows,self.nodes):
            with self.subTest(root=row['root']):
                self.assertNotIn('Natasha',row['root']);self.complete(make_runtime([node]))
    def test_formula_uses_source_lookup_and_property(self):
        r=self.runtime(coefficient=3*SCALE);self.complete(r);d=r.state.damage_history[0]
        self.assertEqual(d['evaluated_amount_raw'],30*SCALE);self.assertEqual(d['hp_after_raw'],70*SCALE)
        self.assertEqual(d['evaluated_operands'][0]['mask'],4);self.assertEqual(d['property_inputs'][0]['key'],'reference_atk')
    def test_frozen_no_policy_still_gap(self):
        r=self.runtime();del r.policies[POLICY_ID];self.gap(r,'DAMAGE_REFERENCE_INPUT_MISSING')
    def test_missing_exact_binding(self):
        r=self.runtime();r.policies[POLICY_ID]['tasks']={};self.gap(r,'DAMAGE_REFERENCE_INPUT_MISSING')
    def test_missing_property_operand(self):
        r=self.runtime();del r.state.properties['a']['reference_atk'];self.gap(r,'DAMAGE_PROPERTY_INPUT_MISSING')
    def test_missing_dynamic_operand(self):
        r=self.runtime();r.state.dynamic_values['supplied']={};self.gap(r,'dynamic_provider')
    def test_all_raw_field_classifications_required(self):
        r=self.runtime();self.binding(r)['attack_fields']={};self.gap(r,'DAMAGE_BINDING_UNKNOWN')
    def test_binding_hash_required(self):
        r=self.runtime();self.binding(r)['source_task_hash']='wrong';self.gap(r,'DAMAGE_BINDING_UNKNOWN')
    def test_unknown_reader_mask(self):
        r=self.runtime();self.binding(r)['target_mask']=8192;self.gap(r,'STRUCTURAL_DAMAGE_GAP')
    def test_target_order_and_multi_target(self):
        r=self.runtime(targets=('c','b'));self.complete(r)
        self.assertEqual([d['request']['payload']['target'] for d in r.state.damage_history],['c','b'])
        self.assertEqual([d['request_id'] for d in r.state.damage_history],['damage:1','damage:2'])
        self.assertEqual(r.state.properties['c']['hp'],80*SCALE)
    def test_duplicate_targets_explicit_preservation(self):
        r=self.runtime(targets=('b','b'));self.complete(r)
        self.assertEqual([d['hp_before_raw'] for d in r.state.damage_history],[100*SCALE,80*SCALE])
        self.assertEqual(r.state.properties['b']['hp'],60*SCALE)
    def test_duplicate_targets_rejection(self):
        r=self.runtime(targets=('b','b'));self.binding(r)['duplicates']='REJECT_REFERENCE';self.gap(r,'DAMAGE_TARGET_DUPLICATION_UNKNOWN')
    def test_distinct_real_requests_serialized_order(self):
        r=make_runtime(self.nodes[:2]);self.complete(r)
        self.assertEqual([d['request']['payload']['source_task_hash'] for d in r.state.damage_history],[n.stable_hash() for n in self.nodes[:2]])
        self.assertEqual(r.state.properties['b']['hp'],60*SCALE)
    def test_invalid_target_rolls_back_selector_rng(self):
        r=self.runtime();del r.state.entities['b'];self.gap(r,'resolved entity identities')
    def test_fixed_point_intermediate_quantization(self):
        r=self.runtime(coefficient=SCALE//3*2);r.state.properties['a']['reference_atk']=SCALE+2
        expected=fixed_binary('mul',SCALE+2,SCALE//3*2);self.complete(r)
        self.assertEqual(r.state.damage_history[0]['evaluated_amount_raw'],expected)
    def test_final_whole_hp_rounding(self):
        r=self.runtime(coefficient=SCALE+2);self.binding(r)['rounding']='WHOLE_HP_TOWARD_ZERO_REFERENCE';self.complete(r)
        self.assertEqual(r.state.damage_history[0]['effective_amount_raw'],10*SCALE)
    def test_overflow_atomic_gap(self):
        r=self.runtime();r.state.properties['a']['reference_atk']=2**63-2;self.gap(r,'DAMAGE_NUMERIC_GAP')
    def test_division_zero_atomic_gap(self):
        r=self.runtime();b=self.binding(r);b['formula']={'op':'div','args':[b['formula'],{'op':'literal_reference','raw':0}]}
        self.gap(r,'division by zero')
    def test_negative_rejection_and_explicit_clamp(self):
        r=self.runtime(coefficient=-SCALE);self.gap(r,'DAMAGE_NEGATIVE_AMOUNT')
        r=self.runtime(coefficient=-SCALE);self.binding(r)['negative']='CLAMP_ZERO_REFERENCE';self.complete(r)
        self.assertEqual(r.state.properties['b']['hp'],100*SCALE)
    def test_zero_amount(self):
        r=self.runtime(coefficient=0);self.complete(r);self.assertEqual(r.state.damage_history[0]['applied_hp_delta_raw'],0)
    def test_hp_clamp_overkill_and_property_mutation(self):
        r=self.runtime(coefficient=20*SCALE);self.complete(r);d=r.state.damage_history[0]
        self.assertEqual((d['hp_after_raw'],d['applied_hp_delta_raw'],d['overkill_raw']),(0,-100*SCALE,100*SCALE))
        self.assertTrue(r.state.entities['b']['alive']);self.assertFalse(r.state.terminal)
    def test_explicit_life_state_policy(self):
        r=self.runtime(coefficient=20*SCALE);self.binding(r)['settlement']['life_state']='SET_ALIVE_FROM_HP_REFERENCE'
        self.complete(r);self.assertFalse(r.state.entities['b']['alive']);self.assertFalse(r.state.terminal)
    def test_death_callback_unknown_rejected(self):
        r=self.runtime();self.binding(r)['settlement']['death_callbacks']='UNKNOWN';self.gap(r,'DAMAGE_SETTLEMENT_POLICY_UNKNOWN')
    def test_shield_toughness_break_unknown_rejected(self):
        for key in ('shield','toughness','break','resources'):
            with self.subTest(key=key):
                r=self.runtime();self.binding(r)['boundaries'][key]='UNKNOWN';self.gap(r,'DAMAGE_'+key.upper()+'_POLICY_UNKNOWN')
    def test_no_toughness_inference(self):
        r=self.runtime();r.state.properties['b'].update(shield=7*SCALE,toughness=30*SCALE)
        self.complete(r);self.assertEqual(r.state.properties['b']['shield'],7*SCALE);self.assertEqual(r.state.properties['b']['toughness'],30*SCALE)
    def test_event_modified_amount_owned_callback(self):
        r=self.runtime();cb=self.amount_callback();reference_listener(r,cb,operation='add');self.complete(r)
        d=r.state.damage_history[0];self.assertEqual(d['effective_amount_raw'],25*SCALE)
        self.assertEqual(r.state.properties['b']['hp'],75*SCALE);self.assertEqual(len(d['callbacks_processed']),1)
        frames=r.state.scheduler.action_execution;cid=d['callbacks_processed'][0]
        self.assertEqual(frames['callbacks'][cid]['action_root_id'],frames['current_root'])
        self.assertEqual(frames['callbacks'][cid]['status'],'CALLBACK_COMPLETE')
        self.assertEqual(d['amount_changes'][0]['event_payload']['damage_request_id'],d['request_id'])
    def test_event_listener_aggregation_order(self):
        r=self.runtime();setcb=self.amount_callback(3*SCALE,'set');mulcb=self.amount_callback(2*SCALE,'mul')
        reference_listener(r,mulcb,operation='mul',identity='second',priority=2)
        reference_listener(r,setcb,operation='set',identity='first',priority=1)
        self.complete(r);self.assertEqual(r.state.damage_history[0]['effective_amount_raw'],6*SCALE)
    def test_missing_callback_authority_rolls_back(self):
        r=self.runtime();reference_listener(r,self.amount_callback());self.gap(r,'DAMAGE_CALLBACK_AUTHORITY_MISSING')
    def test_wrong_amount_modification_stage_rejected(self):
        r=self.runtime();reference_listener(r,self.amount_callback(),operation='add',stage='AFTER_DAMAGE')
        self.gap(r,'DAMAGE_CALLBACK_AUTHORITY_MISSING')
    def test_missing_listener_scope_rejected(self):
        r=self.runtime();self.binding(r)['listener_scope']='UNKNOWN';self.gap(r,'DAMAGE_EVENT_LISTENERS_UNKNOWN')
    def test_missing_r17_event_engine_rejected(self):
        r=self.runtime();del r.policies[MODIFIER];self.gap(r,'MODIFIER_LIFECYCLE_POLICY_MISSING')
    def test_stage_order_rejected(self):
        r=self.runtime();self.binding(r)['ordered_stages']=list(reversed(STAGES));self.gap(r,'DAMAGE_EVENT_ORDER_UNKNOWN')
    def test_post_hp_callback_failure_rolls_back_all_and_retry(self):
        r=self.runtime();good=write('good',5);bad=task('bad','unimplemented_after_damage')
        callback=ability('post_callback',good,task('rng','random_choice',choices=[write('choice',8)]),bad).payload['tasks']
        reference_listener(r,callback,stage='AFTER_DAMAGE');r.state.properties['a']['x']=0
        initial=r.state.clone();result=self.gap(r,'unimplemented_after_damage')
        self.assertEqual(r.state.rng,initial.rng);self.assertEqual(r.state.modifiers,initial.modifiers)
        self.assertEqual(r.state.properties['a']['x'],0)
        clone=r.clone();self.assertEqual(r.run_until_blocked().gap,result.gap)
        self.assertEqual(clone.run_until_blocked().gap,result.gap)
        self.assertEqual(r.stable_hash(),clone.stable_hash())
        r.registry.register('task','unimplemented_after_damage',lambda e,n,s:[])
        self.assertEqual(r.run_until_action_complete().status,ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(r.state.properties['b']['hp'],80*SCALE);self.assertEqual(r.state.rng.draws,1)
    def test_prior_task_remains_committed_on_damage_failure(self):
        node=self.nodes[0];r=self.runtime(root=wrapper([write('prior',9),node]));r.state.properties['a']['x']=0
        reference_listener(r,task('bad','post_gap'),stage='AFTER_DAMAGE');self.gap(r,'post_gap')
        self.assertEqual(r.state.properties['a']['x'],18)
    def test_prior_damage_remains_committed(self):
        r=make_runtime(self.nodes[:2]);self.binding(r,self.nodes[1])['formula']={'op':'unknown'}
        result=r.step('probe');self.assertEqual(result.status,ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(len(r.state.damage_history),1);self.assertEqual(r.state.properties['b']['hp'],80*SCALE)
    def test_budget_checkpoint_clone_restore_hash_replay(self):
        r=self.runtime();reference_listener(r,self.amount_callback(),operation='add');r.start_action('probe')
        self.assertEqual(r.run_ready(8).status,ExecutionStatus.EXECUTION_BUDGET_EXHAUSTED)
        self.assertTrue(r.state.damage_transactions)
        clone=r.clone();restored=BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))
        self.assertEqual(r.stable_hash(),restored.stable_hash())
        results=[x.run_until_action_complete() for x in (r,clone,restored)]
        self.assertEqual(results[0],results[1]);self.assertEqual(results[0],results[2])
        self.assertEqual(r.stable_hash(),clone.stable_hash());self.assertEqual(r.stable_hash(),restored.stable_hash())
    def test_state_hash_includes_pending_damage_and_policy(self):
        r=self.runtime();r.start_action('probe');r.run_ready(5);clone=r.clone()
        clone.state.damage_requests['damage:1']['future_input']=2
        self.assertNotEqual(r.stable_hash(),clone.stable_hash())
        clone=r.clone();self.binding(clone)['rounding']='WHOLE_HP_TOWARD_ZERO_REFERENCE'
        self.assertNotEqual(r.stable_hash(),clone.stable_hash())
    def test_damage_perform_finish_separate_from_action_finish(self):
        node=self.nodes[0];end=task('damage_finish','RPG.GameCore.DamagePerformFinish')
        root=ability('real_damage_with_reference_local_finish',node,end);r=self.runtime(root=root)
        r.policies[POLICY_ID]['finish_tasks'][end.stable_hash()]={'mode':'ASSERT_OWNED_DAMAGE_DRAINED_REFERENCE','authority':'REFERENCE_MODEL'}
        result=r.step('probe');self.assertEqual(result.status,ExecutionStatus.WAITING_SCHEDULER)
        self.assertEqual(r.state.properties['b']['hp'],80*SCALE);self.assertFalse(r.state.scheduler.completion_requested)
    def test_unknown_damage_perform_finish_keeps_settlement(self):
        node=self.nodes[0];end=task('damage_finish','RPG.GameCore.DamagePerformFinish');r=self.runtime(root=ability('root',node,end))
        result=r.step('probe');self.assertIn('DAMAGE_LIFECYCLE_UNKNOWN',result.gap.required_capability)
        self.assertEqual(r.state.properties['b']['hp'],80*SCALE)
    def test_damage_inside_child_ability(self):
        node=self.nodes[0];r=self.runtime(root=ability('root',call(),finish()))
        r.abilities={'child':ability('child',node,finish('child_finish'))};self.complete(r)
        d=r.state.damage_history[0]['request']['payload'];self.assertIsNotNone(r.state.scheduler.action_execution['abilities'][d['ownership']['ability_instance_id']]['parent_ability_id'])
    def test_replay_exact_settlement_results(self):
        r=self.runtime();left,a=r.replay(['probe']);right,b=r.replay(['probe'])
        self.assertEqual(a,b);self.assertEqual(left.stable_hash(),right.stable_hash());self.assertEqual(left.state.damage_history,right.state.damage_history)
    def test_multi_target_settlement_failure_rolls_back_first_target(self):
        r=self.runtime(targets=('b','c'));del r.state.properties['c']['hp']
        self.gap(r,'DAMAGE_PROPERTY_INPUT_MISSING')
    def test_formula_without_real_operand_rejected(self):
        r=self.runtime();self.binding(r)['formula']={'op':'literal_reference','raw':10*SCALE}
        self.gap(r,'a real decoded source expression')
    def test_unknown_real_dynamic_program_remains_gap(self):
        audit=json.loads((ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001/damage_structural_audit.json').read_text())
        row=next(row for row in audit['instances'] if any(e['mask']==4 and e['expression']['op']=='unknown_opcode' for e in row['expression_operands']))
        node=IRNode.from_dict(row['full_source_task']);r=make_runtime([node]);self.gap(r,'expression:unknown_opcode')
    def test_before_damage_property_callback_affects_evaluation(self):
        r=self.runtime();callback=task('property_buff','property_write',owner='a',key='reference_atk',operation='set',value=expr(15*SCALE,True))
        reference_listener(r,callback,stage='BEFORE_DAMAGE');self.complete(r)
        self.assertEqual(r.state.damage_history[0]['evaluated_amount_raw'],30*SCALE)
    def test_transaction_defers_unrelated_scheduled_work(self):
        unrelated=task('unrelated','schedule',tick=0,tasks=[task('outside_gap','outside_damage_gap')])
        r=self.runtime(root=wrapper([unrelated,self.nodes[0]]))
        callback=ability('delayed_callback',wait(duration=5),write('after_delay',8)).payload['tasks']
        reference_listener(r,callback,stage='AFTER_DAMAGE');r.state.properties['a']['x']=0
        result=r.step('probe');self.assertIn('outside_damage_gap',result.gap.required_capability)
        self.assertEqual(r.state.properties['b']['hp'],80*SCALE);self.assertEqual(len(r.state.damage_history),1)
        self.assertEqual(r.state.damage_transactions,[])

if __name__=='__main__': unittest.main()
