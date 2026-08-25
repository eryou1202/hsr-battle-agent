"""Normalize the reviewed external behavior slice without runtime source access.

This module is a reconstruction adapter, not a battle runtime.  It reads a
pinned raw snapshot and produces lossless-reference canonical behavior records
that later compiler work can consume offline.
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


def _nested_operation_groups(value: Any, path: tuple[str, ...] = ()) -> list[tuple[str, list[Any]]]:
    """Find direct nested task arrays while leaving non-task AST payload intact."""
    groups: list[tuple[str, list[Any]]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = path + (str(key),)
            if isinstance(child, list) and any(isinstance(item, Mapping) and "$type" in item for item in child):
                groups.append((".".join(child_path), list(child)))
                continue
            groups.extend(_nested_operation_groups(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            groups.extend(_nested_operation_groups(child, path + (str(index),)))
    return groups


def _callback_entrypoints(value: Any, prefix: str = "") -> list[tuple[str, list[Any], dict[str, Any]]]:
    """Lift modifier/callback task lists without assuming a single schema."""
    found: list[tuple[str, list[Any], dict[str, Any]]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key == "_CallbackList" and isinstance(child, list):
                for callback_index, callback in enumerate(child):
                    callback_map = _mapping(callback)
                    tasks = callback_map.get("CallbackConfig")
                    if isinstance(tasks, list):
                        event = str(callback_map.get("Event", "UNKNOWN"))
                        found.append((f"{path}[{callback_index}]:{event}", list(tasks), {"event": event, "priority": callback_map.get("Priority"), "callback_index": callback_index}))
                continue
            if str(key).startswith("On") and isinstance(child, list):
                found.append((path, list(child), {}))
            else:
                found.extend(_callback_entrypoints(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_callback_entrypoints(child, f"{prefix}[{index}]"))
    return found


def _operation(task: Any, *, behavior_id: str, entrypoint: str, index: int, raw_ref: Mapping[str, Any], parent_operation_id: str | None = None, child_path: str | None = None) -> dict[str, Any]:
    payload = _mapping(task)
    source_type = payload.get("$type") if isinstance(payload.get("$type"), str) else None
    kind, status, scope, risk = OPERATION_MAP.get(source_type or "", ("OPAQUE", "OPAQUE", "UNKNOWN", "UNKNOWN"))
    node_role = "PREDICATE_AST" if source_type and ".By" in source_type else "OPERATION"
    arguments = {key: value for key, value in payload.items() if key not in {"$type", "TargetType"}}
    operation_id = f"{behavior_id}:{entrypoint}:{index}" if parent_operation_id is None else f"{parent_operation_id}/{child_path or 'child'}:{index}"
    children = []
    for group_index, (group_path, tasks) in enumerate(_nested_operation_groups(payload)):
        children.append({"group_id": f"{operation_id}:group:{group_index}", "field_path": group_path, "operations": [_operation(child, behavior_id=behavior_id, entrypoint=entrypoint, index=child_index, raw_ref=raw_ref, parent_operation_id=operation_id, child_path=group_path) for child_index, child in enumerate(tasks)]})
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
        "target": payload.get("TargetType"),
        "arguments": arguments,
        "children": children,
        "phase": "UNKNOWN",
        "state_reads": ["UNKNOWN"],
        "state_writes": ["UNKNOWN"],
        "event_boundary": "UNKNOWN",
        "dependencies": [],
        "source_payload_ref": {**raw_ref, "entrypoint": entrypoint, "operation_index": index},
    }


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
        container_name = "AbilityList" if isinstance(document.get("AbilityList"), list) else "ModifierMap"
        source_items = document.get(container_name)
        iterable = list(_mapping(source_items).items()) if isinstance(source_items, Mapping) else list(enumerate(source_items or []))
        raw_ref = {"source":"TurnBasedGameData", "repository":"https://github.com/DimbreathBot/TurnBasedGameData", "commit":manifest["selected_commit"], "path":relative_path, "raw_sha256":metadata["raw_sha256"], "version_relation":"CLOSE_4.4.0_TO_4.4.54"}
        for key, item in iterable:
            payload = _mapping(item)
            name = _name(payload.get("Name"), str(key))
            behavior_id = f"external:TurnBasedGameData:{relative_path}:{name}"
            entrypoints = []
            for field, value in payload.items():
                if not str(field).startswith("On") or not isinstance(value, list):
                    continue
                entrypoints.append({"event": str(field).upper(), "source_event": field, "operations": [_operation(task, behavior_id=behavior_id, entrypoint=str(field).upper(), index=index, raw_ref=raw_ref) for index, task in enumerate(value)]})
            modifier_callbacks = []
            for callback_name, tasks, callback_metadata in _callback_entrypoints(payload.get("Modifiers")):
                event = f"MODIFIER_CALLBACK:{callback_name}"
                modifier_callbacks.append({"event":event, "source_event":callback_name, "callback_metadata":callback_metadata, "operations":[_operation(task, behavior_id=behavior_id, entrypoint=event, index=index, raw_ref=raw_ref) for index, task in enumerate(tasks)]})
            entrypoints.extend(modifier_callbacks)
            records.append({"behavior_id":behavior_id, "owner_kind":_owner(relative_path), "owner_ref":name, "source_refs":[raw_ref], "entrypoints":entrypoints, "modifier_payload":payload.get("Modifiers"), "raw_unknown":{key:value for key,value in payload.items() if key not in {"Name", "Modifiers"} and not str(key).startswith("On")}, "reconstruction_status":"CANONICALIZED"})
    records.sort(key=lambda record: record["behavior_id"])
    corpus = {"schema":"hsr_battle_agent.external_behavior_corpus/1", "game_version":version, "source":"TurnBasedGameData", "source_commit":manifest["selected_commit"], "records":records}
    corpus["corpus_sha256"] = stable_hash(corpus)
    target = output_path or Path("data") / "semantics" / version / "full_reconstruction" / "external_behavior_corpus_v1.json"
    write_json(target, corpus)
    return {"output_path":str(target), "record_count":len(records), "corpus_sha256":corpus["corpus_sha256"]}
