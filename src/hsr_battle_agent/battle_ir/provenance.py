# -*- coding: utf-8 -*-
"""Source provenance for recovered battle semantics.

These values are evidence / debug / audit metadata only.  Runtime execution
must never branch on ``method_index`` or ``native_rva``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

PROVENANCE_NOTE_DEFAULT = (
    "RVA and method index are provenance only; runtime logic must not depend on them"
)


@dataclass(frozen=True)
class SourceProvenance:
    game_version: str
    runtime_type: str
    method: str
    method_index: int
    native_rva: str
    evidence_level: str
    note: str = PROVENANCE_NOTE_DEFAULT

    def __post_init__(self) -> None:
        if not self.game_version:
            raise ValueError("game_version must be non-empty")
        if not self.runtime_type:
            raise ValueError("runtime_type must be non-empty")
        if not self.method:
            raise ValueError("method must be non-empty")
        if isinstance(self.method_index, bool) or not isinstance(self.method_index, int):
            raise TypeError("method_index must be an int")
        if self.method_index < 0:
            raise ValueError("method_index must be >= 0")

    def source_reference(self) -> str:
        """Compact debug/audit reference; never used for dispatch."""
        return f"{self.game_version}:{self.runtime_type}.{self.method}:{self.method_index}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_version": self.game_version,
            "runtime_type": self.runtime_type,
            "method": self.method,
            "method_index": self.method_index,
            "native_rva": self.native_rva,
            "evidence_level": self.evidence_level,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceProvenance":
        try:
            return cls(
                game_version=data["game_version"],
                runtime_type=data["runtime_type"],
                method=data["method"],
                method_index=data["method_index"],
                native_rva=data["native_rva"],
                evidence_level=data["evidence_level"],
                note=data.get("note", PROVENANCE_NOTE_DEFAULT),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"invalid SourceProvenance dict: {exc}") from exc
