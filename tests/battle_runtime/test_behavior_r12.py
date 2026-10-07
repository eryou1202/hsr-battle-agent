"""R12 focused structural/reference tests; no native-transition qualification."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.behavior import (
    AbilityIR, Authority, CompletionIR, EventDispatchIR, ExpressionIR, IRNode,
    ModifierApplyIR, ModifierRemoveIR, PredicateIR, PropertyMutationIR, RandomChoiceIR,
    ResourceMutationIR, SchedulerBarrierIR, TaskIR, TaskSequenceIR, TargetSelectorIR,
    UnsupportedSemanticIR, walk_nodes)
from hsr_battle_agent.battle_ir.behavior_binding import BehaviorCompiler
from hsr_battle_agent.battle_runtime.behavior import (
    BehaviorRuntime, ExecutionStatus, GapError, default_registry)
from hsr_battle_agent.battle_runtime.behavior_primitives import (
    SCALE, NumericSemanticGap, fixed_binary, heal_formula2_core)
from hsr_battle_agent.battle_runtime.behavior_state import (
    BehaviorBattleState, DeterministicRNG, ModifierInstance)

A = Authority("REFERENCE_MODEL", "test-v1", "test-fixture", "", semantic_status="REFERENCE_MODEL")
GRAPH = REPO / "data/control/real_runtime_4651_natasha_110502_structural_graph_20261004_001.json"
LEDGER = REPO / "data/control/real_runtime_generic_primitive_ledger_20261007_001.json"
EXPRESSIONS = REPO / "tmp/audit/r11_4651_natasha_semantic_closure_20261005_001/selected_dynamic_float_expressions.json"


def n(cls, op, payload=None, identity=None):
    return cls(identity or op, op, A, payload)


def lit(number):
    return n(ExpressionIR, "literal", {"raw": number * SCALE})


def action(tasks):
    return n(AbilityIR, "ability", {"tasks": n(TaskSequenceIR, "immediate_sequence", {"tasks": tasks})})


def state():
    return BehaviorBattleState(entities={"a": {"alive": True}, "b": {"alive": False}},
        properties={"a": {"hp": 10*SCALE}}, progression={"a": {"skill_tree_rows": {"99": {"row": 1}, "8": None}}},
        target_context={"caster": "a", "ability_target": "b", "skill_targets": ["b", "a"], "param_entity": "b", "modifier_owner": "a"})


class BehaviorR12Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        cls.ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.authority = Authority("REAL_CONTENT_RECONSTRUCTED", "4.6.51", GRAPH.relative_to(REPO).as_posix(),
            hashlib.sha256(GRAPH.read_bytes()).hexdigest())
        cls.compiler = BehaviorCompiler(cls.authority, cls.ledger)
        cls.ir = cls.compiler.compile_graph(cls.graph)

    def test_ir_roundtrip_and_hash_stability(self):
        rebuilt = IRNode.from_dict(json.loads(self.ir.canonical_json()))
        self.assertEqual(self.ir, rebuilt)
        self.assertEqual(self.ir.stable_hash(), rebuilt.stable_hash())
        reversed_graph = dict(reversed(list(self.graph.items())))
        self.assertEqual(self.ir.stable_hash(), self.compiler.compile_graph(reversed_graph).stable_hash())

    def test_ir_owns_payload_and_requires_evidence(self):
        payload = {"entities": ["a"]}
        node = n(TargetSelectorIR, "explicit", payload)
        payload["entities"].append("b")
        node.payload["entities"].append("c")
        self.assertEqual(node.payload["entities"], ["a"])
        with self.assertRaises(ValueError):
            Authority("NATIVE_CORRECT", "test", "test", "")
        with self.assertRaises(TypeError):
            n(TaskIR,"invalid",["not-a-map"])

    def test_expression_operations_and_lookup(self):
        runtime = BehaviorRuntime(state())
        runtime.state.dynamic_values["supplied"] = {"arbitrary-hash": 3*SCALE}
        lookup = n(ExpressionIR, "lookup", {"scope": "supplied", "key": "arbitrary-hash"})
        for op, expected in (("add", 5), ("sub", -1), ("mul", 6)):
            self.assertEqual(runtime.evaluate(n(ExpressionIR, op, {"args": [lit(2), lookup]})), expected*SCALE)
        self.assertEqual(runtime.evaluate(n(ExpressionIR, "div", {"args": [lit(6), lit(3)]})), 2*SCALE)
        self.assertEqual(runtime.evaluate(n(ExpressionIR, "min", {"args": [lit(2), lit(3)]})), 2*SCALE)
        self.assertEqual(runtime.evaluate(n(ExpressionIR, "max", {"args": [lit(2), lit(3)]})), 3*SCALE)
        self.assertEqual(runtime.evaluate(n(ExpressionIR, "clamp", {"args": [lit(7), lit(1), lit(4)]})), 4*SCALE)

    def test_comparison_conditional_is_lazy(self):
        runtime = BehaviorRuntime(state())
        cmp = n(ExpressionIR, "compare", {"comparison": "lt", "args": [lit(1), lit(2)]})
        unknown = n(ExpressionIR, "unknown_opcode", {})
        expr = n(ExpressionIR, "conditional", {"condition": cmp, "then": lit(3), "else": unknown})
        self.assertEqual(runtime.evaluate(expr), 3*SCALE)

    def test_missing_lookup_is_not_zero(self):
        with self.assertRaises(GapError) as caught:
            BehaviorRuntime(state()).evaluate(n(ExpressionIR, "lookup", {"scope": "missing", "key": "123"}))
        self.assertIn("missing/123", caught.exception.gap.required_capability)

    def test_unknown_opcode_and_numeric_domains(self):
        with self.assertRaises(GapError):
            BehaviorRuntime(state()).evaluate(n(ExpressionIR, "unknown_opcode", {"opcode": 79}))
        for op, lhs, rhs in (("add", 1, 0), ("div", SCALE, 0), ("add", (2**63)-2, 2)):
            with self.assertRaises(NumericSemanticGap):
                fixed_binary(op, lhs, rhs)
        self.assertEqual(fixed_binary("div", -3*SCALE, 2*SCALE), -3*SCALE//2)

    def test_context_targets_and_order(self):
        runtime = BehaviorRuntime(state())
        for op, ids in (("Caster", ["a"]), ("AbilityTargetEntity", ["b"]), ("SkillTargetEntityList", ["b", "a"]),
                        ("ParamEntity", ["b"]), ("ModifierOwnerEntity", ["a"])):
            self.assertEqual(runtime.select(n(TargetSelectorIR, op)), ids)
        seq = n(TargetSelectorIR, "sequence", {"selectors": [n(TargetSelectorIR,"Caster"),n(TargetSelectorIR,"SkillTargetEntityList")]})
        self.assertEqual(runtime.select(seq), ["a", "b", "a"])

    def test_aliases_are_config_bound_and_unknown_is_gap(self):
        alias = n(TargetSelectorIR, "RPG.GameCore.TargetAlias", {"alias": "custom"})
        with self.assertRaises(GapError):
            BehaviorRuntime(state()).select(alias)
        self.assertEqual(BehaviorRuntime(state(), aliases={"custom": n(TargetSelectorIR,"Caster")}).select(alias), ["a"])

    def test_map_filter_compare_and_random_targets(self):
        runtime = BehaviorRuntime(state())
        source = n(TargetSelectorIR,"SkillTargetEntityList")
        pred = n(PredicateIR,"entity-state", {"target":n(TargetSelectorIR,"ParamEntity"),"key":"alive","value":True})
        self.assertEqual(runtime.select(n(TargetSelectorIR,"filter",{"source":source,"predicate":pred})),["a"])
        self.assertEqual(runtime.select(n(TargetSelectorIR,"map",{"source":source,"selector":n(TargetSelectorIR,"ParamEntity")})),["b","a"])
        self.assertEqual(runtime.select(n(TargetSelectorIR,"compare",{"left":source,"right":n(TargetSelectorIR,"Caster"),"include_matches":False})),["b"])
        clone = runtime.clone()
        selector = n(TargetSelectorIR,"random",{"source":source})
        self.assertEqual(runtime.select(selector),clone.select(selector))
        self.assertEqual(runtime.state.rng.draws, 1)

    def test_predicate_rows_are_data_and_logical_short_circuit(self):
        runtime = BehaviorRuntime(state())
        present = n(PredicateIR,"skill-tree-row-present",{"key":99})
        null = n(PredicateIR,"skill-tree-row-present",{"key":8})
        self.assertTrue(runtime.predicate(present))
        self.assertFalse(runtime.predicate(null))
        self.assertTrue(runtime.predicate(n(PredicateIR,"any",{"args":[present,n(PredicateIR,"unknown")]})))
        self.assertTrue(runtime.predicate(n(PredicateIR,"not",{"arg":null})))
        self.assertFalse(runtime.predicate(n(PredicateIR,"all",{"args":[null,n(PredicateIR,"unknown")]})))

    def test_registry_dispatch_generic_identity_only(self):
        registry = default_registry()
        registry.register("task","custom",lambda engine,node,s: [])
        runtime = BehaviorRuntime(state(),actions={"action":action([n(TaskIR,"custom")])},registry=registry)
        self.assertEqual(runtime.step("action").status,ExecutionStatus.DECISION_POINT)
        with self.assertRaises(ValueError):
            registry.register("task","custom",lambda *args: [])
        self.assertTrue(all(t["semantic_authority"]=="REFERENCE_MODEL" for t in runtime.trace))

    def test_generic_invocation_requires_library_and_explicit_policy(self):
        invoke=n(TaskIR,"RPG.GameCore.TriggerAbility",{"fields":{
            "TargetType":n(TargetSelectorIR,"Caster"),
            "AbilityName":n(ExpressionIR,"literal",{"value":"generic-child"})}})
        parent=action([invoke])
        child=action([n(CompletionIR,"completion")])
        runtime=BehaviorRuntime(state(),actions={"run":parent})
        self.assertIn("decoded_ability_binding",runtime.step("run").gap.required_capability)
        runtime=BehaviorRuntime(state(),actions={"run":parent},abilities={"generic-child":child},
            policies={"invocation":"REFERENCE_SEQUENCE"})
        self.assertEqual(runtime.step("run").status,ExecutionStatus.COMPLETED)

    def test_generic_task_branch_does_not_execute_unselected_gap(self):
        branch=n(TaskIR,"RPG.GameCore.PredicateTaskList",{"fields":{
            "Predicate":n(PredicateIR,"skill-tree-row-present",{"key":99}),
            "SuccessTaskList":n(TaskSequenceIR,"immediate_sequence",{"tasks":[n(CompletionIR,"completion")]}),
            "FailedTaskList":n(TaskSequenceIR,"immediate_sequence",{"tasks":[n(TaskIR,"unknown")]})}})
        runtime=BehaviorRuntime(state(),actions={"run":action([branch])})
        self.assertEqual(runtime.step("run").status,ExecutionStatus.COMPLETED)
        self.assertEqual(runtime.gaps.to_dict()["entries"],[])

    def test_sequence_dynamic_property_and_resource_scopes(self):
        tasks = [n(TaskIR,"dynamic_write",{"scope":"local","key":"x","value":lit(4)}),
            n(PropertyMutationIR,"property_write",{"owner":"a","key":"hp","operation":"add","value":lit(2)}),
            n(ResourceMutationIR,"resource_write",{"scope":"actor","owner":"a","key":"energy","operation":"set","value":lit(7)}),
            n(ResourceMutationIR,"resource_write",{"scope":"team","owner":"allies","key":"bp","operation":"set","value":lit(3)}),
            n(CompletionIR,"completion")]
        runtime=BehaviorRuntime(state(),actions={"run":action(tasks)})
        result=runtime.step("run")
        self.assertEqual(result.status,ExecutionStatus.COMPLETED)
        self.assertEqual(runtime.state.properties["a"]["hp"],12*SCALE)
        self.assertEqual(runtime.state.actor_resources["a"],{"energy":7*SCALE})
        self.assertEqual(runtime.state.team_resources["allies"],{"bp":3*SCALE})
        self.assertEqual(runtime.state.dynamic_values["local"]["x"],4*SCALE)

    def test_scheduler_order_barrier_and_completion_drain(self):
        def write(value):
            return n(TaskIR,"dynamic_write",{"scope":"local","key":"x","value":lit(value)})
        tasks=[n(TaskIR,"schedule",{"tick":4,"tasks":[write(1)],"release":"gate"}),
               n(TaskIR,"schedule",{"tick":4,"tasks":[write(2)]}),
               n(SchedulerBarrierIR,"barrier",{"key":"gate"}), n(CompletionIR,"completion")]
        runtime=BehaviorRuntime(state(),actions={"run":action(tasks)})
        self.assertEqual(runtime.step("run").status,ExecutionStatus.COMPLETED)
        self.assertEqual(runtime.state.dynamic_values["local"]["x"],2*SCALE)
        self.assertEqual(runtime.state.scheduler.tick,4)
        self.assertEqual(runtime.state.scheduler.callbacks,[])

    def test_pending_barrier_snapshot_resume(self):
        runtime=BehaviorRuntime(state(),actions={"run":action([n(SchedulerBarrierIR,"barrier",{"key":"gate"}),n(CompletionIR,"completion")])})
        self.assertEqual(runtime.step("run").status,ExecutionStatus.WAITING_SCHEDULER)
        self.assertEqual(runtime.legal_actions(),())
        restored=BehaviorRuntime.from_snapshot(runtime.snapshot())
        self.assertEqual(runtime.stable_hash(),restored.stable_hash())
        restored.state.scheduler.barriers["gate"]=True
        self.assertEqual(restored.run_until_decision().status,ExecutionStatus.COMPLETED)

    def test_event_dispatch_policy_and_order(self):
        callback=n(TaskIR,"dynamic_write",{"scope":"events","key":"x","value":lit(5)})
        runtime=BehaviorRuntime(state(),actions={"run":action([n(EventDispatchIR,"event_dispatch",{"event_type":"on_test"}),n(CompletionIR,"completion")])},events={"on_test":[callback]})
        self.assertEqual(runtime.step("run").status,ExecutionStatus.COMPLETED)
        self.assertEqual(runtime.state.dynamic_values["events"]["x"],5*SCALE)
        runtime=BehaviorRuntime(state(),actions={"run":action([n(EventDispatchIR,"event_dispatch",{"event_type":"unknown"})])})
        self.assertEqual(runtime.step("run").status,ExecutionStatus.SEMANTIC_GAP)

    def test_rng_known_vector_and_clone_replay(self):
        rng=DeterministicRNG(0)
        self.assertEqual(rng.next_u64(),0xE220A8397B1DCDAF)
        choices=[n(TaskIR,"dynamic_write",{"scope":"local","key":"x","value":lit(i)}) for i in range(4)]
        runtime=BehaviorRuntime(state(),actions={"run":action([n(RandomChoiceIR,"random_choice",{"choices":choices}),n(CompletionIR,"completion")])})
        clone=runtime.clone()
        runtime.step("run");clone.step("run")
        self.assertEqual(runtime.stable_hash(),clone.stable_hash())
        initial=BehaviorRuntime(state(),actions=runtime.actions)
        replayed,results=initial.replay(["run"])
        self.assertEqual(replayed.stable_hash(),runtime.stable_hash())
        self.assertEqual(results[0].status,ExecutionStatus.COMPLETED)

    def test_modifier_representation_and_lifecycle_is_explicit(self):
        instance=ModifierInstance("m1","any-config","a","b","b",2,1,{"ticks":3},
            {"x":SCALE},{"hp":8*SCALE},[{"event":"any","order":1}],A.to_dict())
        runtime=BehaviorRuntime(state(),actions={"apply":action([n(ModifierApplyIR,"modifier_apply",{"instance":instance.__dict__})]),
            "remove":action([n(ModifierRemoveIR,"modifier_remove",{"instance_id":"m1"})])})
        runtime.step("apply")
        clone=runtime.state.clone()
        self.assertEqual(clone,runtime.state)
        clone.modifiers["m1"].dynamic_values["x"]=0
        self.assertEqual(runtime.state.modifiers["m1"].dynamic_values["x"],SCALE)
        self.assertEqual(runtime.step("apply").status,ExecutionStatus.SEMANTIC_GAP)
        runtime.state.scheduler.continuation=[]
        runtime.step("remove")
        self.assertEqual(runtime.state.modifiers,{})

    def test_semantic_gap_preserves_node_evidence_and_retry(self):
        unknown=n(UnsupportedSemanticIR,"UnresearchedTask",{"task_type":"UnresearchedTask","required_capability":"missing primitive"})
        runtime=BehaviorRuntime(state(),actions={"run":action([unknown])})
        result=runtime.step("run")
        self.assertEqual(result.status,ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(result.gap.node,unknown.to_dict())
        self.assertEqual(result.gap.evidence,A.to_dict())
        before=runtime.state.stable_hash()
        runtime.run_until_decision()
        self.assertEqual(runtime.state.stable_hash(),before)
        self.assertEqual(runtime.gaps.to_dict()["entries"][0]["frequency"],2)

    def test_gap_rolls_back_partial_rng_and_property_mutations(self):
        registry=default_registry()
        def broken(engine,node,s):
            s.rng.next_u64();s.properties["a"]["hp"]=0
            raise GapError(node,"hook")
        registry.register("task","broken",broken)
        runtime=BehaviorRuntime(state(),actions={"run":action([n(TaskIR,"broken")])},registry=registry)
        result=runtime.step("run")
        self.assertEqual(result.status,ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(runtime.state.rng.draws,0)
        self.assertEqual(runtime.state.properties["a"]["hp"],10*SCALE)

    def test_heal_formula2_core_reference_only_and_cap(self):
        operands={"d50":100*SCALE,"d28":SCALE//2,"d60":10*SCALE,"dD0":0,"d38":0,
                  "d128":0,"d48":100*SCALE,"dD8":0}
        result=heal_formula2_core(operands,False)
        self.assertEqual(result.amount_raw,60*SCALE)
        self.assertEqual(result.semantic_authority,"REFERENCE_MODEL")
        self.assertIn("settlement",result.unresolved_extension_points)
        operands.update(d70=10*SCALE,d68=SCALE,d40=3*SCALE)
        self.assertEqual(heal_formula2_core(operands,True).amount_raw,7*SCALE)
        with self.assertRaises(NumericSemanticGap):
            heal_formula2_core({},False)
        with self.assertRaises(NumericSemanticGap):
            heal_formula2_core(operands,"false")
        operands.update(dD0=SCALE//2,d38=SCALE//2,d128=SCALE//2,dD8=50*SCALE)
        self.assertEqual(heal_formula2_core(operands,False).amount_raw,240*SCALE)

    def test_natasha_trusted_graph_all_selected_semantic_nodes(self):
        self.assertEqual(self.authority.source_sha256,"9e09bd77ef2bc6416f4936286a528aa9606182e6650b097765351648aab6a4f6")
        nodes=list(walk_nodes(self.ir))
        task_spans={tuple(node.payload["span"]) for node in nodes if node.kind=="TaskIR"}
        self.assertEqual(len(task_spans),21)
        expressions={node.authority.source_pointer for node in nodes if node.kind=="ExpressionIR"}
        self.assertGreaterEqual(len(expressions),19)
        self.assertTrue(any(node.op=="RPG.GameCore.AddModifier" and "HOT" in str(node.payload) for node in nodes))
        self.assertTrue(any(node.op=="RPG.GameCore.BySkillPointActivated" for node in nodes))
        self.assertTrue(all(node.authority.source_artifact for node in nodes))
        self.assertTrue(any(node.authority.ledger_refs for node in nodes))
        dynamic_nodes=self.graph["dynamic_float_structural_nodes"]
        self.assertEqual(len(dynamic_nodes),16)
        for serialized in dynamic_nodes:
            if serialized["tag"]==0:
                raw=int(serialized["signed_payload"]["decoded_signed"])
                self.assertTrue(any(node.kind=="ExpressionIR" and node.op=="literal" and node.payload.get("raw")==raw for node in nodes))
            else:
                self.assertTrue(any(node.kind=="ExpressionIR" and node.op=="identity" and
                    node.payload["serialized_program"]["token_ids"]==serialized["token_ids"] and
                    node.payload["serialized_program"]["int32_operands"]==serialized["int32_operands"] for node in nodes))

    def test_all_archived_selected_expression_ASTs_compile(self):
        records=json.loads(EXPRESSIONS.read_text(encoding="utf-8"))
        self.assertEqual(len(records),19)
        authority=Authority("REAL_CONTENT_RECONSTRUCTED","4.6.51",EXPRESSIONS.relative_to(REPO).as_posix(),
            hashlib.sha256(EXPRESSIONS.read_bytes()).hexdigest())
        compiler=BehaviorCompiler(authority,self.ledger)
        for i,record in enumerate(records):
            expr=compiler.convert(record["serialized"],f"/{i}/serialized")
            self.assertIn(expr.op,{"literal","identity"})
            self.assertEqual(expr,IRNode.from_dict(expr.to_dict()))
            self.assertEqual(expr.authority.source_sha256,authority.source_sha256)

    def test_natasha_prefix_and_first_gap_without_character_handler(self):
        first=self.ir.payload["abilities"][0]
        library={a.payload["content_name"]:a for a in self.ir.payload["abilities"]}
        runtime=BehaviorRuntime(state(),actions={"fixture":first},abilities=library,aliases={"Caster":n(TargetSelectorIR,"Caster")})
        result=runtime.step("fixture")
        self.assertEqual(result.status,ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(result.gap.task_type,"RPG.GameCore.TriggerAbility")
        self.assertIn("context/controller",result.gap.required_capability)
        self.assertTrue(any(t["op"]=="literal" for t in result.trace))
        self.assertTrue(any(t["op"]=="Caster" for t in result.trace))
        self.assertEqual(result.completed_nodes,0)

    def test_dynamic_float_program_is_generic_and_unknown_preserved(self):
        program={"type":"RPG.GameCore.DynamicFloat","tag":1,"token_ids":[1,0,1,1,2,17],"int32_operands":[123,456],"int64_operands":[]}
        expr=self.compiler.convert(program,"/expression")
        runtime=BehaviorRuntime(state());runtime.state.dynamic_values["supplied"]={"123":SCALE,"456":2*SCALE}
        self.assertEqual(runtime.evaluate(expr),3*SCALE)
        program["token_ids"]=[99,17]
        expr=self.compiler.convert(program,"/expression")
        self.assertEqual(expr.op,"unknown_opcode")
        self.assertEqual(expr.payload["decoded"]["token_ids"],[99,17])

    def test_unknown_task_compiles_instead_of_rejection(self):
        record={"kind":"TaskConfig","concrete_type":"RPG.GameCore.NewFutureTask","start":1,"end":2,"structure":{"fields":[]}}
        node=self.compiler.convert(record,"/unknown")
        self.assertIsInstance(node,UnsupportedSemanticIR)
        self.assertEqual(node.payload["decoded"],record)
        self.assertIn(node.stable_hash(),self.compiler.semantic_gaps)

    def test_reader_chain_roles_are_bound_by_config(self):
        record={"type":"decoder.dispatch","reader":"dispatch","child":{
            "type":"decoder.factory","reader":"factory","child":{
                "type":"RPG.GameCore.FutureTask","reader":"body","start":5,"end":8,
                "fields":[{"mask":4,"values":[{"kind":"string","value":"retained"}]}]}}}
        compiler=BehaviorCompiler(self.authority,self.ledger,{"decoder.dispatch":"task"})
        node=compiler.convert(record,"/archived")
        self.assertIsInstance(node,UnsupportedSemanticIR)
        self.assertEqual(node.payload["field_bindings_status"],"UNRESOLVED")
        self.assertEqual(node.payload["fields"]["unbound_bit_0"],"retained")

    def test_full_snapshot_isolation_and_registry_binding(self):
        runtime=BehaviorRuntime(state())
        snapshot=runtime.snapshot();snapshot["state"]["entities"]["a"]["alive"]=False
        self.assertTrue(runtime.state.entities["a"]["alive"])
        restored=BehaviorRuntime.from_snapshot(runtime.snapshot())
        self.assertEqual(restored.stable_hash(),runtime.stable_hash())
        registry=default_registry();registry.register("task","extra",lambda *args: [])
        with self.assertRaises(ValueError):
            BehaviorRuntime.from_snapshot(runtime.snapshot(),registry)
        with self.assertRaises(TypeError):
            BehaviorBattleState(entities={1:{}})

    def test_invalid_action_and_terminal_are_typed(self):
        runtime=BehaviorRuntime(state())
        self.assertEqual(runtime.step("missing").status,ExecutionStatus.INVALID_ACTION)
        runtime.state.terminal=True
        self.assertEqual(runtime.run_until_decision().status,ExecutionStatus.TERMINAL)


if __name__ == "__main__":
    unittest.main()
