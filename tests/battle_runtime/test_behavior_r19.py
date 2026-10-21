"""R19 source-backed continuation and explicit provider/transaction regressions."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime')]
from hsr_battle_agent.battle_ir.behavior import IRNode,ExpressionIR,TargetSelectorIR,PredicateIR
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime,GapError,ExecutionStatus as Status
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE,fixed_binary
from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID as DAMAGE,LIFECYCLE,execute,assert_drained
from hsr_battle_agent.battle_runtime.dynamic_property import POLICY_ID,reference_policy,compile_program,read,AGGREGATION
from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID as MODIFIER,property_contribution,remove_instance
from r18_reference_fixtures import make_runtime,reference_listener
from r19_reference_fixtures import provider_binding,finish_binding,effective_binding
from tests.battle_runtime.test_behavior_r15 import A,task,expr,ability,call,finish,write

class R19Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001'
        cls.damage=IRNode.from_dict(json.loads((p/'real_damage_fixtures.json').read_text())[0]['node'])
        cls.rows=json.loads((p/'joined_explicit_prefix_results.json').read_text())
        cls.end=IRNode.from_dict(next(r['gap_node'] for r in cls.rows if r['primitive']=='RPG.GameCore.DamagePerformFinish'))
        cls.programs=[IRNode.from_dict(r['gap_node']) for r in cls.rows if r['primitive']=='unknown_opcode']
        cls.rank=IRNode.from_dict(next(r['gap_node'] for r in cls.rows if r['primitive']=='RPG.GameCore.ByRankActivated'))

    def runtime(self,*nodes,targets=('b',)):
        r=make_runtime([self.damage],root=ability('reference_root',*(nodes or (self.damage,self.end))),targets=targets)
        r.policies[DAMAGE]['finish_tasks'][self.end.stable_hash()]=finish_binding()
        r.policies[POLICY_ID]=reference_policy()
        return r

    def expression_runtime(self,node=None):
        r=self.runtime();n=node or self.programs[0]
        for key in n.payload['decoded']['int32_operands']:
            r.state.dynamic_values['supplied'][str(key)]=2*SCALE
            r.policies[POLICY_ID]['lookup_bindings']['supplied/'+str(key)]=provider_binding('ABILITY_DYNAMIC_VALUE',scope='supplied')
        return r,n

    def done(self,r):
        result=r.step('probe');self.assertEqual(result.status,Status.ACTION_REFERENCE_COMPLETE,str(result.gap));return result

    def test_source_finish_drains_without_requesting_action(self):
        r=self.runtime();result=r.step('probe');self.assertEqual(result.status,Status.WAITING_SCHEDULER)
        d=r.state.scheduler.action_execution
        self.assertEqual(d['metrics']['damage_perform_finish_completed'],1)
        self.assertFalse(d['roots'][d['current_root']]['completion_requested'])
        self.assertFalse(r.state.damage_history[-1]['ability_completion_requested'])
        self.assertEqual(r.state.properties['b']['hp'],80*SCALE)

    def test_six_serialized_reference_states(self):
        r=self.runtime(self.damage,self.end,finish());self.done(r)
        d=r.state.damage_requests['damage:1']
        self.assertEqual([v['status'] for v in d['lifecycle_transitions']],list(LIFECYCLE))
        self.assertEqual(d['lifecycle_status'],'DAMAGE_REFERENCE_COMPLETE')

    def test_finish_is_a_task_and_next_task_runs(self):
        r=self.runtime(self.damage,self.end,write('after',7),finish());r.state.properties['a']['x']=0;self.done(r)
        self.assertEqual(r.state.properties['a']['x'],14)
        self.assertFalse(r.state.damage_history[-1]['request_completion_requested'])

    def test_unbound_finish_gap_preserves_prior_hp(self):
        r=self.runtime();r.policies[DAMAGE]['finish_tasks']={}
        out=r.step('probe');self.assertIn('DAMAGE_LIFECYCLE_UNKNOWN',out.gap.required_capability)
        self.assertEqual(r.state.properties['b']['hp'],80*SCALE)
        self.assertEqual(len(r.state.damage_requests),1)

    def test_native_finish_mode_rejected(self):
        r=self.runtime();r.policies[DAMAGE]['finish_tasks'][self.end.stable_hash()]['mode']='NATIVE_FINISH'
        self.assertIn('DAMAGE_LIFECYCLE_UNKNOWN',r.step('probe').gap.required_capability)

    def test_multi_target_finish_and_continuation(self):
        r=self.runtime(self.damage,self.end,finish(),targets=('c','b'));self.done(r)
        self.assertEqual(r.state.damage_history[-1]['drained_request_ids'],['damage:1','damage:2'])
        self.assertEqual(r.state.properties['c']['hp'],80*SCALE)

    def test_child_damage_finish_does_not_finish_parent(self):
        r=self.runtime(call(),write('parent_after',3),finish());r.state.properties['a']['x']=0
        r.abilities['child']=ability('child',self.damage,self.end)
        self.done(r);d=r.state.scheduler.action_execution
        self.assertEqual(d['metrics']['child_abilities_completed'],1)
        self.assertEqual(r.state.properties['a']['x'],6)
        self.assertEqual(len(d['completion_requests']),1)

    def test_owned_callbacks_drain_before_finish(self):
        r=self.runtime(self.damage,self.end,finish());r.state.properties['a']['x']=0
        reference_listener(r,write('post_damage',5),stage='AFTER_DAMAGE');self.done(r)
        self.assertEqual(r.state.properties['a']['x'],10)
        self.assertEqual(r.state.scheduler.action_execution['metrics']['callbacks_completed'],1)
        self.assertEqual(r.state.damage_requests['damage:1']['pending_callbacks'],[])

    def test_pending_damage_assertion_is_atomic(self):
        r=self.runtime();r.start_action('probe');r.run_ready(5)
        d=r.state.scheduler.action_execution;r.state.target_context['ability_instance_id']=d['roots'][d['current_root']]['root_ability_id']
        before=r.state.stable_hash()
        with self.assertRaisesRegex(GapError,'DAMAGE_LIFECYCLE_PENDING'):execute(r,self.end)
        self.assertEqual(r.state.stable_hash(),before)

    def test_pending_event_mutation_blocks_finish(self):
        r=self.runtime();r.start_action('probe');r.run_ready(0)
        d=r.state.scheduler.action_execution;r.state.target_context['ability_instance_id']=d['roots'][d['current_root']]['root_ability_id']
        r.state.pending_events.append({'explicit_pending_mutation':True})
        with self.assertRaisesRegex(GapError,'pending transaction/event mutation'):execute(r,self.end)

    def test_pending_callback_blocks_even_without_request(self):
        r=self.runtime();r.start_action('probe');d=r.state.scheduler.action_execution
        aid=d['roots'][d['current_root']]['root_ability_id'];r.state.target_context['ability_instance_id']=aid
        d['callbacks']['pending']={'ability_instance_id':aid,'status':'READY'}
        with self.assertRaisesRegex(GapError,'owned callbacks'):assert_drained(r,self.end,aid)

    def test_all_four_real_programs_use_generic_mul_family(self):
        for n in self.programs:
            with self.subTest(source=n.authority.source_artifact):
                r,n=self.expression_runtime(n);ast=compile_program(n)
                self.assertEqual(ast.payload['arg'].op,'mul')
                self.assertEqual(r.evaluate(n),fixed_binary('mul',2*SCALE,n.payload['decoded']['int64_operands'][0]))
                self.assertEqual(ast.authority,n.authority)

    def test_unknown_program_requires_explicit_provider(self):
        r,n=self.expression_runtime();r.policies[POLICY_ID]['lookup_bindings']={}
        with self.assertRaisesRegex(GapError,'program lookup binding'):r.evaluate(n)

    def test_unknown_opcode_not_admitted(self):
        r,n=self.expression_runtime();p=n.payload;p['decoded']['token_ids'][4]=99
        bad=ExpressionIR(n.node_id,n.op,n.authority,p)
        with self.assertRaisesRegex(GapError,'opcode/termination 99'):r.evaluate(bad)

    def test_program_underflow_operand_index_and_termination_rejected(self):
        for tokens in ([4,17],[1,-1,17],[1,4,17],[1,0,17,17],[1,0,0,0,4]):
            r,n=self.expression_runtime();p=n.payload;p['decoded']['token_ids']=list(tokens)
            with self.assertRaisesRegex(GapError,'DYNAMIC_PROGRAM_UNKNOWN'):r.evaluate(ExpressionIR('bad','unknown_opcode',n.authority,p))

    def test_numeric_quantization_and_negative_multiply(self):
        r,n=self.expression_runtime();key=str(n.payload['decoded']['int32_operands'][0])
        r.state.dynamic_values['supplied'][key]=-SCALE-2
        self.assertEqual(r.evaluate(n),fixed_binary('mul',-SCALE-2,n.payload['decoded']['int64_operands'][0]))

    def test_dynamic_numeric_overflow_and_tagged_values_rejected(self):
        for raw in (2**63-2,3):
            r,n=self.expression_runtime(self.programs[1]);key=str(n.payload['decoded']['int32_operands'][0])
            p=n.payload;p['decoded']['int64_operands'][0]=2*SCALE;n=ExpressionIR('numeric_test',n.op,n.authority,p)
            r.state.dynamic_values['supplied'][key]=raw
            with self.assertRaises(GapError):r.evaluate(n)

    def test_provider_precedence_is_explicit_and_hashable(self):
        r,n=self.expression_runtime();key=str(n.payload['decoded']['int32_operands'][0]);r.state.target_context['override']={key:6*SCALE}
        b=r.policies[POLICY_ID]['lookup_bindings']['supplied/'+key]
        b['providers'].insert(0,{'source':'CONTEXT_OVERRIDE','store':'override','on_missing':'GAP_REFERENCE'})
        first=r.evaluate(n);clone=r.clone();clone.policies[POLICY_ID]['lookup_bindings']['supplied/'+key]['providers'].reverse()
        self.assertNotEqual(first,clone.evaluate(n));self.assertNotEqual(r.stable_hash(),clone.stable_hash())

    def test_missing_provider_does_not_fall_back(self):
        r,n=self.expression_runtime();key=str(n.payload['decoded']['int32_operands'][0])
        b=provider_binding('CONTEXT_OVERRIDE',store='missing');b['providers'].extend(provider_binding('ABILITY_DYNAMIC_VALUE',scope='supplied')['providers'])
        with self.assertRaisesRegex(GapError,'PROPERTY_PROVIDER_INPUT_MISSING'):read(r,n,r.state,b,key)
        b['providers'][0]['on_missing']='CONTINUE_EXPLICIT_REFERENCE'
        self.assertEqual(read(r,n,r.state,b,key)[0],2*SCALE)

    def test_unknown_provider_typed_gap(self):
        r,n=self.expression_runtime()
        with self.assertRaisesRegex(GapError,'PROPERTY_PROVIDER_UNKNOWN'):read(r,n,r.state,provider_binding('UNKNOWN_PROVIDER'),'x')

    def contribution_runtime(self):
        r=self.runtime(self.damage,self.end,finish())
        reference_listener(r,write('unused',0));r.state.target_context['modifier_instance_id']='sandbox_listener'
        n=task('contribution','RPG.GameCore.StackProperty',roles={'target':TargetSelectorIR('atk_target','explicit',A,{'entities':['a']}),
              'property':'reference_atk','value':expr(3*SCALE,True)})
        r.policies[MODIFIER]['property_tasks'][n.stable_hash()]={'aggregation':'ADDITIVE_REVERSIBLE_REFERENCE','properties':{'reference_atk':'reference_atk'}}
        r.start_action('probe')
        property_contribution(r,n)
        b=effective_binding(r.state,'a');r.policies[POLICY_ID]['property_bindings']['attack']=b
        r.policies[DAMAGE]['tasks'][self.damage.stable_hash()]['formula']['args'][0]['binding']='attack'
        return r,n,b

    def test_r17_contribution_effective_damage_hp_pipeline(self):
        r,n,b=self.contribution_runtime();out=r.run_until_action_complete();self.assertEqual(out.status,Status.ACTION_REFERENCE_COMPLETE,str(out.gap))
        self.assertEqual(r.state.properties['b']['hp'],74*SCALE)
        self.assertEqual(r.state.damage_history[0]['property_inputs'][0]['contributions'][0]['raw'],3*SCALE)

    def test_base_effective_contribution_reads_do_not_double_add(self):
        r,n,b=self.contribution_runtime()
        for source,value in [('BASE_PROPERTY',10*SCALE),('EFFECTIVE_PROPERTY',13*SCALE),('MODIFIER_CONTRIBUTION',3*SCALE)]:
            b['providers'][0]['source']=source;self.assertEqual(read(r,n,r.state,b,'reference_atk')[0],value)

    def test_r17_removal_reverses_property_without_cache(self):
        r,n,b=self.contribution_runtime();remove_instance(r,n,r.state.modifiers['sandbox_listener'],'TEST','RETAIN_ENQUEUED_REFERENCE')
        b['modifier_order']=[];self.assertEqual(read(r,n,r.state,b,'reference_atk')[0],10*SCALE)

    def test_unknown_aggregation_is_gap(self):
        r,n,b=self.contribution_runtime();b['aggregation']='UNKNOWN'
        with self.assertRaisesRegex(GapError,'PROPERTY_AGGREGATION_UNKNOWN'):read(r,n,r.state,b,'reference_atk')

    def test_modifier_local_and_snapshot_explicit_precedence(self):
        r,n=self.expression_runtime();reference_listener(r,write('unused',0));m=r.state.modifiers['sandbox_listener']
        m.dynamic_values['x']=2*SCALE;m.snapshot_data['x']=3*SCALE
        b=provider_binding('MODIFIER_LOCAL_DYNAMIC_VALUE',instance=m.instance_id)
        b['providers'].extend(provider_binding('SNAPSHOT_VALUE',instance=m.instance_id)['providers'])
        self.assertEqual(read(r,n,r.state,b,'x')[0],2*SCALE);b['providers'].reverse();self.assertEqual(read(r,n,r.state,b,'x')[0],3*SCALE)

    def rank_runtime(self):
        r=self.runtime();n=self.rank
        r.policies[POLICY_ID]['rank_bindings'][n.stable_hash()]={'authority':'REFERENCE_MODEL','evidence':'explicit test threshold ONLY',
            'mode':'KEYED_THRESHOLD_GE_REFERENCE','key_field':'unbound_bit_0','actor_context':'caster'}
        key=str(n.payload['fields']['unbound_bit_0']);return r,n,key

    def test_rank_missing_input_gap_and_explicit_comparison(self):
        r,n,key=self.rank_runtime()
        with self.assertRaisesRegex(GapError,'RANK_INPUT_MISSING'):r.predicate(n)
        r.state.progression['a']={'rank':1,'rank_requirements':{key:2}}
        self.assertFalse(r.predicate(n));r.state.progression['a']['rank']=2;self.assertTrue(r.predicate(n))

    def test_rank_key_is_content_driven(self):
        r,n,key=self.rank_runtime();p=n.payload;p['fields']['unbound_bit_0']=987
        n2=PredicateIR('another_key',n.op,n.authority,p)
        r.policies[POLICY_ID]['rank_bindings'][n2.stable_hash()]=copy.deepcopy(r.policies[POLICY_ID]['rank_bindings'][n.stable_hash()])
        r.state.progression['a']={'rank':4,'rank_requirements':{'987':3}};self.assertTrue(r.predicate(n2))

    def test_post_hp_expression_failure_rolls_back_rng_modifier_and_hp(self):
        r=self.runtime(write('prior',9),self.damage,self.end,finish());r.state.properties['a']['x']=0
        n=self.programs[0];cb=task('unknown_write','dynamic_write',scope='supplied',key='out',value=n)
        reference_listener(r,ability('cb',task('rng','random_choice',choices=[write('draw',2)]),cb).payload['tasks'],stage='AFTER_DAMAGE')
        original=r.state.clone();out=r.step('probe');self.assertEqual(out.status,Status.SEMANTIC_GAP)
        self.assertEqual(r.state.properties['b']['hp'],100*SCALE);self.assertEqual(r.state.properties['a']['x'],18)
        self.assertEqual(r.state.rng,original.rng);self.assertEqual(r.state.modifiers,original.modifiers)
        self.assertEqual(r.state.damage_requests,{})

    def test_budget_checkpoints_each_lifecycle_clone_restore_replay(self):
        r=self.runtime(self.damage,self.end,finish());initial=r.snapshot();r.start_action('probe');seen=set()
        for _ in range(60):
            out=r.run_ready(1)
            seen.update(v['lifecycle_status'] for v in r.state.damage_requests.values())
            clone=r.clone();restored=BehaviorRuntime.from_snapshot(r.snapshot())
            self.assertEqual(r.stable_hash(),clone.stable_hash());self.assertEqual(r.stable_hash(),restored.stable_hash())
            if out.status==Status.ACTION_REFERENCE_COMPLETE:break
        self.assertEqual(seen,set(LIFECYCLE))
        replay,outcomes=BehaviorRuntime.from_snapshot(initial).replay(['probe'])
        self.assertEqual(outcomes[0].status,Status.ACTION_REFERENCE_COMPLETE);self.assertEqual(replay.stable_hash(),r.stable_hash())

    def test_lifecycle_state_affects_hash(self):
        r=self.runtime();r.start_action('probe');r.run_ready(5);clone=r.clone()
        clone.state.damage_requests['damage:1']['lifecycle_status']='ALTERED'
        self.assertNotEqual(r.stable_hash(),clone.stable_hash())

    def test_original_real_ability_actions_complete_without_inserted_finish(self):
        from r19_followups import ability_runtime
        from hsr_battle_agent.battle_ir.behavior import walk_nodes
        rows=json.loads((ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001/real_graph_prefix_results.json').read_text())
        for index in (0,5):
            row=rows[index]
            with self.subTest(source=row['root']):
                r=ability_runtime(row);source=IRNode.from_dict(row['initial_runtime']['source_root'])
                self.assertEqual(r.actions['probe'],source)
                self.assertTrue(any(n.op=='RPG.GameCore.SkillPerformFinish' for n in walk_nodes(source.payload['tasks'])))
                initial=r.snapshot();self.done(r)
                self.assertEqual(r.state.scheduler.action_execution['metrics']['damage_perform_finish_completed'],1)
                self.assertTrue(all(v['lifecycle_status']=='DAMAGE_REFERENCE_COMPLETE' for v in r.state.damage_requests.values()))
                self.assertFalse(r.state.damage_transactions)
                replay,result=BehaviorRuntime.from_snapshot(initial).replay(['probe'])
                self.assertEqual(result[0].status,Status.ACTION_REFERENCE_COMPLETE)
                self.assertEqual(r.stable_hash(),replay.stable_hash())

    def test_action_completion_cannot_bypass_pending_request(self):
        r=self.runtime(finish());r.start_action('probe');d=r.state.scheduler.action_execution
        aid=d['roots'][d['current_root']]['root_ability_id']
        r.state.damage_requests['explicit_pending']={'status':'PENDING','request':{'payload':{'ownership':{'ability_instance_id':aid,'action_root_id':d['current_root']}}}}
        self.assertEqual(r.run_until_action_complete().status,Status.WAITING_SCHEDULER)
        self.assertNotEqual(d['roots'][d['current_root']]['status'],'ACTION_REFERENCE_COMPLETE')

if __name__=='__main__':unittest.main()
