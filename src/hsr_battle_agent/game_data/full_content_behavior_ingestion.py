"""Deterministic family-scoped discovery and ingestion planning.

The full-content program deliberately promotes *families* of behavior files
from an already commit-pinned tree discovery.  This module does not infer game
IDs, normalise behavior, or execute anything.  It only converts positive
discovery results into an auditable, resumable retrieval manifest that the
external snapshot fetcher can materialize at low concurrency.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .external_reconstruction import CONTENT_VERSION, default_external_root
from .nanoka_content import stable_hash, write_json


TURN_BASED_SOURCE = "TurnBasedGameData"
TURN_BASED_COMMIT = "b11066beacc4de454b625fafc7ea3dd540c5bbf3"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _entries(discovery: Mapping[str, Any], query: str) -> list[Mapping[str, Any]]:
    matches = _mapping(discovery.get("matches"))
    values = matches.get(query)
    return [entry for entry in values if isinstance(entry, Mapping)] if isinstance(values, list) else []


def _non_layout(entries: list[Mapping[str, Any]], *, exclude: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for entry in entries:
        path = str(entry.get("path", ""))
        if not path.endswith(".json") or path.endswith(".layout.json"):
            continue
        if any(token in path for token in exclude):
            continue
        selected.append({
            "path": path,
            "discovery_git_blob_sha": entry.get("git_blob_sha"),
            "discovery_size": entry.get("size"),
        })
    return sorted(selected, key=lambda row: row["path"])


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _family_rows(discovery: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Select only positive, semantically relevant paths from cached discovery."""
    return {
        # Config files are captured as join/support evidence; only ability
        # files feed the behavior normalizer.
        "AVATAR_ABILITY": _non_layout(_entries(discovery, "Config/ConfigAbility/Avatar/")),
        "AVATAR_CONFIG": _non_layout(_entries(discovery, "Config/ConfigCharacter/Avatar/")),
        # Camera configs share this tree but are presentation data, not
        # Monster behavior records.  Their omission is recorded explicitly.
        "MONSTER_ABILITY": _non_layout(
            _entries(discovery, "Config/ConfigAbility/Monster/"),
            exclude=("/Camera/",),
        ),
        "MONSTER_AI": _non_layout(_entries(discovery, "Config/ConfigAI/ComplexSkillAIGlobalGroup/Monster/")),
        "STAGE_BUFF_ABILITY": _non_layout(_entries(discovery, "Config/ConfigAbility/Level/Level_MazeBuff_Ability")),
        "STAGE_ADVENTURE_MODIFIER": _non_layout(
            _entries(discovery, "Config/ConfigAdventureModifier/AdventureModifier_MazeChallenge")
            + _entries(discovery, "Config/ConfigAdventureModifier/AdventureModifier_MazeEnvi")
        ),
        "GLOBAL_MODIFIER": _non_layout(_entries(discovery, "Config/ConfigGlobalModifier/GlobalModifier_")),
    }


