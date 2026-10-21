"""R16 exact content joins, conservative policies and R15 ownership regressions."""
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime')]
from hsr_battle_agent.battle_ir.content_catalog import (ContentCatalog, references, source_key,
                                                      classify_dependency)
from hsr_battle_agent.battle_ir.behavior import IRNode, AbilityIR, TaskSequenceIR, stable_hash
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime, ExecutionStatus
from hsr_battle_agent.battle_runtime.action_scheduler import POLICY_ID
from tests.battle_runtime import test_behavior_r15 as r15
from tests.battle_runtime.test_behavior_r15 import ability, call, finish, task, wait, expr
from r16_dependency_closure import load_catalog, AUDIT, read

def f(mask, value, start=10):
    return {'mask':mask,'start':start,'end':start+2,'values':[value]}

def string(value): return {'kind':'string','value':value}

def directory(name, start=0, typ=1):
    return {'name':name,'type':typ,'source_shard_sha256':'a'*64,'absolute':start,'record_end':start+100,
            'parent_framing':'EXACT_LIST_DICTIONARY_GRAMMAR_0x1EB94850','layout':{'hash':'123'},
            'directory_entry_start':2000+start,'directory_entry_end':2002+start}

def record(entry, child=None, ir=None):
    graph={'type':'RPG.GameCore.TurnBasedAbilityConfig','reader':'0x1EB94400',
           'start':entry['absolute'],'end':entry['record_end'],'fields':[]}
    if child is not None:
        graph['fields']=[f(16,{'kind':'list','children':[{'type':'RPG.GameCore.TriggerAbility',
                            'reader':'0x1EB75180','fields':[f(16,string(child))]}]})]
    result={'identity':entry['name'],'entry':entry,'source_shard_sha256':entry['source_shard_sha256'],
            'record_start':entry['absolute'],'record_end':entry['record_end'],'graph':graph,
            'graph_hash':stable_hash(graph),'status':'ACCEPTED','consumption_status':'BOUNDED_FULL_CONSUMPTION'}
    if ir is not None: result.update(ir=ir.to_dict(),canonical_IR_hash=ir.stable_hash())
    return result

