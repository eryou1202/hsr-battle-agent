"""Validate the bounded Dynamic Core packets and their non-runtime E2E replay."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "semantics" / "4.4.54" / "dynamic_core"
REQUIRED_PACKET_FIELDS = {
    "packet_id", "scope", "supported_version", "question", "inputs",
    "persistent_state_reads", "persistent_state_writes", "selected_rule",
    "alternative_candidates", "external_sources", "local_sources",
    "evidence_level", "reconstruction_status", "ordering_constraints",
    "unknowns", "unsupported_cases", "distinguishing_observations",
    "acceptance_fixtures", "DSH_implementation_boundary",
}
REQUIRED_PACKET_IDS = {
    "DYN-SP-CORE-01", "DYN-ENERGY-CORE-01", "DYN-HEAL-STATE-01",
    "DYN-LEGAL-ACTION-01", "DYN-ORDINARY-ACTION-TURN-01",
    "DYN-DAMAGE-CORE-01", "DYN-DEATH-CORE-01", "DYN-TERMINAL-CORE-01",
    "DYN-BREAK-CORE-01", "DYN-MINIMAL-EVENT-ORDER-01",
    "DYN-ORDINARY-MONSTER-AI-01",
}


def _load(name: str) -> dict:
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def validate() -> dict[str, object]:
    packets = _load("packets_v1.json")
    fixture = _load("standard_dynamic_fixture_v1.json")
    e2e = _load("semantic_e2e_v1.json")
    closure = _load("closure_v1.json")
    assert packets["schema"] == "dynamic_core_semantic_packets/1"
    assert packets["supported_version"] == "4.4.54"
    actual_ids = {packet["packet_id"] for packet in packets["packets"]}
    assert actual_ids == REQUIRED_PACKET_IDS
    for packet in packets["packets"]:
        missing = REQUIRED_PACKET_FIELDS - set(packet)
        assert not missing, (packet["packet_id"], sorted(missing))
        assert packet["supported_version"] == "4.4.54"
        assert packet["reconstruction_status"] in {
            "RECONSTRUCTION_READY", "PARTIAL", "BLOCKED", "DEFERRED"
        }
        assert packet["distinguishing_observations"]
    assert fixture["game_version"] == "4.4.54"
    assert fixture["static_scenario"]["stage_id"] == "30113121"
    assert fixture["static_scenario"]["stage_buffs"] == []
    assert fixture["static_scenario"]["waves"][0]["monster_ids"] == ["4014030"]
    assert e2e["status"] == "PARTIAL"
    assert e2e["fixture_id"] == fixture["fixture_id"]
    assert any(row["boundary"] == "positive_heal_consumer" for row in e2e["trace"])
    assert closure["overall_status"] == "DYNAMIC_CORE_RECONSTRUCTION_PARTIAL"
    assert closure["freeze_mvp_candidate"] is False
    assert closure["packet_statuses"]["DYN-DAMAGE-CORE-01"] == "RECONSTRUCTION_READY"
    return {
        "game_version": packets["supported_version"],
        "packet_count": len(packets["packets"]),
        "fixture_id": fixture["fixture_id"],
        "e2e_status": e2e["status"],
        "overall_status": closure["overall_status"],
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, sort_keys=True, indent=2))
