"""Original source providers, opt-in overlay and R17 parent replay contracts."""
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime')]
from r28_execution import AUDIT, read
from r28_reader import Reader
from r13_frozen_reader import StructuralGap
from hsr_battle_agent.battle_ir.behavior import IRNode, stable_hash
from hsr_battle_agent.battle_ir.jsonenum_provider import JsonEnumProvider
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.original_bindings import bind_remove_reference


class R28Tests(unittest.TestCase):
    def test_three_original_provider_sites(self):
        graph=read(AUDIT/'provider/decoded.json')
        p=JsonEnumProvider(graph,stable_hash(graph))
        self.assertEqual(JsonEnumProvider.from_overlay(ROOT/'data/overlays/r28_4651_v1/manifest.json').resolve([4,1]),p.resolve([4,1]))
        sites=read(AUDIT/'provider/resolved_sites.json')
        self.assertEqual(len(sites),3)
        self.assertEqual([s['resolution']['source_value'] for s in sites],['DOT','DOT','DOT_Poison'])
        for s in sites:self.assertEqual(p.resolve(s['ticket']['serialized_lookup_key']),s['resolution'])

    def test_unknown_and_corrupt_provider_stay_gaps(self):
        graph=read(AUDIT/'provider/decoded.json')
        p=JsonEnumProvider(graph,stable_hash(graph))
        for keys in [[-1,0],[99999,0],[True,1]]:
            with self.assertRaises(ValueError):p.resolve(keys)
        with self.assertRaises(ValueError):JsonEnumProvider(graph,'0'*64)

    def test_dictionary_truncation_unknown_field_and_count(self):
        for data in [b'\x01',b'\x02',b'\x01\x01']:
            with self.assertRaises(StructuralGap):Reader(data,0,len(data),{},{}).read(0x1e6d7c30)

    def test_original_ai_complete_and_not_executable(self):
        row=read(AUDIT/'monster/AI_result.json')
        self.assertEqual(row['result']['status'],'EXACT_BODY_DECODED')
        self.assertEqual(row['result']['cursor'],27101210)
        self.assertEqual(row['source_backed_rules_executed'],0)
        self.assertEqual(stable_hash(read(AUDIT/'monster/AI_decoded.json')),row['result']['graph_hash'])

    def test_two_original_parents_and_command_replay(self):
        for row in read(AUDIT/'character/results.json'):
            if 'Fugue' not in row['root'] and 'Jade' not in row['root']:continue
            folder=AUDIT/'character'/row['root']
            after=read(folder/'after.json')
            r=BehaviorRuntime.from_snapshot(read(folder/'initial_runtime.json'))
            commands=read(AUDIT/'character/scenarios'/(after['canonical_binding']['binding_hash'][:16]+'_template')/'commands.json')
            final,_=r.replay_turn_commands(commands)
            self.assertEqual(final.snapshot(),read(folder/'final_runtime.json'))
            self.assertEqual(final.stable_hash(),after['full_runtime_hash'])
            frames=[t for t in final.state.scheduler.action_execution['tasks'].values()
                    if IRNode.from_dict(t['node']).stable_hash()==row['original_task_hash']]
            self.assertTrue(frames)
            self.assertTrue(all(t['status']=='TASK_COMPLETE' for t in frames))
            self.assertEqual((row['before'],row['after']),(1,2))
            self.assertEqual(row['actions_completed'],0)
            self.assertTrue(after['source_IR_unchanged'])

    def test_binding_keeps_serialized_task_and_requires_explicit_policy(self):
        row=next(r for r in read(AUDIT/'character/results.json') if 'Fugue' in r['root'])
        n=IRNode.from_dict(row['original_task']);before=n.to_dict()
        r=BehaviorRuntime.from_snapshot(read(AUDIT/'character'/row['root']/'initial_runtime.json'))
        with self.assertRaises(ValueError):bind_remove_reference(r,n,pending_callbacks='UNKNOWN',identity_filter={})
        bind_remove_reference(r,n,pending_callbacks='CANCEL_NOT_STARTED_REFERENCE',identity_filter={})
        self.assertEqual(n.to_dict(),before)

    def test_overlay_reproduces_exact_original_hashes(self):
        from r23_reference_fixtures import content
        from hsr_battle_agent.battle_ir.catalog_overlay import load_overlay
        base=content()[0];before=copy.deepcopy(base.records)
        overlay=load_overlay(base,ROOT/'data/overlays/r28_4651_v1/manifest.json')
        self.assertEqual(base.records,before)
        for pin in read(ROOT/'data/overlays/r28_4651_v1/manifest.json')['records']:
            rec=overlay.records[tuple(pin['source_identity'])]
            self.assertEqual(IRNode.from_dict(rec['ir']).stable_hash(),pin['IR_hash'])


if __name__=='__main__':unittest.main()
