"""Reproduce R12 controls from pinned archived JSON; no payload/live/reverse access.

Run with repository-resolved Python. --package writes the user-requested external
handoff only after tests and source preservation checks pass.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
import unittest
import zipfile
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from hsr_battle_agent.battle_ir.behavior import (
    Authority, IRNode, NODE_TYPES, TargetSelectorIR, walk_nodes)
from hsr_battle_agent.battle_ir.behavior_binding import BehaviorCompiler, TASK_MAPPINGS
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime, ExecutionStatus, default_registry
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState

CR = "CR-R12-GENERIC-BEHAVIOR-IR-RUNTIME-REENTRY-20261007-001"
SUFFIX = "20261007_001"
AUDIT = REPO / "tmp/audit/r12_runtime_reentry_20261007_001"
CONTROL = REPO / "data/control"
GRAPH_PATH = "data/control/real_runtime_4651_natasha_110502_structural_graph_20261004_001.json"
LEDGER_PATH = f"data/control/real_runtime_generic_primitive_ledger_{SUFFIX}.json"
CHECKPOINT_PATH = f"data/control/real_runtime_4651_natasha_110502_research_checkpoint_{SUFFIX}.json"
EXPRESSIONS_PATH = "tmp/audit/r11_4651_natasha_semantic_closure_20261005_001/selected_dynamic_float_expressions.json"
PRODUCTION = [
    "src/hsr_battle_agent/battle_ir/behavior.py",
    "src/hsr_battle_agent/battle_ir/behavior_binding.py",
    "src/hsr_battle_agent/battle_runtime/behavior.py",
    "src/hsr_battle_agent/battle_runtime/behavior_state.py",
    "src/hsr_battle_agent/battle_runtime/behavior_primitives.py"]
TESTS = ["tests/battle_runtime/test_behavior_r12.py"]
REPORT_PATH = f"docs/agent/handoffs/generic_behavior_ir_runtime_reentry_{SUFFIX}.md"
# Archived decoder registry identities. Content-specific and obfuscated bindings
# belong to input config, never semantic/evaluator dispatch logic.
ARCHIVED_DECODER_ROLES = {
    "RPG.GameCore.TaskConfig": "task", ".BEMKAFNMJIK": "task",
    "RPG.GameCore.PredicateConfig": "predicate", ".MKIOEPLIEIH": "predicate",
    "RPG.GameCore.TargetEvaluator": "target", ".BKLODCFCAED": "target",
    "RPG.GameCore.TargetSeqOperation": "target", ".KMBDLCNGJFN": "target"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(relative):
    return json.loads((REPO / relative).read_text(encoding="utf-8-sig"))


def write(path, document):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2,
                                    allow_nan=False) + "\n", encoding="utf-8")


def walk_dicts(value, pointer=""):
    if isinstance(value, dict):
        yield pointer, value
        for k, v in value.items():
            yield from walk_dicts(v, pointer + "/" + k.replace("~", "~0").replace("/", "~1"))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk_dicts(v, pointer + "/" + str(i))


def source_authority(path, digest):
    return Authority("REAL_CONTENT_RECONSTRUCTED", "4.6.51", path, digest,
        semantic_status="STRUCTURE_ONLY", oracle_status="RUNTIME_ORACLE_PENDING")


def main(package=False):
    AUDIT.mkdir(parents=True, exist_ok=True)
    checkpoint, ledger, graph = read(CHECKPOINT_PATH), read(LEDGER_PATH), read(GRAPH_PATH)
    expected = checkpoint["structural_checkpoint"]["trusted_graph_ref"]["sha256"]
    if sha(REPO / GRAPH_PATH) != expected:
        raise RuntimeError("trusted graph hash mismatch")
    refs = {}
    for entry in ledger["serialized_type_census"]:
        for ref in entry["evidence_refs"]:
            path = ref["path"]
            if path in refs and refs[path] != ref["sha256"]:
                raise RuntimeError("conflicting archived source pins")
            refs[path] = ref["sha256"]
    receipts = []
    for path, digest in sorted(refs.items()):
        actual = sha(REPO / path)
        if actual != digest:
            raise RuntimeError(f"archived source hash mismatch: {path}")
        receipts.append({"path": path, "sha256": actual, "bytes": (REPO / path).stat().st_size,
                         "source": "ARCHIVED_DECODED_JSON_ONLY", "verified": True})
    expression_pin = next(e for e in checkpoint["artifact_hashes"] if e["path"] == EXPRESSIONS_PATH)
    if sha(REPO / EXPRESSIONS_PATH) != expression_pin["sha256"]:
        raise RuntimeError("selected expression archive hash mismatch")
    expression_records = read(EXPRESSIONS_PATH)
    expression_compiler = BehaviorCompiler(source_authority(EXPRESSIONS_PATH, expression_pin["sha256"]), ledger)
    expression_ir = [expression_compiler.convert(e["serialized"], f"/{i}/serialized")
                     for i,e in enumerate(expression_records)]
    assert len(expression_ir) == 19 and all(e.op in {"literal", "identity"} for e in expression_ir)
    expression_fixture = {"source": EXPRESSIONS_PATH, "source_sha256": expression_pin["sha256"],
        "expression_count": len(expression_ir), "role": "SUPPLEMENTAL_EXPRESSIONS_NOT_IMPLICIT_EXECUTION",
        "nodes": [e.to_dict() for e in expression_ir]}
    write(AUDIT / "archived_expression_ir.json", expression_fixture)
    write(AUDIT / "source_pins.json", {"corpus": receipts,
        "supplemental_selected_expression_source": {"path": EXPRESSIONS_PATH, "sha256": expression_pin["sha256"]},
        "primitive_ledger_sha256": sha(REPO / LEDGER_PATH), "checkpoint_sha256": sha(REPO / CHECKPOINT_PATH)})

    compiler = BehaviorCompiler(source_authority(GRAPH_PATH, expected), ledger)
    ir = compiler.compile_graph(graph)
    restored = IRNode.from_dict(json.loads(ir.canonical_json()))
    assert ir == restored and ir.stable_hash() == restored.stable_hash()
    assert ir.stable_hash() == compiler.compile_graph(graph).stable_hash()
    nodes = list(walk_nodes(ir))
    task_nodes = [n for n in nodes if n.kind == "TaskIR"]
    assert len({tuple(n.payload["span"]) for n in task_nodes}) == 21
    aliases = {"Caster": TargetSelectorIR("fixture-caster", "Caster",
        Authority("REFERENCE_MODEL", "r12-fixture-v1", "explicit_fixture_context", "",
                  semantic_status="REFERENCE_MODEL"))}
    state = BehaviorBattleState(entities={"caster": {}, "target": {}},
        target_context={"caster": "caster", "ability_target": "target"})
    library = {a.payload["content_name"]: a for a in ir.payload["abilities"]}
    runtime = BehaviorRuntime(state, actions={"fixture": ir.payload["abilities"][0]}, abilities=library, aliases=aliases)
    result = runtime.step("fixture")
    assert result.status == ExecutionStatus.SEMANTIC_GAP
    prefix = {"compiled_to_ir": "PASS", "executable_prefix": "PASS",
        "prefix_scope": "First TriggerAbility target and DynamicString operand evaluation only; zero completed top-level tasks",
        "completed_leaf_tasks": result.completed_nodes, "full_transition": result.status.value,
        "first_semantic_gap": asdict(result.gap), "semantic_authority": result.semantic_authority,
        "trace": list(result.trace), "ir_canonical_sha256": ir.stable_hash()}
    write(AUDIT / "fixture_execution.json", prefix)
    write(AUDIT / "fixture_behavior_ir.json", ir.to_dict())

    # Census source nodes, not copied/wrapper occurrences. Metadata-only mentions
    # in the archived ledger are reported separately and never counted as tasks.
    type_records = {}
    semantic_counts = {}
    expression_counts = {"decoded_expressions": 0, "IR_representable": 0, "unknown_programs": 0}
    gaps = []
    registry = default_registry()
    conditional_tasks = {"RPG.GameCore.PredicateTaskList", "RPG.GameCore.TriggerAbility"}
    for source in receipts:
        path = source["path"]
        binder = BehaviorCompiler(source_authority(path, source["sha256"]), ledger, ARCHIVED_DECODER_ROLES)
        seen = set()
        for pointer, record in walk_dicts(read(path)):
            if record.get("type") == "RPG.GameCore.DynamicFloat" and "tag" in record:
                coordinate = ("expression", record.get("start"), record.get("end"))
                if coordinate not in seen:
                    seen.add(coordinate)
                    expr = binder.convert(record, pointer)
                    expression_counts["decoded_expressions"] += 1
                    expression_counts["IR_representable"] += 1
                    if expr.op == "unknown_opcode":
                        expression_counts["unknown_programs"] += 1
                        gaps.append({"primitive": "DynamicFloat", "node": expr.node_id,
                            "content_source": path, "frequency": 1, "blocking": True,
                            "compilation_blocking": False, "evidence_status": expr.authority.to_dict(),
                            "required_capability": expr.payload["required_capability"],
                            "observation_stage": "CORPUS_CAPABILITY_AUDIT",
                            "recommended_next_implementation": "Implement the retained DynamicFloat opcode generically"})
            normalized = binder.normalize_record(record)
            if normalized is None:
                continue
            kind = normalized["kind"]
            config_type = normalized.get("concrete_type")
            if not isinstance(config_type, str):
                continue
            coordinate = (kind, config_type, normalized.get("start"), normalized.get("end"))
            if coordinate[2] is None:
                coordinate += (pointer,)
            if coordinate in seen:
                continue
            seen.add(coordinate)
            node = binder.convert(record, pointer)
            family = {"TaskConfig":"task", "PredicateConfig":"predicate", "TargetSelector":"target"}[kind]
            key = (family, config_type)
            row = type_records.setdefault(key, {"family": family, "type": config_type, "decoded_instances": 0,
                "sources": [], "IR_representable": True, "reference_handler_registered": config_type in registry.handlers[family],
                "reference_executable": family == "task" and config_type in conditional_tasks,
                "reference_execution_requires_explicit_bindings": True,
                "field_bindings_unresolved_instances": 0,
                "oracle_pending": True, "unsupported_semantic": node.kind == "UnsupportedSemanticIR",
                "mapping": list(TASK_MAPPINGS.get(config_type.rsplit('.',1)[-1], ("unsupported", "STRUCTURE_ONLY", "ORACLE_PENDING"))) if family == "task" else None})
            row["decoded_instances"] += 1
            row["field_bindings_unresolved_instances"] += node.payload.get("field_bindings_status") == "UNRESOLVED"
            if path not in row["sources"]:
                row["sources"].append(path)
            semantic_counts[family] = semantic_counts.get(family, 0) + 1
            executable = config_type in conditional_tasks if family == "task" else config_type in registry.handlers[family]
            if not executable or node.payload.get("field_bindings_status") == "UNRESOLVED":
                gaps.append({"primitive": config_type, "node": node.node_id, "content_source": path,
                    "frequency": 1, "blocking": True, "compilation_blocking": False,
                    "evidence_status": node.authority.to_dict(), "required_capability":
                    f"decoded field binding:{config_type}" if node.payload.get("field_bindings_status") == "UNRESOLVED" else f"{family}:{config_type}",
                    "observation_stage": "CORPUS_CAPABILITY_AUDIT",
                    "recommended_next_implementation": f"Implement {family}:{config_type} generically; bind effective context/hooks explicitly"})
        # Keep compiler encounters separate from deduplicated corpus frequencies.
        write(AUDIT / (Path(path).stem + "_compiler_gaps.json"), {
            "source": path, "entries": list(binder.semantic_gaps.values()),
            "frequency_scope": "Compiler encounters including nested repeated conversions"})
    task_rows = sorted((row for (family,_),row in type_records.items() if family == "task"), key=lambda row: row["type"])
    all_rows = sorted(type_records.values(), key=lambda row: (row["family"], row["type"]))
    census = {"schema": "generic_runtime_support_census/2", "change_request": CR,
        "actual_corpus": receipts, "scope": "Four hash-matching archived selected/global-alias graphs; not the 620-skill universe",
        "count_policy": "Distinct source/type/start/end decoded wrappers; copies deduplicated; counts are not runtime calls",
        "archived_ledger": {"primitive_entries": ledger["primitive_count"], "serialized_named_types": ledger["serialized_type_count"],
            "includes_metadata_only": True, "source": LEDGER_PATH, "sha256": sha(REPO / LEDGER_PATH)},
        "archived_decoder_family_bindings": ARCHIVED_DECODER_ROLES,
        "decoded_semantic_instance_counts": semantic_counts,
        "expression_coverage": expression_counts,
        "known_task_types": [r["type"] for r in task_rows],
        "IR_representable_task_types": [r["type"] for r in task_rows],
        "mapped_task_types": [r["type"] for r in task_rows if not r["unsupported_semantic"]],
        "reference_executable_task_types": [r["type"] for r in task_rows if r["reference_executable"]],
        "reference_executable_scope": "Conditional reference sequencing/invocation only with explicit operand/context/controller bindings; no full native skill claim",
        "reference_core_only_task_types": ["RPG.GameCore.HealHP", "RPG.GameCore.SetDynamicValue"],
        "oracle_pending_task_types": [r["type"] for r in task_rows],
        "unsupported_task_types": [r["type"] for r in task_rows if r["unsupported_semantic"]],
        "non_executable_task_types": [r["type"] for r in task_rows if not r["reference_executable"]],
        "types": all_rows, "fully_decoded_skill_count_claimed": False, "native_validated_task_types": []}
    census["counts"] = {k: len(census[k]) for k in ("known_task_types", "IR_representable_task_types", "mapped_task_types",
        "reference_executable_task_types", "oracle_pending_task_types", "unsupported_task_types")}
    write(CONTROL / f"generic_runtime_support_census_v2_{SUFFIX}.json", census)
    # Group census blockers for R13 frequency prioritization; keep exact source-node refs.
    grouped = {}
    for gap in gaps:
        key = (gap["primitive"], gap["content_source"])
        row = grouped.setdefault(key, {**gap, "frequency":0, "nodes":[]})
        row["frequency"] += 1
        row["nodes"].append(gap["node"])
    gap_control = {"schema":"generic_runtime_semantic_gap_ledger/1", "change_request":CR,
        "corpus_gaps": sorted(grouped.values(),key=lambda x:(-x["frequency"],x["primitive"],x["content_source"])),
        "execution_encounters":runtime.gaps.to_dict()["entries"],
        "frequency_policy":"Corpus frequencies deduplicate source coordinates; execution frequencies count actual attempts separately",
        "native_correct_claimed":False}
    write(CONTROL / f"generic_runtime_semantic_gap_ledger_{SUFFIX}.json",gap_control)
    contract = {"schema":"generic_behavior_ir/1", "change_request":CR,
        "canonicalization":"UTF-8 JSON, sorted string keys, compact separators, allow_nan=False; list order preserved; SHA-256",
        "node_kinds":sorted(NODE_TYPES), "authority_fields":list(Authority.__dataclass_fields__),
        "execution_authority":"REFERENCE_MODEL; original per-node authority retained in trace and gaps",
        "task_mappings": {k:{"IR":"IR_SUPPORTED","op_concept":v[0],"semantic_availability":v[1],"oracle":v[2]} for k,v in TASK_MAPPINGS.items()},
        "expression_operations":sorted(registry.handlers["expression"])+["unknown_opcode"],
        "target_operations":sorted(registry.handlers["target"]),
        "predicate_operations":sorted(registry.handlers["predicate"]),
        "registry_identity":registry.identity(),
        "state_schema":"evidence_aware_behavior_state/1", "RNG":"splitmix64_reference_v1",
        "scheduler":"Serialized immediate sequences, retained continuation head, ordered tick/sequence callbacks, explicit barriers, event queue, completion request plus drain",
        "presentation_policy":"Unknown animation/effect/movement/VO retain TaskIR and block; no automatic cosmetic no-op",
        "resource_policy":"Actor and team stores separated; exact SP/BP/energy native joins remain pending",
        "heal_policy":"Generic bounded mode0 FormulaType2 amount-only reference core; pre/post hooks, modifiers, settlement and property/resource listeners unresolved",
        "fixture":{"source":GRAPH_PATH,"source_sha256":expected,"canonical_ir_sha256":ir.stable_hash(),
                   "compiled_to_ir":"PASS","full_transition":"SEMANTIC_GAP","completed_leaf_tasks":result.completed_nodes},
        "supplemental_selected_expression_fixture": {"source":EXPRESSIONS_PATH,
            "source_sha256":expression_pin["sha256"],"expression_count":len(expression_ir),
            "main_graph_expressions":16,"HOT_callback_expressions":3,
            "role":"SUPPLEMENTAL_EXPRESSIONS_NOT_IMPLICIT_EXECUTION"},
        "no_M15_admission":True,"no_native_correct_claim":True}
    write(CONTROL / f"generic_behavior_ir_v1_{SUFFIX}.json",contract)

    # AST-based audit rejects character/skill/name dispatch anywhere in CR production.
    forbidden=[]
    for relative in PRODUCTION:
        text=(REPO/relative).read_text(encoding="utf-8")
        tree=ast.parse(text)
        for item in ast.walk(tree):
            if isinstance(item,ast.Constant) and (item.value in (1105,110502) or
                isinstance(item.value,str) and "natasha" in item.value.lower()):
                forbidden.append({"file":relative,"line":item.lineno,"value":item.value})
            if isinstance(item,(ast.FunctionDef,ast.ClassDef)) and "natasha" in item.name.lower():
                forbidden.append({"file":relative,"line":item.lineno,"name":item.name})
        if "import random" in text or "from random" in text:
            forbidden.append({"file":relative,"reason":"process-global/random import"})
    if forbidden:
        raise RuntimeError(f"forbidden architecture patterns: {forbidden}")
    write(AUDIT / "architecture_scan.json",{"scope":PRODUCTION,"method":"Python AST constants/classes/functions plus RNG import scan",
        "forbidden_patterns":forbidden,"result":"PASS","historical_modules":"Not edited; historical selected handlers are outside R12 dispatch"})

    baseline=read("tmp/audit/r12_runtime_reentry_20261007_001/preexisting_file_hashes.json")
    changed=[path for path,digest in baseline.items() if not path.endswith(".pyc") and
             (not (REPO/path).is_file() or sha(REPO/path)!=digest)]
    write(AUDIT / "frozen_preservation.json",{"preexisting_non_cache_files_checked":sum(not p.endswith('.pyc') for p in baseline),
        "changed_preexisting_files":changed,"frozen_M10_M15_modified":False if not changed else "FAILED",
        "new_production":PRODUCTION,"new_tests":TESTS,"git_writes":"NONE"})
    if changed:
        raise RuntimeError(f"preexisting source/control/test files changed: {changed}")
    with (AUDIT / "focused_tests.txt").open("w",encoding="utf-8") as stream:
        suite=unittest.defaultTestLoader.loadTestsFromName("tests.battle_runtime.test_behavior_r12")
        test_result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    write(AUDIT / "test_receipt.json",{"suite":"tests.battle_runtime.test_behavior_r12","tests":test_result.testsRun,
        "failures":len(test_result.failures),"errors":len(test_result.errors),"successful":test_result.wasSuccessful(),
        "interpreter":sys.version,"native_validation":False})
    if not test_result.wasSuccessful():
        raise RuntimeError("R12 tests failed")
    regression_note = ""
    regression_path = AUDIT / "regression_receipt.json"
    if regression_path.exists():
        regression = json.loads(regression_path.read_text(encoding="utf-8"))
        if not all(row["PASS"] for row in regression):
            raise RuntimeError("frozen FAST_UNIT regression failed")
        regression_note = "Frozen FAST_UNIT regression: " + ", ".join(
            f"{row['suite']} {row['tests']} PASS" for row in regression) + "; total " + str(sum(row['tests'] for row in regression)) + " PASS, zero failures/errors/skips."

    report=f"""# R12 Generic Behavior IR and runtime re-entry

