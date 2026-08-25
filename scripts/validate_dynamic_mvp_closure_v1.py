#!/usr/bin/env python3
"""Validate the non-production Dynamic MVP v1 state-diff handoff."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "semantics" / "4.4.54" / "dynamic_mvp_v1"


def load(name: str) -> dict:
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def trace_item(e2e: dict, item_id: str) -> dict:
    return next(item for item in e2e["trace"] if item["id"] == item_id)


def main() -> int:
    packets = load("blocker_closure_packets_v1.json")["packets"]
    assert len(packets) == 7
    assert {p["closure_status"] for p in packets} <= {
        "CLOSED_LOCAL", "CLOSED_RECONSTRUCTED"
    }
    assert all(p["DSH_implementation_contract"] for p in packets)

    e2e = load("semantic_e2e_mvp_v1.json")
    natasha = trace_item(e2e, "NATASHA-SKILL02-HEAL")
    heal = natasha["effect"]
    old_hp, new_hp = heal["hp"]
    max_hp = e2e["initial_state"]["actors"]["p1105"]["max_hp"]
    assert new_hp == min(max_hp, old_hp + heal["settled_amount"])
    assert heal["overflow"] == old_hp + heal["settled_amount"] - new_hp
    assert natasha["resource_pre_commit"]["team_skill_points"] == [1, 0]
    assert natasha["resource_post_commit"]["energy"] == [60, 90]
    assert natasha["action_completion"]["next_actor"] == "p1307"

    basic = trace_item(e2e, "BLACK-SWAN-BASIC")
    assert basic["resource_post_commit"]["team_skill_points"] == [0, 1]
    assert basic["resource_post_commit"]["energy"] == [80, 100]
    assert basic["action_completion"]["next_actor"] == "m4014030"

    enemy = trace_item(e2e, "MONSTER-SINGLE-CANDIDATE")
    assert enemy["action_completion"]["next_actor"] == "p1105"

    lethal = trace_item(e2e, "NATASHA-BASIC-LETHAL-TERMINAL")
    assert lethal["effect"]["hp"]["m4014030"] == [100, 0]
    assert lethal["death_commit"]["m4014030"] == "DEAD"
    assert lethal["terminal_check"]["battle_result"] == "VICTORY"

    legal = load("legal_action_semantic_spec_v1.json")
    assert "actor.energy >= actor.energy_max" in legal["action_rules"]["Ultra"]["legal_when"]
    closure = load("closure_v1.json")
    assert closure["freeze_mvp_candidate"] is True
    assert closure["hard_blockers"] == []
    print("DYNAMIC_MVP_CLOSURE_V1: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
