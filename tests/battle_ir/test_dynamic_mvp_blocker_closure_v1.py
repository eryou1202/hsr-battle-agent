"""Machine-check the non-production Dynamic MVP v1 handoff fixtures."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SEMANTICS = ROOT / "data" / "semantics" / "4.4.54" / "dynamic_mvp_v1"


def _load(name: str) -> dict:
    return json.loads((SEMANTICS / name).read_text(encoding="utf-8"))


def _trace_item(e2e: dict, item_id: str) -> dict:
    return next(item for item in e2e["trace"] if item["id"] == item_id)


def test_all_mvp_blockers_have_a_permitted_closure_status() -> None:
    packets = _load("blocker_closure_packets_v1.json")["packets"]
    assert len(packets) == 7
    assert {packet["closure_status"] for packet in packets} <= {
        "CLOSED_LOCAL",
        "CLOSED_RECONSTRUCTED",
    }
    assert all(packet["DSH_implementation_contract"] for packet in packets)


def test_heal_hp_transition_is_positive_and_clamped() -> None:
    e2e = _load("semantic_e2e_mvp_v1.json")
    heal = _trace_item(e2e, "NATASHA-SKILL02-HEAL")["effect"]
    old_hp, new_hp = heal["hp"]
    max_hp = e2e["initial_state"]["actors"]["p1105"]["max_hp"]
    amount = heal["settled_amount"]
    assert new_hp == min(max_hp, old_hp + amount)
    assert heal["overflow"] == old_hp + amount - new_hp


def test_sp_and_energy_gate_mutation_contracts() -> None:
    e2e = _load("semantic_e2e_mvp_v1.json")
    natasha = _trace_item(e2e, "NATASHA-SKILL02-HEAL")
    assert natasha["legal_action"]["result"] == "LEGAL"
    assert natasha["resource_pre_commit"]["team_skill_points"] == [1, 0]
    assert natasha["resource_post_commit"]["energy"] == [60, 90]

    basic = _trace_item(e2e, "BLACK-SWAN-BASIC")
    assert basic["resource_pre_commit"]["team_skill_points"] == [0, 0]
    assert basic["resource_post_commit"]["team_skill_points"] == [0, 1]
    assert basic["resource_post_commit"]["energy"] == [80, 100]

    legal = _load("legal_action_semantic_spec_v1.json")
    assert "actor.energy >= actor.energy_max" in legal["action_rules"]["Ultra"]["legal_when"]


def test_av_recharge_orders_the_next_ordinary_actor() -> None:
    e2e = _load("semantic_e2e_mvp_v1.json")
    natasha = _trace_item(e2e, "NATASHA-SKILL02-HEAL")["action_completion"]
    assert natasha["recharge"]["p1105"] == 100
    assert natasha["ordered_remaining_delay"][0] == ["p1307", 20]
    assert natasha["next_actor"] == "p1307"

    enemy = _trace_item(e2e, "MONSTER-SINGLE-CANDIDATE")["action_completion"]
    assert enemy["ordered_remaining_delay"][0] == ["p1105", 70]
    assert enemy["next_actor"] == "p1105"


def test_death_target_domain_and_terminal_transition() -> None:
    e2e = _load("semantic_e2e_mvp_v1.json")
    lethal = _trace_item(e2e, "NATASHA-BASIC-LETHAL-TERMINAL")
    assert lethal["effect"]["hp"]["m4014030"] == [100, 0]
    assert lethal["death_commit"]["m4014030"] == "DEAD"
    assert lethal["death_commit"]["action_domain"] == "removed"
    assert lethal["death_commit"]["target_domain"] == "removed"
    assert lethal["terminal_check"]["battle_result"] == "VICTORY"


def test_freeze_has_no_hard_blocker() -> None:
    closure = _load("closure_v1.json")
    assert closure["freeze_mvp_candidate"] is True
    assert closure["hard_blockers"] == []