class R16CatalogTests(unittest.TestCase):
    def test_exact_reference_evidence(self):
        e=directory('target');r=record(e,ir=ability('target',finish()))
        c=ContentCatalog([e],[r]);resolution=c.resolve({'reference_type':'ABILITY_REFERENCE','identity':'target'})
        self.assertEqual(resolution['status'],'EXACT_RESOLVED_COMPILED')
        self.assertEqual(resolution['target_source_identity'],list(source_key(e)))
        self.assertEqual(resolution['resolved_graph_hash'],r['graph_hash'])
        self.assertIn('directory_span',resolution['resolution_evidence'])
        self.assertEqual(c.executable_abilities()['target'].stable_hash(),r['canonical_IR_hash'])

    def test_catalog_clone_snapshot_identity_and_hash(self):
        e=directory('target');c=ContentCatalog([e],[record(e,ir=ability('target',finish()))])
        restored=ContentCatalog.from_snapshot(json.loads(json.dumps(c.snapshot())))
        self.assertEqual(c.stable_hash(),restored.stable_hash())
        self.assertEqual(c.stable_hash(),c.clone().stable_hash())
        restored.records[source_key(e)]['identity']='mutated_clone'
        self.assertNotEqual(c.stable_hash(),restored.stable_hash())

    def test_name_only_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,'framing'):
            ContentCatalog([{'name':'plausible_Phase','type':1,'source_shard_sha256':'a'*64,'absolute':0,'record_end':2}])

    def test_missing_reference_rejected(self):
        c=ContentCatalog([])
        self.assertEqual(c.resolve({'reference_type':'ABILITY_REFERENCE','identity':'unknown_Camera'})['status'],'REFERENCE_NOT_FOUND')
        self.assertEqual(c.executable_abilities(),{})

    def test_ambiguous_reference_rejected(self):
        a,b=directory('shared'),directory('shared',100)
        c=ContentCatalog([a,b],[record(a,ir=ability('a')),record(b,ir=ability('b'))])
        self.assertEqual(c.resolve({'reference_type':'ABILITY_REFERENCE','identity':'shared'})['status'],'AMBIGUOUS_REFERENCE')
        self.assertNotIn('shared',c.executable_abilities())

    def test_reader_gap_is_not_empty_ability(self):
        e=directory('child')
        c=ContentCatalog([e],[{'source_shard_sha256':'a'*64,'record_start':0,'record_end':100,
                             'status':'STRUCTURAL_READER_GAP','reader_gap':'0x123'}])
        self.assertEqual(c.resolve({'reference_type':'ABILITY_REFERENCE','identity':'child'})['status'],'EXACT_REFERENCE_READER_GAP')
        self.assertEqual(c.executable_abilities(),{})

    def test_recursive_closure_and_decode_callback(self):
        a,b=directory('parent'),directory('child',100)
        c=ContentCatalog([a,b],[record(a,'child',ability('a'))]);calls=[]
        def decode(e): calls.append(source_key(e));return record(e,ir=ability('b'))
        graph=c.closure([source_key(a)],decode)
        self.assertEqual(calls,[source_key(b)])
        edge=next(e for e in graph['edges'] if e['reference_type']=='ABILITY_REFERENCE')
        self.assertEqual(edge['status'],'EXACT_RESOLVED_COMPILED')
        self.assertEqual(edge['parent_graph_hash'],c.records[source_key(a)]['graph_hash'])
        self.assertEqual(len(graph['visited_source_identities']),2)

    def test_cycle_detection_and_work_bound(self):
        a,b=directory('a'),directory('b',100)
        c=ContentCatalog([a,b],[record(a,'b'),record(b,'a')])
        self.assertEqual(len(c.closure([source_key(a)])['cycles']),1)
        bounded=c.closure([source_key(a)],max_depth=0)
        self.assertEqual(bounded['work_gaps'][0]['status'],'WORK_BOUND')

    def test_structural_graph_identity_and_hash(self):
        e=directory('x');r=record(e)
        r['graph']['end']+=1
        with self.assertRaisesRegex(ValueError,'framing'): ContentCatalog([e],[r])
        r=record(e);r['graph_hash']='0'*64
        with self.assertRaisesRegex(ValueError,'graph hash'): ContentCatalog([e],[r])

    def test_ir_hash_rejected_on_drift(self):
        e=directory('x');r=record(e,ir=ability('x'))
        r['canonical_IR_hash']='0'*64
        with self.assertRaisesRegex(ValueError,'IR hash'): ContentCatalog([e],[r])

    def test_context_binding_is_separate(self):
        graph={'type':'RPG.GameCore.TriggerAbility','fields':[f(16,{'type':'RPG.GameCore.DynamicString','bitmap':2,'fields':[]})]}
        site=next(references(graph))
        self.assertEqual(ContentCatalog([]).resolve(site)['status'],'CONTEXT_BINDING_UNRESOLVED')

    def test_template_parameters_all_preserved(self):
        graph={'type':'RPG.GameCore.IncludeTaskListTemplate','fields':[f(2,string('t')),
               *[f(m,{'kind':'dict','children':[string('parameter'),string('original')]}) for m in (4,8,16,32)]]}
        site=next(references(graph))
        self.assertEqual(set(site['template_bindings']),{'4','8','16','32'})
        self.assertEqual(site['template_bindings']['32'],graph['fields'][-1])

    def test_modifier_and_callback_preserved(self):
        graph={'type':'RPG.GameCore.AddModifier','fields':[f(8,{'type':'RPG.GameCore.DynamicString','bitmap':4,'fields':[f(4,string('modifier'))]})]}
        site=next(references(graph));self.assertEqual(site['reference_type'],'MODIFIER_REFERENCE')
        self.assertEqual(site['identity'],'modifier')
        self.assertEqual(site['pointer'],'/fields/0')
        self.assertEqual(graph['fields'][0]['values'],site['serialized_value'])
        callback={'type':'RPG.GameCore.TurnBasedModifierCallbackConfig','start':0,'end':2,'fields':[]}
        resolution=ContentCatalog([]).resolve(next(references(callback)))
        self.assertEqual(resolution['structural_status'],'CONTENT_GRAPH_PRESENT')
        self.assertEqual(resolution['registration'],'NOT_IMPLIED')

    def test_inline_template_body_is_context_gap_not_not_found(self):
        e=directory('owner');r=record(e,ir=ability('owner'))
        body={'type':'RPG.GameCore.TaskListTemplate','start':10,'end':30,'fields':[f(1,string('local_template'))]}
        r['graph']['fields']=[f(128,{'kind':'list','children':[body]})];r['graph_hash']=stable_hash(r['graph'])
        c=ContentCatalog([e],[r]);resolved=c.resolve({'reference_type':'TEMPLATE_REFERENCE','identity':'local_template'})
        self.assertEqual(resolved['status'],'CONTEXT_BINDING_UNRESOLVED')
        self.assertEqual(resolved['structural_status'],'CONTENT_GRAPH_PRESENT')
        self.assertEqual(resolved['candidate_inline_definitions'][0]['inline_source_identity'],['a'*64,10,30])
        self.assertEqual(resolved['candidate_inline_definitions'][0]['canonical_parent_IR_hash'],r['canonical_IR_hash'])
        self.assertEqual(c.compiled_templates(),{})

    def test_inline_modifier_definition_preserves_key_and_parent(self):
        e=directory('owner');r=record(e,ir=ability('owner'))
        body={'type':'RPG.GameCore.TurnBasedModifierConfig','start':50,'end':60,'fields':[]}
        key={'kind':'string','value':'local_modifier','start':40,'end':50}
        r['graph']['fields']=[f(256,{'kind':'dict','children':[key,body]})];r['graph_hash']=stable_hash(r['graph'])
        c=ContentCatalog([e],[r]);resolved=c.resolve({'reference_type':'MODIFIER_REFERENCE','identity':'local_modifier'})
        self.assertEqual(resolved['status'],'CONTEXT_BINDING_UNRESOLVED')
        definition=resolved['candidate_inline_definitions'][0]
        self.assertEqual(definition['serialized_key'],key)
        self.assertEqual(definition['parent_source_identity'],list(source_key(e)))
        self.assertEqual(resolved['modifier_instance_active'],'NOT_IMPLIED')
        self.assertEqual(definition['source_pointer'],'/fields/0/values/0/children/1')

    def test_inline_ambiguity_rejected(self):
        es=[directory('owner'),directory('other',100)];rs=[]
        for e in es:
            r=record(e,ir=ability(e['name']))
            r['graph']['fields']=[f(128,{'kind':'list','children':[
                {'type':'RPG.GameCore.TaskListTemplate','start':e['absolute']+10,'end':e['absolute']+30,
                 'fields':[f(1,string('shared_template'))]}]})]
            r['graph_hash']=stable_hash(r['graph']);rs.append(r)
        c=ContentCatalog(es,rs)
        self.assertEqual(c.resolve({'reference_type':'TEMPLATE_REFERENCE','identity':'shared_template'})['status'],'AMBIGUOUS_REFERENCE')

    def test_camera_classification_never_uses_name(self):
        e=directory('looks_like_Camera');r=record(e)
        r['graph']['fields']=[f(16,{'kind':'list','children':[{'type':'RPG.GameCore.MoveToTargetList'}]})]
        r['graph_hash']=stable_hash(r['graph'])
        self.assertEqual(classify_dependency(r)['classification'],'POSITION_RELEVANT')
        renamed=copy.deepcopy(r);renamed['identity']='different_Phase'
        self.assertEqual(classify_dependency(r),classify_dependency(renamed))
        self.assertEqual(classify_dependency(None)['classification'],'UNKNOWN')

