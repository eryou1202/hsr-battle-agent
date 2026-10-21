"""R20 actor provenance, progression and owned resource transactions."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from dataclasses import asdict, replace
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime')]
from hsr_battle_agent.battle_ir.behavior import IRNode, PredicateIR, TaskSequenceIR, stable_hash
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime,GapError,ExecutionStatus as Status
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState,ModifierInstance
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.actor_binding import ActorRuntimeBinding,supplied,unknown,POLICY_ID as ACTOR
from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE,reference_policy,store
from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID as MODIFIER,reference_policy as modifier_policy
from hsr_battle_agent.battle_runtime.dynamic_property import POLICY_ID as PROPERTY,reference_policy as property_policy,read
from r20_reference_fixtures import actor_binding,resource_spec,progression_policy
from r19_reference_fixtures import provider_binding,effective_binding
from tests.battle_runtime.test_behavior_r15 import A,ability,task,expr,finish,write
from tests.battle_runtime import test_behavior_r15 as r15
from tests.battle_runtime.test_behavior_r17 import definition,property_task
from r17_reference_fixtures import definition_binding

class R20Tests(unittest.TestCase):
    def runtime(self,*nodes,spec=None):
        source=nodes or (task('mutation','resource_mutation_reference',binding='counter'),finish())
        r=r15.R15Tests().runtime(ability('root',*source))
        r.policies[MODIFIER]=modifier_policy();r.policies[RESOURCE]=reference_policy()
        r.state.entities['a']['team']='team';r.state.entities['b']['team']='team'
        r.state.actor_resources={'a':{'reference_actor_counter':4*SCALE},'b':{'reference_actor_counter':SCALE}}
        r.state.team_resources={'team':{'reference_actor_counter':3*SCALE}}
        r.policies[RESOURCE]['bindings']['counter']=copy.deepcopy(spec or resource_spec())
        return r
    def done(self,r):
        out=r.step('root');self.assertEqual(out.status,Status.ACTION_REFERENCE_COMPLETE,str(out.gap));return out
    def balance(self,r):return r.state.actor_resources['a']['reference_actor_counter']
    def listener(self,r,callback,event='change',identity='initial',owner='a'):
        d,_=definition([(event,[callback])]);r.state.modifier_definitions[d['definition_id']]=d
        spec=definition_binding(d,data_only_masks=[],activation_event_ids=[],source_precedence=['MODIFIER_LOCAL','SNAPSHOT','SOURCE_PROVIDER'],
            activation='ACTIVATE_REFERENCE',pending_callbacks='RETAIN_ENQUEUED_REFERENCE')
        m=ModifierInstance(identity,d['config_identity'],owner,'a','a',1,1,
            {'units':'EXPLICIT_REFERENCE_UNITS','remaining':10,'expiry':'MANUAL_REFERENCE'},
            definition_id=d['definition_id'],source_ability='fixture',target=owner,activation_state='REFERENCE_INSTANCE_ACTIVE',
            reference_policy={'initialization_evidence':'explicit R20 reference active instance'},
            authority={'semantic_authority':'REFERENCE_MODEL','definition_graph_hash':d['graph_hash']},
            dynamic_values={'initial':0},snapshot_data={'initial_hp':r.state.properties[owner]['hp']},
            provider_binding={'application_context':copy.deepcopy(r.state.target_context),'source_provider':'supplied',
                'definition_policy':spec,'precedence':['SOURCE_PROVIDER'],'lookup_scopes':['supplied']},
            event_registrations=[{'registration_id':identity+'/registration','modifier_instance_id':identity,
                'event_id':event,'owner':owner,'order':0,'condition':None,'callback':callback.to_dict(),
                'context_policy':'OWNER_CASTER_TARGET_EVENT_EXPLICIT_REFERENCE'}])
        r.state.modifiers[identity]=m
        s=r.policies[RESOURCE]['bindings']['counter'];s['events']['RESOURCE_CHANGE']=[event];s['listener_registrations']=[identity+'/registration']
        return m

    def test_actor_multiple_source_backed_identities(self):
        r=self.runtime();r.bind_actor(actor_binding('low',1001));r.bind_actor(actor_binding('high',1002,level=70,promotion=5,rank=3))
        self.assertEqual(r.state.entities['high']['promotion'],5)
        self.assertEqual(r.state.progression['high']['rank'],3)
        self.assertEqual(r.state.entities['low']['content_identity'],1001)
        self.assertEqual(r.state.mechanics[ACTOR]['actors']['high']['native_legality'],'EFFECTIVE_RUNTIME_UNKNOWN')
    def test_missing_zero_false_unknown_are_distinct(self):
        r=self.runtime();b=actor_binding('new',1001,fields={'rank':supplied(0),'entity_state':supplied({'alive':False}),'promotion':unknown()})
        r.bind_actor(b);self.assertEqual(r.state.progression['new']['rank'],0);self.assertFalse(r.state.entities['new']['alive'])
        self.assertNotIn('promotion',r.state.entities['new']);self.assertNotIn('level',r.state.entities['new'])
        self.assertEqual(r.state.mechanics[ACTOR]['actors']['new']['field_provenance']['promotion']['status'],'UNKNOWN')
    def test_source_pin_tamper_rejected(self):
        r=self.runtime();b=actor_binding('new',1001);c=copy.deepcopy(b.content);c['artifact_sha256']='0'*64
        before=r.stable_hash()
        with self.assertRaisesRegex(GapError,'PROVENANCE'):r.bind_actor(replace(b,content=c))
        self.assertEqual(before,r.stable_hash())
    def test_record_tamper_even_rehashed_rejected(self):
        r=self.runtime();b=actor_binding('new',1001);c=copy.deepcopy(b.content);c['record']['graph']['fields'][0]['values'][0]['value']=999
        c['record_hash']=stable_hash(c['record']);c['identity']=999
        with self.assertRaisesRegex(GapError,'PROVENANCE'):r.bind_actor(replace(b,content=c))
    def test_exact_static_field_provenance(self):
        r=self.runtime();b=actor_binding('new',1001);v=b.content['record']['ordinal']
        f={'presentation':{'status':'KNOWN','authority':'REAL_CONTENT_RECONSTRUCTED','evidence':'source table ordinal for presentation',
                   'version':'4.6.51','pointer':'/ordinal','value':v}}
        r.bind_actor(replace(b,fields=f));self.assertEqual(r.state.presentation['actors']['new'],v)
        f['presentation']['value']=v+1
        with self.assertRaisesRegex(GapError,'PROVENANCE'):self.runtime().bind_actor(replace(b,fields=f))
    def test_version_boundary(self):
        r=self.runtime();b=actor_binding('new',1001)
        with self.assertRaisesRegex(GapError,'VERSIONED_CONTENT_GAP'):r.bind_actor(replace(b,content_version='4.4.54'))
    def test_relabelled_content_version_rejected_by_manifest(self):
        r=self.runtime();b=actor_binding('new',1001);c=copy.deepcopy(b.content);c['version']='4.4.54'
        with self.assertRaisesRegex(GapError,'VERSIONED_CONTENT_GAP'):r.bind_actor(replace(b,content_version='4.4.54',content=c))
    def test_explicit_override_and_unknown_remove_bound_value(self):
        r=self.runtime();b=actor_binding('new',1001);r.bind_actor(replace(b,overrides={'rank':supplied(2)}))
        self.assertEqual(r.state.progression['new']['rank'],2)
        with self.assertRaisesRegex(GapError,'ALREADY_BOUND'):r.bind_actor(b)
    def test_bad_numeric_actor_initialization_atomic(self):
        r=self.runtime();before=r.stable_hash()
        with self.assertRaises(GapError):r.bind_actor(actor_binding('new',1001,hp=3,max_hp=10))
        self.assertEqual(before,r.stable_hash())
    def test_missing_property_is_not_fabricated(self):
        r=self.runtime();r.bind_actor(actor_binding('new',1001,fields={}))
        self.assertNotIn('new',r.state.properties);self.assertNotIn('new',r.state.actor_resources)
    def test_explicit_dynamic_zero_and_ability_catalog_gap(self):
        r=self.runtime();r.bind_actor(actor_binding('new',1001,dynamic_providers={'actor/new':{'v':0}}))
        self.assertEqual(r.state.dynamic_values['actor/new']['v'],0)
        with self.assertRaisesRegex(GapError,'ABILITY_CATALOG_GAP'):self.runtime().bind_actor(actor_binding('new',1001,ability_references=['missing']))
    def test_partial_skill_tree_true_false_missing(self):
        n=PredicateIR('tree','RPG.GameCore.BySkillPointActivated',A,{'fields':{'unbound_bit_0':77}})
        r=self.runtime();r.policies[ACTOR]=progression_policy([n]);r.bind_actor(actor_binding('a',1001,activated_skill_tree_rows={'77':False}))
        self.assertFalse(r.predicate(n));r.state.progression['a']['activated_skill_tree_rows']['77']=True;self.assertTrue(r.predicate(n))
        del r.state.progression['a']['activated_skill_tree_rows']['77']
        with self.assertRaisesRegex(GapError,'PROGRESSION_INPUT_MISSING'):r.predicate(n)
    def test_rank_reuses_r19_keyed_threshold(self):
        n=PredicateIR('rank','RPG.GameCore.ByRankActivated',A,{'fields':{'unbound_bit_0':2089636447}})
        r=self.runtime();p=property_policy();r.policies[PROPERTY]=p
        p['rank_bindings'][n.stable_hash()]={'authority':'REFERENCE_MODEL','evidence':'explicit threshold',
            'mode':'KEYED_THRESHOLD_GE_REFERENCE','key_field':'unbound_bit_0','actor_context':'caster'}
        r.bind_actor(actor_binding('a',1001,rank=2,rank_requirements={'2089636447':2}));self.assertTrue(r.predicate(n))
        del r.state.progression['a']['rank'];self.assertRaisesRegex(GapError,'RANK_INPUT_MISSING',r.predicate,n)
        r.state.progression['a']['rank']=0;del r.state.progression['a']['rank_requirements'];self.assertRaisesRegex(GapError,'RANK_INPUT_MISSING',r.predicate,n)
        p['rank_bindings']={};self.assertRaisesRegex(GapError,'RANK_POLICY_MISSING',r.predicate,n)
    def test_skill_tree_key_after_explicit_target_slot(self):
        from hsr_battle_agent.battle_ir.behavior import TargetSelectorIR
        n=PredicateIR('targeted_tree','RPG.GameCore.BySkillPointActivated',A,{'fields':{
            'unbound_bit_0':TargetSelectorIR('actor-target','explicit',A,{'entities':['a']}),'unbound_bit_1':77},
            'reference_binding':{'unknown_slots':[{'mask':4,'field_index':0},{'mask':8,'field_index':1}]}})
        r=self.runtime();r.policies[ACTOR]=progression_policy([n]);r.bind_actor(actor_binding('a',1001,activated_skill_tree_rows={'77':True}))
        self.assertTrue(r.predicate(n));r.state.target_context['caster']='b'
        self.assertRaisesRegex(GapError,'ACTOR_OWNERSHIP_GAP',r.predicate,n)
    def test_actor_resource_cannot_change_team_or_other_actor(self):
        r=self.runtime();self.done(r);self.assertEqual(self.balance(r),6*SCALE)
        self.assertEqual(r.state.actor_resources['b']['reference_actor_counter'],SCALE)
        self.assertEqual(r.state.team_resources['team']['reference_actor_counter'],3*SCALE)
    def test_team_resource_shared_ownership(self):
        r=self.runtime(spec=resource_spec(domain='TEAM_RESOURCE',owner='team'));self.done(r)
        self.assertEqual(r.state.team_resources['team']['reference_actor_counter'],5*SCALE);self.assertEqual(self.balance(r),4*SCALE)
    def test_team_of_actor_resolution(self):
        s=resource_spec(domain='TEAM_RESOURCE',owner={'context':'caster'});s['owner_resolution']='TEAM_OF_ACTOR_REFERENCE'
        r=self.runtime(spec=s);self.done(r);self.assertEqual(r.state.team_resources['team']['reference_actor_counter'],5*SCALE)
    def test_entity_resource_namespace_independent(self):
        r=self.runtime(spec=resource_spec(domain='ENTITY_RESOURCE'));store(r.state)['entity_resources']={'a':{'reference_actor_counter':0}}
        self.done(r);self.assertEqual(store(r.state)['entity_resources']['a']['reference_actor_counter'],2*SCALE);self.assertEqual(self.balance(r),4*SCALE)
    def test_ability_local_owner_must_be_action_owned(self):
        s=resource_spec(domain='ABILITY_LOCAL_RESOURCE',owner='missing');r=self.runtime(spec=s)
        self.assertIn('OWNERSHIP_GAP',r.step('root').gap.required_capability)
    def test_ability_local_value_does_not_alias_actor_counter(self):
        r=self.runtime();r.start_action('root');d=r.state.scheduler.action_execution
        aid=d['roots'][d['current_root']]['root_ability_id']
        r.policies[RESOURCE]['bindings']['counter']=resource_spec(domain='ABILITY_LOCAL_RESOURCE',owner=aid)
        store(r.state)['ability_resources']={aid:{'reference_actor_counter':0}}
        self.assertEqual(r.run_until_action_complete().status,Status.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(store(r.state)['ability_resources'][aid]['reference_actor_counter'],2*SCALE)
        self.assertEqual(self.balance(r),4*SCALE)
    def test_all_reference_operations(self):
        expected={'READ':4,'SET':2,'ADD':6,'SUBTRACT':2,'CLAMP':4,'COMPARE':4}
        for op,value in expected.items():
            with self.subTest(op=op):
                s=resource_spec(operation=op);s['comparison']='GE';r=self.runtime(spec=s);self.done(r)
                self.assertEqual(self.balance(r),value*SCALE)
                h=store(r.state)['history'][0];self.assertEqual(h['pre_value'],4*SCALE)
                if op=='COMPARE':self.assertTrue(h['comparison'])
    def test_caps_and_overcap(self):
        s=resource_spec(amount=20*SCALE);r=self.runtime(spec=s);self.done(r);self.assertEqual(self.balance(r),10*SCALE)
        s['bounds']['handling']='REJECT_REFERENCE';r=self.runtime(spec=s)
        self.assertIn('BOUNDS_REJECTED',r.step('root').gap.required_capability);self.assertEqual(self.balance(r),4*SCALE)
        s=resource_spec(operation='CLAMP');r=self.runtime(spec=s);r.state.actor_resources['a']['reference_actor_counter']=12*SCALE
        self.assertIn('INITIAL_OVERCAP',r.step('root').gap.required_capability)
        r.policies[RESOURCE]['bindings']['counter']['bounds']['initial_overcap']='ALLOW_REFERENCE';self.assertEqual(r.run_until_action_complete().status,Status.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(self.balance(r),10*SCALE)
    def test_unknown_cap_rounding_scope_and_owner_are_gaps(self):
        for field,value in [('bounds',{}),('numeric','native'),('domain','UNKNOWN_NATIVE_RESOURCE'),('owner','missing')]:
            with self.subTest(field=field):
                s=resource_spec();s[field]=value;r=self.runtime(spec=s);out=r.step('root')
                self.assertEqual(out.status,Status.SEMANTIC_GAP);self.assertEqual(self.balance(r),4*SCALE)
    def test_zero_is_valid_missing_is_gap(self):
        r=self.runtime();r.state.actor_resources['a']['reference_actor_counter']=0;self.done(r);self.assertEqual(self.balance(r),2*SCALE)
        r=self.runtime();del r.state.actor_resources['a']['reference_actor_counter'];self.assertIn('INITIAL_VALUE_MISSING',r.step('root').gap.required_capability)
    def test_resource_callback_owned_and_ordered(self):
        r=self.runtime();self.listener(r,write('callback',5));self.done(r)
        self.assertEqual(r.state.properties['a']['x'],10);h=store(r.state)['history'][0];self.assertEqual(len(h['callbacks_processed']),1)
        d=r.state.scheduler.action_execution;c=next(iter(d['callbacks'].values()))
        self.assertEqual(c['action_root_id'],h['action_root_id']);self.assertEqual(c['ability_instance_id'],h['ability_instance_id'])
    def test_no_implicit_listener_set(self):
        r=self.runtime();self.listener(r,write('callback',1));r.policies[RESOURCE]['bindings']['counter']['listener_registrations']=[]
        self.assertIn('LISTENER_STATE_UNKNOWN',r.step('root').gap.required_capability)
    def test_callback_gap_rolls_back_value_rng_queues_registration(self):
        bad=task('bad','unknown-resource-callback');r=self.runtime(write('earlier',9),task('mutation','resource_mutation_reference',binding='counter'),finish())
        random=task('random','random_choice',choices=[write('provisional',1),write('provisional',2)])
        self.listener(r,TaskSequenceIR('nested_callback','immediate_sequence',A,{'tasks':[random,bad]}))
        rng=r.state.rng.state;listeners=copy.deepcopy(r.state.modifiers);out=r.step('root')
        self.assertEqual(out.status,Status.SEMANTIC_GAP);self.assertEqual(out.gap.task_type,'unknown-resource-callback');self.assertEqual(self.balance(r),4*SCALE)
        self.assertEqual(r.state.properties['a']['x'],18);self.assertEqual(r.state.rng.state,rng);self.assertEqual(r.state.rng.draws,0)
        self.assertEqual(r.state.modifiers,listeners);self.assertFalse(r.state.damage_transactions)
        self.assertEqual(r.state.scheduler.action_execution['event_queue'],[]);self.assertNotIn(RESOURCE,r.state.mechanics)
    def test_gap_resumption_after_explicit_policy_repair(self):
        r=self.runtime(spec=resource_spec(amount=20*SCALE));r.policies[RESOURCE]['bindings']['counter']['bounds']['handling']='REJECT_REFERENCE'
        self.assertEqual(r.step('root').status,Status.SEMANTIC_GAP)
        r.policies[RESOURCE]['bindings']['counter']['bounds']['handling']='CLAMP_REFERENCE'
        self.assertEqual(r.run_until_action_complete().status,Status.ACTION_REFERENCE_COMPLETE);self.assertEqual(self.balance(r),10*SCALE)
    def test_cost_explicit_source_and_insufficient_atomic(self):
        n=task('cost','resource_cost_reference',binding='counter');s=resource_spec(operation='SUBTRACT',amount=5*SCALE)
        s.update(cost_authority='EXPLICIT_SCENARIO_INPUT',cost_source='fixture/cost')
        r=self.runtime(n,finish(),spec=s);self.assertIn('COST_INSUFFICIENT',r.step('root').gap.required_capability);self.assertEqual(self.balance(r),4*SCALE)
        s['amount']=2*SCALE;r=self.runtime(n,finish(),spec=s);self.done(r);self.assertEqual(self.balance(r),2*SCALE)
    def test_modify_sp_requires_exact_source_binding(self):
        rows=json.loads((ROOT/'tmp/audit/r20_actor_resource_progression_20261010_001/resource_instruction_census.json').read_text())['instances']
        n=IRNode.from_dict(next(x['node'] for x in rows if x['node']['op']=='RPG.GameCore.ModifySPNew'))
        r=self.runtime(n,finish());out=r.step('root');self.assertIn('BINDING_MISSING',out.gap.required_capability)
    def test_real_resource_operand_survives_canonical_checkpoint(self):
        from r20_reference_fixtures import extend
        rows=json.loads((ROOT/'tmp/audit/r20_actor_resource_progression_20261010_001/resource_instruction_census.json').read_text())['instances']
        n=IRNode.from_dict(next(x['node'] for x in rows if x['node']['op']=='RPG.GameCore.ModifySPNew'))
        from hsr_battle_agent.battle_ir.behavior import walk_nodes
        from r13_reference_fixtures import fixture
        from r15_scheduler_probes import probe_policy
        from hsr_battle_agent.battle_runtime.action_scheduler import POLICY_ID as SCHEDULER
        nodes=list(walk_nodes(n));state,aliases,policies=fixture({x.payload['alias'] for x in nodes if x.op=='RPG.GameCore.TargetAlias'},
                                                              {x.payload['key'] for x in nodes if x.op=='lookup'})
        policies[SCHEDULER]=probe_policy();policies[MODIFIER]=modifier_policy()
        r=BehaviorRuntime(state,actions={'root':ability('root',n)},aliases=aliases,policies=policies)
        extend(r,nodes,avatar_id=1001);r.start_action('root');r.run_ready(3)
        restored=BehaviorRuntime.from_snapshot(r.snapshot());out=restored.run_until_action_complete()
        self.assertEqual(out.status,Status.WAITING_SCHEDULER,str(out.gap))
        self.assertEqual(store(restored.state)['history'][0]['post_value'],2*SCALE)
    def test_nested_damage_gap_rolls_back_resource_and_hp(self):
        from r18_reference_fixtures import task_binding
        from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID as DAMAGE,reference_policy as damage_policy
        n=IRNode.from_dict(json.loads((ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001/real_damage_fixtures.json').read_text())[0]['node'])
        r=self.runtime();self.listener(r,TaskSequenceIR('damage_callback','immediate_sequence',A,{'tasks':[n,task('unsupported_after_hp','unsupported_after_hp')]}))
        r.state.properties['a']['reference_atk']=10*SCALE;r.state.properties['b']['hp']=100*SCALE;r.state.properties['b']['max_hp']=100*SCALE
        r.policies[DAMAGE]=damage_policy();r.policies[DAMAGE]['tasks'][n.stable_hash()]=task_binding(n)
        from hsr_battle_agent.battle_ir.behavior import walk_nodes,TargetSelectorIR
        for x in walk_nodes(n):
            if x.op=='lookup':r.state.dynamic_values['supplied'][str(x.payload['key'])]=2*SCALE
            if x.op=='RPG.GameCore.TargetAlias':r.aliases[x.payload['alias']]=TargetSelectorIR('bound-target','explicit',A,{'entities':['b']})
        before=r.state.properties['b']['hp'];out=r.step('root');self.assertEqual(out.status,Status.SEMANTIC_GAP)
        self.assertEqual(out.gap.task_type,'unsupported_after_hp')
        self.assertEqual(self.balance(r),4*SCALE);self.assertEqual(r.state.properties['b']['hp'],before)
        self.assertFalse(r.state.damage_requests);self.assertFalse(r.state.damage_transactions)
    def test_replay_api_with_bound_actor_state(self):
        initial=self.runtime();initial.bind_actor(actor_binding('a',1001))
        replay,results=initial.replay(['root']);direct=initial.clone();out=direct.step('root')
        self.assertEqual(results,(out,));self.assertEqual(replay.stable_hash(),direct.stable_hash())
        self.assertEqual(initial.state.actor_resources['a']['reference_actor_counter'],0)
    def test_pre_change_post_callbacks_drain_in_policy_order(self):
        r=self.runtime();m=self.listener(r,write('change',2),event='change')
        registrations=m.event_registrations
        for event_id,name,value in [('pre','pre',1),('post','post',3)]:
            reg=copy.deepcopy(registrations[0]);reg.update(event_id=event_id,registration_id=event_id,callback=write(name,value).to_dict())
            registrations.append(reg)
        spec=r.policies[RESOURCE]['bindings']['counter'];spec['events']={'PRE_RESOURCE':['pre'],'RESOURCE_CHANGE':['change'],'POST_RESOURCE':['post']}
        spec['listener_registrations']=[x['registration_id'] for x in registrations]
        self.done(r);self.assertEqual(r.state.properties['a']['x'],6)
        order=[h['node'] for h in r.state.scheduler.action_execution['history'] if h.get('status')=='TASK_COMPLETE']
        self.assertLess(order.index('pre'),order.index('change'));self.assertLess(order.index('change'),order.index('post'))
    def test_real_cross_character_source_wrappers_not_full_skills(self):
        audit=ROOT/'tmp/audit/r20_actor_resource_progression_20261010_001/isolated_real_resource_results.json'
        rows=json.loads(audit.read_text());self.assertEqual(len(rows),39)
        self.assertGreaterEqual(len({r['binding']['content']['identity'] for r in rows if r['records']}),3)
        self.assertTrue(all(not r['full_real_skill_transition'] and not r['finish_nodes_added'] for r in rows))
    def test_snapshot_clone_hash_replay_every_checkpoint(self):
        for budget in (0,1,3,7,11,18):
            r=self.runtime();r.start_action('root');r.run_ready(budget)
            engines=[r,r.clone(),BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))]
            self.assertEqual(len({e.stable_hash() for e in engines}),1)
            outcomes=[e.run_until_action_complete() for e in engines];self.assertEqual(outcomes[0],outcomes[1]);self.assertEqual(outcomes[1],outcomes[2])
            self.assertEqual(len({e.state.stable_hash() for e in engines}),1)
    def test_semantic_policy_changes_runtime_hash(self):
        r=self.runtime();h=r.stable_hash();r.policies[RESOURCE]['bindings']['counter']['bounds']['maximum']=20*SCALE
        self.assertNotEqual(h,r.stable_hash())
    def test_initial_modifier_provider_and_property_resource_callback(self):
        cb=task('property','property_write',owner='a',key='reference_atk',operation='add',value=expr(3*SCALE,True))
        r=self.runtime();m=self.listener(r,cb);del r.state.modifiers[m.instance_id]
        b=actor_binding('a',1001,active_modifiers=[asdict(m)]);r.bind_actor(b);self.done(r)
        self.assertEqual(r.state.properties['a']['reference_atk'],13*SCALE)
        v,evidence=read(r,cb,r.state,effective_binding(r.state,'a'),'reference_atk');self.assertEqual(v,13*SCALE)
        self.assertEqual(r.state.modifiers[m.instance_id].dynamic_values['initial'],0)
    def test_definition_does_not_imply_active_modifier(self):
        r=self.runtime();d,_=definition();r.state.modifier_definitions[d['definition_id']]=d;r.bind_actor(actor_binding('new',1001))
        self.assertFalse(r.state.modifiers)
    def test_initial_base_effective_reuses_r19_contributions(self):
        from hsr_battle_agent.battle_runtime.dynamic_property import AGGREGATION
        r=self.runtime();m=self.listener(r,write('cb',1));del r.state.modifiers[m.instance_id]
        m.property_contributions=[{'entity':'a','property':'reference_atk','value':3*SCALE,'source_node_hash':'fixture',
                                   'aggregation_policy':{'aggregation':'ADDITIVE_REVERSIBLE_REFERENCE'}}]
        b=actor_binding('a',1001,base_properties={'reference_atk':10*SCALE},effective_properties={'reference_atk':13*SCALE},active_modifiers=[asdict(m)])
        p=copy.deepcopy(b.policy);p.update(effective_property_relation=AGGREGATION,initial_contributions='R17_STORAGE_ALREADY_INCLUDES_REFERENCE')
        r.bind_actor(replace(b,policy=p))
        binding=effective_binding(r.state,'a');self.assertEqual(read(r,task('query','query'),r.state,binding,'reference_atk')[0],13*SCALE)
        binding['providers'][0]['source']='BASE_PROPERTY';self.assertEqual(read(r,task('query','query'),r.state,binding,'reference_atk')[0],10*SCALE)
    def test_base_effective_mismatch_cannot_initialize_legal_state(self):
        from hsr_battle_agent.battle_runtime.dynamic_property import AGGREGATION
        r=self.runtime();b=actor_binding('a',1001,base_properties={'reference_atk':10*SCALE},effective_properties={'reference_atk':13*SCALE})
        p=copy.deepcopy(b.policy);p['effective_property_relation']=AGGREGATION;before=r.stable_hash()
        with self.assertRaisesRegex(GapError,'PROPERTY_INITIALIZATION_GAP'):r.bind_actor(replace(b,policy=p))
        self.assertEqual(before,r.stable_hash())
    def test_initial_modifier_wrong_owner_is_atomic(self):
        r=self.runtime();m=self.listener(r,write('cb',1));del r.state.modifiers[m.instance_id];before=r.stable_hash()
        with self.assertRaisesRegex(GapError,'OWNERSHIP'):r.bind_actor(actor_binding('new',1001,active_modifiers=[asdict(m)]))
        self.assertEqual(before,r.stable_hash())

if __name__=='__main__': unittest.main()
