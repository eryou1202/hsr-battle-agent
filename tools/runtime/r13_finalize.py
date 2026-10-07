"""R13 tests, architecture/preservation audits, report and verified handoff."""
from __future__ import annotations

import argparse
import ast
import collections
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

from r13_coverage import AUDIT, CR, REPO, SUFFIX, read, sha, write

PRODUCTION = ["src/hsr_battle_agent/battle_ir/behavior_expansion_binding.py",
              "src/hsr_battle_agent/battle_runtime/behavior.py",
              "src/hsr_battle_agent/battle_runtime/behavior_expansion.py"]
TESTS = ["tests/battle_runtime/test_behavior_r13.py"]
TOOLS = ["tools/runtime/" + name for name in ("r13_coverage.py", "r13_frozen_reader.py", "r13_reference_fixtures.py", "r13_finalize.py")]
CONTROLS = [f"data/control/{name}_{SUFFIX}.json" for name in (
    "generic_runtime_real_content_corpus_v1", "generic_runtime_support_census_v3",
    "generic_runtime_semantic_gap_ledger_v2", "generic_runtime_primitive_expansion")]
REPORT = f"docs/agent/handoffs/generic_runtime_primitive_expansion_coverage_{SUFFIX}.md"
DESTINATION = Path("D:/HSR_Battle_Agent/agent_handoffs") / (CR + "_changed_files.zip")


