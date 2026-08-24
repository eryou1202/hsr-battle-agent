#!/usr/bin/env python3
"""Create an auditable discriminator slice from a generated registry."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--discriminator", required=True, type=int, action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    source: dict[str, Any] = json.loads(args.input.read_text(encoding="utf-8"))
    mappings = source.get("mappings")
    if not isinstance(mappings, list):
        raise RuntimeError("source registry has no mappings list")
    requested = sorted(set(args.discriminator))
    selected = [row for row in mappings if row.get("discriminator") in requested]
    found = sorted(row["discriminator"] for row in selected)
    if found != requested:
        raise RuntimeError(f"requested/found discriminator mismatch: {requested} != {found}")
    if any(row.get("mapping_status") != "CONCRETE_PARSER_RECOVERED" for row in selected):
        raise RuntimeError("every selected mapping must have a recovered concrete parser")

    result = {
        "schema": "generated_config_registry_slice/1",
        "game_version": source.get("game_version"),
        "status": "GENERATED_CONFIG_DISCRIMINATOR_SLICE_CONFIRMED",
        "source_registry": {
            "path": str(args.input),
            "sha256": sha256(args.input),
            "schema": source.get("schema"),
            "status": source.get("status"),
        },
        "registry": source.get("registry"),
        "statistics": source.get("statistics"),
        "requested_discriminators": requested,
        "mappings": selected,
        "claims_not_made": source.get("claims_not_made", []),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output} mappings={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
