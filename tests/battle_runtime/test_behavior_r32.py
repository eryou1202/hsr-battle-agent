"""R32 source absence and original replay refusal tests; no execution claim."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/runtime'))
from r32_closure import AUDIT,KEYS,read
from hsr_battle_agent.battle_ir.behavior import IRNode
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime,GapError
from hsr_battle_agent.battle_runtime.modifier_lifecycle import apply,POLICY_ID

class R32ConstructionStop(unittest.TestCase):
    def test_exact_directory_absence_is_scoped(self):
        d=read(AUDIT/'directory_receipt.json')
        self.assertEqual(len(d['entries']),20)
        self.assertTrue(all(k not in [e['name'] for e in d['entries']] for k in KEYS))
        for row in read(AUDIT/'definition_acquisition.json'):
            self.assertEqual(row['status'],'MODIFIER_DEFINITION_MISSING')
            self.assertEqual(row['matches'],[])
    def test_original_hashes_and_distinct_selectors(self):
        rows=read(AUDIT/'jade/results.json')
        self.assertEqual([r['target_selector']['payload']['alias'] for r in rows],['AbilityTargetEntity','Caster'])
        for row in rows:
            self.assertEqual(IRNode.from_dict(row['node']).stable_hash(),row['task_hash'])
            self.assertEqual(row['serialized']['bitmap'],522)
            self.assertEqual([f['mask'] for f in row['serialized']['fields']],[2,8,512])
    def test_complete_public_replay_and_natural_blocker(self):
        for branch in ['b','false']:
            folder=AUDIT/'jade'/branch
            r,_=BehaviorRuntime.from_snapshot(read(folder/'initial_runtime.json')).replay_turn_commands(read(folder/'commands.json'))
            self.assertEqual(r.snapshot(),read(folder/'final_runtime.json'))
            row=read(folder/'receipt.json')
            self.assertEqual(row['before'],row['after'])
            self.assertFalse(row['parent_finish']);self.assertFalse(row['turn_released'])
            self.assertEqual(r.clone().run_until_blocked().gap.task_type,'RPG.GameCore.AddModifier')
            self.assertEqual(r.state.modifiers,{})
            self.assertEqual(r.clone().stable_hash(),r.stable_hash())
    def test_unknown_definition_fails_atomically_in_r17(self):
        for branch in ['b','false']:
            folder=AUDIT/'jade'/branch
            r=BehaviorRuntime.from_snapshot(read(folder/'final_runtime.json'))
            node=IRNode.from_dict(read(folder/'receipt.json')['node'])
            r.policies[POLICY_ID]['applications'][node.stable_hash()]={'definition_id':'MISSING_EXACT_SOURCE'}
            before=r.snapshot()
            with self.assertRaisesRegex(GapError,'CONTENT_GRAPH_MISSING'):apply(r,node)
            self.assertEqual(r.snapshot(),before)
    def test_no_reference_application_authority_installed(self):
        for branch in ['b','false']:
            r=BehaviorRuntime.from_snapshot(read(AUDIT/'jade'/branch/'final_runtime.json'))
            self.assertEqual(r.policies[POLICY_ID]['applications'],{})
            self.assertEqual(r.state.modifier_definitions,{})
    def test_reused_native_hashes(self):
        d=read(AUDIT/'native/evidence.json')
        self.assertEqual(d['additional_selected_bodies'],0)
        for m in d['reused_methods']:
            self.assertEqual(hashlib.sha256((AUDIT/'native'/m['artifact']).read_bytes()).hexdigest(),m['sha256'])

if __name__=='__main__':unittest.main()
