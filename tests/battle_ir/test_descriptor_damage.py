# -*- coding: utf-8 -*-
from __future__ import annotations

import json, sys, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorBatch, DescriptorError
from hsr_battle_agent.battle_ir.descriptors.damage import DamageDescriptor
from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue as P
from hsr_battle_agent.battle_ir.provenance import SourceProvenance
from hsr_battle_agent.battle_sandbox.evidence_boundary import EvidenceBoundaryError, require_native_contract

AUTHORITY = REPO / "data/semantics/4.4.54/full_reconstruction/astra_damage_survival_v1.json"


def _blocker(): return UnknownHandle("DS-Q1", "DAMAGE", {"formula": "UNKNOWN"}, {}, ("native formula",)).to_dict()


def _item(order=0, unresolved=False, payload=None):
    contract = ContractRef("damage", "battle.descriptor.damage", "1", EvidenceMode.REFERENCE_MODEL, "6" * 64, ("freeze:damage",))
    provenance = SourceProvenance("4.4.54", "DamageRequest", "Read", None, "UNKNOWN", "REFERENCE_MODEL")
    return DamageDescriptor(
        contract, EvidenceMode.REFERENCE_MODEL, provenance, ("request_shape_families", order), order,
        P.present(payload if payload is not None else {"id": "DS-FAMILY-001", "name": "RATIO__SPHIT"}),
        {
            "damage_root": P.present("damage-root:1"), "damage_hit": P.present(f"damage-hit:{order}"),
            "damage_component": P.present("damage-component:1"),
            "context": P.present({"target": "entity:2"}),
            "survival_dependencies": P.present(["shield", "hp", "toughness"]),
            "resource_dependencies": P.present(["sp_hit"]),
            "special_channel_references": P.present(["Break", "DOT", "Break"]),
            "knowledge": P.present("UNRESOLVED" if unresolved else "REPRESENTED"),
            "blocker": P.present(_blocker()) if unresolved else P.absent(),
        },
        {"rounding": P.absent()},
    )


class TestDamageDescriptor(unittest.TestCase):
    def test_frozen_fixture_round_trip(self):
        frozen = json.loads(AUTHORITY.read_text(encoding="utf-8"))["request_shape_families"][0]
        self.assertEqual(frozen["id"], "DS-FAMILY-001")
        self.assertEqual(frozen["field_presence"], ["DamagePercentage", "SPHitRatio"])
        item = _item(payload=frozen)
        self.assertEqual(DamageDescriptor.from_dict(item.to_dict()).to_dict(), item.to_dict())

    def test_root_hit_component_and_dependencies_stay_distinct(self):
        item = _item()
        self.assertNotEqual(item.fields["damage_root"], item.fields["damage_hit"])
        self.assertNotEqual(item.fields["damage_hit"], item.fields["damage_component"])
        self.assertEqual(item.fields["special_channel_references"].require_present(), ["Break", "DOT", "Break"])

    def test_repeat_hits_and_order_survive(self):
        batch = DescriptorBatch((_item(1), _item(0)))
        self.assertEqual(DescriptorBatch.from_dict(batch.to_dict()).to_dict(), batch.to_dict())

    def test_unknown_formula_is_representable_but_blocked(self):
        self.assertTrue(_item(unresolved=True).is_blocked())
        broken = _item().to_dict(); broken["fields"][4]["value"] = P.present("shield").to_dict()
        with self.assertRaises(DescriptorError): DamageDescriptor.from_dict(broken)

    def test_no_formula_or_native_permission(self):
        self.assertFalse(hasattr(DamageDescriptor, "calculate"))
        with self.assertRaises(EvidenceBoundaryError): require_native_contract(_item(), role="damage descriptor")


if __name__ == "__main__": unittest.main()
