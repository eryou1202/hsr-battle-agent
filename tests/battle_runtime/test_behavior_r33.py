"""R33 structural/refusal tests. No successful original application claimed."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/runtime'))
from r33_authority import AUDIT,R32,read,sha,CONTROLS
from hsr_battle_agent.battle_ir.behavior import IRNode,stable_hash
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime,GapError
from hsr_battle_agent.battle_runtime.modifier_lifecycle import apply,bind_definitions,POLICY_ID

class R33Authority(unittest.TestCase):
    def control(self,i):return read(ROOT/CONTROLS[i])
    def runtime(self,branch='b'):
        r=BehaviorRuntime.from_snapshot(read(AUDIT/'jade'/branch/'final_runtime.json'))
        row=read(AUDIT/'jade'/branch/'receipt.json')
        return r,IRNode.from_dict(row['node'])
    def test_exact_two_definition_joins_and_callbacks(self):
        tasks={r['modifier']:r for r in self.control(2)['scenarios']}
        for row in read(R32/'inline_definition_acquisition.json'):
            d=row['definition'];self.assertEqual(d['graph_hash'],stable_hash(d['decoded_graph']))
            self.assertEqual(tasks[row['key']]['node']['payload']['fields']['unbound_bit_1']['payload']['value'],row['inline_matches'][0]['serialized_key']['value'])
            cb=next(f for f in d['compiled_decoded']['fields'] if f['mask']==33554432)
            self.assertEqual(len(cb['values'][0]['children']),2)
    def test_constructor_provenance_is_hash_pinned(self):
        d=read(AUDIT/'native/dataflow.json')
        for m in d['methods']:self.assertEqual(sha(AUDIT/'native'/m['artifact']),m['sha256'])
        allocation=next(e for e in d['edges'] if e['edge']=='actual creation call site')
        self.assertIn('0xF12944E',allocation['site'])
        self.assertIn('stack6=rbx',allocation['operand_identity'])
        text=(AUDIT/'native/method_f1290a0.txt').read_text()
        self.assertIn('18f12944e:',text);self.assertIn('call   0x18f17a830',text)
    def test_missing_provider_refusal_atomic_both_branches(self):
        for branch in ['b','false']:
            r,n=self.runtime(branch);before=r.snapshot()
            with self.assertRaisesRegex(GapError,'REFERENCE_INSTANCE_INPUT_MISSING'):apply(r,n)
            self.assertEqual(r.snapshot(),before)
    def test_known_definition_does_not_supply_lifetime_stack_or_listener_authority(self):
        for branch in ['b','false']:
            r,n=self.runtime(branch)
            d=next(x['definition'] for x in read(R32/'inline_definition_acquisition.json') if x['key']==n.to_dict()['payload']['fields']['unbound_bit_1']['payload']['value'])
            bind_definitions(r.state,SimpleNamespace(modifier_definitions=lambda:{d['definition_id']:copy.deepcopy(d)}))
            r.policies[POLICY_ID]['applications'][n.stable_hash()]={'definition_id':d['definition_id']}
            before=r.snapshot()
            with self.assertRaisesRegex(GapError,'MODIFIER_LIFECYCLE_POLICY_MISSING'):apply(r,n)
            self.assertEqual(r.snapshot(),before);self.assertFalse(r.state.modifiers)
    def test_owner_identity_not_promoted_to_native_context(self):
        for row in self.control(2)['scenarios']:
            a=row['ability_ownership'];self.assertEqual(a['ability:26']['parent_ability_id'],'ability:20')
            self.assertEqual(a['ability:26']['context']['caster'],'a')
        operands={r['operand']:r for r in self.control(1)['operands']}
        self.assertEqual(operands['target']['status'],'REFERENCE_CONTEXT_ONLY')
        self.assertEqual(operands['source Ability instance']['status'],'OWNERSHIP_PROVEN_NATIVE_MAPPING_UNBOUND')
    def test_unknown_operands_never_defaulted(self):
        c=self.control(1)
        self.assertFalse(c['executable_contract'])
        self.assertTrue(all(not r['default_supplied'] for r in c['operands']))
        self.assertEqual(c['original_dynamic_operand'],dict(mask=512,key=-1022829777,role='UNKNOWN',value='UNKNOWN'))
        self.assertEqual(c['self_additional_definition_mask']['role'],'UNKNOWN')
    def test_clone_snapshot_hash_and_public_replay_both_branches(self):
        for branch in ['b','false']:
            r,_=self.runtime(branch)
            self.assertEqual(r.stable_hash(),r.clone().stable_hash())
            self.assertEqual(r.stable_hash(),BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot()))).stable_hash())
            replay,_=BehaviorRuntime.from_snapshot(read(AUDIT/'jade'/branch/'initial_runtime.json')).replay_turn_commands(read(AUDIT/'jade'/branch/'commands.json'))
            self.assertEqual(replay.stable_hash(),r.stable_hash())
    def test_suspension_exact_gap_ir_and_ownership_preserved(self):
        for branch in ['b','false']:
            r,n=self.runtime(branch);before=r.snapshot();diag=r.clone().run_until_blocked()
            self.assertEqual(diag.gap.node,n.to_dict());self.assertEqual(r.snapshot(),before)
            row=read(AUDIT/'jade'/branch/'receipt.json')
            self.assertEqual(n.stable_hash(),row['original_task_hash'])
            self.assertEqual(row['task_count_after'],8);self.assertFalse(row['parent_complete']);self.assertFalse(row['R22_turn_released'])
    def test_camera_mandatory_before_finish_and_graph_incomplete(self):
        c=self.control(3);self.assertFalse(c['complete_dependency_graph'])
        camera=c['camera_continuation'];self.assertTrue(camera['mandatory_on_both_saved_paths'])
        self.assertEqual(camera['classification'],'PROVEN_REQUIRED_BLOCKER')
        nodes=[r for r in c['ordered_tasks'] if r['ability'].endswith('Phase02') and '/structure/' not in r['node_id']]
        ops={r['sequence_index']:r['op'] for r in nodes}
        self.assertEqual(ops[8],'RPG.GameCore.SetCameraRootFollow');self.assertEqual(ops[10],'RPG.GameCore.SkillPerformFinish')
        camera_sites=[e for e in c['known_dependency_sites'] if (e.get('identity') or '').endswith(('Skill02_Camera','Skill02_Camera_Self'))]
        self.assertEqual(len(camera_sites),2)
        self.assertTrue(all(e['classification']=='PROVEN_REQUIRED_BLOCKER' for e in camera_sites))
        self.assertTrue(all(e['downstream']=='UNSEEN' for e in camera_sites))
    def test_no_source_reference_or_native_count_inflation(self):
        c=self.control(0)
        for key in ['source_evidenced_construction','explicit_reference_construction','source_evidenced_activation','original_task_complete','original_parent_complete','native_effective_validated','full_joined_skills','original_monster_actions']:self.assertEqual(c[key],0)
        self.assertEqual(c['verdict'],'MODIFIER_INSTANCE_AUTHORITY_BLOCKED')
    def test_feasibility_all_joined_roots_and_finish_exclusions(self):
        c=self.control(4);self.assertEqual(len(c['roots']),160)
        self.assertEqual(c['best_alternative']['root'],'Avatar_Huohuo_00_Skill01_Phase01')
        self.assertTrue(all(not r['completion_ready'] for r in c['roots']))
        self.assertTrue(all(r['remaining_gap_sites']>0 for r in c['combat_priority']))
        self.assertTrue(all(r['original_finish_nodes']==0 for r in c['maze_exclusions']))
    def test_budget_and_blocked_lifecycle_acceptance(self):
        c=self.control(5);self.assertEqual(c['additional_native_bodies'],2);self.assertTrue(c['constructor_workstream_stopped'])
        self.assertTrue(all(v.startswith('BLOCKED_') for v in c['unsupported_acceptance_cases'].values()))

if __name__=='__main__':unittest.main()
