"""Generic R17 policies/state/owned-event transactions and real source fixtures."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime')]
from hsr_battle_agent.battle_ir.behavior import AbilityIR, ExpressionIR, PredicateIR, IRNode, TaskSequenceIR, TargetSelectorIR, stable_hash, walk_nodes
from hsr_battle_agent.battle_ir.content_catalog import ContentCatalog
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime, ExecutionStatus
from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID, reference_policy, bind_definitions
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from tests.battle_runtime.test_behavior_r15 import A, ability, task, finish, expr, wait, write
from tests.battle_runtime import test_behavior_r15 as r15
from tests.battle_runtime.test_behavior_r16 import directory, record
from r17_reference_fixtures import definition_binding, application_binding, configure

def target(entity='b'): return TargetSelectorIR('target/'+entity,'explicit',A,{'entities':[entity]})
def add(name='add',config='buff',entity='b'):
    return task(name,'RPG.GameCore.AddModifier',roles={'target':target(entity),'modifier':expr(config)})
def event(name='event',event_id=53,**payload):
    return task(name,'modifier_event_dispatch',event_id=event_id,source='a',payload=payload)
def lookup(key='v',scope='supplied'): return ExpressionIR('read/'+key,'lookup',A,{'key':key,'scope':scope})
def property_task(name='contribution',value=None):
    return task(name,'RPG.GameCore.StackProperty',roles={'target':target(),'property':44,'value':value or expr(6,True)})
def field(mask,values): return {'mask':mask,'start':1,'end':2,'values':values}

def definition(callbacks=(),name='buff',data_fields=()):
    bodies=[]
    for item in callbacks:
        event_id,nodes=item[:2]
        bodies.append({'type':'RPG.GameCore.TurnBasedModifierCallbackConfig','start':2,'end':90,
            'fields':[field(1,[event_id]),*([field(2,[item[2].to_dict() if hasattr(item[2],'to_dict') else item[2]])] if len(item)>2 else []),
                      field(4,[{'kind':'list','children':[n.to_dict() for n in nodes]}])]})
    graph={'type':'RPG.GameCore.TurnBasedModifierConfig','start':0,'end':100,
        'fields':list(data_fields)+([field(33554432,[{'kind':'list','children':bodies}])] if bodies else [])}
    entry=directory(name,typ=0);r=record(entry)
    root=AbilityIR('definition','structure_record',A,{'root_type':graph['type'],'decoded':graph})
    r.update(graph=graph,graph_hash=stable_hash(graph),ir=root.to_dict(),canonical_IR_hash=root.stable_hash())
    c=ContentCatalog([entry],[r]);return next(iter(c.modifier_definitions().values())),c

class R17Tests(unittest.TestCase):
    def runtime(self,nodes=(),callbacks=(),activation=(53,),**kwargs):
        root=ability('root',*(nodes or [add(),finish()]))
        r=r15.R15Tests().runtime(root)
        d,c=definition(callbacks,**kwargs)
        bind_definitions(r.state,c)
        p=reference_policy();r.policies[POLICY_ID]=p
        spec=definition_binding(d,data_only_masks=[f['mask'] for f in d['decoded_fields'] if f['mask']!=33554432],
            activation_event_ids=activation,source_precedence=['MODIFIER_LOCAL','SNAPSHOT','SOURCE_PROVIDER'],
            activation='ACTIVATE_REFERENCE',pending_callbacks='RETAIN_ENQUEUED_REFERENCE')
        binding=application_binding(add(),d,owner='b',caster='a',original_caster='b',source_provider='supplied',
            duration={'units':'EXPLICIT_REFERENCE_UNITS','remaining':5,'expiry':'EXPLICIT_ADVANCE_REFERENCE'},
            initial_dynamic_values={'v':8},snapshot_properties={'saved_hp':{'entity':'CASTER_REFERENCE','property':'hp'}},operand_roles={})
        p['definitions'][d['definition_id']]=spec
        for node in root.payload['tasks'].payload['tasks']:
            if node.op=='RPG.GameCore.AddModifier': p['applications'][node.stable_hash()]=copy.deepcopy(binding)
        for item in callbacks:
            cb=item[1]
            for node in cb:
                if node.op=='RPG.GameCore.StackProperty': p['property_tasks'][node.stable_hash()]={
                    'aggregation':'ADDITIVE_REVERSIBLE_REFERENCE','properties':{'44':'hp'}}
        return r,p,d
    def complete(self,r):
        result=r.step('root');self.assertEqual(result.status,ExecutionStatus.ACTION_REFERENCE_COMPLETE,str(result.gap));return result
    def instance(self,r): return next(iter(r.state.modifiers.values()))
    def removal(self,p,node,pending='RETAIN_ENQUEUED_REFERENCE',identity='modifier:1'):
        p['removals'][node.stable_hash()]={'selection':'INSTANCE_REFERENCE','instance_id':identity,'reason':'TEST_REFERENCE','pending_callbacks':pending}

    def test_source_definition_binding_roundtrip_unknown_fields(self):
        r,p,d=self.runtime(data_fields=[field(4,[987])])
        self.assertEqual(d['decoded_fields'],d['unknown_fields']);self.assertEqual(d['source_span'],[0,100])
        self.assertEqual(r.state.clone().modifier_definitions,r.state.modifier_definitions)
        self.assertEqual(d['evidence_boundary'],'DECODED_MODIFIER_DEFINITION')
    def test_definition_does_not_activate(self):
        r,p,d=self.runtime();self.assertEqual(r.state.modifiers,{})
        p['applications']={};result=r.step('root')
        self.assertIn('REFERENCE_INSTANCE_INPUT_MISSING',result.gap.required_capability);self.assertEqual(r.state.modifiers,{})
    def test_insert_identity_duration_authority_and_snapshot(self):
        r,p,d=self.runtime();self.complete(r);m=self.instance(r)
        self.assertEqual((m.owner,m.caster,m.original_caster,m.target),('b','a','b','b'))
        self.assertEqual((m.stack,m.count,m.duration['original'],m.duration['remaining']),(1,1,5,5))
        self.assertEqual(m.snapshot_data['saved_hp'],5*SCALE)
        self.assertEqual(m.authority['native_effective_state'],'UNKNOWN')
        self.assertEqual(m.activation_state,'REFERENCE_INSTANCE_ACTIVE')
    def test_unknown_numeric_native_application_policy_gap(self):
        r,p,d=self.runtime();p['applications'][add().stable_hash()]['application_policy']=7
        self.assertIn('NATIVE_POLICY_UNKNOWN',r.step('root').gap.required_capability);self.assertEqual(r.state.modifiers,{})
    def test_unknown_definition_field_policy_atomic_gap(self):
        r,p,d=self.runtime(data_fields=[field(64,[1])]);p['definitions'][d['definition_id']]['field_bindings']={}
        self.assertIn('all decoded',r.step('root').gap.required_capability);self.assertEqual(r.state.modifiers,{})
    def test_refresh_preserves_id_values_and_source(self):
        refresh=add('refresh');r,p,d=self.runtime(nodes=[add(),refresh,finish()])
        b=p['applications'][refresh.stable_hash()];b.update(application_policy='REFRESH_EXISTING_REFERENCE',duration={**b['duration'],'remaining':9})
        self.complete(r);m=self.instance(r);self.assertEqual(m.instance_id,'modifier:1');self.assertEqual(m.refresh_count,1)
        self.assertEqual(m.duration['remaining'],9);self.assertEqual(m.dynamic_values['v'],8)
    def test_replace_records_removal_and_new_id(self):
        replacement=add('replace');r,p,d=self.runtime(nodes=[add(),replacement,finish()])
        p['applications'][replacement.stable_hash()]['application_policy']='REPLACE_EXISTING_REFERENCE'
        self.complete(r);m=self.instance(r);self.assertEqual(m.replacement_of,'modifier:1');self.assertEqual(m.instance_id,'modifier:2')
        self.assertTrue(any(h.get('removal_reason')=='REPLACED_REFERENCE' for h in r.state.modifier_history))
    def test_increment_stack_count_explicit_policy(self):
        stack=add('stack');r,p,d=self.runtime(nodes=[add(),stack,finish()])
        p['applications'][stack.stable_hash()].update(application_policy='INCREMENT_STACK_REFERENCE',stack=2,count=3)
        self.complete(r);m=self.instance(r);self.assertEqual((m.stack,m.count),(3,4))
    def test_reject_duplicate_and_insert_collision(self):
        second=add('second');r,p,d=self.runtime(nodes=[add(),second,finish()])
        p['applications'][second.stable_hash()]['application_policy']='REJECT_DUPLICATE_REFERENCE'
        self.complete(r);self.assertEqual(len(r.state.modifiers),1)
        r,p,d=self.runtime(nodes=[add(),second,finish()]);self.assertEqual(r.step('root').status,ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(len(r.state.modifiers),1)
    def test_different_original_caster_keeps_distinct_instances(self):
        second=add('second');r,p,d=self.runtime(nodes=[add(),second,finish()])
        p['applications'][second.stable_hash()]['original_caster']='a'
        self.complete(r);self.assertEqual(len(r.state.modifiers),2)
    def test_provider_precedence_and_callback_property_contribution(self):
        cb=property_task(value=lookup());r,p,d=self.runtime(callbacks=[(53,[cb])])
        before=r.state.properties['b']['hp'];r.state.dynamic_values['supplied']['v']=12
        self.complete(r);m=self.instance(r)
        self.assertEqual(r.state.properties['b']['hp'],before+8)
        self.assertEqual(len(m.property_contributions),1);self.assertEqual(len(m.event_registrations),1)
        self.assertEqual(r.state.scheduler.action_execution['metrics']['modifier_callbacks_completed'],1)
    def test_snapshot_read_in_later_callback(self):
        read=ExpressionIR('snapshot','modifier_snapshot_read',A,{'key':'saved_hp'})
        cb=task('snapshot_write','property_write',owner='a',key='x',operation='set',value=read)
        r,p,d=self.runtime(callbacks=[(53,[cb])]);self.complete(r);self.assertEqual(r.state.properties['a']['x'],5*SCALE)
    def test_missing_provider_and_read_are_gaps(self):
        r,p,d=self.runtime();p['applications'][add().stable_hash()]['source_provider']='missing'
        self.assertIn('DYNAMIC_PROVIDER_MISSING',r.step('root').gap.required_capability)
        r,p,d=self.runtime(callbacks=[(53,[property_task(value=lookup('absent'))])])
        self.assertIn('DYNAMIC_PROVIDER_MISSING',r.step('root').gap.required_capability)
        self.assertEqual(self.instance(r).property_contributions,[])
    def test_local_dynamic_write_and_later_read(self):
        cb=task('local_write','RPG.GameCore.SetDynamicValue',fields={'DynamicKey':expr('v'),'Value':expr(20,True)})
        r,p,d=self.runtime(callbacks=[(53,[cb,property_task(value=lookup())])])
        p['dynamic_writes']={cb.stable_hash():{'provider':'MODIFIER_LOCAL_REFERENCE'}}
        self.complete(r);self.assertEqual(self.instance(r).dynamic_values['v'],20)
    def test_registration_context_and_owner_action_drain(self):
        r,p,d=self.runtime(callbacks=[(53,[write('cb',3)])]);self.complete(r)
        s=r.state.scheduler.action_execution;c=next(iter(s['callbacks'].values()));m=self.instance(r)
        self.assertEqual(c['action_root_id'],s['current_root']);self.assertEqual(c['modifier_instance_id'],m.instance_id)
        for k,v in {'owner':'b','caster':'a','original_caster':'b','event_source':'a','param_entity':'b'}.items():
            self.assertEqual(c['context'][k],v)
        self.assertEqual(c['context']['action_root_id'],s['current_root']);self.assertEqual(m.pending_lifecycle_callbacks,[])
    def test_listener_order_and_nested_event_callbacks(self):
        nested=event('nested',54);r,p,d=self.runtime(callbacks=[(53,[write('first',1),nested]),(54,[write('nested_write',2)])])
        self.complete(r);self.assertEqual(r.state.properties['a']['x'],4)
        s=r.state.scheduler.action_execution;self.assertEqual(s['metrics']['modifier_callbacks_completed'],2)
        nested_frame=next(c for c in s['callbacks'].values() if c['callback_ir']['node_id'].endswith(
            next(n['callback']['node_id'].rsplit('/',1)[-1] for n in self.instance(r).event_registrations if n['event_id']==54)))
        self.assertIsNotNone(nested_frame['callback_owner'])
    def test_remove_listener_and_property_cleanup(self):
        remove=task('remove','modifier_remove_reference')
        r,p,d=self.runtime(callbacks=[(53,[property_task()])]);initial=r.state.properties['b']['hp'];self.complete(r)
        self.assertEqual(r.state.properties['b']['hp'],initial+6)
        r.actions['remove']=ability('remove',remove,finish());self.removal(p,remove)
        self.assertEqual(r.step('remove').status,ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(r.state.modifiers,{});self.assertEqual(r.state.properties['b']['hp'],initial)
        self.assertEqual(r.state.modifier_history[-1]['final_state']['event_registrations'],[])
    def test_pending_callback_retention_and_cancellation(self):
        for pending,expected in [('RETAIN_ENQUEUED_REFERENCE',6),('CANCEL_NOT_STARTED_REFERENCE',0)]:
            remove=task('remove','modifier_remove_reference')
            r,p,d=self.runtime(nodes=[add(),remove,finish()],callbacks=[(53,[write('cb',3)])])
            self.removal(p,remove,pending);self.complete(r);self.assertEqual(r.state.properties['a']['x'],expected)
    def test_retained_dynamic_read_after_removal(self):
        remove=task('remove','modifier_remove_reference')
        cb=task('retained','property_write',owner='a',key='x',operation='set',value=lookup())
        r,p,d=self.runtime(nodes=[add(),remove,finish()],callbacks=[(53,[cb])]);self.removal(p,remove)
        self.complete(r);self.assertEqual(r.state.properties['a']['x'],8)
    def test_persistence_across_actions_no_original_action_open(self):
        r,p,d=self.runtime(callbacks=[(53,[write('cb',3)])],activation=[]);self.complete(r)
        original=r.state.scheduler.action_execution['current_root']
        r.actions['later']=ability('later',event(),finish());self.assertEqual(r.step('later').status,ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        s=r.state.scheduler.action_execution;self.assertNotEqual(original,s['current_root'])
        self.assertTrue(all(c['action_root_id']==s['current_root'] for c in s['callbacks'].values()))
        self.assertEqual(len(r.state.modifiers),1)
    def test_explicit_lifetime_advance_and_expiry_event(self):
        advance=task('advance','modifier_lifetime_advance_reference',delta=5)
        r,p,d=self.runtime(nodes=[add(),advance,finish()]);self.complete(r);self.assertEqual(r.state.modifiers,{})
        r,p,d=self.runtime(nodes=[add(),event(event_id=100),finish()]);p['applications'][add().stable_hash()]['duration']={
            'units':'EXPLICIT_REFERENCE_UNITS','remaining':None,'expiry':'EXPLICIT_EVENT_REFERENCE','event_id':100}
        self.complete(r);self.assertEqual(r.state.modifiers,{})
    def test_construct_then_explicit_delayed_activation(self):
        activate=task('activate','modifier_activate_reference')
        r,p,d=self.runtime(nodes=[add(),activate,finish()],callbacks=[(53,[write('cb',2)])])
        p['definitions'][d['definition_id']]['activation']='CONSTRUCT_ONLY_REFERENCE'
        p['activations']={activate.stable_hash():{'instance_id':'modifier:1','activation':'ACTIVATE_REFERENCE'}}
        self.complete(r);self.assertEqual(self.instance(r).activation_state,'REFERENCE_INSTANCE_ACTIVE');self.assertEqual(r.state.properties['a']['x'],4)
    def test_callback_gap_is_resumable_without_duplication(self):
        bad=property_task(value=lookup('missing'));r,p,d=self.runtime(callbacks=[(53,[write('before',1),bad])])
        result=r.step('root');self.assertEqual(result.status,ExecutionStatus.SEMANTIC_GAP)
        before=r.state.stable_hash();again=r.run_until_blocked();self.assertEqual(result.gap,again.gap);self.assertEqual(before,r.state.stable_hash())
        self.instance(r).dynamic_values['missing']=2
        self.assertEqual(r.run_until_blocked().status,ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(len(self.instance(r).property_contributions),1)
    def test_half_registration_rolls_back_application(self):
        r,p,d=self.runtime(callbacks=[(53,[write('first',1)]),(54,[write('second',2)])])
        callbacks=p['definitions'][d['definition_id']]['callbacks'];del callbacks[next(reversed(callbacks))]
        self.assertIn('EVENT_REGISTRATION_UNKNOWN',r.step('root').gap.required_capability)
        self.assertEqual((r.state.modifiers,r.state.next_modifier_id,r.state.next_listener_id),({},0,0))
    def test_callback_cycle_budget_and_rollback(self):
        recursive=event('repeat');r,p,d=self.runtime(nodes=[add(),recursive,finish()],callbacks=[(53,[recursive])],activation=[])
        result=r.step('root');self.assertIn('CYCLE',result.gap.required_capability)
        before=r.state.stable_hash();self.assertEqual(r.run_until_blocked().gap,result.gap);self.assertEqual(before,r.state.stable_hash())
    def test_clone_mid_callback_snapshot_hash_and_replay(self):
        r,p,d=self.runtime(callbacks=[(53,[wait('callback_wait',2),write('cb',2)])])
        initial=r.snapshot();r.start_action('root');self.assertEqual(r.run_ready().status,ExecutionStatus.WAITING_SCHEDULER)
        engines=[r,r.clone(),BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))]
        results=[e.run_until_blocked() for e in engines]
        self.assertEqual(results[0],results[1]);self.assertEqual(results[0],results[2]);self.assertEqual(len({e.stable_hash() for e in engines}),1)
        replay,outcomes=BehaviorRuntime.from_snapshot(initial).replay(['root']);self.assertEqual(replay.stable_hash(),r.stable_hash())
    def test_policy_identity_changes_state_hash(self):
        r,p,d=self.runtime();self.complete(r);clone=r.state.clone();self.instance(r).reference_policy['application_policy']='NATIVE_POLICY_UNKNOWN'
        self.assertNotEqual(r.state.stable_hash(),clone.stable_hash())

    def test_listener_priority_order_and_false_predicate(self):
        condition=PredicateIR('false','comparison',A,{'expression':expr(False)})
        r,p,d=self.runtime(callbacks=[(53,[write('first',1)]),(53,[write('second',2)]),(53,[write('skipped',9)],condition)])
        bindings=list(p['definitions'][d['definition_id']]['callbacks'].values())
        bindings[0]['priority']=10;bindings[1]['priority']=0;bindings[2]['priority']=-10
        self.complete(r);self.assertEqual(r.state.properties['a']['x'],2)
        s=r.state.scheduler.action_execution
        order=[h['node'] for h in s['history'] if h.get('status')=='TASK_COMPLETE']
        self.assertLess(order.index('second'),order.index('first'));self.assertNotIn('skipped',order)
    def test_random_selector_rolls_back_on_late_registration_gap(self):
        node=task('random_add','RPG.GameCore.AddModifier',roles={'modifier':expr('buff'),
            'target':TargetSelectorIR('random','random',A,{'source':TargetSelectorIR('candidates','explicit',A,{'entities':['a','b']})})})
        r,p,d=self.runtime(nodes=[node,finish()],callbacks=[(53,[write('first',1)])])
        p['applications'][node.stable_hash()]['owner']='RESOLVED_TARGET_REFERENCE'
        p['definitions'][d['definition_id']]['callbacks']={}
        result=r.step('root');self.assertIn('EVENT_REGISTRATION_UNKNOWN',result.gap.required_capability)
        self.assertEqual(r.state.rng.draws,0);self.assertEqual(r.state.modifiers,{})
        before=r.state.stable_hash();r.run_until_blocked();self.assertEqual(r.state.stable_hash(),before)
    def test_callback_depth_limit(self):
        r,p,d=self.runtime(callbacks=[(53,[event('nested',54)]),(54,[write('second',2)])])
        r.policies['r15_action_scheduler_reference_v1']['max_callback_depth']=1
        self.assertIn('DEPTH',r.step('root').gap.required_capability)
    def test_remove_config_target_and_filter(self):
        remove=task('remove_config','RPG.GameCore.RemoveModifier',roles={'target':target(),'modifier':expr('buff')})
        r,p,d=self.runtime(nodes=[add(),remove,finish()])
        p['removals'][remove.stable_hash()]={'selection':'CONFIG_TARGET_REFERENCE','identity_filter':{'caster':'a'},
            'reason':'CONFIG_REFERENCE','pending_callbacks':'RETAIN_ENQUEUED_REFERENCE'}
        self.complete(r);self.assertEqual(r.state.modifiers,{})
    def test_explicit_heal_stage_callback_before_hp_settlement(self):
        cb=task('amount_override','dynamic_write',scope='supplied',key='heal_amount',value=expr(SCALE,True))
        heal=task('heal','RPG.GameCore.HealHP',fields={'FormulaType':2,'TargetType':target()})
        r,p,d=self.runtime(nodes=[add(),heal,finish()],callbacks=[(90,[cb])],activation=[])
        p['heal_stages'][heal.stable_hash()]={'formula':'FORMULA_TYPE2_REFERENCE','settlement':'CLAMP_HP_REFERENCE',
            'ordering':['pre_heal','effective_amount','settlement','hp_mutation','post_heal'],
            'events':{'pre_heal':None,'effective_amount':90,'settlement':None,'hp_mutation':None,'post_heal':None},
            'event_source':'a','amount_provider':'supplied','amount_key':'heal_amount','cap_enabled':False,
            'operands':{'d50':SCALE,'d28':SCALE,'d60':0,'dD0':0,'d38':0,'d128':0,'d48':100*SCALE,'dD8':0}}
        initial=r.state.properties['b']['hp'];self.complete(r)
        self.assertEqual(r.state.properties['b']['hp'],initial+SCALE)
        s=r.state.scheduler.action_execution
        self.assertEqual(s['metrics']['reference_heal_settlements'],1)
        self.assertEqual(s['metrics']['modifier_callbacks_completed'],1)
    def test_damage_extension_does_not_implement_damage_formula(self):
        extension=task('before_damage','combat_event_extension_reference',stage='before_damage',event_id=90,source='a')
        r,p,d=self.runtime(nodes=[add(),extension,finish()],callbacks=[(90,[write('callback',1)])],activation=[])
        self.complete(r);self.assertEqual(r.state.properties['a']['x'],2)
        r,p,d=self.runtime(nodes=[task('damage','RPG.GameCore.DamageByAttackProperty'),finish()])
        self.assertIn('DAMAGE',r.step('root').gap.required_capability)
    def test_initial_dynamic_values_use_explicit_source_provider(self):
        r,p,d=self.runtime();r.state.dynamic_values['selected']={'input':12}
        r.state.dynamic_values['supplied']['input']=4
        p['applications'][add().stable_hash()].update(source_provider='selected',initial_dynamic_values={'v':lookup('input').to_dict()})
        # Policy documents carry IR as JSON; initialization accepts serialized IR.
        self.complete(r);self.assertEqual(self.instance(r).dynamic_values['v'],12)
    def test_numeric_callback_field_never_becomes_predicate(self):
        r,p,d=self.runtime(callbacks=[(53,[write('cb',1)],7)])
        binding=next(iter(p['definitions'][d['definition_id']]['callbacks'].values()))
        binding['fields']['2']='predicate'
        self.assertIn('numeric fields are not predicates',r.step('root').gap.required_capability)
        self.assertEqual(r.state.modifiers,{})
        r,p,d=self.runtime(callbacks=[(53,[write('cb',1)],7)])
        self.complete(r);self.assertEqual(self.instance(r).event_registrations[0]['opaque_decoded_fields'],[7])

class R17RealContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from r16_dependency_closure import load_catalog
        from r17_checks import AUDIT,read
        cls.catalog=load_catalog();cls.definitions=cls.catalog.modifier_definitions()
        cls.fixtures=read(AUDIT/'real_modifier_reference_fixtures.json')
    def test_exact_unique_definition_census_and_pins(self):
        import hashlib
        self.assertEqual(len(self.definitions),296)
        self.assertEqual(sum(not d['source_pointer'] for d in self.definitions.values()),153)
        state=BehaviorBattleState()
        self.assertEqual(bind_definitions(state,self.catalog),296)
        self.assertEqual(state.stable_hash(),state.clone().stable_hash())
        for d in self.definitions.values():
            with self.subTest(source=d['source_identity']):
                self.assertEqual(d['graph_hash'],stable_hash(d['decoded_graph']))
                self.assertEqual(hashlib.sha256((ROOT/d['source_artifact']).read_bytes()).hexdigest(),d['source_artifact_sha256'])
                self.assertEqual(d['native_activation'],'NATIVE_EFFECTIVE_STATE_UNKNOWN')
    def test_real_addmodifier_config_callback_and_determinism(self):
        from r17_probes import wrapper
        from r17_reference_fixtures import callback_nodes
        from r13_reference_fixtures import fixture
        from r15_scheduler_probes import probe_policy,POLICY_ID as SCHEDULER_POLICY
        completed=[]
        for f in self.fixtures:
            with self.subTest(config=f['config']):
                definition=self.definitions[f['definition']['definition_id']]
                self.assertEqual(definition,f['definition'])
                node=IRNode.from_dict(f['node'])
                aliases_needed={n.payload['alias'] for cb in callback_nodes(definition)
                               for n in walk_nodes(cb)
                               if n.op=='RPG.GameCore.TargetAlias'}
                aliases_needed.update(n.payload['alias'] for n in walk_nodes(node) if n.op=='RPG.GameCore.TargetAlias')
                _,aliases,policies=fixture(aliases_needed)
                policies[SCHEDULER_POLICY]=probe_policy();policies[POLICY_ID]=f['policy']
                root=wrapper(node,f['config']+'/reference',node.authority)
                r=BehaviorRuntime(BehaviorBattleState.from_snapshot(f['initial_state']),actions={'probe':root},
                    aliases=aliases,abilities=self.catalog.executable_abilities(),templates=self.catalog.compiled_templates(),policies=policies)
                r.start_action('probe');r.run_ready(5)
                engines=[r,r.clone(),BehaviorRuntime.from_snapshot(r.snapshot())]
                results=[x.run_until_blocked() for x in engines]
                self.assertEqual(results[0],results[1]);self.assertEqual(results[0],results[2])
                self.assertEqual(len({x.state.stable_hash() for x in engines}),1)
                if results[0].status==ExecutionStatus.ACTION_REFERENCE_COMPLETE:completed.append(f['config'])
                else:self.assertEqual(results[0].status,ExecutionStatus.SEMANTIC_GAP)
                self.assertTrue(r.state.modifiers)
                for m in r.state.modifiers.values():self.assertEqual(m.authority['native_effective_state'],'UNKNOWN')
        self.assertIn('MAvatar_Bailu_00_PointB3',completed)
        self.assertIn('MAvatar_Acheron_00_Rank06_ForceStanceDamage',completed)
        self.assertIn('MAvatar_Seele_Rank06',completed)
    def test_natasha_progression_not_supplied_and_frozen_denominators(self):
        from r17_checks import AUDIT,read
        summary=read(AUDIT/'probe_summary.json');natasha=read(AUDIT/'natasha_regression.json')
        self.assertEqual((summary['combat']['after']['roots'],summary['joined']['after']['roots']),(632,160))
        self.assertTrue(natasha['actor_progression_preserved']);self.assertFalse(natasha['native_actor_supplied'])

if __name__=='__main__': unittest.main()
