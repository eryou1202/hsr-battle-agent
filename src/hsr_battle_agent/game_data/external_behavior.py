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


def _operation(task: Any, *, behavior_id: str, entrypoint: str, index: int, raw_ref: Mapping[str, Any]) -> dict[str, Any]:
    payload = _mapping(task)
    source_type = payload.get("$type") if isinstance(payload.get("$type"), str) else None
    kind, status, scope, risk = OPERATION_MAP.get(source_type or "", ("OPAQUE", "OPAQUE", "UNKNOWN", "UNKNOWN"))
    arguments = {key: value for key, value in payload.items() if key not in {"$type", "TargetType"}}
    return {
        "operation_id": f"{behavior_id}:{entrypoint}:{index}",
        "source_type": source_type,
        "kind": kind,
        "semantic_status": status,
        "scope": scope,
        "gating_risk": risk,
        "target": payload.get("TargetType"),
        "arguments": arguments,
        "children": [],
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
            records.append({"behavior_id":behavior_id, "owner_kind":_owner(relative_path), "owner_ref":name, "source_refs":[raw_ref], "entrypoints":entrypoints, "modifier_payload":payload.get("Modifiers"), "raw_unknown":{key:value for key,value in payload.items() if key not in {"Name", "Modifiers"} and not str(key).startswith("On")}, "reconstruction_status":"CANONICALIZED"})
    records.sort(key=lambda record: record["behavior_id"])
    corpus = {"schema":"hsr_battle_agent.external_behavior_corpus/1", "game_version":version, "source":"TurnBasedGameData", "source_commit":manifest["selected_commit"], "records":records}
    corpus["corpus_sha256"] = stable_hash(corpus)
    target = output_path or Path("data") / "semantics" / version / "full_reconstruction" / "external_behavior_corpus_v1.json"
    write_json(target, corpus)
    return {"output_path":str(target), "record_count":len(records), "corpus_sha256":corpus["corpus_sha256"]}