Change request: `{CR}`. Verdict: **GENERIC_RUNTIME_REENTRY_ESTABLISHED**.
Starting HEAD `17750b300eace78b9d2895d0fec4ad54572b96ff`; branch `terra/implementation`.
No Git writes. Every preexisting non-cache source/test/control/handoff file in the start baseline is hash-preserved.
M10-M15, strict admission and existing ScenarioCompiler remain frozen. Unrelated dirty files are preserved.

The pipeline is decoded real content -> evidence-aware binding -> canonical IR -> generic reference executor -> generic battle state -> local decision/actions -> future planner adapter. Native client remains a separate reference oracle and eventual live-state source. R11 live capture and reverse work were not reopened.

Existing architecture decisions are in `tmp/audit/r12_runtime_reentry_20261007_001/existing_runtime_inventory.json`.
New code extends the existing `battle_ir` and `battle_runtime` packages. It does not create a scenario compiler, DB, strict-executor facade or M11 admission adapter.

IR v1 defines all {len(NODE_TYPES)} requested node concepts. Every node retains evidence level, source version/path/hash/pointer, native method references, ledger IDs, semantic status and oracle status. Frozen payload JSON gives copy isolation and deterministic round trips. Original source authority is retained; execution authority is always REFERENCE_MODEL. Structural records and unavailable semantics are never upgraded.

