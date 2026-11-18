"""Evidence and fail-closed original execution tests, not native adapter acceptance.

No scope/setter/callback behavior is fabricated to satisfy the blocked cases.
"""
import hashlib
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/runtime'))
from r30_numeric import pack_observed_count
from hsr_battle_agent.battle_ir.behavior import IRNode
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
OLD=ROOT/'tmp/audit/r29_original_executor_context_20261108_001'
AUDIT=ROOT/'tmp/audit/r30_dynamic_context_closure_20261108_001'
def read(p):return json.loads(p.read_text(encoding='utf8'))

class R30Evidence(unittest.TestCase):
    def test_count_encoding_boundaries(self):
        for n in [0,1,-1,(1<<30)-1,-((1<<30)-1)]:
            self.assertEqual(pack_observed_count(n),n*(1<<33))
        for n in [1<<30,-(1<<30),(1<<31)-1,-(1<<31)]:
            self.assertEqual(pack_observed_count(n),(n*(1<<26))|1)
    def test_count_rejects_unsupported_representation(self):
        for n in [True,1.0,'1',1<<31,-(1<<31)-1,None]:
            with self.assertRaises(ValueError):pack_observed_count(n)
    def test_selected_native_evidence_hashes(self):
        for folder in [OLD,AUDIT]:
            for m in read(folder/'native_methods.json')['methods']:
                self.assertEqual(hashlib.sha256((folder/m['artifact']).read_bytes()).hexdigest(),m['sha256'])
    def test_writer_interface_identity(self):
        t=next(t for t in read(AUDIT/'selected_metadata.json')['types'] if t['type']['index']==10867)
        self.assertEqual({m['slot']:m['name'] for m in t['methods'] if m['slot'] in [3,4,5,7]}, {3:'get_Val',4:'set_Val',5:'get_MinValue',7:'get_MaxValue'})
    def test_scope_zero_dispatch_distinct_from_scope_nine(self):
        tables=read(AUDIT/'selected_metadata.json')['scope_tables']
        self.assertEqual(tables[1]['entries'][0],{'scope':0,'target':'0xEDF7148'})
        self.assertNotIn(9,[r['scope'] for t in tables for r in t['entries']])
    def original(self,name,count):
        row=next(r for r in read(OLD/'character/results.json') if name in r['root'])
        folder=OLD/'character'/row['root'];initial=read(folder/'initial_runtime.json')
        task=IRNode.from_dict(row['current_task']);self.assertEqual(task.stable_hash(),row['task_hash'])
        final,_=BehaviorRuntime.from_snapshot(initial).replay_turn_commands(read(folder/'commands.json'))
        self.assertEqual(final.snapshot(),read(folder/'final_runtime.json'))
        self.assertEqual(row['after_completed'],count)
        self.assertEqual(final.clone().stable_hash(),BehaviorRuntime.from_snapshot(json.loads(json.dumps(final.snapshot()))).stable_hash())
        self.assertEqual(initial,read(folder/'initial_runtime.json'))
        self.assertEqual(task.stable_hash(),row['task_hash'])
        self.assertEqual(row['actions_completed'],0)
    def test_original_lynx_remains_blocked_without_setter_authority(self):self.original('Lynx',1)
    def test_original_klara_remains_blocked_without_candidate_authority(self):self.original('Klara',0)

if __name__=='__main__':unittest.main()
