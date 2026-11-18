"""Exact recovered inline sources; structural checks do not imply application."""
import copy
import hashlib
from types import SimpleNamespace
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/runtime'))
from r32_closure import AUDIT,KEYS,read
from hsr_battle_agent.battle_ir.behavior import IRNode,stable_hash
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime,GapError
from hsr_battle_agent.battle_runtime.modifier_lifecycle import bind_definitions,apply,POLICY_ID

class R32RecoveredSources(unittest.TestCase):
    def test_exact_inline_dictionary_not_filename_binding(self):
        rows=read(AUDIT/'inline_definition_acquisition.json')
        tasks={r['modifier']:r['node'] for r in read(AUDIT/'jade/results.json')}
        self.assertEqual({r['key'] for r in rows},set(KEYS))
        for row in rows:
            self.assertEqual(row['status'],'EXACT_INLINE_DEFINITION_RECOVERED')
            self.assertEqual(len(row['inline_matches']),1)
            site=row['inline_matches'][0];definition=row['definition']
            self.assertEqual(site['serialized_key']['value'],row['key'])
            self.assertEqual(tasks[row['key']]['payload']['fields']['unbound_bit_1']['payload']['value'],site['serialized_key']['value'])
            self.assertEqual(definition['config_identity'],row['key'])
            self.assertEqual(site['field_identity']['storage'],'INLINE_NAMED_DICTIONARY')
            self.assertEqual(definition['graph_hash'],stable_hash(definition['decoded_graph']))
            self.assertEqual(definition['source_span'],site['span'])
    def test_distinct_source_definitions_and_original_callback_bodies(self):
        rows=read(AUDIT/'inline_definition_acquisition.json')
        self.assertNotEqual(rows[0]['definition']['definition_id'],rows[1]['definition']['definition_id'])
        for row in rows:
            definition=row['definition']
            callbacks=[f for f in definition['compiled_decoded']['fields'] if f['mask']==33554432]
            self.assertEqual(len(callbacks),1)
            self.assertTrue(callbacks[0]['values'][0]['children'])
            self.assertEqual(hashlib.sha256((ROOT/definition['source_artifact']).read_bytes()).hexdigest(),definition['source_artifact_sha256'])
    def test_lifecycle_definition_registration_does_not_construct(self):
        r=BehaviorRuntime.from_snapshot(read(AUDIT/'jade/b/final_runtime.json'))
        definitions={x['definition']['definition_id']:x['definition'] for x in read(AUDIT/'inline_definition_acquisition.json')}
        self.assertEqual(bind_definitions(r.state,SimpleNamespace(modifier_definitions=lambda:copy.deepcopy(definitions))),2)
        self.assertEqual(r.state.modifiers,{})
        self.assertEqual(r.clone().stable_hash(),r.stable_hash())
    def test_known_definition_without_constructor_policy_still_refuses(self):
        r=BehaviorRuntime.from_snapshot(read(AUDIT/'jade/b/final_runtime.json'))
        definition=read(AUDIT/'inline_definition_acquisition.json')[0]['definition']
        bind_definitions(r.state,SimpleNamespace(modifier_definitions=lambda:{definition['definition_id']:definition}))
        node=IRNode.from_dict(read(AUDIT/'jade/b/receipt.json')['node'])
        r.policies[POLICY_ID]['applications'][node.stable_hash()]={'definition_id':definition['definition_id']}
        before=r.snapshot()
        with self.assertRaisesRegex(GapError,'MODIFIER_LIFECYCLE_POLICY_MISSING'):apply(r,node)
        self.assertEqual(r.snapshot(),before)

if __name__=='__main__':unittest.main()