class R16SchedulerTests(unittest.TestCase):
    def runtime(self,*args,**kwargs): return r15.R15Tests().runtime(*args,**kwargs)

    def test_nested_catalog_execution_context_clone_snapshot_replay(self):
        e1,e2=directory('child'),directory('grandchild',100)
        c=ContentCatalog([e1,e2],[record(e1,'grandchild',ability('child',call('nested','grandchild'),wait())),
                                   record(e2,ir=ability('grandchild',wait('grand-wait',2)))])
        root=ability('root',call(),finish())
        r=self.runtime(root,children=c.executable_abilities());r.start_action('root');r.run_ready(7)
        clones=[r,r.clone(),BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))]
        outcomes=[x.run_until_blocked() for x in clones]
        self.assertEqual(outcomes[0].status,ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(outcomes[0],outcomes[1]);self.assertEqual(outcomes[0],outcomes[2])
        self.assertEqual(len({x.stable_hash() for x in clones}),1)
        d=r.state.scheduler.action_execution
        self.assertEqual(d['metrics']['abilities_invoked'],2)
        self.assertEqual(d['metrics']['child_abilities_completed'],2)
        self.assertEqual(len({a['action_root_id'] for a in d['abilities'].values()}),1)
        self.assertTrue(all(a['context']['owner']=='a' for a in d['abilities'].values()))

    def test_missing_child_rollback(self):
        r=self.runtime(ability('root',call('unbound','missing_Camera'),finish()))
        r.start_action('root');first=r.run_until_blocked()
        self.assertEqual(first.status,ExecutionStatus.SEMANTIC_GAP)
        before=r.stable_hash();second=r.run_until_blocked()
        self.assertEqual(first.gap,second.gap);self.assertEqual(before,r.stable_hash())
        self.assertEqual(r.state.scheduler.action_execution['metrics']['abilities_invoked'],0)

    def test_template_parameter_policy_gap_and_explicit_mapping(self):
        t=task('template','RPG.GameCore.IncludeTaskListTemplate',roles={'template':'t','parameters':{'original':7}})
        r=self.runtime(ability('root',t,finish()));r.templates={'t':TaskSequenceIR('t','immediate_sequence',t.authority,{'tasks':[wait()]})}
        self.assertIn('TEMPLATE_PARAMETER_INHERITANCE',r.step('root').gap.required_capability)
        binding={'authority':'REFERENCE_MODEL','caller_context':'INHERIT_EXPLICIT','parameters':{'arg':7},
                 'numeric_parameters':{'arg':7},'string_parameters':{'text':'original'},'sequence_parameters':{'seq':[]}}
        r=self.runtime(ability('root',t,finish()));r.templates={'t':TaskSequenceIR('t','immediate_sequence',t.authority,{'tasks':[wait()]})}
        r.policies[POLICY_ID]['template_call_bindings']={t.stable_hash():binding}
        self.assertEqual(r.step('root').status,ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        child=next(a for a in r.state.scheduler.action_execution['abilities'].values() if a['parent_ability_id'])
        self.assertEqual(child['context']['template_call_binding'],binding)

    def test_template_missing_context_rejected(self):
        t=task('t','RPG.GameCore.IncludeTaskListTemplate',roles={'template':'t','parameters':{'arg':1}})
        r=self.runtime(ability('root',t));r.policies[POLICY_ID]['template_call_bindings']={t.stable_hash():{'authority':'REFERENCE_MODEL'}}
        self.assertIn('TEMPLATE_PARAMETER_INHERITANCE',r.step('root').gap.required_capability)

    def test_lifecycle_slots_not_omitted(self):
        root=ability('root',finish())
        root=AbilityIR(root.node_id,root.op,root.authority,{**root.payload,'reference_unbound_sequences':[4],
                       'decoded':{'fields':[f(4,{'kind':'list','children':[wait('extra-slot')]})]}})
        self.assertIn('lifecycle',self.runtime(root).step('root').gap.required_capability)
        r=self.runtime(root);r.policies[POLICY_ID]['lifecycle_slot_bindings']={root.stable_hash():{'authority':'REFERENCE_MODEL','ordered_masks':[16]}}
        self.assertIn('all nonempty slots',r.step('root').gap.required_capability)
        r=self.runtime(root);r.policies[POLICY_ID]['lifecycle_slot_bindings']={root.stable_hash():{'authority':'REFERENCE_MODEL','ordered_masks':[16,4]}}
        self.assertEqual(r.step('root').status,ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(r.state.scheduler.action_execution['logical_time'],14)

    def test_compiled_template_entry_requires_hash_bound_policy(self):
        template=AbilityIR('template','structure_record',finish().authority,
            {'root_type':'RPG.GameCore.TaskListTemplate','decoded':{'fields':[
                f(1,string('t')),f(2,{'kind':'list','children':[wait('template-wait')]})]}})
        t=task('t','RPG.GameCore.IncludeTaskListTemplate',roles={'template':'t'})
        r=self.runtime(ability('root',t,finish()));r.templates={'t':template}
        self.assertIn('TEMPLATE_PARAMETER_INHERITANCE',r.step('root').gap.required_capability)
        r=self.runtime(ability('root',t,finish()));r.templates={'t':template}
        r.policies[POLICY_ID]['template_entry_bindings']={template.stable_hash():
            {'authority':'REFERENCE_MODEL','task_list_mask':2,'parameter_context':'EXPLICIT_CALLER_MAPPING_ONLY'}}
        self.assertEqual(r.step('root').status,ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        d=r.state.scheduler.action_execution
        self.assertEqual(d['metrics']['child_abilities_completed'],1)
        self.assertEqual(d['logical_time'],14)

class R16RealContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=load_catalog()

    def test_real_non_natasha_phase_exact_binding(self):
        c=self.catalog
        resolution=c.resolve({'reference_type':'ABILITY_REFERENCE','identity':'Avatar_Bailu_00_Skill02_Phase02'})
        self.assertEqual(resolution['status'],'EXACT_RESOLVED_COMPILED')
        r=c.records[tuple(resolution['target_source_identity'])]
        self.assertTrue(r['newly_decoded']);ir=IRNode.from_dict(r['ir'])
        self.assertEqual(ir.stable_hash(),IRNode.from_dict(json.loads(ir.canonical_json())).stable_hash())

    def test_real_camera_gap_stays_explicit(self):
        r=self.catalog.resolve({'reference_type':'ABILITY_REFERENCE','identity':'Avatar_Anaxa_00_Skill01_Camera'})
        self.assertEqual(r['status'],'REFERENCE_NOT_FOUND')
        self.assertNotIn('Avatar_Anaxa_00_Skill01_Camera',self.catalog.executable_abilities())

    def test_real_expanded_template_modifier_and_callback_graphs(self):
        records=[r for r in self.catalog.records.values() if r.get('newly_decoded')]
        self.assertTrue(any(r['graph']['type']=='RPG.GameCore.TaskListTemplate' for r in records))
        modifiers=[r for r in records if r['graph']['type']=='RPG.GameCore.TurnBasedModifierConfig']
        self.assertTrue(any(any(s['reference_type']=='CALLBACK_REFERENCE' for s in references(r['graph'])) for r in modifiers))

if __name__=='__main__': unittest.main()
