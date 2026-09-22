# -*- coding: utf-8 -*-
from __future__ import annotations

import json, sys, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorBatch, DescriptorError
from hsr_battle_agent.battle_ir.descriptors.scenario import ScenarioDescriptor, ScenarioDescriptorKind
from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue as P
from hsr_battle_agent.battle_ir.provenance import SourceProvenance
from hsr_battle_agent.battle_sandbox.evidence_boundary import EvidenceBoundaryError, require_native_contract

AUTHORITY = REPO / "data/semantics/4.4.54/full_reconstruction/astra_stage_environment_mode_v1.json"


def _blocker(): return UnknownHandle("D9-Q2", "SCENARIO", {"advance": "UNKNOWN"}, {}, ("native wave transition",)).to_dict()


def _item(kind=ScenarioDescriptorKind.WAVE_GROUP, order=0, unresolved=False, payload=None, mode=EvidenceMode.REFERENCE_MODEL):
    contract = ContractRef("scenario", "battle.descriptor.scenario", "1", mode, "9" * 64, ("freeze:scenario",))
    provenance = SourceProvenance("4.4.54", "Scenario", "Read", None, "UNKNOWN", mode.value)
    return ScenarioDescriptor(contract, mode, provenance, ("pipeline", order), order, P.present(payload if payload is not None else {"from": "ScenarioInput"}), {
        "kind": P.present(kind.value), "scenario_identity": P.present("scenario:1"),
        "source_items": P.present([{"group": "g2", "slot": "Monster1"}, {"group": "g1", "slot": "Monster0"}, {"group": "g2", "slot": "Monster1"}]),
        "environment": P.present({"family": "MazeBuff"}) if kind is ScenarioDescriptorKind.ENVIRONMENT else P.absent(),
        "mode": P.present({"collection": "maze"}) if kind is ScenarioDescriptorKind.MODE else P.absent(),
        "terminal_rule": P.present({"condition": "custom"}) if kind is ScenarioDescriptorKind.TERMINAL else P.absent(),
        "terminal_rule_class": P.present(mode.value) if kind is ScenarioDescriptorKind.TERMINAL else P.absent(),
        "knowledge": P.present("UNRESOLVED" if unresolved else "REPRESENTED"),
        "blocker": P.present(_blocker()) if unresolved else P.absent(),
    }, {"native_wave_advance": P.absent()})


class TestScenarioDescriptor(unittest.TestCase):
    def test_frozen_fixture_round_trip(self):
        frozen = json.loads(AUTHORITY.read_text(encoding="utf-8"))["pipeline"][0]
        self.assertEqual(frozen, {"from": "ScenarioInput", "to": "OfficialStageDefinition OR NormalizedScenarioDefinition", "status": "REPRESENTATION_CLOSED", "rule": "OfficialStage is an optional template; caller-owned custom IDs require no invented StageID."})
        item = _item(payload=frozen)
        self.assertEqual(ScenarioDescriptor.from_dict(item.to_dict()).to_dict(), item.to_dict())

    def test_all_scenario_kinds_are_distinct(self):
        items = [_item(kind, i) for i, kind in enumerate(ScenarioDescriptorKind)]
        self.assertEqual([x.kind for x in items], list(ScenarioDescriptorKind))

    def test_wave_group_slot_occurrence_order_and_duplicates_survive(self):
        item = _item()
        source = item.fields["source_items"].require_present()
        self.assertEqual([x["group"] for x in source], ["g2", "g1", "g2"])
        batch = DescriptorBatch((_item(order=1), _item(order=0)))
        self.assertEqual(DescriptorBatch.from_dict(batch.to_dict()).to_dict(), batch.to_dict())

    def test_unknown_scenario_is_representable_but_blocked(self):
        self.assertTrue(_item(unresolved=True).is_blocked())
        broken = _item().to_dict(); broken["fields"][2]["value"] = P.present((1, 2)).to_dict()
        with self.assertRaises(DescriptorError): ScenarioDescriptor.from_dict(broken)

    def test_sandbox_terminal_rule_stays_explicitly_separate(self):
        terminal = _item(ScenarioDescriptorKind.TERMINAL, mode=EvidenceMode.SANDBOX_EXTENSION)
        self.assertEqual(terminal.fields["terminal_rule_class"].require_present(), "SANDBOX_EXTENSION")
        self.assertIs(terminal.evidence_mode, EvidenceMode.SANDBOX_EXTENSION)

    def test_no_flattened_legacy_waves_or_native_permission(self):
        self.assertFalse(hasattr(ScenarioDescriptor, "compile_waves"))
        with self.assertRaises(EvidenceBoundaryError): require_native_contract(_item(), role="scenario")


if __name__ == "__main__": unittest.main()