Expressions support literals, explicitly scoped lookups, arithmetic, min/max/clamp, comparisons, lazy conditionals and unknown opcodes. R11 DynamicFloat opcodes 0/1/2/17 compile through generic stack decoding; operand hashes are content data. Mode0 signed raw/2^33 arithmetic is bounded with explicit toward-zero quantization at raw step2. Tagged/mixed/overflow and missing-provider domains block. This policy is not native arithmetic equivalence.

Targets use explicit caster/ability target/skill target list/param entity/modifier owner context, configured aliases, sequence/map/filter/compare/random operations. No effective alias winner is assumed. Predicates include progression row presence (any content key), entity-state tests, comparisons and logical composition. The primitive ledger ({ledger['primitive_count']} entries, {ledger['serialized_type_count']} named types including metadata) is consumed for per-type evidence/native refs and coverage classification.

State separates entities, properties, actor/team resources, progression, modifier instances, dynamic providers, target context, scheduler, pending events and RNG. Mechanics can hold position/summon/phase state; presentation is separate. Clone, equality, canonical snapshots, hashes, registry-qualified runtime restore and local action replay are implemented. Identity is serialized IDs, never Unity/Python object identity.

SplitMix64 reference RNG stores algorithm, state and draw count; selection uses rejection sampling. It is not the client stream. Scheduler retains serialized continuations, barriers, tick/sequence ordered callbacks and event queues. Completion request becomes COMPLETED only after owned queues drain. Unknown native waits/effects/movement/VO remain blockers. No ordinary AV/turn rules or native action completion are invented.

