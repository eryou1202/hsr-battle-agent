# -*- coding: utf-8 -*-
"""Canonical manifest and deterministic export for local planner data."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes
from hsr_battle_agent.planner.generator import GenerationPolicy, GenerationResult
from hsr_battle_agent.planner.trajectory import (
    ExclusionRecord,
    Trajectory,
    TrajectoryError,
    TrajectoryValidationLabel,
    VALIDATION_VOCABULARY_VERSION,
)

DATASET_SCHEMA = "terra_planner_dataset/1"
CONTENT_TARGET = "HSR-4.4.54"


class DatasetError(ValueError):
    pass


def _identity(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_v2_bytes(document)).hexdigest()


class PlannerDataset:
    __slots__ = ("_document", "_trajectories", "_exclusions")

    _FIELDS = {
        "schema", "dataset_id", "generator", "content_target",
        "scenario_identity", "policy_identity", "generation_horizon",
        "validation_vocabulary", "classification", "trajectory_count",
        "exclusion_count", "trajectory_identities", "exclusion_identities",
        "trajectories", "exclusions", "golden_count", "native_trace_count",
        "oracle_status",
    }

    def __init__(self, document: Mapping[str, Any]) -> None:
        if not isinstance(document, Mapping) or set(document) != self._FIELDS:
            raise DatasetError("dataset has missing or unknown fields")
        owned = copy.deepcopy(dict(document))
        if owned["schema"] != DATASET_SCHEMA:
            raise DatasetError("unknown planner-dataset schema")
        if owned["content_target"] != CONTENT_TARGET:
            raise DatasetError("dataset content target is not HSR 4.4.54")
        if owned["golden_count"] != 0 or owned["native_trace_count"] != 0:
            raise DatasetError("local dataset cannot claim Golden or native traces")
        if owned["oracle_status"] != "NO_INDEPENDENT_ORACLE":
            raise DatasetError("local dataset oracle status changed")
        expected_classification = {
            "scope": "LOCAL_SANDBOX_EXTENSION",
            "validation": TrajectoryValidationLabel.DETERMINISTIC_REPLAY_ONLY.value,
            "golden": "NOT_GOLDEN",
            "native_trace": "NOT_NATIVE_TRACE",
        }
        if owned["classification"] != expected_classification:
            raise DatasetError("dataset classification overclaims validation")
        vocabulary = owned["validation_vocabulary"]
        if vocabulary != {
            "version": VALIDATION_VOCABULARY_VERSION,
            "assigned_label": TrajectoryValidationLabel.DETERMINISTIC_REPLAY_ONLY.value,
        }:
            raise DatasetError("unknown validation vocabulary")
        trajectories = [Trajectory.from_dict(item) for item in owned["trajectories"]]
        exclusions = [ExclusionRecord.from_dict(item) for item in owned["exclusions"]]
        if not trajectories:
            raise DatasetError("planner dataset requires at least one complete trajectory")
        if owned["trajectory_count"] != len(trajectories):
            raise DatasetError("trajectory count mismatch")
        if owned["exclusion_count"] != len(exclusions):
            raise DatasetError("exclusion count mismatch")
        if owned["trajectory_identities"] != [item.trajectory_id for item in trajectories]:
            raise DatasetError("ordered trajectory identity list mismatch")
        if owned["exclusion_identities"] != [item.exclusion_id for item in exclusions]:
            raise DatasetError("ordered exclusion identity list mismatch")
        generation_policy = GenerationPolicy.from_dict(owned["generator"])
        if owned["generation_horizon"] != generation_policy.max_depth:
            raise DatasetError("generation horizon differs from generator policy")
        first = trajectories[0].to_dict()
        if first["scenario_identity"] != owned["scenario_identity"]:
            raise DatasetError("dataset scenario identity mismatch")
        first_policy = first["initial_state"]["snapshot"]["policy_identity"]
        if first_policy != owned["policy_identity"]:
            raise DatasetError("dataset policy identity mismatch")
        for trajectory in trajectories:
            data = trajectory.to_dict()
            if data["scenario_identity"] != owned["scenario_identity"]:
                raise DatasetError("mixed scenario identities are forbidden")
            if data["generation_policy"] != owned["generator"]:
                raise DatasetError("mixed generation policies are forbidden")
            if data["initial_state"]["snapshot"]["policy_identity"] != owned["policy_identity"]:
                raise DatasetError("mixed snapshot policies are forbidden")
        payload = copy.deepcopy(owned)
        supplied = payload.pop("dataset_id")
        if supplied != _identity(payload):
            raise DatasetError("dataset identity mismatch")
        self._document = owned
        self._trajectories = tuple(trajectories)
        self._exclusions = tuple(exclusions)

    @classmethod
    def from_generation(cls, result: GenerationResult) -> "PlannerDataset":
        if not isinstance(result, GenerationResult) or not result.trajectories:
            raise DatasetError("generation result must contain complete trajectories")
        trajectories = [item.to_dict() for item in result.trajectories]
        exclusions = [item.to_dict() for item in result.exclusions]
        policy_identity = trajectories[0]["initial_state"]["snapshot"]["policy_identity"]
        document: dict[str, Any] = {
            "schema": DATASET_SCHEMA,
            "generator": result.policy.to_dict(),
            "content_target": CONTENT_TARGET,
            "scenario_identity": result.scenario_identity,
            "policy_identity": copy.deepcopy(policy_identity),
            "generation_horizon": result.policy.max_depth,
            "validation_vocabulary": {
                "version": VALIDATION_VOCABULARY_VERSION,
                "assigned_label": TrajectoryValidationLabel.DETERMINISTIC_REPLAY_ONLY.value,
            },
            "classification": {
                "scope": "LOCAL_SANDBOX_EXTENSION",
                "validation": TrajectoryValidationLabel.DETERMINISTIC_REPLAY_ONLY.value,
                "golden": "NOT_GOLDEN",
                "native_trace": "NOT_NATIVE_TRACE",
            },
            "trajectory_count": len(trajectories),
            "exclusion_count": len(exclusions),
            "trajectory_identities": [item.trajectory_id for item in result.trajectories],
            "exclusion_identities": [item.exclusion_id for item in result.exclusions],
            "trajectories": trajectories,
            "exclusions": exclusions,
            "golden_count": 0,
            "native_trace_count": 0,
            "oracle_status": "NO_INDEPENDENT_ORACLE",
        }
        document["dataset_id"] = _identity(document)
        return cls(document)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlannerDataset":
        return cls(data)

    @property
    def dataset_id(self) -> str:
        return self._document["dataset_id"]

    @property
    def trajectories(self) -> tuple[Trajectory, ...]:
        return self._trajectories

    @property
    def exclusions(self) -> tuple[ExclusionRecord, ...]:
        return self._exclusions

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._document)

    def to_bytes(self) -> bytes:
        return (
            json.dumps(
                self._document,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")


def export_dataset(
    dataset: PlannerDataset,
    output_directory: str | Path,
    *,
    filename: str = "terra_planner_dataset_v1.json",
) -> Path:
    if not isinstance(dataset, PlannerDataset):
        raise DatasetError("dataset must be PlannerDataset")
    directory = Path(output_directory)
    if not directory.exists() or not directory.is_dir():
        raise DatasetError("caller-supplied output directory must already exist")
    if Path(filename).name != filename or not filename.endswith(".json"):
        raise DatasetError("filename must be a simple .json basename")
    target = directory / filename
    target.write_bytes(dataset.to_bytes())
    return target


def load_dataset(path: str | Path) -> PlannerDataset:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetError(f"cannot read planner dataset: {exc}") from exc
    try:
        return PlannerDataset.from_dict(document)
    except (TrajectoryError, ValueError, TypeError) as exc:
        raise DatasetError(f"invalid planner dataset: {exc}") from exc
