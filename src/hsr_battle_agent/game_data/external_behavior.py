"""Normalize the reviewed external behavior slice without runtime source access.

This module is a reconstruction adapter, not a battle runtime.  It reads a
pinned raw snapshot and produces lossless-reference canonical behavior records
that later compiler work can consume offline.

Recursive lifting covers:

- every entrypoint task array (``On*`` root fields),
- every Modifier ``_CallbackList``, both nested inside an Ability's
  ``Modifiers`` map and a Modifier record's own top-level ``_CallbackList``,
- ``SuccessTaskList`` / ``FailedTaskList`` / ``FailTaskList`` / ``TaskList`` /
  ``Retarget.TaskList`` / loop children / ``Predicate.PredicateList`` and any
  other list of typed task payloads,
- singular ``Predicate`` mappings, which are lifted as ``PREDICATE_AST`` child
  groups rather than left inside the parent's raw arguments,
- ``TaskListTemplate`` definitions (preserved as canonical template nodes with
  an invocation link from ``IncludeTaskListTemplate``), and
- ``DynamicValues`` definitions (preserved as canonical definition records).
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .external_reconstruction import CONTENT_VERSION, default_external_root
from .nanoka_content import stable_hash, write_json


TURN_BASED_BEHAVIOR_PATHS = (
    "Config/ConfigAbility/Avatar/Avatar_Natasha_00_Ability.json",
    "Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json",
    "Config/ConfigAbility/Monster/Monster_AML_Minion01_00_Ability.json",
    "Config/ConfigAbility/Level/Level_MazeBuff_Ability.json",
    "Config/ConfigAdventureModifier/AdventureModifier_MazeChallenge.json",
    "Config/ConfigAdventureModifier/AdventureModifier_MazeEnvi.json",
    "Config/ConfigGlobalModifier/GlobalModifier_Common_Property.json",
    "Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json",
)

OPERATION_MAP: Mapping[str, tuple[str, str, str, str]] = {
    "RPG.GameCore.TriggerAbility": ("INVOKE_BEHAVIOR", "MODELLED", "UNKNOWN", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.PredicateTaskList": ("CONDITIONAL", "REQUIRES_PACKET", "UNKNOWN", "UNKNOWN"),
    "RPG.GameCore.AddModifier": ("ADD_MODIFIER", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.RemoveModifier": ("REMOVE_MODIFIER", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.DamageByAttackProperty": ("DAMAGE_REQUEST", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.HealHP": ("HEAL_REQUEST", "MODELLED", "ORDINARY_MVP", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ModifySPNew": ("MODIFY_TEAM_SP", "MODELLED", "ORDINARY_MVP", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.Retarget": ("RETARGET", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetDynamicValue": ("SET_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetStageBattleEvents": ("REGISTER_STAGE_EVENTS", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.CreateBattleEvent": ("CREATE_STAGE_EVENT", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SkillPerformFinish": ("ACTION_COMPLETION_MARKER", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.DamagePerformFinish": ("DAMAGE_COMPLETION_MARKER", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.TriggerAnimState": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.TriggerEffect": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.LookAt": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.HeadLookAt": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.VCameraConfigChange": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.GlobalMainIntensityEffect": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.ShowBattleUI": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.SetNoShadowCaster": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.ScaleCharacterModel": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.SetAttachmentScale": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.FindClosestAttachPoint": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.RemoveEffect": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.HideLevelStage": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.TriggerUINotify": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.ToastPage": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.WaitAnimState": ("PRESENTATION_WAIT", "PRESENTATION", "PRESENTATION", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.WaitSecond": ("PRESENTATION_WAIT", "PRESENTATION", "PRESENTATION", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.WaitTimelineFinish": ("PRESENTATION_WAIT", "PRESENTATION", "PRESENTATION", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.StartAim": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.StopAim": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.MoveToTargetPosition": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.AlignTargetToTeamCenter": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.SyncCharLightAndCameraDir": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.SetTeamFormation": ("FORMATION_CHANGE", "REQUIRES_PACKET", "UNKNOWN", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.SkillExecutionStart": ("ACTION_START_MARKER", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.LoopExecuteTaskListWithInterval": ("LOOP", "REQUIRES_PACKET", "UNKNOWN", "UNKNOWN"),
    "RPG.GameCore.ConditionLoopExecuteTaskListWithInterval": ("CONDITIONAL_LOOP", "REQUIRES_PACKET", "UNKNOWN", "UNKNOWN"),
    "RPG.GameCore.IncludeTaskListTemplate": ("INCLUDE_TASK_TEMPLATE", "REQUIRES_PACKET", "UNKNOWN", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.TriggerSkipDeadHandler": ("DEATH_HANDLER", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.FireProjectile": ("PROJECTILE_DISPATCH", "REQUIRES_PACKET", "UNKNOWN", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.StackProperty": ("MODIFY_PROPERTY_STACK", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ModifyDamageData": ("MODIFY_DAMAGE_DATA", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetDynamicValueByModifierValue": ("SET_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetDynamicValueByStatisticCustomValue": ("SET_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetDynamicValueByProperty": ("SET_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetDynamicValueByStatusCount": ("SET_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetModifierDynamicValue": ("SET_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetAdventureDynamicValue": ("SET_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.DefineDynamicValue": ("DEFINE_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.RandomConfig": ("RANDOM_SELECTION", "REQUIRES_PACKET", "UNKNOWN", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.ModifyActionDelay": ("DELAY_ACTION", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.TurnInsertAbility": ("INSERT_ACTION", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.TriggerBreak": ("TRIGGER_BREAK", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ResetStance": ("RESET_TOUGHNESS", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ChangeMechanismBarValue": ("MODIFY_SPECIAL_RESOURCE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ModifyHealData": ("MODIFY_HEAL_DATA", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.DispelStatus": ("DISPEL_STATUS", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.AddAdventureModifier": ("ADD_MODIFIER", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.RemoveAdventureModifier": ("REMOVE_MODIFIER", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.AddClientMazeBuff": ("ADD_STAGE_BUFF", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.AdventureModifyTeamPlayerHP": ("MODIFY_TEAM_HP", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.AdvChangeSkillTreeLevel": ("MODIFY_SKILL_TREE_LEVEL", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ModifierAttachEffect": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.ModifierDetachEffect": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.ModifierReattachEffect": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.SetAttachEffectTimeSlow": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.DebugLog": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.ShowUIPage": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.ShowBonusUIEffect": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.CharacterPlayVO": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.TriggerSound": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.ToastPile": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.TutorialTaskUnlock": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.ModifierOverrideOnHitEffect": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.ModifyAdventureCharacterRunSpeedRatio": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.RemoveSelfModifier": ("REMOVE_MODIFIER", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.TurnInsertAction": ("INSERT_ACTION", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.AddBuffPerform": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "POSSIBLE_STATE_COMMIT"),
    "RPG.GameCore.AttachSkillTypeDisable": ("MODIFY_ACTION_STATE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetModifierValue": ("SET_MODIFIER_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetSkillTextDialogType": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.StackStatusDesc": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.ShowEntityFloatMessage": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.StackWeakness": ("MODIFY_WEAKNESS", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.HideCharacterFilteredEffect": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.SetDynamicValueByVariateType": ("SET_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.AddBehaviorFlagForModifier": ("MODIFY_MODIFIER_FLAG", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.RemoveBehaviorFlagForModifier": ("MODIFY_MODIFIER_FLAG", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ModifySkillPropertyByType": ("MODIFY_SKILL_PROPERTY", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ModifyCurrentSkillDelayCost": ("MODIFY_ACTION_COST", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ResetTeammateAttackPerform": ("MODIFY_ACTION_STATE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetDynamicEntityParam": ("SET_DYNAMIC_ENTITY_PARAM", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.TargetMapDynamicEntityParam": ("SET_DYNAMIC_ENTITY_PARAM", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetDynamicValueByCopying": ("SET_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetDynamicValueByChangeValue": ("SET_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetDynamicValueBySkillMaxHitSplitCount": ("SET_DYNAMIC_VALUE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ShowBattleScreenEffect": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.AbortModifierPhasePerform": ("MODIFY_ACTION_STATE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.LockHP": ("LOCK_HP", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ForceKill": ("FORCE_KILL", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.OwnerEntityAddAbility": ("GRANT_ABILITY", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetCameraRootFollow": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
    "RPG.GameCore.SetResilience": ("SET_RESILIENCE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.TargetFilter": ("TARGET_FILTER", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.CharmUseSkill": ("CHARM_USE_SKILL", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.InitShield": ("INIT_SHIELD", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.RemoveShield": ("REMOVE_SHIELD", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.LevelChallengeTurnAcc": ("MODIFY_SPECIAL_RESOURCE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.ResetActionDelay": ("DELAY_ACTION", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetActionDelay": ("DELAY_ACTION", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetStanceCount": ("MODIFY_TOUGHNESS", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SetTeammateAttackFormation": ("FORMATION_CHANGE", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.StackRedirectSkillTarget": ("RETARGET", "REQUIRES_PACKET", "UNKNOWN", "KNOWN_STATE_COMMIT"),
    "RPG.GameCore.SwitchCaseByAttackDamageType": ("SWITCH_CASE", "REQUIRES_PACKET", "UNKNOWN", "UNKNOWN"),
    "RPG.GameCore.SwitchCaseByDynamicValue": ("SWITCH_CASE", "REQUIRES_PACKET", "UNKNOWN", "UNKNOWN"),
    "RPG.GameCore.TriggerEffectList": ("PRESENTATION", "PRESENTATION", "PRESENTATION", "NONE"),
}

# Fields whose typed list children are task/predicate groups, never lifted as
# independent nodes by themselves; they are already represented as children.
TASK_ARRAY_FIELDS = {
    "SuccessTaskList",
    "FailedTaskList",
    "FailTaskList",
    "TaskList",
    "PredicateList",
    "CallbackConfig",
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _name(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    nested = _mapping(value)
    candidate = nested.get("Value")
    return str(candidate) if candidate is not None else fallback


def _owner(path: str) -> str:
    if "/Avatar/" in path:
        return "Avatar"
    if "/Monster/" in path:
        return "Monster"
    if "MazeBuff" in path:
        return "StageBuff"
    if "Modifier" in path:
        return "Modifier"
    return "ExternalBehavior"


def _is_typed_task(value: Any) -> bool:
    return isinstance(value, Mapping) and isinstance(value.get("$type"), str)


def _is_predicate_source_type(source_type: str | None) -> bool:
    return bool(source_type) and (
        ".By" in source_type or source_type.startswith("RPG.GameCore.AdventureBy")
    )


def _nested_operation_groups(value: Any, path: tuple[str, ...] = ()) -> list[tuple[str, list[Any]]]:
    """Find direct nested task arrays while leaving non-task AST payload intact.

    A singular ``Predicate`` mapping is a boundary: it is lifted by
    ``_nested_predicate_groups`` and its inner ``PredicateList`` is then lifted
    while processing that predicate child, never twice.  Target-payload fields
    (``TargetType`` / ``ParamTargetType`` / filters) are preserved as payload,
    never lifted as operations.
    """
    groups: list[tuple[str, list[Any]]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = path + (str(key),)
            if key == "Predicate" and _is_typed_task(child):
                continue
            if str(key) in {"TargetType", "ParamTargetType", "TargetList", "TargetFilter", "CasterFilter"}:
                continue
            if isinstance(child, list) and any(_is_typed_task(item) for item in child):
                groups.append((".".join(child_path), list(child)))
                continue
            groups.extend(_nested_operation_groups(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            groups.extend(_nested_operation_groups(child, path + (str(index),)))
    return groups


def _nested_predicate_groups(value: Any, path: tuple[str, ...] = ()) -> list[tuple[str, list[Any]]]:
    """Lift singular ``Predicate`` mappings as PREDICATE_AST child groups.

    ``PredicateList`` arrays and other typed task lists are lifted as child
    operations by ``_nested_operation_groups``; descending into those lists
    here would lift the same predicates twice, so lists are not traversed.
    """
    groups: list[tuple[str, list[Any]]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = path + (str(key),)
            if key == "Predicate" and _is_typed_task(child):
                groups.append((".".join(child_path), [child]))
                continue
            groups.extend(_nested_predicate_groups(child, child_path))
    return groups


def _callback_list_entrypoints(
    callback_list: list[Any],
    *,
    prefix: str,
    behavior_id: str,
    raw_ref: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Canonicalize one ``_CallbackList`` into Modifier callback entrypoints."""
    found: list[dict[str, Any]] = []
    for callback_index, callback in enumerate(callback_list):
        callback_map = _mapping(callback)
        tasks = callback_map.get("CallbackConfig")
        if not isinstance(tasks, list):
            tasks = []
        event = str(callback_map.get("Event", "UNKNOWN"))
        source_event = f"{prefix}[{callback_index}]:{event}"
        canonical_event = f"MODIFIER_CALLBACK:{source_event}"
        found.append({
            "event": canonical_event,
            "source_event": source_event,
            "callback_metadata": {
                "event": event,
                "priority": callback_map.get("Priority"),
                "callback_index": callback_index,
                "callback_path": source_event,
            },
            "operations": [
                _operation(
                    task,
                    behavior_id=behavior_id,
                    entrypoint=canonical_event,
                    index=index,
                    raw_ref=raw_ref,
                )
                for index, task in enumerate(tasks)
            ],
        })
    return found