Registry families are task, predicate, target, expression and event. Generic local operations include sequencing, conditional branches, explicit invocation policy, dynamic write, direct property/resource storage mutation, modifier instance insert/remove, event queue dispatch with configured callbacks, barrier/callback scheduling, random choice and completion drain. Property/modifier operations are explicit storage reference policies; native hooks/activation/renew rules are not simulated. Local legal_actions lists only caller-bound idle actions; native costs/target legality/turn ownership are not claimed. Beam/MCTS and live advising are future consumers, not integrated by R12.

The generic heal FormulaType2 core is amount-only, requires all operands and cap flag, and exposes pre-heal, effective amount modifiers, settlement, HP property hooks, post-heal and resource-listener extension points. HealHP remains a typed blocker. SetDynamicValue has a safe explicit-provider primitive, but recovered provider visibility remains blocked. Native actor ModifySPNew is not mapped into team BP or energy by inference. AddModifier and HOT renewal/activation remain oracle pending.

Natasha Skill02 trusted graph compilation: **PASS**. All 21 distinct selected task spans, 16 main-graph DynamicFloat ASTs, selectors, predicates and HOT config reference are retained. All 19 archived selected DynamicFloat ASTs (16 main plus 3 HOT callback expressions) compile as a separately pinned supplemental IR fixture. Supplemental expressions are not silently attached to an active modifier/execution path. Fixture IR canonical SHA-256: `{ir.stable_hash()}`.
Executable prefix: **PASS**, specifically the first TriggerAbility target and DynamicString operand evaluation; **0 completed top-level tasks**. Full transition: **SEMANTIC_GAP**.
First gap: `{result.gap.task_type}` requires `{result.gap.required_capability}`. Phase02 is present in the catalog; invocation is deliberately not inferred to be synchronous or context-preserving. Supplying a catalog entry alone does not close controller inheritance. No deterministic Natasha post-state/native validation is claimed.

