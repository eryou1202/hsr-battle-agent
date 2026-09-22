# -*- coding: utf-8 -*-
from __future__ import annotations

import json, sys, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorBatch, DescriptorError
from hsr_battle_agent.battle_ir.descriptors.target import ResolvedTargetSet, RetargetDescriptor, TargetIntent
from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue as P
from hsr_battle_agent.battle_ir.provenance import SourceProvenance
from hsr_battle_agent.battle_sandbox.evidence_boundary import EvidenceBoundaryError, require_native_contract

AUTHORITY = REPO / "data/semantics/4.4.54/full_reconstruction/astra_target_retarget_v1.json"


def _contract(kind): return ContractRef(kind, "battle.descriptor.target", "1", EvidenceMode.REFERENCE_MODEL, "7" * 64, ("freeze:target",))
def _prov(): return SourceProvenance("4.4.54", "Target", "Read", None, "UNKNOWN", "REFERENCE_MODEL")
def _blocker(): return UnknownHandle("TR-Q1", "TARGET", {"selection": "UNKNOWN"}, {}, ("native selection",)).to_dict()


def _intent(order=0, unresolved=False):
    return TargetIntent(_contract("intent"), EvidenceMode.REFERENCE_MODEL, _prov(), ("intent", order), order, P.present({"type": "AliasExpr"}), {
        "intent_kind": P.present("AliasExpr"), "intent": P.present({"Alias": "AllEnemy"}),
        "knowledge": P.present("UNRESOLVED" if unresolved else "REPRESENTED"),
        "blocker": P.present(_blocker()) if unresolved else P.absent(),
    }, {"automatic_revalidation": P.absent()})


def _resolved(targets, order=0, unresolved=False):
    return ResolvedTargetSet(_contract("resolved"), EvidenceMode.REFERENCE_MODEL, _prov(), ("resolved", order), order, P.present({"source": "fixture"}), {
        "targets": P.present(targets), "resolution_stage": P.present("SOURCE"),
        "duplicate_policy": P.present("PRESERVE"), "rng_provenance": P.absent(),
        "knowledge": P.present("UNRESOLVED" if unresolved else "REPRESENTED"),
        "blocker": P.present(_blocker()) if unresolved else P.absent(),
    }, {})


def _retarget(payload=None, unresolved=False):
    return RetargetDescriptor(_contract("retarget"), EvidenceMode.REFERENCE_MODEL, _prov(), ("retarget_families", 0), 0, P.present(payload if payload is not None else {"family": "Retarget"}), {
        "input_intent": P.present({"Alias": "AllEnemy"}), "predicate": P.null(),
        "random_request": P.present(False), "include_limbo": P.absent(), "maximum": P.present(3),
        "nested_tasks": P.present(["success", "failure"]), "affected_context": P.absent(), "lifetime": P.absent(),
        "knowledge": P.present("UNRESOLVED" if unresolved else "REPRESENTED"),
        "blocker": P.present(_blocker()) if unresolved else P.absent(),
    }, {"death_fallback": P.absent()})


class TestTargetDescriptors(unittest.TestCase):
    def test_frozen_retarget_fixture_round_trip(self):
        frozen = json.loads(AUTHORITY.read_text(encoding="utf-8"))["retarget_families"][0]
        self.assertEqual(frozen["family"], "Retarget")
        self.assertEqual(frozen["mutation_kind"], "UNKNOWN replace/append/remove/reorder")
        item = _retarget(payload=frozen)
        self.assertEqual(RetargetDescriptor.from_dict(item.to_dict()).to_dict(), item.to_dict())

    def test_empty_null_duplicate_and_order_are_distinct(self):
        empty, one_null = _resolved([]), _resolved([None])
        repeated = _resolved(["entity:2", None, "entity:2", "entity:1"])
        self.assertNotEqual(empty.to_dict(), one_null.to_dict())
        self.assertEqual(repeated.targets, ["entity:2", None, "entity:2", "entity:1"])
        with self.assertRaises(DescriptorError):
            _resolved(("entity:1",))

    def test_targets_property_returns_a_detached_list(self):
        item = _resolved(["entity:2", None, "entity:2"])
        before = item.to_dict()
        exported = item.targets
        self.assertIsInstance(exported, list)
        exported.append("entity:3")
        self.assertEqual(item.to_dict(), before)
        self.assertEqual(item.targets, ["entity:2", None, "entity:2"])

    def test_three_types_remain_separate_and_repeat_occurrences_survive(self):
        self.assertNotIsInstance(_intent(), ResolvedTargetSet)
        self.assertNotIsInstance(_retarget(), TargetIntent)
        batch = DescriptorBatch((_intent(1), _intent(0)))
        self.assertEqual(DescriptorBatch.from_dict(batch.to_dict()).to_dict(), batch.to_dict())

    def test_unknown_branches_remain_blocked(self):
        self.assertTrue(_intent(unresolved=True).is_blocked())
        self.assertTrue(_resolved([], unresolved=True).is_blocked())
        self.assertTrue(_retarget(unresolved=True).is_blocked())

    def test_no_random_selection_or_native_permission(self):
        self.assertFalse(hasattr(RetargetDescriptor, "select_random"))
        for item in (_intent(), _resolved([]), _retarget()):
            with self.assertRaises(EvidenceBoundaryError): require_native_contract(item, role="target descriptor")


if __name__ == "__main__": unittest.main()
