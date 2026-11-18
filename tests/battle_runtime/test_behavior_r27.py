"""R27 exact offline source storage and original Monster admission contracts."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tools/runtime')]
from r27_checks import AUDIT,read
from r27_reader import Reader,machinery
from r14_corpus import Assets,scalar
from r13_frozen_reader import StructuralGap

class R27ReaderTests(unittest.TestCase):
    def test_jsonenum_retains_signed_keys_and_unknown_value(self):
        reader=Reader(bytes([0,1]),0,2,{}, {})
        node=reader.read(0x1e6d6bf0)
        self.assertEqual(node['serialized_lookup_keys'],[0,-1])
        self.assertEqual(node['raw_keys'],[0,1])
        self.assertIsNone(node['native_value'])
        self.assertEqual(node['resolution'],'SOURCE_PROVIDER_UNRESOLVED')
        self.assertEqual((node['start'],node['end']),(0,2))

    def test_jsonenum_does_not_consume_outside_body(self):
        with self.assertRaises(StructuralGap):Reader(b'\x00',0,1,{},{}).read(0x1e6d6bf0)

    def test_enum_list_negative_count_rejected(self):
        reader=Reader(b'\x01',0,1,{}, {})
        with self.assertRaises(StructuralGap):reader.operation(dict(kind='enum_list',element=dict(kind='enum',type={},underlying=8)),1)

    def test_enum_list_signed_storage_and_truncation(self):
        op=dict(kind='enum_list',element=dict(kind='enum',type={'name':'source-enum'},underlying=8))
        value=Reader(bytes([4,2,3]),0,3,{},{}).operation(op,1)
        self.assertEqual([x['value'] for x in value['children']],[1,-2])
        self.assertEqual([(x['start'],x['end']) for x in value['children']],[(1,2),(2,3)])
        with self.assertRaises(StructuralGap):Reader(bytes([4,2]),0,2,{},{}).operation(op,1)

    def test_multiple_original_records_across_three_tables(self):
        assets=Assets();schemas,dispatch=machinery()
        for name,rva in [('MonsterConfig',0x1e7eeaa0),('MonsterTemplateConfig',0x1e7f6f70),('MonsterSkillConfig',0x1e7f49e0)]:
            doc=read(AUDIT/'monster'/f'{name}_table.json')
            self.assertTrue(doc['complete'])
            data,pin=assets.source(doc['asset'])
            self.assertEqual(pin['sha256'],doc['pin']['sha256'])
            for index in (0,len(doc['rows'])//2,len(doc['rows'])-1):
                expected=doc['rows'][index]
                p=Reader(data,expected['start'],expected['end'],schemas,dispatch)
                self.assertEqual(p.read(rva),expected)
                self.assertEqual(p.cursor,expected['end'])

    def test_all_recovered_phase_bodies_repeat_from_original_bytes(self):
        from r27_character import decode
        assets=Assets()
        additions=read(AUDIT/'character/catalog_additions.json')
        self.assertGreaterEqual(len(additions),4)
        for rec in additions:
            result=decode(assets,rec['entry'])
            self.assertEqual(result['status'],'ACCEPTED')
            self.assertEqual(result['graph'],rec['graph'])
            self.assertEqual(result['graph_hash'],rec['graph_hash'])

    def test_monster_identity_join_uses_serialized_skill_ownership(self):
        actors=read(AUDIT/'monster/selected_actors.json')['actors']
        tables=read(AUDIT/'monster/MonsterSkillConfig_table.json')['rows']
        skills={scalar(g,1):g for g in tables}
        configs={c['path']:c for c in read(AUDIT/'monster/character_configs.json') if c['status']=='ACCEPTED'}
        from r14_corpus import children
        for join in read(AUDIT/'monster/exact_joins.json'):
            actor=next(a for a in actors if a['monster_id']==join['monster_id'])
            self.assertIn(join['skill_id'],[x['value'] for x in children(actor['graph'],1<<31)])
            self.assertEqual(scalar(skills[join['skill_id']],4),join['trigger_key'])
            slots=[s for s in children(configs[join['character_path']]['graph'],1<<25) if scalar(s,1)==join['trigger_key']]
            self.assertEqual(len(slots),1)
            self.assertEqual(scalar(slots[0],1<<38),join['entry_ability'])

    def test_original_monster_command_replay_and_kind(self):
        from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
        for path in sorted((AUDIT/'monster/execution').glob('*/commands.json')):
            initial=BehaviorRuntime.from_snapshot(read(path.parent/'initial_runtime.json'))
            final,_=initial.replay_turn_commands(read(path))
            self.assertEqual(final.snapshot(),read(path.parent/'final_runtime.json'))
            self.assertEqual(final.state.entities['a']['content_kind'],'Monster')
            row=read(path.parent/'result.json')
            self.assertTrue(row['source_IR_unchanged'])
            self.assertEqual(final.stable_hash(),row['full_runtime_hash'])
            self.assertFalse(row['native_AI'])

if __name__=='__main__':unittest.main()
