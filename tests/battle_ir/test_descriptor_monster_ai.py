# -*- coding: utf-8 -*-
from __future__ import annotations

import json, sys, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorBatch, DescriptorError
from hsr_battle_agent.battle_ir.descriptors.monster_ai import MonsterAIDescriptor
from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue as P
from hsr_battle_agent.battle_ir.provenance import SourceProvenance
from hsr_battle_agent.battle_sandbox.evidence_boundary import EvidenceBoundaryError, require_native_contract

AUTHORITY = REPO / "data/semantics/4.4.54/full_reconstruction/astra_monster_ai_v1.json"


def _blocker(): return UnknownHandle("MA-Q01", "MONSTER_AI", {"winner": "UNKNOWN"}, {}, ("native selection",)).to_dict()


def _item(order=0, unresolved=False, payload=None):
    contract = ContractRef("monster-ai", "battle.descriptor.monster_ai", "1", EvidenceMode.REFERENCE_MODEL, "5" * 64, ("freeze:monster-ai",))
    provenance = SourceProvenance("4.4.54", "MonsterAI", "Read", None, "UNKNOWN", "REFERENCE_MODEL")
    return MonsterAIDescriptor(
        contract, EvidenceMode.REFERENCE_MODEL, provenance, ("policy_body_families", order), order,
        P.present(payload if payload is not None else {"family": "STEPPER_DECISION_GROUP_WITH_PREDICATE_AXES"}),
        {
            "policy_body": P.present({"groups": 2}), "state": P.present({"cursor": None}),
            "sequence": P.present(["skill:2", "skill:1", "skill:1"]),
            "use_skill": P.present({"skill": "skill:2"}), "variables": P.present({"flag": False}),
            "sequence_occurrence": P.present(order), "admission_handoff": P.absent(),
            "target_handoff": P.present({"status": "UNRESOLVED"}),
            "knowledge": P.present("UNRESOLVED" if unresolved else "REPRESENTED"),
            "blocker": P.present(_blocker()) if unresolved else P.absent(),
        },
        {"DefaultDSE": P.absent()},
    )


class TestMonsterAIDescriptor(unittest.TestCase):
    def test_frozen_fixture_round_trip(self):
        frozen = json.loads(AUTHORITY.read_text(encoding="utf-8"))["policy_body_families"][0]
        self.assertEqual(frozen["family"], "STEPPER_DECISION_GROUP_WITH_PREDICATE_AXES")
        self.assertEqual(frozen["native_winner"], "BLOCKED_BY_EVIDENCE")
        item = _item(payload=frozen)
        self.assertEqual(MonsterAIDescriptor.from_dict(item.to_dict()).to_dict(), item.to_dict())

    def test_sequence_order_duplicates_and_occurrences_survive(self):
        batch = DescriptorBatch((_item(1), _item(0)))
        self.assertEqual(batch.occurrences[0].fields["sequence"].require_present(), ["skill:2", "skill:1", "skill:1"])
        self.assertEqual(DescriptorBatch.from_dict(batch.to_dict()).to_dict(), batch.to_dict())

    def test_unresolved_handoffs_are_explicit_and_blocked(self):
        item = _item(unresolved=True)
        self.assertTrue(item.is_blocked())
        self.assertTrue(item.fields["admission_handoff"].is_absent())

    def test_sequence_occurrence_validation(self):
        broken = _item().to_dict(); broken["fields"][5]["value"] = P.present(-1).to_dict()
        with self.assertRaises(DescriptorError): MonsterAIDescriptor.from_dict(broken)

    def test_no_winner_or_native_permission(self):
        self.assertFalse(hasattr(MonsterAIDescriptor, "select_winner"))
        with self.assertRaises(EvidenceBoundaryError): require_native_contract(_item(), role="AI descriptor")


if __name__ == "__main__": unittest.main()
