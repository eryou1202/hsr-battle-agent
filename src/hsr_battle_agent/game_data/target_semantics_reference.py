"""Deterministic reference semantics for TargetAlias resolution (TARGET-001).

This module is a reconstruction reference, not a production runtime.  It
combines the E4 local TaskContext target primitives
(``target_selector_batch_05.json``) with the 37 distinct TargetAlias values
observed in the repaired TurnBasedGameData corpus and selects deterministic
team/faction/position rules for each family.

Unsupported or corpus-rare aliases raise ``UnsupportedTargetAlias`` instead of
silently resolving to an empty list.  Callers must provide an explicit
``BattleTargetContext``; alias resolution never reads source JSON.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .dynamic_value_reference import DynamicValueSemanticError


class UnsupportedTargetAlias(DynamicValueSemanticError):
    """The alias family has no selected deterministic resolution yet."""


@dataclass(frozen=True)
class EntitySnapshot:
    entity_id: str
    team: str
    alive: bool = True
    selectable: bool = True
    position: tuple[int, int] = (0, 0)

    def __post_init__(self) -> None:
        if self.team not in {"light", "dark", "neutral"}:
            raise ValueError(f"unknown team {self.team!r}")
        if len(self.position) != 2:
            raise ValueError("position must be (row, column)")

    @staticmethod
    def from_mapping(value: Mapping) -> "EntitySnapshot":
        entity_id = str(value.get("entity_id", ""))
        if not entity_id:
            raise ValueError("entity_id is required")
        team = str(value.get("team", "neutral"))
        alive = bool(value.get("alive", True))
        selectable = bool(value.get("selectable", True))
        position = value.get("position", (0, 0))
        return EntitySnapshot(entity_id, team, alive, selectable, (int(position[0]), int(position[1])))


@dataclass(frozen=True)
class BattleTargetContext:
    """Explicit battle context required by alias resolution."""

    entities: Mapping[str, EntitySnapshot]
    caster_id: str | None = None
    ability_target_id: str | None = None
    param_entity_ids: tuple[str, ...] = ()
    param_entity2_ids: tuple[str, ...] = ()
    damage_attacker_id: str | None = None
    damage_defender_id: str | None = None
    current_turn_action_entity_id: str | None = None
    current_turn_owner_id: str | None = None
    modifier_owner_id: str | None = None
    snapshot_property_entity_id: str | None = None
    snapshot_actual_owner_id: str | None = None
    level_entity_id: str | None = None
    skill_point_entity_id: str | None = None
    ability_target_list: tuple[str, ...] = ()
    skill_target_list: tuple[str, ...] = ()
    attack_target_list: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entities, Mapping) or not self.entities:
            raise ValueError("entities must be a non-empty mapping")

    def snapshot(self, entity_id: str | None) -> EntitySnapshot | None:
        if entity_id is None:
            return None
        return self.entities.get(entity_id)


def _team_entities(context: BattleTargetContext, team: str, *, selectable_only: bool, alive_only: bool = True) -> tuple[str, ...]:
    entities = [
        entity
        for entity in context.entities.values()
        if entity.team == team
        and (not alive_only or entity.alive)
        and (not selectable_only or entity.selectable)
    ]
    entities.sort(key=lambda entity: (entity.position[0], entity.position[1], entity.entity_id))
    return tuple(entity.entity_id for entity in entities)


def _opposing_team(team: str) -> str:
    return "dark" if team == "light" else "light" if team == "dark" else "neutral"


def _position_rank(entity: EntitySnapshot | None) -> tuple[int, int]:
    if entity is None:
        return (10**9, 10**9)
    return entity.position


def _adjoin(context: BattleTargetContext, center_id: str | None, *, selectable_only: bool = True) -> tuple[str, ...]:
    center = context.snapshot(center_id)
    if center is None:
        return ()
    row, column = center.position
    candidates = []
    for entity in context.entities.values():
        if entity.entity_id == center.entity_id or entity.team != center.team or not entity.alive:
            continue
        if selectable_only and not entity.selectable:
            continue
        # Adjacent in the same row (left/right) or immediately behind in
        # formation order; diagonal adjacency is not selected.
        if entity.position[0] == row and abs(entity.position[1] - column) == 1:
            candidates.append(entity)
    candidates.sort(key=lambda entity: (entity.position[0], entity.position[1], entity.entity_id))
    return tuple(entity.entity_id for entity in candidates)


def resolve_target_alias(alias: str, context: BattleTargetContext) -> tuple[str, ...]:
    """Resolve one TargetAlias to an ordered entity-id tuple."""
    key = alias.strip()
    if not key:
        return ()
    caster = context.snapshot(context.caster_id)
    owner = context.snapshot(context.modifier_owner_id)
    if key == "Caster":
        return (context.caster_id,) if context.caster_id else ()
    if key == "AbilityTargetEntity":
        return (context.ability_target_id,) if context.ability_target_id else ()
    if key == "AbilityTargetList" or key == "AbilityTargetEntityList":
        return tuple(context.ability_target_list)
    if key == "AttackTargetList":
        return tuple(context.attack_target_list)
    if key == "SkillTargetEntityList":
        return tuple(context.skill_target_list)
    if key == "ParamEntity":
        return context.param_entity_ids
    if key == "ParamEntity2":
        return context.param_entity2_ids
    if key == "ParamEntityList":
        return context.param_entity_ids
    if key == "DamageAttackerEntity":
        return (context.damage_attacker_id,) if context.damage_attacker_id else ()
    if key == "DamageDefenderEntity":
        return (context.damage_defender_id,) if context.damage_defender_id else ()
    if key == "CurrentTurnActionEntity":
        return (context.current_turn_action_entity_id,) if context.current_turn_action_entity_id else ()
    if key == "CurrentTurnOwnerEntity":
        return (context.current_turn_owner_id,) if context.current_turn_owner_id else ()
    if key == "ModifierOwnerEntity":
        return (context.modifier_owner_id,) if context.modifier_owner_id else ()
    if key == "SnapshotPropertyEntity":
        return (context.snapshot_property_entity_id,) if context.snapshot_property_entity_id else ()
    if key == "SnapshotEntityActualOwner":
        return (context.snapshot_actual_owner_id,) if context.snapshot_actual_owner_id else ()
    if key == "LevelEntity":
        return (context.level_entity_id,) if context.level_entity_id else ()
    if key == "SkillPointEntity":
        return (context.skill_point_entity_id,) if context.skill_point_entity_id else ()
    if key == "AllEnemy":
        team = _opposing_team(caster.team) if caster else "dark"
        return _team_entities(context, team, selectable_only=True)
    if key == "AllEnemyWithUnSelectable" or key == "AllEnemyWithUnSelectable.RemoveBattleEvent":
        team = _opposing_team(caster.team) if caster else "dark"
        return _team_entities(context, team, selectable_only=False)
    if key == "AllDarkTeam":
        return _team_entities(context, "dark", selectable_only=True)
    if key == "AllLightTeam":
        return _team_entities(context, "light", selectable_only=True)
    if key == "AllTeamMember":
        team = caster.team if caster else "neutral"
        return _team_entities(context, team, selectable_only=False)
    if key == "AllTeammate":
        team = caster.team if caster else "neutral"
        return _team_entities(context, team, selectable_only=True)
    if key == "AllTeammateWithUnselectable.WithBattleEvent" or key == "AllTeamMemberWithUnselectable.WithBattleEvent":
        team = caster.team if caster else "neutral"
        return _team_entities(context, team, selectable_only=False)
    if key == "LightTeamEntity":
        return _team_entities(context, "light", selectable_only=False)
    if key == "DarkTeamEntity":
        return _team_entities(context, "dark", selectable_only=False)
    if key == "DarkTeamCenter":
        dark = _team_entities(context, "dark", selectable_only=True)
        return (dark[0],) if dark else ()
    if key == "ModifierOwnerAdjoinEntity":
        return _adjoin(context, context.modifier_owner_id)
    if key == "AbilityTargetAdjoinEntity":
        return _adjoin(context, context.ability_target_id)
    if key == "ParamEntityAdjoinEntity":
        return _adjoin(context, context.param_entity_ids[0] if context.param_entity_ids else None)
    if key == "ModifierOwnerAllEnemy":
        team = _opposing_team(owner.team) if owner else "dark"
        return _team_entities(context, team, selectable_only=True)
    if key == "ModifierOwnerSkillTargetEntityList":
        return tuple(context.skill_target_list)
    if key == "CasterWithAllEnemy":
        enemies = resolve_target_alias("AllEnemy", context)
        return ((context.caster_id,) if context.caster_id else ()) + enemies
    if key == "AdvLocalPlayer":
        return _team_entities(context, "light", selectable_only=True)
    if key == "HimekoNova_00_AssistTarget":
        # Special follow-up assist target: outside the generic TARGET-001
        # packet until the Himeko special-mechanic packet selects it.
        raise UnsupportedTargetAlias(key)
    raise UnsupportedTargetAlias(key)


def alias_from_payload(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        alias = value.get("Alias")
        if isinstance(alias, str) and alias:
            return alias
    raise DynamicValueSemanticError(f"TargetAlias payload is not a named alias: {value!r}")


def resolve_target_payload(value: Any, context: BattleTargetContext) -> tuple[str, ...]:
    return resolve_target_alias(alias_from_payload(value), context)
