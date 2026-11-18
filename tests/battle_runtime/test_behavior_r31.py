"""Real original predicate operands, canonical parent, and refusal boundaries."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/runtime'))
from r31_execution import original, bound_runtime, execute, read, OLD, AUDIT
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime, GapError
from hsr_battle_agent.battle_runtime.original_bindings import bind_compare_target_reference
from hsr_battle_agent.battle_ir.behavior import IRNode

class R31OriginalPredicate(unittest.TestCase):
    def test_source_bodies_hashed(self):
        for m in read(AUDIT/'native_methods.json')['methods']:
            self.assertEqual(hashlib.sha256((AUDIT/m['artifact']).read_bytes()).hexdigest(),m['sha256'])
    def test_no_binding_preserves_original_gap(self):
        folder,node=original()
        r=BehaviorRuntime.from_snapshot(read(folder/'initial_runtime.json'))
        with self.assertRaisesRegex(GapError,'anonymous bitmap'):r.predicate(node)
    def test_original_true_and_false(self):
        r,node,_=bound_runtime();before=node.stable_hash()
        r.state.target_context.update(ability_target='a',caster='a')
        self.assertTrue(r.predicate(node))
        r.state.target_context['ability_target']='b'
        self.assertFalse(r.predicate(node))
        self.assertEqual(node.stable_hash(),before)
    def test_first_entity_not_whole_collection(self):
        r,node,_=bound_runtime()
        selector=node.payload['fields']['unbound_bit_0']
        # Explicit reference alias state, leaving original operands untouched.
        d=r.aliases['AbilityTargetEntity'].to_dict();d['op']='explicit';d['payload']={'entities':['a','b','a']}
        r.aliases['AbilityTargetEntity']=IRNode.from_dict(d)
        self.assertTrue(r.predicate(node))
    def test_empty_left_short_circuits_unknown_right(self):
        r,node,_=bound_runtime()
        d=r.aliases['AbilityTargetEntity'].to_dict();d['op']='explicit';d['payload']={'entities':[]}
        r.aliases['AbilityTargetEntity']=IRNode.from_dict(d);del r.aliases['Caster']
        self.assertFalse(r.predicate(node))
    def test_unknown_selector_is_gap(self):
        r,node,_=bound_runtime();del r.aliases['AbilityTargetEntity']
        with self.assertRaisesRegex(GapError,'effective_target_alias'):r.predicate(node)
    def test_unknown_entity_is_gap(self):
        r,node,_=bound_runtime();r.state.target_context['ability_target']='missing'
        with self.assertRaises(GapError):r.predicate(node)
    def test_unsupported_predicate_result_contract(self):
        r,node,_=bound_runtime()
        r.policies['r13_reference_v1']['original_entity_comparisons'][node.stable_hash()]['result_policy']='FORCE_TRUE'
        with self.assertRaisesRegex(GapError,'CONTRACT_UNSUPPORTED'):r.predicate(node)
    def test_additional_serialized_flags_refused(self):
        r,node,_=bound_runtime();d=node.to_dict()
        d['payload']['reference_binding']['unknown_slots'].append({'mask':1,'field_index':2})
        with self.assertRaisesRegex(GapError,'LAYOUT_UNSUPPORTED'):
            bind_compare_target_reference(r,IRNode.from_dict(d),selector_policy='MASK15_CALLER_RESOLVED_REFERENCE',result_policy='BOOLEAN_TO_R15_BRANCH_REFERENCE')
    def test_snapshot_and_policy_replay_identity(self):
        r,node,_=bound_runtime()
        self.assertEqual(r.stable_hash(),r.clone().stable_hash())
        restored=BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))
        self.assertEqual(r.predicate(node),restored.predicate(node))
    def test_real_original_parent_both_branches(self):
        for target in ['b','false']:
            with self.subTest(target=target):
                row=execute(target)
                self.assertGreaterEqual(row['after'],8)
                self.assertNotEqual(row['next_gap']['task_type'],'RPG.GameCore.ByCompareTarget')
                self.assertEqual(row['clone_snapshot_replay'],'PASS')
                self.assertFalse(row['native_effective_validated'])
                self.assertEqual(row['decisions'][0]['predicate_result'],target=='b')

if __name__=='__main__':unittest.main()
