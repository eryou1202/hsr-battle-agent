"""Offline compiler from canonical BehaviorRecord into source-independent IR.

The compiler is intentionally strict: a captured source operation is only
compiled when its semantic status and headless gating rule permit it.  Other
nodes become attributable diagnostics, never hidden runtime fallbacks.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from .nanoka_content import stable_hash


class BehaviorCompileError(ValueError):
    """A canonical behavior record cannot form a sound IR graph."""


PRIMITIVE_BINDINGS: Mapping[str, Mapping[str, Any]] = {
    "HEAL_REQUEST": {"packet": "dynamic_mvp_v1:HEAL_STATE_TRANSITION", "execution_scope": "ORDINARY_MVP"},
    "MODIFY_TEAM_SP": {"packet": "dynamic_mvp_v1:SP_CORE", "execution_scope": "ORDINARY_MVP"},
    "INVOKE_BEHAVIOR": {"packet": "KERNEL-EVENT-001", "execution_scope": "STRUCTURAL_CALL_ONLY"},
    "ADD_MODIFIER": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "REMOVE_MODIFIER": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_PROPERTY_STACK": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_DAMAGE_DATA": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_HEAL_DATA": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "DISPEL_STATUS": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "CONDITIONAL": {"packet": "COMPILER-PREDICATE-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "PREDICATE": {"packet": "COMPILER-PREDICATE-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


class BehaviorCompiler:
    """Compile only canonical IR; raw external payload is never consulted."""

    def compile_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        entrypoints: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        structural_only = False
        source_operation_count = 0
        for entrypoint in record.get("entrypoints", []):
            entry = _mapping(entrypoint)
            source_operation_count += len(entry.get("operations", []))
            operations, entry_diagnostics, entry_structural = self._compile_operations(entry.get("operations", []))
            diagnostics.extend(entry_diagnostics)
            structural_only = structural_only or entry_structural
            entrypoints.append({
                "event": entry.get("event"),
                "source_event": entry.get("source_event"),
                "callback_metadata": entry.get("callback_metadata"),
                "operations": operations,
            })
        if source_operation_count == 0:
            diagnostics.append({
                "operation_id": None,
                "source_type": None,
                "kind": None,
                "semantic_status": None,
                "semantic_importance": "P1_UNCLASSIFIED_SEMANTIC",
                "gating_risk": "UNKNOWN",
                "reason": "NO_OPERATIONAL_ENTRYPOINTS",
                "policy": "REJECT_NOT_NOOP",
            })
        compiled = {
            "schema": "hsr_battle_agent.behavior_ir/1",
            "game_version": "4.4.54",
            "behavior_id": record.get("behavior_id"),
            "owner_kind": record.get("owner_kind"),
            "owner_ref": record.get("owner_ref"),
            "source_refs": record.get("source_refs", []),
            "entrypoints": entrypoints,
            "compile_status": "COMPILED_STRUCTURE_ONLY" if not diagnostics else "REJECTED",
            "executable": False,
            "execution_blockers": diagnostics,
            "structural_only": structural_only,
        }
        compiled["ir_sha256"] = stable_hash(compiled)
        return compiled

    def _compile_operations(self, values: Iterable[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        operations: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        structural_only = False
        for raw in values:
            operation = _mapping(raw)
            operation_id = str(operation.get("operation_id", "UNKNOWN_OPERATION"))
            status = str(operation.get("semantic_status", "OPAQUE"))
            risk = str(operation.get("gating_risk", "UNKNOWN"))
            kind = str(operation.get("kind", "OPAQUE"))
            if status == "PRESENTATION" and risk == "NONE":
                disposition = "HEADLESS_PRESENTATION_OMITTED"
                binding = None
            elif status in {"MODELLED", "REQUIRES_PACKET"}:
                binding = PRIMITIVE_BINDINGS.get(kind)
                if binding is None:
                    diagnostics.append(self._diagnostic(operation, "REQUIRES_PACKET_HAS_NO_COMPILER_BINDING" if status == "REQUIRES_PACKET" else "MODELLED_TYPE_HAS_NO_COMPILER_BINDING"))
                    continue
                disposition = "BOUND_UNEXECUTABLE_PACKET" if status == "REQUIRES_PACKET" else "BOUND_PRIMITIVE"
                structural_only = structural_only or binding["execution_scope"] in {"STRUCTURAL_CALL_ONLY", "STRUCTURAL_PACKET_ONLY"}
            else:
                diagnostics.append(self._diagnostic(operation, "BEHAVIOR_AFFECTING_NODE_NOT_COMPILED"))
                continue
            children, child_diagnostics, child_structural = self._compile_children(operation)
            diagnostics.extend(child_diagnostics)
            structural_only = structural_only or child_structural
            operations.append({
                "operation_id": operation_id,
                "kind": kind,
                "node_role": operation.get("node_role"),
                "target": operation.get("target"),
                "arguments": operation.get("arguments"),
                "state_reads": operation.get("state_reads"),
                "state_writes": operation.get("state_writes"),
                "event_boundary": operation.get("event_boundary"),
                "dependencies": list(operation.get("dependencies", [])) + ([binding["packet"]] if binding else []),
                "disposition": disposition,
                "children": children,
                "source_operation_id": operation_id,
            })
        return operations, diagnostics, structural_only

    def _compile_children(self, operation: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        groups: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        structural_only = False
        for raw_group in operation.get("children", []):
            group = _mapping(raw_group)
            children, child_diagnostics, child_structural = self._compile_operations(group.get("operations", []))
            groups.append({"group_id": group.get("group_id"), "field_path": group.get("field_path"), "operations": children})
            diagnostics.extend(child_diagnostics)
            structural_only = structural_only or child_structural
        return groups, diagnostics, structural_only

    @staticmethod
    def _diagnostic(operation: Mapping[str, Any], reason: str) -> dict[str, Any]:
        return {
            "operation_id": operation.get("operation_id"),
            "source_type": operation.get("source_type"),
            "kind": operation.get("kind"),
            "semantic_status": operation.get("semantic_status"),
            "semantic_importance": operation.get("semantic_importance"),
            "gating_risk": operation.get("gating_risk"),
            "reason": reason,
            "policy": "REJECT_NOT_NOOP",
        }

    def compile_corpus(self, corpus: Mapping[str, Any]) -> dict[str, Any]:
        compiled = [self.compile_record(record) for record in corpus.get("records", [])]
        compiled.sort(key=lambda record: str(record["behavior_id"]))
        successful = [record for record in compiled if record["compile_status"] == "COMPILED_STRUCTURE_ONLY"]
        failure_reasons = Counter(diagnostic["reason"] for record in compiled for diagnostic in record["execution_blockers"])
        by_owner = {}
        for owner in sorted({str(record["owner_kind"]) for record in compiled}):
            owner_records = [record for record in compiled if record["owner_kind"] == owner]
            by_owner[owner] = {"captured": len(owner_records), "structural_compiled": sum(record["compile_status"] == "COMPILED_STRUCTURE_ONLY" for record in owner_records), "golden_tested": 0}
        result = {
            "schema": "hsr_battle_agent.behavior_compiler_report/1",
            "game_version": corpus.get("game_version"),
            "input_corpus_sha256": corpus.get("corpus_sha256"),
            "compiler_policy": "canonical-only strict compiler; behavior-affecting uncompiled nodes reject the record and never become no-ops",
            "records": compiled,
            "coverage": {"captured": len(compiled), "canonicalized": len(compiled), "structural_compiled": len(successful), "executable": 0, "golden_tested": 0, "by_owner_kind": by_owner, "failure_reasons": dict(sorted(failure_reasons.items()))},
        }
        result["report_sha256"] = stable_hash(result)
        return result
