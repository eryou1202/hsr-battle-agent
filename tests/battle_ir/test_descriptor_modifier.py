# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorBatch, DescriptorError
from hsr_battle_agent.battle_ir.descriptors.modifier import ModifierDescriptor, ModifierDescriptorKind
from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue as P
from hsr_battle_agent.battle_ir.provenance import SourceProvenance
from hsr_battle_agent.battle_sandbox.evidence_boundary import EvidenceBoundaryError, require_native_contract

AUTHORITY = REPO / "data/semantics/4.4.54/full_reconstruction/astra_modifier_v1.json"


def _contract():
    return ContractRef("modifier", "battle.descriptor.modifier", "1", EvidenceMode.REFERENCE_MODEL, "2" * 64, ("freeze:modifier",))


def _prov():
    return SourceProvenance("4.4.54", "Modifier", "Read", None, "UNKNOWN", "REFERENCE_MODEL")


def _blocker():
    return UnknownHandle("MOD-Q1", "MODIFIER", {"matcher": "unknown"}, {}, ("native matcher",)).to_dict()


def _item(kind=ModifierDescriptorKind.STACKING_TRANSITION, operation="Refresh", order=0, unresolved=False, payload=None):
    names = {"REQUEST": "request", "LOOKUP_QUERY": "lookup_query", "STACKING_TRANSITION": "stacking_transition", "LIFECYCLE_CALLBACK": "lifecycle_callback"}
    active = names[kind.value]
    parts = {name: P.absent() for name in names.values()}
    parts[active] = P.present({"operation": operation} if active == "stacking_transition" else {"shape": active})
    return ModifierDescriptor(
        _contract(), EvidenceMode.REFERENCE_MODEL, _prov(), ("policy_family_table", order), order,
        P.present(payload if payload is not None else {"policy": "Unknow", "native_ordinal": 0}),
        {
            "kind": P.present(kind.value), **parts,
            "provider": P.present("provider:1"), "caster": P.present("caster:1"),
            "stacking_policy": P.present("Unknow"),
            "knowledge": P.present("UNRESOLVED" if unresolved else "REPRESENTED"),
            "blocker": P.present(_blocker()) if unresolved else P.absent(),
        },
        {"future": P.present([None])},
    )


class TestModifierDescriptor(unittest.TestCase):
    def test_frozen_fixture_and_round_trip(self):
        frozen = json.loads(AUTHORITY.read_text(encoding="utf-8"))["policy_family_table"][0]
        expected = {"policy": "Unknow", "native_ordinal": 0}
        self.assertEqual({k: frozen[k] for k in expected}, expected)
        item = _item(payload=frozen)
        self.assertEqual(ModifierDescriptor.from_dict(item.to_dict()).to_dict(), item.to_dict())

    def test_refresh_and_replace_never_collapse(self):
        refresh, replace = _item(operation="Refresh"), _item(operation="Replace")
        self.assertNotEqual(refresh.to_dict(), replace.to_dict())
        self.assertEqual(refresh.fields["stacking_transition"].require_present()["operation"], "Refresh")

    def test_provider_and_caster_are_distinct(self):
        item = _item()
        self.assertNotEqual(item.fields["provider"], item.fields["caster"])

    def test_all_four_kinds_and_repeats_round_trip(self):
        items = tuple(_item(kind, order=i) for i, kind in enumerate(ModifierDescriptorKind))
        batch = DescriptorBatch(items)
        self.assertEqual([x.kind for x in items], list(ModifierDescriptorKind))
        self.assertEqual(DescriptorBatch.from_dict(batch.to_dict()).to_dict(), batch.to_dict())

    def test_unknown_branch_remains_blocked(self):
        self.assertTrue(_item(unresolved=True).is_blocked())
        with self.assertRaises(DescriptorError):
            _item(operation="replace")

    def test_no_native_permission(self):
        with self.assertRaises(EvidenceBoundaryError):
            require_native_contract(_item(), role="modifier descriptor")


if __name__ == "__main__":
    unittest.main()
