"""R23 exact source chains, conservative context binding and owned execution."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime')]
from hsr_battle_agent.battle_ir.behavior import IRNode, TaskSequenceIR, stable_hash, walk_nodes
from hsr_battle_agent.battle_ir.content_catalog import ContentCatalog, field
from hsr_battle_agent.battle_runtime.action_scheduler import POLICY_ID, _serialized_template_parameters
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime, ExecutionStatus, GapError
from hsr_battle_agent.battle_runtime.battle_turn import KEY, TurnError
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from tests.battle_runtime import test_behavior_r15 as r15
from tests.battle_runtime.test_behavior_r15 import ability, task, finish, call, expr, wait
from tests.battle_runtime.test_behavior_r16 import directory, record
from r23_reference_fixtures import content, joined_runtime, decoded_skill, owner_binding
from r22_reference_fixtures import inputs, runtime as turn_runtime, submit


def serialized_call(operand=None, **changes):
    dictionary={'kind':'dict','count':1,'children':['arg',{'child':operand or expr(2*SCALE,True)}]}
    return task('serialized-call','RPG.GameCore.IncludeTaskListTemplate',
        fields={'unbound_bit_0':'template','unbound_bit_1':dictionary},
        roles={'template':'template','parameters':dictionary},
        reference_binding={'roles':{'parameters':dictionary},'unknown_slots':[]},
        decoded={'structure':{'fields':[{'mask':2},{'mask':4}]}},**changes)


def dictionary_policy():
    return {'authority':'REFERENCE_MODEL','mode':'SERIALIZED_DICTIONARIES_REFERENCE',
        'caller_context':'INHERIT_EXPLICIT','provider_inheritance':'INHERIT_EXPLICIT',
        'dictionary_masks':{'4':'numeric','8':'string','32':'sequence'}}


class R23ContextTests(unittest.TestCase):
    def test_numeric_dictionary_evaluates_original_operand(self):
        n=serialized_call();r=r15.R15Tests().runtime(ability('root'))
        result=_serialized_template_parameters(r,n,dictionary_policy())
        self.assertEqual(result['parameters'],{'arg':2*SCALE})
        self.assertEqual(result['numeric_parameters'],{'arg':2*SCALE})
        self.assertEqual(result['string_parameters'],{})

    def test_missing_parameter_does_not_become_zero(self):
        from hsr_battle_agent.battle_ir.behavior import ExpressionIR
        operand=ExpressionIR('missing','lookup',expr(0).authority,{'scope':'absent','key':'arg'})
        n=serialized_call(operand);r=r15.R15Tests().runtime(ability('root'))
        before=r.stable_hash()
        with self.assertRaisesRegex(GapError,'dynamic_provider'):
            _serialized_template_parameters(r,n,dictionary_policy())
        self.assertEqual(before,r.stable_hash())

    def test_string_and_sequence_dictionaries_retain_original_values(self):
        r=r15.R15Tests().runtime(ability('root'));n=serialized_call().to_dict()
        p=n['payload'];p['decoded']['structure']['fields'].extend([{'mask':8},{'mask':32}])
        seq=TaskSequenceIR('original-sequence','immediate_sequence',expr(0).authority,{'tasks':[wait()]})
        p['fields']['unbound_bit_2']={'kind':'dict','count':1,'children':['text',expr('original').to_dict()]}
        p['fields']['unbound_bit_3']={'kind':'dict','count':1,'children':['seq',seq.to_dict()]}
        result=_serialized_template_parameters(r,IRNode.from_dict(n),dictionary_policy())
        self.assertEqual(result['string_parameters'],{'text':'original'})
        self.assertEqual(result['sequence_parameters']['seq'],seq.to_dict())

    def test_unknown_context_mask_and_duplicate_parameter_reject(self):
        r=r15.R15Tests().runtime(ability('root'));n=serialized_call().to_dict()
        n['payload']['decoded']['structure']['fields'].append({'mask':16});n=IRNode.from_dict(n)
        with self.assertRaisesRegex(GapError,'context mask:16'):
            _serialized_template_parameters(r,n,dictionary_policy())
        n=serialized_call().to_dict();d=n['payload']['fields']['unbound_bit_1'];d['children']*=2;d['count']=2
        n=IRNode.from_dict(n)
        with self.assertRaisesRegex(GapError,'duplicate'):
            _serialized_template_parameters(r,n,dictionary_policy())

    def test_nested_template_context_and_owned_completion(self):
        first=serialized_call();second=task('nested-call','RPG.GameCore.IncludeTaskListTemplate',roles={'template':'inner'})
        r=r15.R15Tests().runtime(ability('root',first,finish()))
        r.templates={'template':TaskSequenceIR('outer','immediate_sequence',first.authority,{'tasks':[second]}),
                     'inner':TaskSequenceIR('inner','immediate_sequence',first.authority,{'tasks':[wait()]})}
        r.policies[POLICY_ID]['template_call_bindings']={first.stable_hash():dictionary_policy()}
        r.start_action('root');r.run_ready(7)
        copies=[r,r.clone(),BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))]
        results=[x.run_until_action_complete() for x in copies]
        self.assertEqual(results[0].status,ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        self.assertEqual(results[0],results[1]);self.assertEqual(results[0],results[2])
        self.assertEqual(len({x.stable_hash() for x in copies}),1)
        d=r.state.scheduler.action_execution
        self.assertEqual(d['metrics']['child_abilities_completed'],2)
        self.assertTrue(all(a['context']['parameters']=={'arg':2*SCALE} for a in d['abilities'].values() if a['parent_ability_id']))

    def test_missing_child_holds_r22_turn_owner(self):
        r,*_=turn_runtime(root=ability('unrepaired-root',call(child='missing-content'),finish()))
        submit(r);out=r.run_until_next_turn()
        self.assertEqual(out.kind,'SEMANTIC_GAP')
        self.assertEqual(r.current_turn_owner(),'b')
        self.assertEqual(r.state.mechanics[KEY]['normal_turn_count'],0)
        before=r.stable_hash();r.run_until_decision();self.assertEqual(before,r.stable_hash())

    def test_original_finish_and_r22_release_after_owned_children(self):
        root=ability('explicit-source-model',call(),finish())
        r,*_=turn_runtime(root=root);r.abilities['child']=ability('child',wait())
        original=root.stable_hash();submit(r)
        restored=BehaviorRuntime.from_snapshot(r.snapshot())
        a=r.run_until_next_turn();b=restored.run_until_next_turn()
        self.assertEqual(a,b);self.assertEqual(r.stable_hash(),restored.stable_hash())
        self.assertEqual(r.state.mechanics[KEY]['normal_turn_count'],1)
        self.assertEqual(r.actions['root'].stable_hash() if 'root' in r.actions else next(iter(r.actions.values())).stable_hash(),original)

    def test_ambiguous_reference_never_binds_by_name(self):
        a,b=directory('shared'),directory('shared',100)
        c=ContentCatalog([a,b],[record(a,ir=ability('a',finish())),record(b,ir=ability('b',finish()))])
        self.assertEqual(c.resolve({'reference_type':'ABILITY_REFERENCE','identity':'shared'})['status'],'AMBIGUOUS_REFERENCE')
        self.assertEqual(c.executable_abilities(),{})


class R23RealSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog,cls.owners,cls.characters,cls.joins,cls.corpus=content()

    def graph(self,name):
        return next(g for g in self.corpus['graphs'] if g['record_identity']==name)

    def source_triplet(self):
        avatar=self.owners['avatars'][0]
        sid=field(avatar['graph'],65536)['values'][0]['children'][0]['value']
        skill=decoded_skill(next(s for s in self.owners['skills'] if s['skill_id']==sid and s['level']==1))
        path='BakedConfig/'+field(avatar['graph'],256)['values'][0]['value'].removesuffix('.json')+'.bytes'
        character=next(c for c in self.characters if c['path']==path)
        return avatar,skill,character

    def test_exact_canonical_owner_config_root_chain(self):
        a,s,c=self.source_triplet()
        b=self.catalog.canonical_skill(a,s,c,source_version='4.6.51')
        self.assertEqual(b['avatar_id'],1001);self.assertEqual(b['skill_id'],100101)
        self.assertEqual(b['skill_trigger_key'],b['skill_config_name'])
        self.assertEqual(b['entry_ability'],'Avatar_Mar_7th_00_Skill01_Phase01')
        self.assertEqual(b['binding_hash'],stable_hash({k:v for k,v in b.items() if k!='binding_hash'}))

    def test_forged_skill_row_rejected_against_decoded_source(self):
        a,s,c=self.source_triplet();s=copy.deepcopy(s);s['trigger_key']='fabricated'
        with self.assertRaisesRegex(ValueError,'decoded SkillID'):
            self.catalog.canonical_skill(a,s,c,source_version='4.6.51')
        a,s,c=self.source_triplet()
        with self.assertRaisesRegex(ValueError,'version boundary'):
            self.catalog.canonical_skill(a,s,c,source_version='4.4.54')

    def test_arbitrary_owner_and_character_path_rejected(self):
        a,s,c=self.source_triplet();a=copy.deepcopy(a)
        field(a['graph'],65536)['values'][0]['children']=[]
        with self.assertRaisesRegex(ValueError,'SkillList'):
            self.catalog.canonical_skill(a,s,c,source_version='4.6.51')
        a,s,c=self.source_triplet();c=copy.deepcopy(c);c['path']='different-source.bytes'
        with self.assertRaisesRegex(ValueError,'JsonPath'):
            self.catalog.canonical_skill(a,s,c,source_version='4.6.51')

    def test_ambiguous_skill_config_rejected(self):
        a,s,c=self.source_triplet();c=copy.deepcopy(c)
        entries=field(c['graph'],1<<25)['values'][0]['children'];entries.append(copy.deepcopy(entries[0]))
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            self.catalog.canonical_skill(a,s,c,source_version='4.6.51')

    def test_unjoined_r22_ability_cannot_claim_canonical_skill(self):
        with self.assertRaisesRegex(ValueError,'owner join absent'):
            owner_binding(self.graph('Avatar_Anaxa_00_Skill01_Phase02'))

    def test_exact_phase_binding_preserves_source_ir_and_finish(self):
        parent=self.graph('Avatar_Natasha_00_Skill02_Phase01')
        r,b,_=joined_runtime(parent,turn=False)
        child=r.abilities['Avatar_Natasha_00_Skill02_Phase02']
        original=child.stable_hash()
        finishes={n.stable_hash() for n in walk_nodes(child) if n.op=='RPG.GameCore.SkillPerformFinish'}
        self.assertTrue(finishes)
        r.start_action('canonical');r.run_until_action_complete()
        self.assertEqual(child.stable_hash(),original)
        self.assertTrue(any(a['parent_ability_id'] for a in r.state.scheduler.action_execution['abilities'].values()))
        self.assertEqual(r.actions['canonical'].stable_hash(),parent['canonical_IR_hash'])

    def test_scoped_inline_template_uses_exact_parent_body(self):
        resolved=self.catalog.resolve({'reference_type':'TEMPLATE_REFERENCE','identity':'AddDot'})
        definition=resolved['candidate_inline_definitions'][0];parent=definition['parent_source_identity']
        p={'authority':'REFERENCE_MODEL','scope':'EXACT_PARENT_ONLY_REFERENCE','parent_source_identity':parent}
        key,ir,receipt=self.catalog.scoped_template('AddDot',parent,p)
        self.assertEqual(receipt['source']['graph_hash'],definition['graph_hash'])
        self.assertFalse(receipt['source_tasks_added'])
        self.assertEqual(ir.payload['decoded']['start'],definition['inline_source_identity'][1])
        with self.assertRaises(ValueError):self.catalog.scoped_template('AddDot',parent,{})
        self.assertEqual(self.catalog.scoped_template('AddDot',parent,p)[1].stable_hash(),ir.stable_hash())

    def test_real_template_dictionary_advance_and_next_gap(self):
        from r23_probes import execute
        g=self.graph('Avatar_BlackSwan_00_Skill02_Phase01')
        before=execute(g,templates=False);after=execute(g,templates=True)
        self.assertIn('TEMPLATE_PARAMETER',before['required_capability'])
        self.assertNotEqual(before['required_capability'],after['required_capability'])
        self.assertTrue(after['source_IR_unchanged'])
        self.assertEqual(after['cohort'],'PARTIAL_REAL_SKILL_PREFIX')
        provider=execute(g,templates=True,template_providers=True)
        self.assertNotEqual(provider['required_capability'],after['required_capability'])
        self.assertTrue(provider['source_IR_unchanged'])
        self.assertEqual(provider['actions_completed'],0)

    def test_camera_audit_uses_exact_source_not_presentation_assumption(self):
        from r23_checks import AUDIT
        x=json.loads((AUDIT/'camera_audit.json').read_text(encoding='utf-8'))
        self.assertEqual(len(x['sites']),68)
        self.assertLessEqual(x['new_source_path_families'],2)
        self.assertTrue(all(not s['presentation_noop_authorized'] and s['behavior_classification']=='UNKNOWN' for s in x['sites']))

    def test_r22_permission_rejects_changed_owner_or_entry_atomically(self):
        r,b,_=joined_runtime(self.graph('Avatar_Anaxa_00_Skill01_Phase01'),turn=False)
        participants,p,providers=inputs(r,(('a',100),('b',100)))
        for part in participants:part['actor_binding']=None
        providers['availability']['actors']['a']['actions'][0]['canonical_skill_binding']=copy.deepcopy(b)
        bad=providers['availability']['actors']['a']['actions'][0]['canonical_skill_binding']
        bad['avatar_id']+=1;bad['binding_hash']=stable_hash({k:v for k,v in bad.items() if k!='binding_hash'})
        before=r.stable_hash()
        with self.assertRaisesRegex(TurnError,'binding mismatch'):r.initialize_turns(participants,p,providers)
        self.assertEqual(before,r.stable_hash())

    def test_cross_character_exact_permissions_and_gap_ownership_replay(self):
        from r23_probes import execute
        for name in ['Avatar_Anaxa_00_Skill01_Phase01','Avatar_Natasha_00_Skill02_Phase01','Avatar_Serval_Skill02_Phase01']:
            with self.subTest(root=name):
                row=execute(self.graph(name),replay=True)
                self.assertEqual(row['replay'],'PASS')
                self.assertEqual(row['turn_owner'],'a')
                self.assertEqual(row['normal_turns_completed'],0)
                self.assertTrue(row['source_IR_unchanged'])


if __name__=='__main__':unittest.main()
