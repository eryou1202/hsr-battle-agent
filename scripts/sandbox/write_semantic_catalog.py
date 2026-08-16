#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write the explicit semantic artifact catalog for the sandbox bootstrap.

The catalog is the only source of truth for which semantic artifacts are
loaded by ``PrimitiveRegistry.create_default``.  Filesystem globs are not
used.  This script computes the sha256 values it records.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "data" / "semantics" / "4.4.54" / "catalog.json"

ARTIFACTS = [
    {
        "path": "vertical_slice_01.json",
        "schema": "battle_semantics_vertical_slice/1",
        "enabled": True,
    },
    {
        "path": "dynamic_value_batch_02.json",
        "schema": "battle_semantics_batch/1",
        "enabled": True,
    },
    {
        "path": "fixpoint_comparison_batch_03.json",
        "schema": "battle_semantics_batch/1",
        "enabled": True,
    },
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    entries = []
    for item in ARTIFACTS:
        path = CATALOG.parent / item["path"]
        if not path.is_file():
            raise SystemExit(f"missing artifact: {path}")
        entries.append(
            {
                "path": item["path"],
                "schema": item["schema"],
                "sha256": sha256_file(path),
                "enabled": item["enabled"],
            }
        )
    doc = {
        "schema": "battle_semantics_catalog/1",
        "game_version": "4.4.54",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "artifacts": entries,
    }
    CATALOG.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {CATALOG}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO / "src"))
    raise SystemExit(main())
