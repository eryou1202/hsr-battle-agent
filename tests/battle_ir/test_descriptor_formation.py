# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorBatch, DescriptorError
from hsr_battle_agent.battle_ir.descriptors.formation import FormationTopologyDescriptor
from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue as P
from hsr_battle_agent.battle_ir.provenance import SourceProvenance
from hsr_battle_agent.battle_sandbox.evidence_boundary import EvidenceBoundaryError, require_native_contract

AUTHORITY = REPO / "data/semantics/4.4.54/full_reconstruction/astra_formation_boss_v1.json"


def _blocker():
    return UnknownHandle("FB-Q1", "TOPOLOGY", {"adjacency": "UNKNOWN"}, {}, ("native topology",)).to_dict()


def _item(order=0, unresolved=False, payload=None):
    contract = ContractRef("formation", "battle.descriptor.formation", "1", EvidenceMode.REFERENCE_MODEL, "3" * 64, ("freeze:formation",))
    provenance = SourceProvenance("4.4.54", "Formation", "Read", None, "UNKNOWN", "REFERENCE_MODEL")
    return FormationTopologyDescriptor(
        contract, EvidenceMode.REFERENCE_MODEL, provenance, ("boss_topology_families", order), order,
        P.present(payload if payload is not None else {"id": "EXPLICIT_PART_MAP_WITH_UNSELECTABLE_ANCHOR"}),
        {
            "team_identity": P.present("team:1"), "formation_index": P.present(2),
            "row_index": P.present(0), "spatial_order": P.present(["slot:b", "slot:a"]),
            "entity_identity": P.present("entity:part"), "lineup_index": P.null(),
            "relations": P.present([{"type": "PART", "to": "entity:root"}]),
            "knowledge": P.present("UNRESOLVED" if unresolved else "REPRESENTED"),
            "blocker": P.present(_blocker()) if unresolved else P.absent(),
        },
        {"native_adjacency": P.absent()},
    )


class TestFormationDescriptor(unittest.TestCase):
    def test_frozen_fixture_round_trip(self):
        frozen = json.loads(AUTHORITY.read_text(encoding="utf-8"))["boss_topology_families"][0]
        self.assertEqual(frozen["id"], "EXPLICIT_PART_MAP_WITH_UNSELECTABLE_ANCHOR")
        self.assertEqual(frozen["runtime_eligibility"], "TOPOLOGY_SCHEMA_ONLY")
        item = _item(payload=frozen)
        self.assertEqual(FormationTopologyDescriptor.from_dict(item.to_dict()).to_dict(), item.to_dict())

    def test_team_formation_row_lineup_and_entity_are_separate(self):
        item = _item()
        self.assertEqual(item.fields["team_identity"].require_present(), "team:1")
        self.assertEqual(item.fields["formation_index"].require_present(), 2)
        self.assertTrue(item.fields["lineup_index"].is_null())
        self.assertEqual(item.fields["entity_identity"].require_present(), "entity:part")

    def test_source_order_and_repeats_survive(self):
        batch = DescriptorBatch((_item(1), _item(0)))
        self.assertEqual(DescriptorBatch.from_dict(batch.to_dict()).to_dict(), batch.to_dict())
        self.assertEqual([x.source_order for x in batch.occurrences], [1, 0])

    def test_unknown_topology_is_representable_but_blocked(self):
        self.assertTrue(_item(unresolved=True).is_blocked())
        with self.assertRaises(DescriptorError):
            broken = _item().to_dict(); broken["fields"][1]["value"] = P.present(1.5).to_dict(); FormationTopologyDescriptor.from_dict(broken)

    def test_no_native_permission(self):
        with self.assertRaises(EvidenceBoundaryError):
            require_native_contract(_item(), role="formation")


if __name__ == "__main__": unittest.main()
