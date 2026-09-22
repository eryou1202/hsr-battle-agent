# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorBatch, DescriptorError
from hsr_battle_agent.battle_ir.descriptors.invocation import InvocationDescriptor
from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue as P
from hsr_battle_agent.battle_ir.provenance import SourceProvenance
from hsr_battle_agent.battle_sandbox.evidence_boundary import EvidenceBoundaryError, require_native_contract

AUTHORITY = REPO / "data/semantics/4.4.54/full_reconstruction/astra_triggerability_v1.json"
FROZEN_FIXTURE = {
    "id": "NAME_OMITTED_FLAG",
    "argument_keys": ["AbilityName"],
    "operations": 52,
    "execution_status": "REJECT_FLAG_DEFAULT_UNPROVEN",
}


def _contract(mode=EvidenceMode.REFERENCE_MODEL):
    return ContractRef("invocation", "battle.descriptor.invocation", "1", mode, "1" * 64, ("freeze:triggerability",))


def _provenance():
    return SourceProvenance("4.4.54", "TriggerAbility", "Read", None, "UNKNOWN", "REFERENCE_MODEL")


def _blocker():
    return UnknownHandle("TA-P4-Q1", "INVOCATION", {"branch": "unknown"}, {"source": "freeze"}, ("native boundary",)).to_dict()


def _item(order=0, flag=P.absent(), unresolved=False, payload=None):
    return InvocationDescriptor(
        _contract(), EvidenceMode.REFERENCE_MODEL, _provenance(),
        ("payload_families", order), order,
        P.present(FROZEN_FIXTURE if payload is None else payload),
        {
            "caller": P.present({"receiver": "entity:1"}),
            "context": P.present({"ability_target": ["entity:2"]}),
            "arguments": P.present({"AbilityName": "Nested"}),
            "is_skill_perform": flag,
            "continuation_handles": P.present(["wait:1", "finish:1"]),
            "knowledge": P.present("UNRESOLVED" if unresolved else "REPRESENTED"),
            "blocker": P.present(_blocker()) if unresolved else P.absent(),
        },
        {"future_field": P.present((1, 2))},
    )


class TestInvocationDescriptor(unittest.TestCase):
    def test_frozen_fixture_and_lossless_round_trip(self):
        frozen = json.loads(AUTHORITY.read_text(encoding="utf-8"))["payload_families"][2]
        self.assertEqual(frozen, FROZEN_FIXTURE)
        item = _item()
        self.assertEqual(InvocationDescriptor.from_dict(item.to_dict()).to_dict(), item.to_dict())

    def test_is_skill_perform_presence_is_not_defaulted(self):
        absent, false, true = _item(flag=P.absent()), _item(flag=P.present(False)), _item(flag=P.present(True))
        self.assertTrue(absent.is_skill_perform.is_absent())
        self.assertIs(false.is_skill_perform.require_present(), False)
        self.assertIs(true.is_skill_perform.require_present(), True)
        self.assertNotEqual(absent.to_dict(), false.to_dict())

    def test_repeat_occurrences_and_source_order_survive(self):
        batch = DescriptorBatch((_item(1), _item(0)))
        restored = DescriptorBatch.from_dict(batch.to_dict())
        self.assertEqual([x.source_order for x in restored.occurrences], [1, 0])
        self.assertNotEqual(batch.occurrences[0].occurrence_identity(), batch.occurrences[1].occurrence_identity())

    def test_unknown_branch_is_representable_and_blocked(self):
        item = _item(unresolved=True)
        self.assertTrue(item.is_blocked())
        self.assertTrue(InvocationDescriptor.from_dict(item.to_dict()).is_blocked())

    def test_invalid_flag_rejects(self):
        with self.assertRaises(DescriptorError):
            _item(flag=P.present(0))

    def test_descriptor_is_not_native_permission(self):
        with self.assertRaises(EvidenceBoundaryError):
            require_native_contract(_item(), role="invocation")
        with self.assertRaises(DescriptorError):
            _item().execution_permitted()


if __name__ == "__main__":
    unittest.main()
