"""R14 corpus trust boundaries, exact joins and canonical existing IR."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/runtime'))
import r14_corpus as c
from r14_expand import join_skill, references
from r14_discovery import COMBAT, metrics, stratum_metrics
from r12_runtime_reentry import ARCHIVED_DECODER_ROLES, source_authority
from hsr_battle_agent.battle_ir.behavior import IRNode, UnsupportedSemanticIR, walk_nodes
from hsr_battle_agent.battle_ir.behavior_expansion_binding import ExpansionCompiler


def fields(**values):
    return {'fields':[{'mask':int(m),'start':10,'end':12,'values':[v]} for m,v in values.items()]}


def value(v):
    return {'kind':'string' if isinstance(v,str) else 'uleb','value':v}


class R14CorpusTests(unittest.TestCase):
    def test_exact_recovered_path_hash(self):
        self.assertEqual(c.path_hash('BakedConfig/Config/ConfigAbility/Avatar/Avatar_Common_Ability.bytes'),
                         '13611823635731997992')
        self.assertEqual(c.path_hash('BakedConfig/Config/ConfigCharacter/Avatar/Avatar_Natasha_00_Config.bytes'),
                         '13839639219909291635')

    def test_bounded_decode_determinism_and_overread(self):
        schemas={0x1eb94400:{'kind':'bitmap','type':'RPG.GameCore.TurnBasedAbilityConfig','fields':[]}}
        entry={'type':1,'absolute':0,'record_end':1}
        a=c.decode_entry(b'\x00',entry,schemas,{})
        b=c.decode_entry(b'\x00',entry,schemas,{})
        self.assertEqual(a,b)
        self.assertEqual(a['status'],'ACCEPTED')
        self.assertEqual(c.decode_entry(b'',entry,schemas,{})['status'],'FRAMING_GAP')

    def test_unknown_active_field_is_not_accepted(self):
        schemas={0x1eb94400:{'kind':'bitmap','type':'RPG.GameCore.TurnBasedAbilityConfig','fields':[]}}
        result=c.decode_entry(b'\x01',{'type':1,'absolute':0,'record_end':1},schemas,{})
        self.assertEqual(result['status'],'STRUCTURAL_READER_GAP')
        self.assertNotIn('graph',result)
        self.assertEqual(result['reader_gap'],'0x1eb94400')

    def test_unexplained_trailing_bytes_rejected(self):
        schemas={0x1eb94400:{'kind':'bitmap','type':'RPG.GameCore.TurnBasedAbilityConfig','fields':[]}}
        result=c.decode_entry(b'\x00\x00',{'type':1,'absolute':0,'record_end':2},schemas,{})
        self.assertEqual(result['status'],'FRAMING_GAP')

    def test_exact_parent_dictionary_key_framing(self):
        # Parent bitmap 3: two ability bodies, then two named modifier bodies.
        data=b'\x03\x04\x00\x00\x04\x01A\x00\x01B\x00'
        config={'offset':0,'length':len(data)}
        entries=[{'name':'a','type':1,'absolute':2},{'name':'b','type':1,'absolute':3},
                 {'name':'A','type':0,'absolute':7},{'name':'B','type':0,'absolute':10}]
        result=c.frame_container(data,config,entries,{}, {})
        self.assertEqual([e['record_end'] for e in result],[3,4,8,11])
        self.assertEqual(result[2]['parent_key_span'],[5,7])

    def test_parent_prefix_spoof_rejected(self):
        data=b'\x02\x02\x01X\x00'
        with self.assertRaises(c.StructuralGap):
            c.frame_container(data,{'offset':0,'length':len(data)},[{'name':'Y','type':0,'absolute':4}],{}, {})

    def test_parent_count_mismatch_rejected(self):
        with self.assertRaises(c.StructuralGap):
            c.frame_container(b'\x01\x04\x00',{'offset':0,'length':3},[{'name':'a','type':1,'absolute':2}],{}, {})

    def test_parent_empty_groups_exactly_consumed(self):
        data=b'\x07\x00\x00\x02\x00'
        result=c.frame_container(data,{'offset':0,'length':len(data)},[{'name':'T','type':2,'absolute':4}],{}, {})
        self.assertEqual(result[0]['record_end'],5)

    def test_graph_dedup_uses_source_coordinates(self):
        r={'source_shard_sha256':'hash','record_start':1,'record_end':3,'graph_hash':'graph','identity':'same'}
        different={**r,'record_start':4,'record_end':6}
        self.assertEqual(len(c.deduplicate([r,{**r,'identity':'other'},different])),2)
        with self.assertRaises(c.StructuralGap):
            c.deduplicate([r,{**r,'graph_hash':'different'}])

    def test_unknown_task_preserved_in_existing_IR(self):
        compiler=ExpansionCompiler(source_authority('fixture.json','0'*64),{'primitives':[]},ARCHIVED_DECODER_ROLES)
        root={'type':'.BEMKAFNMJIK','reader':'0x123','child':{'type':'RPG.GameCore.UnseenCombatTask',
            'reader':'0x124','start':5,'end':8,'bitmap':1,**fields(**{'1':value('unbound')})}}
        node=compiler.convert(root,'/task')
        self.assertIsInstance(node,UnsupportedSemanticIR)
        self.assertIn('unbound',node.canonical_json())
        self.assertEqual(IRNode.from_dict(json.loads(node.canonical_json())).stable_hash(),node.stable_hash())

    def test_canonical_IR_stability(self):
        compiler=ExpansionCompiler(source_authority('fixture.json','0'*64),{'primitives':[]},ARCHIVED_DECODER_ROLES)
        graph={'type':'RPG.GameCore.TurnBasedAbilityConfig','reader':'0x1eb94400','fields':[],'start':5,'end':6}
        first=compiler.compile_record(graph,'/record','test')
        second=compiler.compile_record(copy.deepcopy(graph),'/record','test')
        self.assertEqual(first.stable_hash(),second.stable_hash())
        self.assertEqual(IRNode.from_dict(first.to_dict()),first)

    def test_obfuscated_concrete_task_remains_unsupported_IR(self):
        compiler=ExpansionCompiler(source_authority('fixture.json','0'*64),{'primitives':[]},ARCHIVED_DECODER_ROLES)
        decoded={'type':'.BEMKAFNMJIK','reader':'0x123','child':{
            'type':'.UNKNOWN_CONCRETE_TYPE','reader':'0x124','start':1,'end':3,'fields':[]}}
        node=compiler.convert(decoded,'/task')
        self.assertIsInstance(node,UnsupportedSemanticIR)
        self.assertEqual(node.op,'.UNKNOWN_CONCRETE_TYPE')

    def _join_inputs(self):
        avatar={'graph':{'start':1,**fields(**{'1':value(7),'65536':{'kind':'list','children':[value(99)]}})},
                'source_shard_sha256':'av'}
        skills={99:[{'graph':{'start':2,'end':3,**fields(**{'64':value('Slot')})},'source_shard_sha256':'skills'}]}
        slot={'start':10,**fields(**{'1':value('Slot'),str(1<<38):value('ExactRoot')})}
        character={'status':'ACCEPTED','source_shard_sha256':'char',
                   'graph':fields(**{str(1<<25):{'kind':'list','children':[slot]}})}
        directories=[{'name':'ExactRoot','type':1,'source_shard_sha256':'root','absolute':15,'record_end':20,
                      'layout':{'hash':'directory'},'ordinal':4}]
        decoded={('root',15,20):{'graph':{}}}
        return avatar,skills,character,directories,decoded

    def test_owner_skill_root_join_exact_decoded_relations(self):
        row=join_skill(*self._join_inputs())[0]
        self.assertEqual(row['status'],'EXACT_ROOT_JOIN')
        self.assertTrue(row['root_structurally_decoded'])
        self.assertEqual(len(row['evidence']),5)

    def test_root_join_does_not_claim_undecoded_body(self):
        args=list(self._join_inputs());args[4]={}
        row=join_skill(*args)[0]
        self.assertEqual(row['status'],'EXACT_ROOT_JOIN')
        self.assertFalse(row['root_structurally_decoded'])
        self.assertFalse(row['root_ir_compiled'])

    def test_duplicate_root_identity_is_explicit_gap(self):
        args=list(self._join_inputs());args[3].append({**args[3][0],'absolute':30,'record_end':40})
        self.assertEqual(join_skill(*args)[0]['status'],'ROOT_REFERENCE_FOUND_GRAPH_UNDECODED')

    def test_character_display_name_does_not_join(self):
        args=list(self._join_inputs());args[2]['graph']=fields(**{str(1<<25):{'kind':'list','children':[
            {'start':10,**fields(**{'1':value('Other'),str(1<<38):value('ExactRoot')})}]}})
        self.assertEqual(join_skill(*args)[0]['status'],'SKILL_CONFIG_FOUND_NO_ROOT')

    def test_skill_level_key_disagreement_is_explicit(self):
        args=list(self._join_inputs());args[1][99].append({'graph':{'start':3,'end':4,**fields(**{'64':value('Other')})}})
        self.assertEqual(join_skill(*args)[0]['status'],'STRUCTURAL_READER_GAP')

    def test_template_structural_binding_preserves_unknown_inheritance(self):
        graph={'type':'RPG.GameCore.IncludeTaskListTemplate',**fields(**{'2':value('T'),
            '4':{'kind':'dict','count':1,'children':[value('x'),{'type':'RPG.GameCore.DynamicFloat','tag':0}]},
            '8':{'kind':'dict','count':0,'children':[]}})}
        ref=list(references(graph))[0]
        self.assertEqual(ref['identity'],'T')
        self.assertEqual(ref['inheritance_policy'],'UNRESOLVED')
        self.assertEqual(set(ref['serialized_parameter_binding']),{'4','8'})

    def test_modifier_structural_reference_requires_literal_slot(self):
        dynamic={'type':'RPG.GameCore.DynamicString','bitmap':4,**fields(**{'4':value('M')})}
        graph={'type':'RPG.GameCore.AddModifier',**fields(**{'8':dynamic})}
        self.assertEqual(list(references(graph))[0]['identity'],'M')
        graph['fields'][0]['values'][0]['bitmap']=5
        self.assertEqual(list(references(graph)),[])

    def test_combat_stratification_excludes_alias_frequency(self):
        graphs=[{'stratum':'ALIAS_CORPUS'} for _ in range(196)]+[
            {'stratum':'ABILITY_CORPUS','skill_joined':True},{'stratum':'PASSIVE_CORPUS'},
            {'stratum':'MODIFIER_CORPUS'},{'stratum':'OTHER_RUNTIME_CONFIG'}]
        summary=stratum_metrics(graphs)
        self.assertEqual(summary['GLOBAL_CORPUS'],200)
        self.assertEqual(summary['COMBAT_CORPUS'],3)
        self.assertEqual(summary['SKILL_JOINED_CORPUS'],1)

    def test_coverage_metrics_do_not_infer_complete_transitions(self):
        rows=[{'family':'task','type':'Known','support':'CONDITIONAL_REFERENCE','stratum':'ABILITY_CORPUS'},
              {'family':'task','type':'New','support':'UNSUPPORTED','stratum':'ABILITY_CORPUS'},
              {'family':'target','type':'AliasOnly','support':'CONDITIONAL_REFERENCE','stratum':'ALIAS_CORPUS'}]
        m=metrics([n for n in rows if n['stratum'] in COMBAT])
        self.assertEqual(m['task']['instances'],2)
        self.assertEqual(m['task']['REFERENCE_EXECUTABLE_instances'],0)
        self.assertEqual(m['target']['instances'],0)


if __name__=='__main__':
    unittest.main()
