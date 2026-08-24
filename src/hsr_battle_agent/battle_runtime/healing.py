"""Scoped real Natasha Skill02 FormulaType 4 and event-boundary runtime."""
from __future__ import annotations

from typing import Any

from hsr_battle_agent.battle_ir.healing import (
    DispelStatusRequestBoundary,
    HealRequestBoundary,
    NatashaSkill02HealConfig,
    RealSkillExecutionBoundaryResult,
    RealSkillExternalBindings,
)
from hsr_battle_agent.battle_ir.targets import EntityRef
from hsr_battle_agent.battle_runtime.predicates import (
    fixpoint_from_int32,
    fixpoint_is_positive,
)
from hsr_battle_agent.battle_runtime.property import (
    fixedpoint_add,
    fixedpoint_multiply,
    fixedpoint_subtract,
    get_property_entry,
)

MAX_HP_PROPERTY_ID = 1
CURRENT_HP_PROPERTY_ID = 10
HEAL_RATIO_PROPERTY_ID = 124
HEAL_TAKEN_RATIO_PROPERTY_ID = 127

_ONE_RAW = fixpoint_from_int32(1)
_EXPECTED_ABILITY = "Avatar_Natasha_00_Skill02_Phase02"
_BOUNDARY_BLOCKERS = (
    "DispelStatus effect consumer is not recovered",
    "positive HealData event consumer and CurrentHP mutation are not recovered",
    "generic post-action recharge writer/formula is not recovered",
)


class HealSemanticError(Exception):
    """Base error for the explicitly scoped real-heal runtime."""


class RealSkillTurnMismatchError(HealSemanticError):
    pass


class UnsupportedSpecialHealComponentError(HealSemanticError):
    pass


class RequiredHealPropertyMissingError(HealSemanticError):
    pass


def heal_formula_type4_ordinary(
    *,
    target_max_hp_raw: int,
    target_current_hp_raw: int,
    heal_percentage_raw: int,
    modify_value_raw: int,
    healer_heal_ratio_raw: int,
    target_heal_taken_ratio_raw: int,
) -> int:
    """M504575 FormulaType 4 in the ordinary non-special, non-rally branch.

    `SetupHealData` initializes the special factor to exactly one for this
    branch, so no unrecovered generic FixPoint division is needed here.
    """
    base = fixedpoint_subtract(target_max_hp_raw, target_current_hp_raw)
    configured = fixedpoint_add(
        fixedpoint_multiply(base, heal_percentage_raw), modify_value_raw
    )
    ordinary_factor = fixedpoint_add(
        fixedpoint_add(_ONE_RAW, healer_heal_ratio_raw),
        target_heal_taken_ratio_raw,
    )
    amount = fixedpoint_multiply(configured, ordinary_factor)
    # Preserve the native ordinary special-factor multiplication: defaults
    # are ExtraHealAddedRatio=0, ExtraHealBase=100, ExtraHealConvert=0, hence 1.
    amount = fixedpoint_multiply(amount, _ONE_RAW)
    return amount if fixpoint_is_positive(amount) else 0


def _property_raw(state: Any, entity: EntityRef, property_id: int, name: str) -> int:
    entry = get_property_entry(state, entity, property_id)
    if entry is None:
        raise RequiredHealPropertyMissingError(
            f"entity {entity.runtime_id} has no required {name} property {property_id}"
        )
    return entry.materialized


def _require_active_caster(state: Any, caster: EntityRef) -> None:
    timeline = getattr(state, "turn_timeline", None)
    if not isinstance(timeline, dict):
        raise RealSkillTurnMismatchError("turn timeline is not initialized")
    if timeline.get("phase") != "active":
        raise RealSkillTurnMismatchError("real skill requires an active turn")
    if timeline.get("current_actor_runtime_id") != caster.runtime_id:
        raise RealSkillTurnMismatchError("caster is not the active turn actor")


