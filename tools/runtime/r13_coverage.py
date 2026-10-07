"""Reproducible R13 coverage audit; no Git mutation or live runtime access."""
from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import subprocess
import sys
import copy
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from r12_runtime_reentry import ARCHIVED_DECODER_ROLES, walk_dicts, source_authority

SUFFIX = "20261007_001"
AUDIT = REPO / "tmp/audit/r13_generic_coverage_20261007_001"
CR = "CR-R13-GENERIC-PRIMITIVE-COVERAGE-20261007-001"


def read(path):
    return json.loads((REPO / path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")


def freeze():
    destination = AUDIT / "start_gate.json"
    if destination.exists():
        return
    git = lambda *args: subprocess.run(["git", *args], cwd=REPO, text=True,
                                      capture_output=True, check=True).stdout.strip()
    hashes = {}
    for directory in ("src", "tests", "data/control", "docs/agent", "tools/runtime"):
        for path in (REPO / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                hashes[path.relative_to(REPO).as_posix()] = sha(path)
    controls = {key: read(f"data/control/{key}_{SUFFIX}.json") for key in (
        "generic_behavior_ir_v1", "generic_runtime_semantic_gap_ledger",
        "generic_runtime_support_census_v2")}
    write(destination, {"HEAD": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
        "status": git("status", "--short"), "preexisting_hashes": hashes,
        "R12_present": True, "git_writes": "NONE"})
    write(AUDIT / "baseline_controls.json", controls)


def inspect():
    from hsr_battle_agent.battle_ir.behavior_binding import BehaviorCompiler
    census = read(f"data/control/generic_runtime_support_census_v2_{SUFFIX}.json")
    ledger = read(f"data/control/real_runtime_generic_primitive_ledger_{SUFFIX}.json")
    print("BASELINE", census["counts"], census["decoded_semantic_instance_counts"])
    for family in ("target", "predicate", "task"):
        print(family, [(r["type"].split(".")[-1], r["decoded_instances"], r["field_bindings_unresolved_instances"])
                       for r in sorted(census["types"], key=lambda r: -r["decoded_instances"]) if r["family"] == family])
    samples = {}
    for source in census["actual_corpus"]:
        binder = BehaviorCompiler(source_authority(source["path"], source["sha256"]), ledger, ARCHIVED_DECODER_ROLES)
        graph = read(source["path"])
        print("SOURCE", source["path"], "ROOT", list(graph)[:15] if isinstance(graph, dict) else f"list {len(graph)}")
        for pointer, record in walk_dicts(graph):
            normal = binder.normalize_record(record)
            if normal:
                identity = normal["concrete_type"]
                if identity not in samples:
                    samples[identity] = {"source": source["path"], "pointer": pointer, "normalized": normal}
    write(AUDIT / "decoded_type_samples.json", samples)
    for identity, sample in sorted(samples.items()):
        structure = sample["normalized"].get("structure", {})
        print(identity, "FIELDS", [(f.get("field", f.get("mask", f.get("bit"))),
            [(v.get("type", v.get("concrete_type", v.get("kind"))), v.get("value"), v.get("count"))
             if isinstance(v, dict) else v for v in f.get("values", [])]) for f in structure.get("fields", [])])


def baseline_registry():
    from hsr_battle_agent.battle_runtime.behavior import SemanticRegistry, _tasks, _targets, _predicate, _expression, _event
    contract = read(AUDIT.relative_to(REPO) / "baseline_controls.json")["generic_behavior_ir_v1"]
    registry = SemanticRegistry()
    for family, key, handler in (("target", "target_operations", _targets), ("predicate", "predicate_operations", _predicate),
                                  ("expression", "expression_operations", _expression)):
        for operation in contract[key]:
            if operation != "unknown_opcode":
                registry.register(family, operation, handler)
    for operation in ("RPG.GameCore.PredicateTaskList", "RPG.GameCore.TriggerAbility", "RPG.GameCore.SetDynamicValue", "RPG.GameCore.HealHP",
        "dynamic_write", "property_write", "resource_write", "modifier_apply", "modifier_remove", "random_choice", "barrier", "schedule", "completion", "event_dispatch"):
        registry.register("task", operation, _tasks)
    registry.register("event", "event_dispatch", _event)
    assert registry.identity() == contract["registry_identity"]
    return registry


def source_roots(path, document, binder):
    from hsr_battle_agent.battle_ir.behavior import IRNode
    result = []
    if isinstance(document, dict) and document.get("schema") == "real_runtime_4651_structural_graph/1":
        graph = binder.compile_graph(document)
        for ability in graph.payload["abilities"]:
            result.append((ability.payload["content_name"], "RPG.GameCore.TurnBasedAbilityConfig", ability, None))
    elif isinstance(document, dict) and any(isinstance(v, dict) and "task_list" in v for v in document.values()):
        graph = binder.compile_graph(document)
        result.extend((a.payload["content_name"], "RPG.GameCore.TurnBasedAbilityConfig", a, None) for a in graph.payload["abilities"])
    elif isinstance(document, dict) and "certified_empty_readers" in document:
        for i, entry in enumerate(document["entries"]):
            identity = entry["key"].get("value")
            ir = binder.convert(entry["value"], f"/entries/{i}/value")
            result.append((identity, "TargetAliasGraph", ir, entry["value"].get("start")))
    else:
        entries = document if isinstance(document, list) else document.get("accepted", document.get("entries", []))
        for i, entry in enumerate(entries):
            if "graph" not in entry or entry.get("status") == "PARTIAL_DECODE":
                continue
            graph = entry["graph"]
            identity = entry.get("identity", entry.get("name"))
            ir = binder.compile_record(graph, f"/records/{i}", identity)
            result.append((identity, graph.get("type"), ir, graph.get("start")))
    return result


def batch():
    from hsr_battle_agent.battle_ir.behavior import IRNode, walk_nodes
    from hsr_battle_agent.battle_ir.behavior_binding import BehaviorCompiler
    from hsr_battle_agent.battle_ir.behavior_expansion_binding import ExpansionCompiler, EXPANSION_TASK_MAPPINGS
    from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime, ExecutionStatus, GapError, default_registry
    from hsr_battle_agent.battle_runtime.behavior_expansion import TASK_OPERATIONS
    from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
    from hsr_battle_agent.battle_runtime.behavior_state import ModifierInstance
    from r13_reference_fixtures import fixture
    baseline = read(AUDIT.relative_to(REPO) / "baseline_controls.json")["generic_runtime_support_census_v2"]
    ledger = read(f"data/control/real_runtime_generic_primitive_ledger_{SUFFIX}.json")
    baseline_engine = baseline_registry()
    from r13_frozen_reader import expand
    expansion = expand()
    expanded_path = AUDIT / "expanded_decoded_records.json"
    write(expanded_path, expansion)
    sources = copy.deepcopy(baseline["actual_corpus"])
    sources.append({"path": expanded_path.relative_to(REPO).as_posix(), "sha256": sha(expanded_path),
                    "bytes": expanded_path.stat().st_size, "source": "FROZEN_SCHEMA_BATCH_DECODE", "verified": True})
    compiled_roots, node_records, seen_raw, alias_names, lookup_keys = [], [], set(), set(), set()
    seen_roots = set()
    for source_index, source in enumerate(sources):
        path = source["path"]
        if sha(REPO/path) != source["sha256"]:
            raise RuntimeError("source pin drift:" + path)
        document = read(path)
        compiler = ExpansionCompiler(source_authority(path, source["sha256"]), ledger, ARCHIVED_DECODER_ROLES)
        old_compiler = BehaviorCompiler(source_authority(path, source["sha256"]), ledger, ARCHIVED_DECODER_ROLES)
        roots = source_roots(path, document, compiler)
        for identity, root_type, ir, start in roots:
            key = (identity, root_type)
            if key in seen_roots:
                continue
            seen_roots.add(key)
            restored = IRNode.from_dict(json.loads(ir.canonical_json()))
            if restored != ir or restored.stable_hash() != ir.stable_hash():
                raise RuntimeError("IR round trip changed")
            compiled_roots.append({"source": source, "identity": identity, "root_type": root_type,
                "ir": ir, "start": start, "baseline": source_index < len(sources)-1})
        seen = set()
        for pointer, record in walk_dicts(document):
            normalized = compiler.normalize_record(record)
            if normalized is not None:
                config_type = normalized.get("concrete_type")
                if not isinstance(config_type, str):
                    continue
                kind = normalized["kind"]
                coordinate = (kind, config_type, normalized.get("start"), normalized.get("end"))
                if coordinate[2] is None:
                    coordinate += (pointer,)
                structure = normalized.get("structure", {})
                raw_coordinate = (config_type, structure.get("start", normalized.get("start")), normalized.get("end"))
                family = {"TaskConfig": "task", "TargetSelector": "target", "PredicateConfig": "predicate"}[kind]
                if coordinate in seen:
                    continue
                seen.add(coordinate)
                if source_index == len(sources)-1 and raw_coordinate in seen_raw:
                    continue
                seen_raw.add(raw_coordinate)
                new_node, old_node = compiler.convert(record, pointer), old_compiler.convert(record, pointer)
                node_records.append({"family": family, "type": config_type, "source": path, "pointer": pointer,
                    "node": new_node, "old_node": old_node, "baseline": source_index < len(sources)-1})
                for node in walk_nodes(new_node):
                    if node.op == "RPG.GameCore.TargetAlias":
                        alias_names.add(node.payload.get("alias"))
                    if node.op == "lookup":
                        lookup_keys.add(node.payload["key"])
            if record.get("type") == "RPG.GameCore.DynamicFloat" and "tag" in record:
                coordinate = ("expression", record.get("start"), record.get("end"))
                if coordinate in seen:
                    continue
                seen.add(coordinate)
                raw_coordinate = ("RPG.GameCore.DynamicFloat", record.get("start"), record.get("end"))
                if source_index == len(sources)-1 and raw_coordinate in seen_raw:
                    continue
                seen_raw.add(raw_coordinate)
                node = compiler.convert(record, pointer)
                node_records.append({"family": "expression", "type": "RPG.GameCore.DynamicFloat", "source": path,
                    "pointer": pointer, "node": node, "old_node": old_compiler.convert(record, pointer),
                    "baseline": source_index < len(sources)-1})
                for child in walk_nodes(node):
                    if child.op == "lookup":
                        lookup_keys.add(child.payload["key"])
    state, aliases, reference_policies = fixture(alias_names, lookup_keys)
    catalog = {r["identity"]: r["ir"] for r in compiled_roots if r["root_type"] == "RPG.GameCore.TurnBasedAbilityConfig"}
    fixture_receipt = {"classification": "SYNTHETIC_EXPLICIT_PRIMITIVE_PROBE", "legal_battle_execution": False,
        "alias_authority": "CONFIGURED_REFERENCE_ALIAS", "native_effective_alias": "UNAVAILABLE",
        "description": "Two synthetic entities, explicit ordered relations/category/enum policies; aliases are caller reference bindings, not native winners",
        "state": state.snapshot(), "aliases": {k: v.to_dict() for k, v in aliases.items()}, "policies": reference_policies}
    write(AUDIT / "reference_fixture.json", fixture_receipt)
    outcomes = []
    for row in node_records:
        record = {k: v for k, v in row.items() if k not in ("node", "old_node")}
        record["node_hash"] = row["node"].stable_hash()
        for mode, registry, node, policies in (("before", baseline_engine, row["old_node"], {}),
                                               ("after", default_registry(), row["node"], reference_policies)):
            runtime = BehaviorRuntime(state, abilities=catalog, aliases=aliases, policies=policies, registry=registry)
            root_policy = runtime.policies.get("r13_reference_v1", {})
            if mode == "after" and node.op == "RPG.GameCore.SetDynamicValue":
                root_policy["dynamic_providers"][node.node_id] = "supplied"
            if mode == "after" and node.op == "RPG.GameCore.AddModifier":
                f = node.payload["fields"]
                role = node.payload.get("reference_binding", {}).get("roles", {})
                selector, name = f.get("TargetType", role.get("target")), f.get("ModifierName", role.get("modifier"))
                try:
                    targets = runtime.select(selector) if selector else []
                    identity = runtime.evaluate(name) if name else None
                    if len(targets) == 1 and isinstance(identity, str):
                        duration = {}
                        if "LifeTime" in f:
                            duration["serialized_lifetime_raw"] = runtime.evaluate(f["LifeTime"])
                        instance = ModifierInstance("probe:" + node.node_id, identity, targets[0], "a", "a", 1, 1, duration)
                        if "DynamicValues" in f:
                            from hsr_battle_agent.battle_runtime.behavior_expansion import dynamic_dictionary
                            instance.dynamic_values = dynamic_dictionary(runtime, node, runtime.state, f["DynamicValues"])
                        root_policy["modifiers"]["applications"][node.node_id] = {"operation": "INSERT_NEW_REFERENCE", "instance": asdict(instance)}
                except GapError:
                    pass
            if mode == "after" and node.op == "RPG.GameCore.HealHP":
                # Inputs are explicit synthetic reference operands, never recovered effective HealData.
                root_policy["heal_inputs"][node.node_id] = {"formula": "FORMULA_TYPE2_REFERENCE", "settlement": "CLAMP_HP_REFERENCE",
                    "operands": {"d50": 2*SCALE, "d28": SCALE, "d60": 0, "dD0": 0, "d38": 0, "d128": 0, "d48": 100*SCALE, "dD8": 0},
                    "cap_enabled": False, "hooks": {key: "EXPLICIT_EMPTY_REFERENCE" for key in (
                        "pre_heal_hooks", "effective_amount_modifiers", "settlement", "property_mutation_hooks", "post_heal_hooks", "resource_listeners")}}
            if row["family"] == "task" and node.kind == "UnsupportedSemanticIR":
                record[mode] = {"status": "SEMANTIC_GAP", "capability": node.payload["required_capability"]}
                continue
            try:
                result = runtime.registry.invoke(row["family"], runtime, node, runtime.state)
                record[mode] = {"status": "PASS", "semantic_authority": "REFERENCE_MODEL"}
            except GapError as exc:
                record[mode] = {"status": "SEMANTIC_GAP", "capability": exc.gap.required_capability,
                                "gap_node_id": exc.gap.node["node_id"], "gap_evidence": exc.gap.evidence,
                                "gap_primitive": exc.gap.task_type, "gap_span": exc.gap.node["payload"].get("span")}
        outcomes.append(record)
    write(AUDIT / "primitive_probe_receipts.json", outcomes)
    before_outcomes = [r for r in outcomes if r["baseline"]]
    def metrics(rows, mode):
        weighted = {}
        for family in ("task", "target", "predicate", "expression"):
            values = [r for r in rows if r["family"] == family]
            supported = sum(r[mode]["status"] == "PASS" for r in values)
            weighted[family] = {"supported": supported, "total": len(values), "fraction": supported / len(values) if values else 0,
                               "supported_types": len({r["type"] for r in values if r[mode]["status"] == "PASS"}),
                               "known_types": len({r["type"] for r in values})}
        return weighted
    measured = {"before": metrics(before_outcomes, "before"), "after_same_corpus": metrics(before_outcomes, "after"),
                "after_expanded_corpus": metrics(outcomes, "after"),
                "measurement": "Actual isolated primitive invocation with explicit synthetic inputs; children returned by tasks are not claimed executed"}
    iteration = "coverage_iteration_1.json" if not (AUDIT / "coverage_iteration_1.json").exists() else "coverage_iteration_2.json"
    write(AUDIT / iteration, measured)
    root_rows, first_gaps = [], collections.Counter()
    for root in compiled_roots:
        ir = root["ir"]
        nodes = list({n.stable_hash(): n for n in walk_nodes(ir)}.values())
        counts = {family: dict(collections.Counter(n.op for n in nodes if n.kind == kind))
                  for family, kind in (("task", "TaskIR"), ("predicate", "PredicateIR"), ("target", "TargetSelectorIR"))}
        expressions = sum(n.payload.get("serialized_type") == "RPG.GameCore.DynamicFloat" for n in nodes)
        row = {"source_version": "4.6.51", "source_artifact": root["source"]["path"], "source_artifact_sha256": root["source"]["sha256"],
            "source_shard": expansion["source_shard"]["relative_path"], "source_shard_sha256": expansion["source_shard"]["sha256"],
            "record_identity": root["identity"], "root_type": root["root_type"], "start": root["start"],
            "canonical_graph_hash": ir.stable_hash(), "task_types": counts["task"], "target_types": counts["target"],
            "predicate_types": counts["predicate"], "expression_count": expressions,
            "compile_status": "PASS_WITH_STRUCTURE_ONLY_NODES" if any(n.kind == "UnsupportedSemanticIR" or n.authority.semantic_status == "STRUCTURE_ONLY" for n in nodes) else "PASS",
            "baseline_record": root["baseline"], "execution_scope": "SYNTHETIC_EXPLICIT_REFERENCE_FIXTURE"}
        runtime = BehaviorRuntime(state, abilities=catalog, aliases=aliases, policies=reference_policies)
        runtime.state.target_context["current_ability"] = root["identity"]
        if ir.op == "structure_record":
            row["execution_status"] = "SEMANTIC_GAP"
            row["first_SemanticGap"] = "modifier/event root installation and callback lifecycle policy"
            row["completed_top_level_tasks"] = 0
        elif ir.kind == "TargetSelectorIR":
            try:
                runtime.select(ir)
                row.update(execution_status="COMPLETED", first_SemanticGap=None, completed_top_level_tasks=0)
            except GapError as exc:
                row.update(execution_status="SEMANTIC_GAP", first_SemanticGap=exc.gap.required_capability, completed_top_level_tasks=0)
        else:
            runtime.actions["probe"] = ir
            result = runtime.step("probe")
            top = {n.node_id for n in ir.payload["tasks"].payload["tasks"]}
            pending_calls = {frame.get("parent_node") for frame in runtime.state.mechanics.get("reference_invocations", [])}
            row.update(execution_status=result.status.value,
                first_SemanticGap=result.gap.required_capability if result.gap else None,
                accepted_top_level_primitives=sum(t["node"] in top for t in result.trace),
                completed_top_level_tasks=sum(t["node"] in top and t["node"] not in pending_calls for t in result.trace),
                reached_nested_tasks=sum(t["node"] not in top and t["op"] in runtime.registry.handlers["task"] for t in result.trace)
                    + int(result.gap is not None and result.gap.node["node_id"] not in top and result.gap.task_type in runtime.registry.handlers["task"]))
        if row["first_SemanticGap"]:
            first_gaps[row["first_SemanticGap"]] += 1
        root_rows.append(row)
    distribution = collections.Counter(r["after"]["capability"] for r in outcomes if r["after"]["status"] != "PASS")
    tasks = sorted({r["type"] for r in outcomes if r["family"] == "task"})
    mapped = [t for t in tasks if t.rsplit(".", 1)[-1] in EXPANSION_TASK_MAPPINGS]
    executable = [t for t in tasks if t.rsplit(".", 1)[-1] in TASK_OPERATIONS]
    type_rows = []
    for family, identity in sorted({(r["family"], r["type"]) for r in outcomes}):
        rows = [r for r in outcomes if (r["family"], r["type"]) == (family, identity)]
        type_rows.append({"family": family, "type": identity, "decoded_instances": len(rows),
            "reference_probe_pass_instances": sum(r["after"]["status"] == "PASS" for r in rows),
            "reference_handler_registered": identity in default_registry().handlers[family] if family != "expression" else True,
            "oracle_pending": True, "sources": sorted({r["source"] for r in rows})})
    census = {"schema": "generic_runtime_support_census/3", "change_request": CR, "actual_corpus": sources,
        "counts": {"known_task_types": len(tasks), "mapped_task_types": len(mapped), "reference_executable_task_types": len(executable),
                   "unsupported_task_types": len(tasks)-len(mapped), "oracle_pending_task_types": len(tasks)},
        "known_task_types": tasks, "mapped_task_types": mapped, "reference_executable_task_types": executable,
        "unsupported_task_types": [t for t in tasks if t not in mapped], "types": type_rows, "coverage": measured,
        "decoded_semantic_instance_counts": {family: sum(r["family"] == family for r in outcomes) for family in ("task", "target", "predicate")},
        "reference_executable_definition": "Implemented conditional reference policies; unresolved inputs may still block an instance. Probe success reported separately.",
        "corpus_gap_frequency": dict(distribution.most_common()), "first_gap_distribution": dict(first_gaps.most_common()),
        "native_validated_task_types": [], "fully_decoded_skill_count_claimed": False}
    write(REPO / f"data/control/generic_runtime_support_census_v3_{SUFFIX}.json", census)
    root_counts = collections.Counter(r["root_type"] for r in root_rows)
    corpus = {"schema": "generic_runtime_real_content_corpus/1", "change_request": CR,
        "baseline_archived_graph_bundles": 4, "expanded_archived_graph_bundles": len(sources),
        "decoded_behavior_graphs": len(root_rows), "baseline_decoded_behavior_graphs": sum(r["baseline_record"] for r in root_rows),
        "ability_config_records": root_counts["RPG.GameCore.TurnBasedAbilityConfig"],
        "modifier_graphs": root_counts["RPG.GameCore.TurnBasedModifierConfig"], "alias_graphs": root_counts["TargetAliasGraph"],
        "skills_with_proven_owner_root_join": 1, "executable_skill_count_claimed": False,
        "structural_corpus_gaps": expansion["structural_gaps"], "graphs": root_rows,
        "count_policy": "Archived bundles and distinct identity/root-type graphs reported separately; baseline partial root bodies excluded; decoded primitive spans remain counted"}
    write(REPO / f"data/control/generic_runtime_real_content_corpus_v1_{SUFFIX}.json", corpus)
    baseline_frequencies = collections.Counter(r["type"] for r in before_outcomes if r["before"]["status"] != "PASS")
    rankings = []
    for identity, frequency in baseline_frequencies.items():
        short = identity.rsplit(".", 1)[-1]
        family = next(r["family"] for r in before_outcomes if r["type"] == identity)
        fan_out = 5 if short in ("TargetSequence", "TargetConcat", "PredicateTaskList") else 3 if family in ("target", "predicate") else 2
        affected_nodes = [r["node"] for r in node_records if r["baseline"] and r["type"] == identity]
        observed_children = [len({n.stable_hash() for n in walk_nodes(node)}) - 1 for node in affected_nodes]
        average_children = sum(observed_children) / len(observed_children) if observed_children else 0
        fan_out = max(fan_out, 1 + average_children)
        confidence = 0.9 if short in ("TargetSequence", "TargetConcat", "ByAnd", "ByNot", "ByCharacterDamageType") else 0.65
        risk = 0.7 if short in ("AddModifier", "IncludeTaskListTemplate", "ModifySPNew") else 0.25
        sources_affected = sorted({r["source"] for r in before_outcomes if r["type"] == identity})
        total_frequency = sum(r["type"] == identity for r in before_outcomes)
        rankings.append({"primitive": identity, "corpus_frequency": total_frequency, "baseline_gap_instances": frequency, "downstream_fan_out": fan_out,
            "enables_other_nodes": fan_out > 2, "implementation_confidence": confidence, "invented_semantics_risk": risk,
            "existing_evidence": "Hash-pinned decoded structures / archived reader and primitive ledger references; native runtime policy unresolved",
            "score": round(total_frequency*fan_out*confidence*(1-risk), 3), "affected_corpus_sources": sources_affected,
            "observed_mean_descendant_nodes": average_children,
            "rationale": "Frequency x downstream fan-out x reference implementation confidence x (1 - invented-semantics risk)"})
    rankings.sort(key=lambda r: (-r["score"], r["primitive"]))
    gaps = []
    for capability, frequency in distribution.most_common():
        affected = [r for r in outcomes if r["after"].get("capability") == capability]
        gaps.append({"status": "RUNTIME_ORACLE_PENDING", "required_capability": capability, "frequency": frequency,
            "frequency_scope": "Failed primitive probes including downstream propagation",
            "distinct_originating_gap_instances": len({(r["after"].get("gap_primitive"), r["after"].get("gap_evidence", {}).get("source_artifact"),
                tuple(r["after"].get("gap_span") or [r["after"].get("gap_node_id")])) for r in affected}),
            "affected_primitives": sorted({r["type"] for r in affected}), "affected_corpus_graphs": sorted({r["source"] for r in affected}),
            "minimum_oracle_evidence": "One bounded trace proving exact field/enum/context/lifecycle behavior for this generic operation; or existing exact reader schema for structural gaps",
            "decoded_node_references": [{"source": r["source"], "pointer": r["pointer"], "gap_node": r["after"].get("gap_node_id"),
                                         "gap_evidence": r["after"].get("gap_evidence")} for r in affected],
            "observation_stage": "ISOLATED_PRIMITIVE_REFERENCE_PROBE", "blocking": True, "compilation_blocking": False})
    gap_control = {"schema": "generic_runtime_semantic_gap_ledger/2", "change_request": CR, "baseline_rankings": rankings,
        "corpus_gaps": gaps, "first_gap_distribution": dict(first_gaps.most_common()), "structural_corpus_gaps": expansion["structural_gaps"],
        "frequency_policy": "One probe per distinct decoded coordinate; gaps from failed whole graphs counted separately",
        "native_correct_claimed": False}
    write(REPO / f"data/control/generic_runtime_semantic_gap_ledger_v2_{SUFFIX}.json", gap_control)
    summary = {"baseline_counts": baseline["counts"], "expanded_counts": census["counts"], "coverage": measured,
        "corpus": {k: v for k, v in corpus.items() if k not in ("graphs", "structural_corpus_gaps")},
        "top_gaps": distribution.most_common(12), "top_rankings": rankings[:12],
        "natasha": [r for r in root_rows if r["record_identity"] and "Skill02_Phase" in r["record_identity"]],
        "structural_gap_count": len(expansion["structural_gaps"])}
    write(AUDIT / "summary.json", summary)
    print(json.dumps({"coverage": measured, "counts": census["counts"], "corpus": summary["corpus"], "top_gaps": distribution.most_common(12)}, indent=2))


if __name__ == "__main__":
    freeze()
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    inspect() if args.inspect else batch()