def _callback_entrypoints(value: Any, prefix: str = "") -> list[tuple[str, list[Any], dict[str, Any]]]:
    """Lift every ``_CallbackList`` under a nested ``Modifiers`` payload."""
    found: list[tuple[str, list[Any], dict[str, Any]]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key == "_CallbackList" and isinstance(child, list):
                for callback_index, callback in enumerate(child):
                    callback_map = _mapping(callback)
                    tasks = callback_map.get("CallbackConfig")
                    if not isinstance(tasks, list):
                        tasks = []
                    event = str(callback_map.get("Event", "UNKNOWN"))
                    found.append((
                        f"{path}[{callback_index}]:{event}",
                        list(tasks),
                        {
                            "event": event,
                            "priority": callback_map.get("Priority"),
                            "callback_index": callback_index,
                            "callback_path": f"{path}[{callback_index}]:{event}",
                        },
                    ))
                continue
            if str(key).startswith("On") and isinstance(child, list):
                found.append((path, list(child), {}))
            else:
                found.extend(_callback_entrypoints(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_callback_entrypoints(child, f"{prefix}[{index}]"))
    return found


def _operation(
    task: Any,
    *,
    behavior_id: str,
    entrypoint: str,
    index: int,
    raw_ref: Mapping[str, Any],
    parent_operation_id: str | None = None,
    child_path: str | None = None,
) -> dict[str, Any]:
    payload = _mapping(task)
    source_type = payload.get("$type") if isinstance(payload.get("$type"), str) else None
    kind, status, scope, risk = _classify_operation(source_type)
    node_role = "PREDICATE_AST" if _is_predicate_source_type(source_type) else "OPERATION"
    arguments = {key: value for key, value in payload.items() if key not in {"$type", "TargetType"}}
    operation_id = (
        f"{behavior_id}:{entrypoint}:{index}"
        if parent_operation_id is None
        else f"{parent_operation_id}/{child_path or 'child'}:{index}"
    )
    operation_ref = {**raw_ref, "entrypoint": entrypoint, "operation_index": index}
    if parent_operation_id is not None:
        operation_ref["parent_child_path"] = child_path
    children: list[dict[str, Any]] = []
    group_index = 0
    for group_path, tasks in _nested_operation_groups(payload):
        children.append({
            "group_id": f"{operation_id}:group:{group_index}",
            "field_path": group_path,
            "operations": [
                _operation(
                    child,
                    behavior_id=behavior_id,
                    entrypoint=entrypoint,
                    index=child_index,
                    raw_ref=raw_ref,
                    parent_operation_id=operation_id,
                    child_path=group_path,
                )
                for child_index, child in enumerate(tasks)
            ],
        })
        group_index += 1
    for group_path, tasks in _nested_predicate_groups(payload):
        children.append({
            "group_id": f"{operation_id}:group:{group_index}",
            "field_path": group_path,
            "operations": [
                _operation(
                    child,
                    behavior_id=behavior_id,
                    entrypoint=entrypoint,
                    index=child_index,
                    raw_ref=raw_ref,
                    parent_operation_id=operation_id,
                    child_path=group_path,
                )
                for child_index, child in enumerate(tasks)
            ],
        })
        group_index += 1
    template_ref = None
    if kind == "INCLUDE_TASK_TEMPLATE" and isinstance(arguments.get("Name"), str):
        template_ref = f"{behavior_id}:template:{arguments['Name']}"
    return {
        "operation_id": operation_id,
        "parent_operation_id": parent_operation_id,
        "parent_child_path": child_path,
        "source_type": source_type,
        "node_role": node_role,
        "kind": kind,
        "semantic_status": status,
        "scope": scope,
        "gating_risk": risk,
        "semantic_importance": _semantic_importance(kind, status, risk),
        "target": payload.get("TargetType"),
        "arguments": arguments,
        "template_ref": template_ref,
        "children": children,
        "phase": "UNKNOWN",
        "state_reads": ["UNKNOWN"],
        "state_writes": ["UNKNOWN"],
        "event_boundary": "UNKNOWN",
        "dependencies": [],
        "source_payload_ref": operation_ref,
    }


def _classify_operation(source_type: str | None) -> tuple[str, str, str, str]:
    """Classify structural families without claiming they are executable.

    External type names can safely identify a predicate AST as a predicate, or
    an action-delay task as scheduler-relevant.  This reduces opaque *schema*
    loss while retaining ``REQUIRES_PACKET`` until the actual state transition
    is reconstructed and compiled.
    """
    if source_type in OPERATION_MAP:
        return OPERATION_MAP[source_type]
    if _is_predicate_source_type(source_type):
        return ("PREDICATE", "REQUIRES_PACKET", "UNKNOWN", "UNKNOWN")
    return ("OPAQUE", "OPAQUE", "UNKNOWN", "UNKNOWN")


def _semantic_importance(kind: str, status: str, risk: str) -> str:
    """Conservative priority for corpus triage, not a support claim."""
    if kind in {
        "DEATH_HANDLER",
        "ACTION_COMPLETION_MARKER",
        "DAMAGE_COMPLETION_MARKER",
        "ACTION_START_MARKER",
        "INCLUDE_TASK_TEMPLATE",
        "LOOP",
        "CONDITIONAL_LOOP",
        "INSERT_ACTION",
        "DELAY_ACTION",
        "TRIGGER_BREAK",
        "PROJECTILE_DISPATCH",
        "MODIFY_ACTION_STATE",
        "MODIFY_ACTION_COST",
        "LOCK_HP",
        "FORCE_KILL",
        "CHARM_USE_SKILL",
        "GRANT_ABILITY",
    }:
        return "P0_SCHEDULER_OR_TERMINAL"
    if kind in {
        "ADD_MODIFIER",
        "REMOVE_MODIFIER",
        "MODIFY_PROPERTY_STACK",
        "DISPEL_STATUS",
        "MODIFY_DAMAGE_DATA",
        "MODIFY_HEAL_DATA",
        "SET_MODIFIER_VALUE",
        "MODIFY_MODIFIER_FLAG",
        "MODIFY_SKILL_PROPERTY",
        "INIT_SHIELD",
        "REMOVE_SHIELD",
        "SET_RESILIENCE",
        "MODIFY_TOUGHNESS",
        "MODIFY_WEAKNESS",
    }:
        return "P0_MODIFIER_OR_DAMAGE_PIPELINE"
    if kind in {
        "PREDICATE",
        "CONDITIONAL",
        "RETARGET",
        "RANDOM_SELECTION",
        "MODIFY_TEAM_SP",
        "MODIFY_SPECIAL_RESOURCE",
        "SWITCH_CASE",
        "TARGET_FILTER",
        "SET_DYNAMIC_ENTITY_PARAM",
    }:
        return "P1_LEGALITY_OR_RESOURCE"
    if status == "PRESENTATION" and risk == "NONE":
        return "P3_PRESENTATION_ONLY"
    if status == "PRESENTATION":
        return "P2_PRESENTATION_GATING_RISK"
    return "P1_UNCLASSIFIED_SEMANTIC"


def _template_definitions(
    value: Mapping[str, Any],
    *,
    behavior_id: str,
    raw_ref: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Lift TaskListTemplate definitions into canonical template nodes."""
    templates = value.get("TaskListTemplate")
    if not isinstance(templates, list):
        return []
    definitions: list[dict[str, Any]] = []
    used_names: set[str] = set()
    for template_index, template in enumerate(templates):
        template_map = _mapping(template)
        name = _name(template_map.get("Name"), f"Template{template_index}")
        template_id = f"{behavior_id}:template:{name}"
        if template_id in used_names:
            template_id = f"{template_id}#{template_index}"
        used_names.add(template_id)
        entrypoint = f"TEMPLATE_DEFINITION:{name}"
        tasks = template_map.get("TaskList")
        operations = [] if not isinstance(tasks, list) else [
            _operation(
                task,
                behavior_id=behavior_id,
                entrypoint=entrypoint,
                index=index,
                raw_ref={**raw_ref, "template_index": template_index},
            )
            for index, task in enumerate(tasks)
        ]
        definitions.append({
            "template_id": template_id,
            "name": name,
            "source_field_path": f"TaskListTemplate[{template_index}]",
            "entrypoint": entrypoint,
            "operations": operations,
            "source_payload_ref": {**raw_ref, "template_index": template_index},
        })
    return definitions


def _dynamic_value_definitions(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Preserve DynamicValues definitions as canonical definition records."""
    dynamic_values = value.get("DynamicValues")
    if not isinstance(dynamic_values, Mapping):
        return []
    definitions: list[dict[str, Any]] = []
    for scope_name in sorted(str(key) for key in dynamic_values):
        bucket = dynamic_values[scope_name]
        if not isinstance(bucket, Mapping):
            continue
        for dynamic_hash in sorted(str(key) for key in bucket):
            definition = bucket[dynamic_hash]
            definitions.append({
                "dynamic_hash": dynamic_hash,
                "scope": scope_name,
                "source_field_path": f"DynamicValues.{scope_name}.{dynamic_hash}",
                "definition": definition,
            })
    return definitions


def build_external_behavior_corpus(
    version: str = CONTENT_VERSION,
    *,
    source_root: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic canonical index for the reviewed behavior slice."""
    if version != CONTENT_VERSION:
        raise ValueError(f"external behavior corpus is pinned to {CONTENT_VERSION}, not {version}")
    root = source_root or default_external_root()
    base = root / "TurnBasedGameData"
    manifest_path = base / "manifest.json"
    manifest = _mapping(json.loads(manifest_path.read_text(encoding="utf-8")))
    if manifest.get("selected_commit") != "b11066beacc4de454b625fafc7ea3dd540c5bbf3":
        raise ValueError("TurnBasedGameData snapshot commit mismatch")
    file_meta = _mapping(manifest.get("files"))
    records: list[dict[str, Any]] = []
    for relative_path in TURN_BASED_BEHAVIOR_PATHS:
        metadata = _mapping(file_meta.get(relative_path))
        path = base / "files" / relative_path
        if not path.exists() or not metadata.get("raw_sha256"):
            raise ValueError(f"missing reviewed behavior payload: {relative_path}")
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != metadata.get("raw_sha256"):
            raise ValueError(f"behavior payload hash mismatch: {relative_path}")
        document = _mapping(json.loads(raw.decode("utf-8")))
        containers: list[tuple[str, str]] = []
        if document.get("AbilityList") is not None:
            containers.append(("AbilityList", _owner(relative_path)))
        if isinstance(document.get("GlobalModifiers"), Mapping):
            containers.append(("GlobalModifiers", "Modifier"))
        if document.get("ModifierMap") is not None:
            containers.append(("ModifierMap", "Modifier"))
        raw_ref = {
            "source": "TurnBasedGameData",
            "repository": "https://github.com/DimbreathBot/TurnBasedGameData",
            "commit": manifest["selected_commit"],
            "path": relative_path,
            "raw_sha256": metadata["raw_sha256"],
            "version_relation": "CLOSE_4.4.0_TO_4.4.54",
        }
        for container_name, owner_kind in containers:
            source_items = document.get(container_name)
            iterable = list(_mapping(source_items).items()) if isinstance(source_items, Mapping) else list(enumerate(source_items or []))
            container_ref = {**raw_ref, "source_container": container_name}
            for key, item in iterable:
                payload = _mapping(item)
                name = _name(payload.get("Name"), str(key))
                id_prefix = f":{container_name}:" if container_name == "GlobalModifiers" else ":"
                behavior_id = f"external:TurnBasedGameData:{relative_path}{id_prefix}{name}"
                entrypoints: list[dict[str, Any]] = []
                # 1. Root On* task arrays.
                for field, value in payload.items():
                    if not str(field).startswith("On") or not isinstance(value, list):
                        continue
                    entrypoints.append({
                        "event": str(field).upper(),
                        "source_event": field,
                        "operations": [
                            _operation(task, behavior_id=behavior_id, entrypoint=str(field).upper(), index=index, raw_ref=container_ref)
                            for index, task in enumerate(value)
                        ],
                    })
                # 2. A Modifier record's own _CallbackList is itself the
                #    entrypoint source; it must never remain raw-only.
                own_callbacks = payload.get("_CallbackList")
                if isinstance(own_callbacks, list):
                    entrypoints.extend(
                        _callback_list_entrypoints(
                            own_callbacks,
                            prefix=f"{name}._CallbackList",
                            behavior_id=behavior_id,
                            raw_ref=container_ref,
                        )
                    )
                # 3. Nested Modifiers inside an Ability payload.
                nested_modifiers = payload.get("Modifiers")
                for callback_name, tasks, callback_metadata in _callback_entrypoints(nested_modifiers):
                    event = f"MODIFIER_CALLBACK:{callback_name}"
                    entrypoints.append({
                        "event": event,
                        "source_event": callback_name,
                        "callback_metadata": callback_metadata,
                        "operations": [
                            _operation(task, behavior_id=behavior_id, entrypoint=event, index=index, raw_ref=container_ref)
                            for index, task in enumerate(tasks)
                        ],
                    })
                raw_unknown = {
                    key: value
                    for key, value in payload.items()
                    if key not in {
                        "Name",
                        "Modifiers",
                        "_CallbackList",
                        "TaskListTemplate",
                        "DynamicValues",
                    } and not str(key).startswith("On")
                }
                records.append({
                    "behavior_id": behavior_id,
                    "owner_kind": owner_kind,
                    "owner_ref": name,
                    "source_refs": [container_ref],
                    "entrypoints": entrypoints,
                    "template_definitions": _template_definitions(
                        payload,
                        behavior_id=behavior_id,
                        raw_ref=container_ref,
                    ),
                    "dynamic_value_definitions": _dynamic_value_definitions(payload),
                    "modifier_payload": payload.get("Modifiers"),
                    "raw_unknown": raw_unknown,
                    "reconstruction_status": "CANONICALIZED",
                })
    records.sort(key=lambda record: record["behavior_id"])
    corpus = {
        "schema": "hsr_battle_agent.external_behavior_corpus/2",
        "game_version": version,
        "source": "TurnBasedGameData",
        "source_commit": manifest["selected_commit"],
        "records": records,
    }
    corpus["corpus_sha256"] = stable_hash(corpus)
    target = output_path or Path("data") / "semantics" / version / "full_reconstruction" / "external_behavior_corpus_v1.json"
    write_json(target, corpus)
    return {"output_path": str(target), "record_count": len(records), "corpus_sha256": corpus["corpus_sha256"]}