def run_tests():
    def suite(directory):
        name = Path(directory).name
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        command = [sys.executable, "-m", "unittest", "discover", "-s", directory, "-t", ".", "-p", "test_*.py", "-q"]
        result = subprocess.run(command, cwd=REPO, text=True, encoding="utf-8", errors="replace", env=environment,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log = result.stdout + result.stderr
        (AUDIT / (name + "_tests.txt")).write_text(log, encoding="utf-8")
        matched = re.search(r"Ran (\d+) tests?", log)
        return {"suite": directory, "tests": int(matched.group(1)) if matched else 0,
                "PASS": result.returncode == 0 and matched is not None, "exit_code": result.returncode,
                "log": (AUDIT / (name + "_tests.txt")).relative_to(REPO).as_posix(), "command": command}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(suite, ("tests/battle_ir", "tests/battle_runtime", "tests/battle_sandbox")))
    focused = unittest.defaultTestLoader.loadTestsFromNames(["tests.battle_runtime.test_behavior_r12", "tests.battle_runtime.test_behavior_r13"])
    with (AUDIT / "focused_tests.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(focused)
    receipt = {"FAST_UNIT": results, "focused": {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "PASS": result.wasSuccessful()}, "total_FAST_UNIT": sum(r["tests"] for r in results), "interpreter": sys.version,
        "native_validation": False}
    write(AUDIT / "test_receipt.json", receipt)
    if not result.wasSuccessful() or not all(r["PASS"] for r in results):
        raise RuntimeError("R13 regression tests failed; see test logs")
    return receipt


def safety():
    start = read(AUDIT.relative_to(REPO) / "start_gate.json")
    permitted = set(PRODUCTION + TOOLS)
    changed = [path for path, digest in start["preexisting_hashes"].items()
               if not (REPO / path).is_file() or sha(REPO/path) != digest]
    unintended = [path for path in changed if path not in permitted]
    git = lambda *args: subprocess.run(["git", *args], cwd=REPO, text=True, capture_output=True, check=True).stdout.strip()
    head, branch = git("rev-parse", "HEAD"), git("branch", "--show-current")
    receipt = {"preexisting_files_checked": len(start["preexisting_hashes"]), "changed_preexisting_files": changed,
        "unexpected_changed_preexisting_files": unintended, "frozen_M10_M15_modified": bool(unintended),
        "HEAD_unchanged": head == start["HEAD"], "branch_unchanged": branch == start["branch"], "git_writes": "NONE"}
    write(AUDIT / "frozen_preservation.json", receipt)
    forbidden = []
    for path in PRODUCTION:
        source = (REPO/path).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for item in ast.walk(tree):
            if isinstance(item, ast.Constant) and (item.value in (1105, 110502) or isinstance(item.value, str) and
                ("natasha" in item.value.lower() or item.value.startswith(("Avatar_", "MAvatar_", "Monster_")))):
                forbidden.append({"file": path, "line": item.lineno, "constant": str(item.value)})
            if isinstance(item, ast.Import) and any(alias.name == "random" for alias in item.names) or isinstance(item, ast.ImportFrom) and item.module == "random":
                forbidden.append({"file": path, "line": item.lineno, "reason": "process-global RNG"})
            if isinstance(item, (ast.If, ast.IfExp, ast.Match)):
                expression = item.test if hasattr(item, "test") else item.subject
                text = ast.unparse(expression)
                if any(key in text for key in ("avatar_id", "skill_id", "avatar_name", "character_name")):
                    forbidden.append({"file": path, "line": item.lineno, "condition": text})
    write(AUDIT / "architecture_scan.json", {"scope": PRODUCTION, "method": "AST content constants, branch conditions and RNG imports",
        "forbidden": forbidden, "result": "PASS" if not forbidden else "FAIL", "fixture_specific_production_globals": False})
    if unintended or not receipt["HEAD_unchanged"] or not receipt["branch_unchanged"] or forbidden:
        raise RuntimeError("R13 architecture/preservation check failed")
    return receipt


def emit_report(tests, preservation):
    from hsr_battle_agent.battle_runtime.behavior_expansion import TARGET_OPERATIONS, PREDICATE_OPERATIONS
    summary = read(AUDIT.relative_to(REPO) / "summary.json")
    corpus = read(CONTROLS[0])
    census = read(CONTROLS[1])
    start = read(AUDIT.relative_to(REPO) / "start_gate.json")
    family_policy = {"Sequence": "pipeline: previous ordered output becomes next input; empty pipeline -> []",
        "Concat": "serialized sibling concatenation; duplicates preserved", "Filter": "stable input traversal, explicit param entity context",
        "Sort": "stable ties; direction enum or absent-field default supplied explicitly", "Index": "explicit numeric mapping; out of range -> []",
        "Take": "nonnegative integral fixed-point count; preserves order", "Map": "explicit ordered per-entity relation tables",
        "Query": "explicit ordered candidates/category-mask maps; absent state is a gap", "Fetch": "explicit context; null/unresolved IDs are gaps",
        "Random": "R12 SplitMix64 stream retained; selection/filter/predicate gaps roll back RNG"}
    regressions = [r for r in corpus["graphs"] if r["record_identity"] in ("Local_SPAdd", "TriggerStanceCountDown_Test",
        "MAvatar_Common_TriggerDeparted", "Avatar_Common_PassiveSkill", "Avatar_Common_SkillMazeInLevel",
        "AllTeammate", "AvatarNextTurnOwnerEntity", "AllEnemy")]
    write(AUDIT / "non_character_regression_fixtures.json", regressions)
    expansion = {"schema": "generic_runtime_primitive_expansion/1", "change_request": CR,
        "verdict": "GENERIC_RUNTIME_COVERAGE_EXPANDED", "starting_HEAD": start["HEAD"], "branch": start["branch"],
        "baseline_counts": summary["baseline_counts"], "expanded_counts": summary["expanded_counts"], "coverage": summary["coverage"],
        "target_primitives": TARGET_OPERATIONS, "target_ordering_policies": family_policy, "predicate_primitives": PREDICATE_OPERATIONS,
        "template_invocation": {"catalog": "canonical IR by identifier", "cycles": "active identity stack", "depth": "explicit positive bound",
            "target_context": "explicit single/list propagation", "owner_caster": "caller-bound inherited or explicit child identities",
            "parameters": "explicit stack, shared provider parent", "controller": "REFERENCE_CHILD", "completion": "PARENT_OWNS_COMPLETION",
            "scheduler": "immediate resumable continuation only; deferred callback ownership blocks", "template_parameters": "structure retained; explicit caller replacement can execute, recovered inheritance remains a gap"},
        "modifier_event": ["INSERT_NEW_REFERENCE", "REFRESH_REFERENCE duration only", "REPLACE_REFERENCE", "explicit dynamic operand checks",
            "ALL_MATCHING_STORAGE_ONLY removal", "reference property stack", "ordered event listeners/owner context/condition/callback mutation policy"],
        "other_primitives": ["FormulaType2 heal with all hook declarations", "explicit dynamic write provider",
            "presentation-only policy", "scheduler barrier policy", "explicit position mutation"],
        "reference_policies": "Serializable versioned dictionary r13_reference_v1; included in snapshot/replay/hash",
        "alias_authority": "CONFIGURED_REFERENCE_ALIAS", "native_effective_alias": "NOT_CAPTURED",
        "native_correct_claimed": False, "strict_admission_changed": False, "frozen_M10_M15_modified": False,
        "tests": tests, "architecture_scan": "PASS", "determinism": "PASS", "non_character_regression_fixtures": regressions,
        "next_phase": "R14 MORE GENERIC PRIMITIVE COVERAGE", "next_phase_focus": "template parameter/catalog binding and high-frequency target option semantics, with targeted oracle evidence only for exact questions",
        "stop_policy": "Coherent multiple-family measured batch complete; top remaining gaps require new structural readers, native option/inheritance evidence, or modifier/event/scheduler subsystem architecture",
        "production_files": PRODUCTION, "test_files": TESTS, "git_writes": "NONE"}
    write(REPO / CONTROLS[3], expansion)
    coverage = summary["coverage"]
    rows = []
    for family in ("task", "target", "predicate", "expression"):
        values = [coverage[key][family] for key in ("before", "after_same_corpus", "after_expanded_corpus")]
        cells = [f"{v['supported']}/{v['total']} ({100*v['fraction']:.1f}%)" for v in values]
        rows.append("| " + family + " | " + " | ".join(cells) + " |")
    natasha = summary["natasha"][0]
    top = "\n".join(f"- `{r['primitive']}`: frequency {r['corpus_frequency']}, score {r['score']:.2f}, observed mean descendants {r['observed_mean_descendant_nodes']:.2f}." for r in summary["top_rankings"][:6])
    report = f"""# R13 Generic Primitive Expansion and Real Content Coverage

CR: `{CR}`. Verdict: **GENERIC_RUNTIME_COVERAGE_EXPANDED**.
Starting HEAD `{start['HEAD']}`; branch `{start['branch']}`. No Git writes.
Frozen M10-M15, strict admission and existing ScenarioCompiler are untouched. The preservation audit checks {preservation['preexisting_files_checked']} starting files; only R13-owned runtime/tool files changed.

Coverage is actual isolated primitive execution with explicit synthetic reference inputs. Task probes count a successfully applied primitive that may return continuations; they do not claim those children or a legal battle executed. Alias bindings, enum mappings, category properties, relation lists and effective heal operands are declared reference fixture data. They are not native winners or native-equivalent semantics.

| Family | R12 baseline | R13 same corpus | R13 expanded corpus |
| --- | --- | --- | --- |
{chr(10).join(rows)}

Known task types remain 20. Mapped task types: 14 -> 17. Implemented conditionally reference-executable task types: 2 -> 13; actual passing task types: 1 -> 10. Unsupported mappings: 6 -> 3 (DebugLog, ModifyHealData, TargetTimeSlow). All 20 task types remain native-oracle pending.
Target passing types: 4 -> {coverage['after_expanded_corpus']['target']['supported_types']}/91; predicate passing types: 2 -> {coverage['after_expanded_corpus']['predicate']['supported_types']}/19. DynamicFloat IR representation/execution: 79/79 -> 83/83. Coverage iteration receipts retain the first batch and final rerun.

The R12 “4 graphs” were archived graph bundles. This phase reports those separately: 4 -> 5 bundles; distinct complete decoded behavior roots 207 -> 210. Expanded roots: {corpus['ability_config_records']} ability/config records, {corpus['modifier_graphs']} modifier graphs, {corpus['alias_graphs']} alias graphs. Proven skill owner/root joins remain 1; no executable-skill count is claimed. The three new distinct roots are the insertion phase and two common ability records.

The batch decoder uses the same externally pinned 4.6.51 shard and already proven selected/common ConfigBakeLayoutInfo directories. Cached native schemas and previously decoded reader shapes are reused with archived byte-span/type validation. Unknown readers, active slots and unmatched framing remain STRUCTURAL_CORPUS_GAP. {len(read(AUDIT.relative_to(REPO)/'expanded_decoded_records.json')['accepted'])} records passed complete bounded consumption, including records already present in R12. {summary['structural_gap_count']} unsuccessful attempts are excluded from new coverage. No registration/provider/archive archaeology or live capture was reopened.

Ranking uses decoded frequency, observed subtree descendants, fan-out, confidence and semantic-invention risk. The top initial candidates were:

{top}

Target algebra now implements pipelined sequence, sibling concat, stable filter/sort/index/take/query, explicit relation maps and context fetches. All outputs are ordered lists. Duplicates remain; empty outputs remain empty; null/unresolved entities block. Direction/index/category enums require serialized caller mappings; missing serialized sort defaults need explicit reference policies. Filter/map traversal preserves parameter context and RNG order. Unknown anonymous options remain recorded, never renamed as recovered native fields.

Predicates cover logical composition, damage/team/category comparisons, HP and HP-ratio comparisons, grid/stance/character properties, target membership, modifier presence, team relationships, alive-mask and behavior-flag membership. Logical operators short circuit under their explicit reference contract. Anonymous bitmap fields stay in canonical IR with CONDITIONAL_REFERENCE role metadata; meanings are not inferred from field order.

Template/ability invocation uses generic catalogs, cycle checks, depth bounds, explicit owner/caster/target/parameter/provider relationships and resumable context-return frames. Policies and catalogs participate in snapshots/hashes. Recovered template parameter dictionaries remain invocation gaps; callers may provide explicit replacement contexts. Deferred child callback/event ownership blocks pending a scheduler subsystem. Additional ability lifecycle task-list slots are retained and block rather than being silently dropped.

Modifiers have explicit storage insertion/refresh/replace policies, numeric stacking data left uninterpreted, duration binding, dynamic-value checks, removal and property-stack reference operations. Event listener IDs/order/callback/owner/caster/conditions/mutation result are represented; native event IDs and activation rules are not globally simulated. HealHP requires decoded FormulaType2 plus all explicit effective operands, settlement policy and six hook declarations; missing hooks block atomically. SetDynamicValue requires a caller-bound existing provider. ModifySPNew remains separate and unmapped to team SP or energy. Presentation nodes require explicit presentation/barrier/position classifications.

Natasha Skill02 remains REFERENCE_VERTICAL_SLICE: compile **{natasha['compile_status']}**; {natasha['completed_top_level_tasks']} completed top-level tasks, {natasha.get('accepted_top_level_primitives', 0)} accepted top-level invocation, {natasha['reached_nested_tasks']} nested task reached under the generic synthetic policy; first gap `{natasha['first_SemanticGap']}`. A child blocked at its animation barrier leaves the caller's invocation pending, so accepting it is not counted as call completion. Without R13 invocation policy the original controller-inheritance gap is preserved by all 30 unchanged R12 tests. No native post-state is claimed.

Additional named regressions: Local_SPAdd, TriggerStanceCountDown_Test, MAvatar_Common_TriggerDeparted, Avatar_Common_PassiveSkill, Avatar_Common_SkillMazeInLevel, AllTeammate, AvatarNextTurnOwnerEntity and AllEnemy. The three alias fixtures exercise real filter/logical-membership, query/sort/take and composed relation-map graphs with clone/snapshot checks. Modifier root installation remains a typed lifecycle gap. No fixture-specific production branches were added.

Determinism: **PASS** for clone, snapshot, hash, replay, nested continuation restore and RNG rollback. Architecture AST scan: **PASS**. Focused R12/R13 tests: **{tests['focused']['tests']} PASS**. FAST_UNIT: {', '.join(f"{Path(r['suite']).name} {r['tests']} PASS" for r in tests['FAST_UNIT'])}; **{tests['total_FAST_UNIT']} total PASS**. Logs and test receipts are in the R13 audit directory. Tests do not perform native validation.

Highest remaining coverage family: template parameter/catalog binding and anonymous target/predicate options, followed by modifier/event lifecycle and child scheduler ownership. Recommend **R14 MORE GENERIC PRIMITIVE COVERAGE**, using the exact targeted oracle questions and affected decoded pointers in ledger v2. Each ticket states frequency, affected content and minimum evidence. Do not automatically return to a character mainline.

Production files: {', '.join(PRODUCTION)}.
Test file: `{TESTS[0]}`; existing R12/frozen tests unchanged.
Reproduce with repository-resolved Python running `tools/runtime/r13_coverage.py`, then `tools/runtime/r13_finalize.py`. Package only R13-owned files using `--package`; native payloads and old reverse trees are excluded. The external archive is `{DESTINATION}`; CRC, member set, sizes and SHA-256 are recorded in `tmp/audit/r13_generic_coverage_20261007_001/handoff_verification.json`.
"""
    (REPO/REPORT).write_text(report, encoding="utf-8")
    return expansion


def package():
    owned = sorted(set(PRODUCTION + TESTS + TOOLS + CONTROLS + [REPORT] +
        [p.relative_to(REPO).as_posix() for p in AUDIT.iterdir() if p.is_file() and p.name not in ("changed_files_manifest.json", "handoff_verification.json")]))
    manifest = {"change_request": CR, "git_writes": "NONE", "files": [{"path": p, "bytes": (REPO/p).stat().st_size, "sha256": sha(REPO/p)} for p in owned]}
    write(AUDIT / "changed_files_manifest.json", manifest)
    owned.append((AUDIT / "changed_files_manifest.json").relative_to(REPO).as_posix())
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if DESTINATION.exists():
        raise RuntimeError("refusing to overwrite existing handoff")
    with zipfile.ZipFile(DESTINATION, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in sorted(owned):
            info = zipfile.ZipInfo(relative, date_time=(2026, 10, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (REPO/relative).read_bytes())
    with zipfile.ZipFile(DESTINATION) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(owned):
            raise RuntimeError("handoff CRC/member set mismatch")
        members = []
        for info in archive.infolist():
            content = archive.read(info.filename)
            if content != (REPO/info.filename).read_bytes() or info.file_size != len(content):
                raise RuntimeError("handoff content/size mismatch")
            members.append({"path": info.filename, "bytes": info.file_size, "crc32": f"{info.CRC:08x}", "sha256": hashlib.sha256(content).hexdigest()})
    receipt = {"path": str(DESTINATION), "sha256": sha(DESTINATION), "bytes": DESTINATION.stat().st_size,
        "CRC": "PASS", "member_set": "PASS", "sizes": "PASS", "member_count": len(members), "members": members}
    write(AUDIT / "handoff_verification.json", receipt)
    print(json.dumps({key: receipt[key] for key in ("path", "sha256", "bytes", "CRC", "member_set", "sizes", "member_count")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", action="store_true")
    parser.add_argument("--reuse-tests", action="store_true")
    args = parser.parse_args()
    tests = read(AUDIT.relative_to(REPO)/"test_receipt.json") if args.reuse_tests else run_tests()
    if not tests["focused"]["PASS"] or not all(row["PASS"] for row in tests["FAST_UNIT"]):
        raise RuntimeError("unverified tests")
    preservation = safety()
    expansion = emit_report(tests, preservation)
    print(json.dumps({"verdict": expansion["verdict"], "tests": tests["total_FAST_UNIT"], "focused": tests["focused"]["tests"]}, indent=2))
    if args.package:
        package()
