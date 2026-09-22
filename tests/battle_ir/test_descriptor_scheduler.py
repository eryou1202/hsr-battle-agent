# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorBatch, DescriptorError
from hsr_battle_agent.battle_ir.descriptors.scheduler import SchedulerDescriptor, SchedulerFamily
from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue as P
from hsr_battle_agent.battle_ir.provenance import SourceProvenance
from hsr_battle_agent.battle_sandbox.evidence_boundary import EvidenceBoundaryError, require_native_contract

AUTHORITY = REPO / "data/semantics/4.4.54/full_reconstruction/astra_scheduler_arbitration_v1.json"


def _blocker():
    return UnknownHandle("SA-Q1", "SCHEDULER", {"tie": "UNKNOWN"}, {}, ("native tie ordering",)).to_dict()


def _item(family=SchedulerFamily.ORDINARY, order=0, unresolved=False, payload=None):
    contract = ContractRef("scheduler", "battle.descriptor.scheduler", "1", EvidenceMode.REFERENCE_MODEL, "4" * 64, ("freeze:scheduler",))
    provenance = SourceProvenance("4.4.54", "Scheduler", "Read", None, "UNKNOWN", "REFERENCE_MODEL")
    return SchedulerDescriptor(
        contract, EvidenceMode.REFERENCE_MODEL, provenance, ("candidate_families", order), order,
        P.present(payload if payload is not None else {"kind": "ORDINARY_TURN"}),
        {
            "family": P.present(family.value), "candidate": P.present({"actor": "entity:1"}),
            "partial_order": P.present(["request", "admission"]),
            "source_sequence": P.present(["candidate:b", "candidate:a", "candidate:a"]),
            "knowledge": P.present("UNRESOLVED" if unresolved else "REPRESENTED"),
            "blocker": P.present(_blocker()) if unresolved else P.absent(),
        },
        {"equal_key_stability": P.absent()},
    )


class TestSchedulerDescriptor(unittest.TestCase):
    def test_frozen_fixture_round_trip(self):
        frozen = json.loads(AUTHORITY.read_text(encoding="utf-8"))["candidate_families"][0]
        self.assertEqual(frozen["kind"], "ORDINARY_TURN")
        self.assertEqual(frozen["native_full_admission"], "UNKNOWN")
        item = _item(payload=frozen)
        self.assertEqual(SchedulerDescriptor.from_dict(item.to_dict()).to_dict(), item.to_dict())

    def test_all_scheduler_families_are_distinct(self):
        items = [_item(f, i) for i, f in enumerate(SchedulerFamily)]
        self.assertEqual(len({x.family for x in items}), 8)
        self.assertNotEqual(SchedulerFamily.TURN_INSERT_ABILITY, SchedulerFamily.TURN_INSERT_ACTION)
        self.assertNotEqual(SchedulerFamily.ACTION_TASK, SchedulerFamily.DAMAGE_TASK)

    def test_order_and_duplicates_are_preserved_not_sorted(self):
        item = _item()
        self.assertEqual(item.fields["source_sequence"].require_present(), ["candidate:b", "candidate:a", "candidate:a"])
        batch = DescriptorBatch((_item(SchedulerFamily.ONE_MORE, 1), _item(order=0)))
        self.assertEqual(DescriptorBatch.from_dict(batch.to_dict()).to_dict(), batch.to_dict())

    def test_unknown_tie_is_representable_but_blocked(self):
        self.assertTrue(_item(unresolved=True).is_blocked())
        broken = _item().to_dict(); broken["fields"][0]["value"] = P.present("UNIVERSAL").to_dict()
        with self.assertRaises(DescriptorError): SchedulerDescriptor.from_dict(broken)

    def test_not_legal_action_or_native_permission(self):
        self.assertFalse(hasattr(SchedulerDescriptor, "as_player_legal_action"))
        with self.assertRaises(EvidenceBoundaryError): require_native_contract(_item(), role="scheduler")


if __name__ == "__main__": unittest.main()
