"""Deterministic reference evaluator for corpus Predicate AST families.

This is the COMPILER-PREDICATE-001 evaluator companion.  Boolean composition
and value comparisons are fully deterministic; entity/modifier/behavior-flag/
wave/skill facts are supplied through explicit ``PredicateContext`` hooks so
the evaluator never guesses battle state.  Unsupported predicate types raise
``UnsupportedPredicate`` and reject the containing behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from .dynamic_value_reference import DynamicValueSemanticError, dynamic_key_from_payload, value_spec_from_payload
from .target_semantics_reference import alias_from_payload, resolve_target_alias

PredicateError = DynamicValueSemanticError


class UnsupportedPredicate(PredicateError):
    """The predicate type has no selected evaluator yet."""


DynamicGetter = Callable[[str | None, str], Decimal | int | float | str]
EntityFlagGetter = Callable[[str, str], bool]
EntityTeamGetter = Callable[[str], str]
EntityAliveGetter = Callable[[str], bool]
EntityCharacterGetter = Callable[[str], int | None]
ModifierPresenceGetter = Callable[[str, str, bool, bool], bool]
RandomGetter = Callable[[], Decimal]
WeaknessGetter = Callable[[str, str], bool]
SummonRelationGetter = Callable[[str, str], bool]
SomatoTypeGetter = Callable[[str], str | None]
ParamStringGetter = Callable[[str], str | None]


@dataclass(frozen=True)
class PredicateContext:
    """Explicit battle facts needed by predicate evaluation."""

    resolve_target: Callable[[str], Sequence[str]] | None = None
    dynamic_get: DynamicGetter | None = None
    has_modifier: ModifierPresenceGetter | None = None
    has_behavior_flag: EntityFlagGetter | None = None
    entity_team: EntityTeamGetter | None = None
    entity_alive: EntityAliveGetter | None = None
    entity_character_id: EntityCharacterGetter | None = None
    random_01: RandomGetter | None = None
    skill_type: str = ""
    skill_name: str = ""
    attack_types: tuple[str, ...] = ()
    wave_count: int = 1
    challenge_left: int | None = None
    monster_rank: int | None = None
    rank_trigger_hashes: tuple[int, ...] = ()
    skill_point_trigger_keys: tuple[str, ...] = ()
    ability_level: int = 80
    in_turn_based_game_mode_state: bool = True
    control_skill_disabled: bool = False
    triggered_block_damage: bool = False
    last_battle_win: bool | None = None
    maze_skill_affects_current_wave: bool = False
    current_hp: Decimal | None = None
    current_max_hp: Decimal | None = None
    current_red_stance_count: int = 0
    current_entity_id: str | None = None
    current_turn_owner_id: str | None = None
    current_turn_action_entity_id: str | None = None
    change_value_1: Decimal | None = None
    change_value_2: Decimal | None = None
    has_stance_weak: WeaknessGetter | None = None
    has_summon_relation: SummonRelationGetter | None = None
    entity_somato_type: SomatoTypeGetter | None = None
    param_string: ParamStringGetter | None = None
    modifier_callback_name: str = ""
    npc_monster_purpose_type: str = ""

    def targets(self, payload: Mapping[str, Any], default_alias: str = "Caster") -> tuple[str, ...]:
        raw = payload.get("TargetType")
        alias = alias_from_payload(raw) if isinstance(raw, Mapping) and isinstance(raw.get("Alias"), str) else default_alias
        if self.resolve_target is None:
            raise UnsupportedPredicate("PredicateContext.resolve_target hook is required")
        return tuple(self.resolve_target(alias))


def _d(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception as error:  # noqa: BLE001
        raise PredicateError(f"non-numeric predicate value {value!r}") from error


def _compare(left: Any, compare_type: str, right: Any) -> bool:
    a, b = _d(left), _d(right)
    key = str(compare_type).lower()
    if key in {"equal", "=="}:
        return a == b
    if key in {"notequal", "!="}:
        return a != b
    if key in {"less", "<"}:
        return a < b
    if key in {"lessequal", "<="}:
        return a <= b
    if key in {"greater", ">"}:
        return a > b
    if key in {"greaterequal", ">="}:
        return a >= b
    raise UnsupportedPredicate(f"unsupported compare type {compare_type}")


def _team(value: Any) -> str:
    if isinstance(value, str):
        lower = value.lower()
        if "dark" in lower:
            return "dark"
        if "light" in lower:
            return "light"
    raise UnsupportedPredicate(f"unsupported team value {value!r}")


def _value_of(payload: Mapping[str, Any], context: PredicateContext) -> Decimal:
    spec = value_spec_from_payload(payload)
    if spec.is_dynamic:
        if context.dynamic_get is None:
            raise UnsupportedPredicate("dynamic comparison requires PredicateContext.dynamic_get")
        resolver = lambda key: context.dynamic_get(None, str(key))
        return spec.evaluate(resolver)
    if spec.fixed_value is None:
        raise PredicateError("predicate value has no fixed value")
    return spec.fixed_value


def _children(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    predicate_list = payload.get("PredicateList")
    if isinstance(predicate_list, list):
        return tuple(item for item in predicate_list if isinstance(item, Mapping))
    singular = payload.get("Predicate")
    if isinstance(singular, Mapping):
        return (singular,)
    return ()


def evaluate_predicate(payload: Any, context: PredicateContext) -> bool:
    """Evaluate one predicate AST payload deterministically."""
    if not isinstance(payload, Mapping):
        raise PredicateError("predicate payload must be a mapping")
    source_type = str(payload.get("$type", ""))
    key = source_type.rsplit(".", 1)[-1]
    inverse = bool(payload.get("Inverse", False))
    result = _evaluate_named(key, payload, context)
    return (not result) if inverse else result


def _evaluate_named(key: str, payload: Mapping[str, Any], context: PredicateContext) -> bool:
    if key == "ByAnd":
        children = _children(payload)
        return all(evaluate_predicate(child, context) for child in children)
    if key == "ByAny":
        children = _children(payload)
        return any(evaluate_predicate(child, context) for child in children)
    if key == "ByNot":
        children = _children(payload)
        if len(children) != 1:
            raise PredicateError("ByNot requires exactly one child")
        return not evaluate_predicate(children[0], context)
    if key == "ByTargetTeam":
        team = _team(payload.get("Team"))
        if context.entity_team is None:
            raise UnsupportedPredicate("ByTargetTeam requires entity_team hook")
        return all(context.entity_team(entity) == team for entity in context.targets(payload))
    if key == "ByIsContainModifier":
        if context.has_modifier is None:
            raise UnsupportedPredicate("ByIsContainModifier requires has_modifier hook")
        modifier = payload.get("ModifierName")
        modifier_name = modifier.get("Value") if isinstance(modifier, Mapping) else str(modifier)
        added_or_alive = bool(payload.get("AddedOrAlive", False))
        caster_filter = payload.get("CasterFilter")
        caster_id = None
        if isinstance(caster_filter, Mapping):
            ids = context.targets({"TargetType": caster_filter})
            caster_id = ids[0] if ids else None
        return any(context.has_modifier(entity, modifier_name, added_or_alive, caster_id is not None and entity == caster_id) for entity in context.targets(payload, "ModifierOwnerEntity"))
    if key == "ByContainBehaviorFlag":
        if context.has_behavior_flag is None:
            raise UnsupportedPredicate("ByContainBehaviorFlag requires has_behavior_flag hook")
        flag = str(payload.get("Flag", ""))
        return any(context.has_behavior_flag(entity, flag) for entity in context.targets(payload, "ModifierOwnerEntity"))
    if key == "ByCompareDynamicValue":
        if context.dynamic_get is None:
            raise UnsupportedPredicate("ByCompareDynamicValue requires dynamic_get hook")
        scope = payload.get("ContextScope")
        scope = str(scope) if isinstance(scope, str) and scope else None
        dynamic_key = dynamic_key_from_payload(payload.get("DynamicKey"))
        actual = context.dynamic_get(scope, dynamic_key)
        expected = _value_of(payload.get("CompareValue", {}), context)
        return _compare(actual, payload.get("CompareType", "Equal"), expected)
    if key == "ByCompareModifierValue":
        if context.dynamic_get is None:
            raise UnsupportedPredicate("ByCompareModifierValue requires dynamic_get hook")
        scope = str(payload.get("ContextScope") or "ContextModifier")
        value_type = str(payload.get("ValueType") or payload.get("ModifierName") or "")
        actual = context.dynamic_get(scope, value_type)
        expected = _value_of(payload.get("CompareValue", {}), context)
        return _compare(actual, payload.get("CompareType", "Equal"), expected)
    if key == "ByRandomChance":
        if context.random_01 is None:
            raise UnsupportedPredicate("ByRandomChance requires random_01 hook")
        chance = _value_of(payload.get("Chance", {}), context)
        return context.random_01() < chance
    if key == "ByHaveEnemyAlive":
        alias = "AllEnemyWithUnSelectable" if payload.get("IncludeUnselectable") else "AllEnemy"
        return any(context.entity_alive(entity) if context.entity_alive is not None else True for entity in context.targets({"TargetType": {"Alias": alias}}))
    if key == "ByCasterAliveOrLimbo":
        return any(context.entity_alive(entity) if context.entity_alive is not None else True for entity in context.targets(payload, "Caster"))
    if key == "ByIsTargetValid":
        alive_only = bool(payload.get("AliveOnly", False))
        for entity in context.targets(payload, "AbilityTargetEntity"):
            if context.entity_alive is None:
                return bool(entity)
            if not alive_only or context.entity_alive(entity):
                return True
        return False
    if key == "ByCurrentSkillType":
        expected = payload.get("SkillType")
        if expected is None:
            return bool(context.skill_type)
        return context.skill_type == str(expected)
    if key == "ByCurrentSkillName":
        expected = payload.get("SkillName")
        return bool(expected) and context.skill_name == str(expected)
    if key == "ByAttackType":
        expected = tuple(str(item) for item in payload.get("AttackTypes", []))
        return any(item in expected for item in context.attack_types)
    if key == "ByCompareCharacterID":
        expected = int(_value_of(payload.get("TargetCharacterID", {}), context))
        if context.entity_character_id is None:
            raise UnsupportedPredicate("ByCompareCharacterID requires entity_character_id hook")
        return any(context.entity_character_id(entity) == expected for entity in context.targets(payload, "ModifierOwnerEntity"))
    if key == "ByCompareCharacterNumber":
        expected = int(_value_of(payload.get("CompareNumber", {}), context))
        actual = sum(
            1
            for entity in context.targets(payload, "AllTeamMember")
            if context.entity_alive is not None and context.entity_alive(entity)
        )
        return _compare(actual, payload.get("CompareType", "Equal"), expected)
    if key == "ByCompareWaveCount":
        return _compare(context.wave_count, payload.get("CompareType", "Equal"), _value_of(payload.get("CompareValue", {}), context))
    if key == "ByCompareChallengeLeft":
        if context.challenge_left is None:
            raise UnsupportedPredicate("ByCompareChallengeLeft requires challenge_left")
        expected = payload.get("CompareValue", 0)
        if isinstance(expected, Mapping):
            expected = _value_of(expected, context)
        return _compare(context.challenge_left, payload.get("CompareType", "Equal"), expected)
    if key == "ByCompareHP":
        if context.current_hp is None:
            raise UnsupportedPredicate("ByCompareHP requires current_hp")
        return _compare(context.current_hp, payload.get("CompareType", "Equal"), _value_of(payload.get("CompareValue", {}), context))
    if key == "ByCompareHPRatio":
        if context.current_hp is None or context.current_max_hp in (None, 0):
            raise UnsupportedPredicate("ByCompareHPRatio requires current_hp and current_max_hp")
        ratio = context.current_hp / context.current_max_hp
        return _compare(ratio, payload.get("CompareType", "Equal"), _value_of(payload.get("CompareValue", {}), context))
    if key == "ByCompareMonsterRank":
        if context.monster_rank is None:
            raise UnsupportedPredicate("ByCompareMonsterRank requires monster_rank")
        return _compare(context.monster_rank, payload.get("CompareType", "Equal"), payload.get("CompareValue", 0))
    if key == "ByCompareAbilityProperty":
        property_name = str(payload.get("Property", ""))
        actual = {"Level": context.ability_level}.get(property_name)
        if actual is None:
            raise UnsupportedPredicate(f"ability property {property_name}")
        return _compare(actual, payload.get("CompareType", "Equal"), _value_of(payload.get("CompareValue", {}), context))
    if key == "ByCompareTarget":
        compare_alias = payload.get("CompareType")
        compare_alias = compare_alias.get("Alias") if isinstance(compare_alias, Mapping) else compare_alias
        left = context.targets(payload)
        right = context.targets({"TargetType": {"Alias": compare_alias}})
        return bool(left) and left == right
    if key == "ByTargetListIntersects":
        first = set(context.targets({"TargetType": payload.get("FirstTargetType")}))
        second = set(context.targets({"TargetType": payload.get("SecondTargetType")}))
        return bool(first & second)
    if key == "ByRankActivated":
        trigger = payload.get("TriggerKey")
        trigger_hash = trigger.get("Hash") if isinstance(trigger, Mapping) else trigger
        return int(trigger_hash) in context.rank_trigger_hashes
    if key == "BySkillPointActivated":
        return str(payload.get("PointTriggerKey")) in context.skill_point_trigger_keys
    if key == "ByInTurnBasedGameModeState":
        return context.in_turn_based_game_mode_state
    if key == "ByIsTurnOwnerEntity":
        return context.current_entity_id == context.current_turn_owner_id
    if key == "ByIsTurnActionEntity":
        return context.current_entity_id == context.current_turn_action_entity_id
    if key == "ByCompareChangeValue":
        index = int(payload.get("ChangeValueIndex", 1))
        value = context.change_value_1 if index == 1 else context.change_value_2
        if value is None:
            raise UnsupportedPredicate(f"change value {index}")
        return _compare(value, payload.get("CompareType", "Equal"), _value_of(payload.get("CompareValue", {}), context))
    if key == "ByCompareRedStanceCount":
        return _compare(context.current_red_stance_count, payload.get("CompareType", "Equal"), _value_of(payload.get("CompareValue", {}), context))
    if key == "ByHasStanceWeak":
        if context.has_stance_weak is None:
            raise UnsupportedPredicate("ByHasStanceWeak requires has_stance_weak hook")
        weak_type = payload.get("WeakType")
        damage_type = weak_type.get("DamageType") if isinstance(weak_type, Mapping) else weak_type
        if not damage_type:
            raise UnsupportedPredicate("ByHasStanceWeak missing WeakType.DamageType")
        target_alias = payload.get("TargetType", {"Alias": "ModifierOwnerEntity"})
        return any(context.has_stance_weak(entity, str(damage_type)) for entity in context.targets({"TargetType": target_alias}, "ModifierOwnerEntity"))
    if key == "ByHasSummonRelation":
        if context.has_summon_relation is None:
            raise UnsupportedPredicate("ByHasSummonRelation requires has_summon_relation hook")
        servant = context.targets({"TargetType": payload.get("ServantType")}, "ModifierOwnerEntity")
        summoner = context.targets({"TargetType": payload.get("SummonerType")}, "ParamEntity")
        if not servant or not summoner:
            return False
        return context.has_summon_relation(servant[0], summoner[0])
    if key == "ByCompareSomatoType":
        if context.entity_somato_type is None:
            raise UnsupportedPredicate("ByCompareSomatoType requires entity_somato_type hook")
        expected = {str(item) for item in payload.get("SomatoTypes", [])}
        return any(context.entity_somato_type(entity) in expected for entity in context.targets({"TargetType": payload.get("Target")}, "ModifierOwnerEntity"))
    if key == "ByCompareParamString":
        if context.param_string is None:
            raise UnsupportedPredicate("ByCompareParamString requires param_string hook")
        expected = payload.get("CompareValue")
        expected = expected.get("Value") if isinstance(expected, Mapping) else expected
        return context.param_string(str(payload.get("ParamKey", ""))) == str(expected)
    if key == "ByCheckModifierCallBackName":
        expected = payload.get("ModifierName")
        expected = expected.get("Value") if isinstance(expected, Mapping) else expected
        return context.modifier_callback_name == str(expected)
    if key == "ByCheckModifierCallBackBehaviorFlag":
        if context.has_behavior_flag is None:
            raise UnsupportedPredicate("ByCheckModifierCallBackBehaviorFlag requires has_behavior_flag hook")
        flag = str(payload.get("Flag", ""))
        return any(context.has_behavior_flag(entity, flag) for entity in context.targets(payload, "ModifierOwnerEntity"))
    if key == "AdventureByNPCMonsterPurposeType":
        return context.npc_monster_purpose_type == str(payload.get("PurposeType", ""))
    if key == "ByIsDamageType":
        expected = tuple(str(item) for item in payload.get("DamageTypeList", []))
        return any(item in expected for item in context.attack_types)
    if key == "ByIsControlSkillDisable":
        return context.control_skill_disabled
    if key == "ByIsTriggeredBlockDamage":
        return context.triggered_block_damage
    if key == "ByIsLastBattleWin":
        return bool(context.last_battle_win)
    if key == "ByIsMazeSkillAffectCurrentWave":
        return context.maze_skill_affects_current_wave
    raise UnsupportedPredicate(source_type_for_error(key))


def source_type_for_error(key: str) -> str:
    return f"RPG.GameCore.{key}"
