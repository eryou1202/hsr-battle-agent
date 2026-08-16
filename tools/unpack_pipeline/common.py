# -*- coding: utf-8 -*-
"""Shared helpers for the unpack pipeline.

The pipeline deliberately reuses the pure-Python PE reader and the byte-level
dispatch helpers from the reverse session.  Capstone-dependent historical
tools are treated as optional enrichment and are never required for a static
pipeline run.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REVERSE_SCRIPTS = REPO_ROOT / "tools" / "reverse" / "scripts"
if str(REVERSE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(REVERSE_SCRIPTS))

from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

STAGE_NAMES = [
    "VERSION_DISCOVERY",
    "ASSET_DISCOVERY",
    "DESIGNDATA_STRUCTURAL_PARSE",
    "MHY_METADATA_PARSE",
    "TYPE_REGISTRY",
    "MEMBER_REGISTRY",
    "METHOD_CODE_REGISTRY",
    "DESIGN_RUNTIME_BRIDGE",
    "NORMALIZATION",
    "VERSION_DIFF",
]

STATIC_STAGES = {
    "VERSION_DISCOVERY",
    "ASSET_DISCOVERY",
    "DESIGNDATA_STRUCTURAL_PARSE",
    "MHY_METADATA_PARSE",
    "TYPE_REGISTRY",
    "MEMBER_REGISTRY",
    "METHOD_CODE_REGISTRY",
    "DESIGN_RUNTIME_BRIDGE",
    "NORMALIZATION",
    "VERSION_DIFF",
}

RUNTIME_OPTIONAL_COMPONENT = "DESIGN_RUNTIME_BRIDGE.generated_polymorphic_registry"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, data: Any, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent, ensure_ascii=False)
        fh.write("\n")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class StageResult:
    stage: str
    status: str  # PASS | FAIL | NOT_RUN | WARN
    artifacts: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    runtime: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "artifacts": [str(a) for a in self.artifacts],
            "counts": self.counts,
            "warnings": self.warnings,
            "error": self.error,
            "runtime": self.runtime,
        }


@dataclass
class Anomaly:
    stage: str
    expected_invariant: str
    observed_result: str
    severity: str  # INFO | WARN | ERROR
    suggested_follow_up: str

    def as_dict(self) -> dict[str, str]:
        return {
            "stage": self.stage,
            "expected_invariant": self.expected_invariant,
            "observed_result": self.observed_result,
            "severity": self.severity,
            "suggested_follow_up": self.suggested_follow_up,
        }


def stage_key(name: str) -> int:
    try:
        return STAGE_NAMES.index(name)
    except ValueError:
        return 999


def load_pe(game_assembly: Path) -> PeImage:
    if not game_assembly.is_file():
        raise FileNotFoundError(f"GameAssembly.dll not found: {game_assembly}")
    return PeImage(game_assembly)