def execute_natasha_skill02_boundary(
    state: Any,
    caster: EntityRef,
    config: NatashaSkill02HealConfig,
    bindings: RealSkillExternalBindings,
) -> RealSkillExecutionBoundaryResult:
    """Run the real content slice up to its unresolved effect consumers.

    This function performs no HP or dispel mutation.  It returns the ordered
    request boundaries that a future recovered event consumer must apply.
    """
    if not isinstance(caster, EntityRef):
        raise TypeError("caster must be EntityRef")
    if not isinstance(config, NatashaSkill02HealConfig):
        raise TypeError("config must be NatashaSkill02HealConfig")
    if not isinstance(bindings, RealSkillExternalBindings):
        raise TypeError("bindings must be RealSkillExternalBindings")
    if (
        config.ability_name != _EXPECTED_ABILITY
        or config.parent_discriminator != 1960
        or config.predicate_discriminator != 496
        or config.dispel_discriminator != 1199
        or config.heal_discriminator != 1481
        or config.heal_formula_type != 4
        or config.target_discriminator != 12
        or config.target_name != "AbilityTargetEntity"
    ):
        raise HealSemanticError("config is outside the accepted real Natasha slice")
    _require_active_caster(state, caster)

    target = bindings.ability_target
    if not bindings.predicate_satisfied:
        return RealSkillExecutionBoundaryResult(
            ability_name=config.ability_name,
            caster=caster,
            target=target,
            predicate_satisfied=False,
            predicate_provenance=bindings.predicate_provenance,
            dispel_request=None,
            heal_request=None,
            status="PREDICATE_FALSE_NO_SUCCESS_TASKS",
            blockers=("BySkillPointActivated semantics supplied externally",),
        )
    if not bindings.ordinary_healer_branch:
        raise UnsupportedSpecialHealComponentError(
            "healer component kind 225 special properties require the deferred branch"
        )

    dispel_numbers = bindings.resolve(config.dispel_numbers)
    heal_percentage = bindings.resolve(config.heal_percentage)
    modify_value = bindings.resolve(config.modify_value)
    target_max = _property_raw(state, target, MAX_HP_PROPERTY_ID, "MaxHP")
    target_current = _property_raw(state, target, CURRENT_HP_PROPERTY_ID, "CurrentHP")
    healer_ratio = _property_raw(state, caster, HEAL_RATIO_PROPERTY_ID, "HealRatio")
    target_taken = _property_raw(
        state, target, HEAL_TAKEN_RATIO_PROPERTY_ID, "HealTakenRatio"
    )
    amount = heal_formula_type4_ordinary(
        target_max_hp_raw=target_max,
        target_current_hp_raw=target_current,
        heal_percentage_raw=heal_percentage.value_raw,
        modify_value_raw=modify_value.value_raw,
        healer_heal_ratio_raw=healer_ratio,
        target_heal_taken_ratio_raw=target_taken,
    )
    dispel_request = DispelStatusRequestBoundary(
        caster=caster,
        target=target,
        numbers_raw=dispel_numbers.value_raw,
        order=config.dispel_order,
        config_ref=f"{config.content_artifact_ref}#0xBC9A24",
        resolution_provenance=dispel_numbers.provenance,
    )
    heal_request = HealRequestBoundary(
        healer=caster,
        target=target,
        amount_raw=amount,
        observed_current_hp_raw=target_current,
        formula_type=config.heal_formula_type,
        config_ref=f"{config.content_artifact_ref}#0xBC9A4B",
        dynamic_resolution_provenance=(
            heal_percentage.provenance,
            modify_value.provenance,
            bindings.target_provenance,
            bindings.healer_branch_provenance,
        ),
    )
    return RealSkillExecutionBoundaryResult(
        ability_name=config.ability_name,
        caster=caster,
        target=target,
        predicate_satisfied=True,
        predicate_provenance=bindings.predicate_provenance,
        dispel_request=dispel_request,
        heal_request=heal_request,
        status="ORDERED_EFFECT_BOUNDARIES_EMITTED",
        blockers=_BOUNDARY_BLOCKERS,
    )