Census v2 inspects {len(receipts)} hash-matching archived graph files only. Known task types: {census['counts']['known_task_types']}; IR-representable: {census['counts']['IR_representable_task_types']} (unknown types retained as UnsupportedSemanticIR); mapped: {census['counts']['mapped_task_types']}; conditionally reference-executable: {census['counts']['reference_executable_task_types']}; oracle-pending: {census['counts']['oracle_pending_task_types']}; unknown task mappings: {census['counts']['unsupported_task_types']}. {len(census['non_executable_task_types'])} types have no reference task execution yet. Actual deduplicated records: {semantic_counts}; DynamicFloat expressions: {expression_counts}. Anonymous bitmap fields in reader-chain archives remain explicitly unbound and blocking even where a type has a registered handler. Serialized references/copies are deduplicated by source coordinates. No claim that 620 skills were structurally decoded. Compiler encounter diagnostics and corpus frequencies remain separate from actual runtime attempts.

Tests: **{test_result.testsRun} PASS**, zero failures/errors. They cover IR/hash isolation, expressions, missing providers, target/predicate dispatch, scheduler resume/order/drain, events, RNG vector/clone/replay, modifiers, rollback on gap, heal core and real graph compilation/prefix. Architecture scan: PASS; no character/skill/name-specific execution branches in CR-owned code. Existing historical selected handlers are untouched and never used by R12.
{regression_note}

