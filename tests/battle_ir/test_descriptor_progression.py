# -*- coding: utf-8 -*-
from __future__ import annotations

import json, sys, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorBatch, DescriptorError
from hsr_battle_agent.battle_ir.descriptors.progression import ActivationState, ProgressionActivationDescriptor
from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue as P
from hsr_battle_agent.battle_ir.provenance import SourceProvenance
from hsr_battle_agent.battle_sandbox.evidence_boundary import EvidenceBoundaryError, require_native_contract

AUTHORITY = REPO / "data/semantics/4.4.54/full_reconstruction/astra_equipment_trace_eidolon_v1.json"


def _blocker(): return UnknownHandle("D8-Q1", "PROGRESSION", {"activation": "UNKNOWN"}, {}, ("runtime activation",)).to_dict()


def _item(state=ActivationState.UNRESOLVED, order=0, payload=None):
    contract = ContractRef("progression", "battle.descriptor.progression", "1", EvidenceMode.REFERENCE_MODEL, "8" * 64, ("freeze:progression",))
    provenance = SourceProvenance("4.4.54", "Loadout", "Read", None, "UNKNOWN", "REFERENCE_MODEL")
    return ProgressionActivationDescriptor(contract, EvidenceMode.REFERENCE_MODEL, provenance, ("behavior_binding_families", order), order, P.present(payload if payload is not None else {"kind": "EXACT_CONTENT_ID_RELATION"}), {
        "source_family": P.present("EIDOLON"), "source_identity": P.present(f"eidolon:{order}"),
        "activation_state": P.present(state.value), "activation_provenance": P.present({"source": "fixture"}),
        "candidate_mapping": P.present({"kind": "EXACT_CONTENT_ID_RELATION"}),
        "blocker": P.present(_blocker()) if state is ActivationState.UNRESOLVED else P.absent(),
    }, {"cumulative": P.absent()})


class TestProgressionDescriptor(unittest.TestCase):
    def test_frozen_fixture_round_trip(self):
        frozen = json.loads(AUTHORITY.read_text(encoding="utf-8"))["behavior_binding_families"][0]
        self.assertEqual(frozen, {"kind": "EXACT_CONTENT_ID_RELATION", "status": "OBSERVED_STATIC", "evidence": "data/semantics/4.4.54/full_reconstruction/astra_equipment_trace_eidolon_targeted_evidence_v1.json#/static_edge_ledger"})
        item = _item(payload=frozen)
        self.assertEqual(ProgressionActivationDescriptor.from_dict(item.to_dict()).to_dict(), item.to_dict())

    def test_three_activation_states_are_distinct_per_source(self):
        items = [_item(state, i) for i, state in enumerate(ActivationState)]
        self.assertEqual([x.activation_state for x in items], list(ActivationState))
        self.assertEqual(len({x.to_dict()["fields"][2]["value"]["value"] for x in items}), 3)

    def test_candidate_mapping_does_not_enable(self):
        item = _item(ActivationState.UNRESOLVED)
        self.assertTrue(item.is_blocked())
        self.assertEqual(item.fields["candidate_mapping"].require_present()["kind"], "EXACT_CONTENT_ID_RELATION")

    def test_repeat_source_occurrences_and_order_survive(self):
        batch = DescriptorBatch((_item(ActivationState.DISABLED, 1), _item(ActivationState.ENABLED, 0)))
        self.assertEqual(DescriptorBatch.from_dict(batch.to_dict()).to_dict(), batch.to_dict())

    def test_invalid_state_and_native_gate_reject(self):
        broken = _item().to_dict(); broken["fields"][2]["value"] = P.present("CANDIDATE").to_dict()
        with self.assertRaises(DescriptorError): ProgressionActivationDescriptor.from_dict(broken)
        with self.assertRaises(EvidenceBoundaryError): require_native_contract(_item(), role="progression")


if __name__ == "__main__": unittest.main()