def _equipment_directory_rows(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Split the direct pinned Equip directory without filename speculation.

    The directory itself is an explicit upstream schema boundary.  Its
    ``RelicAbility`` document is kept separate from the remaining Equipment
    documents, but this only establishes a source *family*; static IDs are
    still joined later by the mapping pass.
    """
    if not path.exists():
        return {}
    artifact = _mapping(json.loads(path.read_text(encoding="utf-8")))
    if artifact.get("selected_commit") != TURN_BASED_COMMIT:
        raise ValueError("equipment directory discovery commit mismatch")
    lightcone: list[dict[str, Any]] = []
    relic: list[dict[str, Any]] = []
    for entry in artifact.get("entries", []):
        row = _mapping(entry)
        source_path = str(row.get("path", ""))
        if row.get("type") != "file" or not source_path.endswith(".json") or source_path.endswith(".layout.json"):
            continue
        normalized = {
            "path": source_path,
            "discovery_git_blob_sha": row.get("git_blob_sha"),
            "discovery_size": row.get("size"),
        }
        (relic if Path(source_path).name == "RelicAbility.json" else lightcone).append(normalized)
    return {
        "LIGHTCONE_ABILITY": sorted(lightcone, key=lambda row: row["path"]),
        "RELIC_SET_ABILITY": sorted(relic, key=lambda row: row["path"]),
    }


def build_full_content_behavior_ingestion_manifest(
    *,
    source_root: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Publish the exact retrieval plan from the existing pinned discovery.

    Absence from the discovery remains non-authoritative because the upstream
    GitHub recursive-tree reply was marked truncated.  The manifest therefore
    distinguishes ``NOT_DISCOVERED_IN_TRUNCATED_TREE`` from a behavior gap.
    """
    root = source_root or default_external_root()
    source_root_path = root / TURN_BASED_SOURCE
    discovery_path = source_root_path / "semantic_discovery_v1.json"
    source_manifest_path = source_root_path / "manifest.json"
    equipment_discovery_path = source_root_path / "full_content_equipment_directory_001.json"
    discovery = _mapping(json.loads(discovery_path.read_text(encoding="utf-8")))
    source_manifest = _mapping(json.loads(source_manifest_path.read_text(encoding="utf-8")))
    if discovery.get("selected_commit") != TURN_BASED_COMMIT:
        raise ValueError("TurnBasedGameData discovery commit mismatch")
    if source_manifest.get("selected_commit") != TURN_BASED_COMMIT:
        raise ValueError("TurnBasedGameData source manifest commit mismatch")

    cached_files = _mapping(source_manifest.get("files"))
    families = _family_rows(discovery)
    families.update(_equipment_directory_rows(equipment_discovery_path))
    all_paths: dict[str, dict[str, Any]] = {}
    family_summaries: list[dict[str, Any]] = []
    for family, rows in sorted(families.items()):
        cached = 0
        for row in rows:
            path = str(row["path"])
            payload_path = source_root_path / "files" / path
            metadata = _mapping(cached_files.get(path))
            row["family"] = family
            row["version_relation"] = "CLOSE_4.4.0_TO_4.4.54"
            row["capture_status"] = (
                "CACHED_VERIFIED"
                if payload_path.exists() and metadata.get("raw_sha256")
                else "DISCOVERED_NOT_CACHED"
            )
            if row["capture_status"] == "CACHED_VERIFIED":
                cached += 1
                row["raw_sha256"] = metadata.get("raw_sha256")
                row["raw_size"] = metadata.get("raw_size")
            prior = all_paths.get(path)
            if prior is None:
                all_paths[path] = dict(row)
            else:
                prior["families"] = sorted({
                    *[str(value) for value in prior.get("families", [prior.get("family")])],
                    family,
                })
        family_summaries.append({
            "family": family,
            "positive_discovery_paths": len(rows),
            "cached_verified_paths": cached,
            "missing_paths": len(rows) - cached,
            "normalizer_input": family not in {"AVATAR_CONFIG", "MONSTER_AI"},
            "notes": (
                "Avatar Config supplies source-side Ability/SkillList join evidence; it is not a behavior document."
                if family == "AVATAR_CONFIG"
                else "ComplexSkillAI is retained for Monster AI reconstruction; no behavior normalizer claim is made yet."
                if family == "MONSTER_AI"
                else "Pinned positive discovery paths only."
            ),
        })
    normalizer_families = {
        "AVATAR_ABILITY", "MONSTER_ABILITY", "STAGE_BUFF_ABILITY",
        "STAGE_ADVENTURE_MODIFIER", "GLOBAL_MODIFIER", "LIGHTCONE_ABILITY",
        "RELIC_SET_ABILITY",
    }
    normalized_paths = [
        row for row in all_paths.values()
        if row["family"] in normalizer_families
    ]
    payload = {
        "report_id": "FULL-CONTENT-BEHAVIOR-INGESTION-MANIFEST-001",
        "game_version": CONTENT_VERSION,
        "status": "FAMILY_SCOPED_POSITIVE_DISCOVERY_RETRIEVAL_PLAN",
        "source": {
            "repository": source_manifest.get("repository_url"),
            "source": TURN_BASED_SOURCE,
            "selected_commit": TURN_BASED_COMMIT,
            "declared_game_version": source_manifest.get("declared_game_version"),
            "version_relation": "CLOSE_4.4.0_TO_4.4.54",
            "discovery_path": str(discovery_path).replace("\\", "/"),
            "discovery_sha256": _sha256(discovery_path),
            "tree_truncated": bool(discovery.get("tree_truncated")),
            "equipment_directory_discovery_path": (
                str(equipment_discovery_path).replace("\\", "/")
                if equipment_discovery_path.exists() else None
            ),
            "equipment_directory_discovery_sha256": (
                _sha256(equipment_discovery_path)
                if equipment_discovery_path.exists() else None
            ),
        },
        "selection_rule": {
            "include": "positive paths from the pinned discovery artifact, .json excluding .layout.json",
            "monster_exclude": ["/Camera/"],
            "normalizer_input_families": sorted(normalizer_families),
            "not_discovered_meaning": "NOT_DISCOVERED_IN_TRUNCATED_TREE, never NOT_PRESENT_IN_SOURCE",
        },
        "families": family_summaries,
        "paths": sorted(all_paths.values(), key=lambda row: row["path"]),
        "normalizer_paths": sorted(normalized_paths, key=lambda row: row["path"]),
        "known_uncovered_families": [
            {
                "family": family,
                "status": "NOT_DISCOVERED_IN_CURRENT_TRUNCATED_TREE",
                "next_action": "Run a family-scoped pinned discovery; do not infer absence.",
            }
            for family in (
                ("MODE_BUFF", "ENVIRONMENT_BUFF")
                if equipment_discovery_path.exists()
                else ("LIGHTCONE", "RELIC_SET", "MODE_BUFF", "ENVIRONMENT_BUFF")
            )
        ],
    }
    payload["manifest_sha256"] = stable_hash(payload)
    target = output_path or Path("data") / "semantics" / CONTENT_VERSION / "full_reconstruction" / "full_content_behavior_ingestion_manifest_001.json"
    write_json(target, payload)
    return payload