Controls: `data/control/generic_behavior_ir_v1_{SUFFIX}.json`, `data/control/generic_runtime_semantic_gap_ledger_{SUFFIX}.json`, `data/control/generic_runtime_support_census_v2_{SUFFIX}.json`. Audit directory: `tmp/audit/r12_runtime_reentry_20261007_001/`.
Production additions: {', '.join(PRODUCTION)}.
Test addition: `{TESTS[0]}`. Audit/reproduction tool: `tools/runtime/r12_runtime_reentry.py`.

Next phase: **R13 GENERIC PRIMITIVE EXPANSION + REAL CONTENT COVERAGE**. Rank gap primitives by actual corpus frequency, implement generic reference policies, re-run coverage, and use native oracle research only for the primitive joins that need it. Do not return automatically to a character-only reverse phase.

Handoff contains only CR-owned additions and manifest, no game payloads or old reverse trees. Its CRC, member sizes and SHA-256 are recorded in the external package receipt to avoid circular hashing. Reproduce controls/tests with repository-resolved Python running `tools/runtime/r12_runtime_reentry.py`; add `--package` for the explicitly requested handoff location.
"""
    (REPO/REPORT_PATH).write_text(report,encoding="utf-8")
    summary={"verdict":"GENERIC_RUNTIME_REENTRY_ESTABLISHED","ir_hash":ir.stable_hash(),
        "census":census["counts"],"tests":test_result.testsRun,"first_gap":result.gap.required_capability}
    write(AUDIT/"summary.json",summary)
    if package:
        package_handoff()
    print(json.dumps(summary,indent=2))


def package_handoff():
    owned=PRODUCTION+TESTS+["tools/runtime/r12_runtime_reentry.py",REPORT_PATH]+[
        f"data/control/{prefix}_{SUFFIX}.json" for prefix in (
            "generic_behavior_ir_v1","generic_runtime_semantic_gap_ledger","generic_runtime_support_census_v2")]
    owned += [p.relative_to(REPO).as_posix() for p in AUDIT.iterdir()
              if p.is_file() and p.name not in {"changed_files_manifest.json","handoff_verification.json"}]
    owned=sorted(set(owned))
    manifest={"change_request":CR,"git_writes":"NONE","files":[
        {"path":p,"bytes":(REPO/p).stat().st_size,"sha256":sha(REPO/p)} for p in owned]}
    write(AUDIT/"changed_files_manifest.json",manifest)
    owned.append((AUDIT/"changed_files_manifest.json").relative_to(REPO).as_posix())
    destination=Path("D:/HSR_Battle_Agent/agent_handoffs")/(CR+"_changed_files.zip")
    if destination.exists():
        raise RuntimeError(f"handoff already exists; refusing to overwrite {destination}")
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for relative in sorted(owned):
            info=zipfile.ZipInfo(relative,date_time=(2026,10,7,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,(REPO/relative).read_bytes())
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        members=[]
        for info in archive.infolist():
            assert archive.read(info.filename)==(REPO/info.filename).read_bytes()
            members.append({"path":info.filename,"bytes":info.file_size,"compressed_bytes":info.compress_size,
                            "crc32":f"{info.CRC:08x}","sha256":hashlib.sha256(archive.read(info.filename)).hexdigest()})
    write(AUDIT/"handoff_verification.json",{"path":str(destination),"sha256":sha(destination),
        "bytes":destination.stat().st_size,"CRC":"PASS","members":members,"member_count":len(members)})


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--package",action="store_true")
    args=parser.parse_args()
    main(args.package)
