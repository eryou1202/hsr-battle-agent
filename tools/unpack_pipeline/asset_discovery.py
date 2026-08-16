# -*- coding: utf-8 -*-
"""STAGE 2 - ASSET_DISCOVERY.

Static inventory of the three asset classes the pipeline consumes:
  * GameAssembly.dll
  * global-metadata.dat
  * DesignData hash-named .bytes files + DesignV channel files
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .common import sha256_file, utc_now, write_json

DESIGNDATA_DIRS = (
    "StarRail_Data/Persistent/DesignData/Windows",
    "StarRail_Data/StreamingAssets/DesignData",
)

CORE_FILES = {
    "GameAssembly.dll": "GameAssembly.dll",
    "global-metadata.dat": "StarRail_Data/il2cpp_data/Metadata/global-metadata.dat",
    "BinaryVersion.bytes": "StarRail_Data/StreamingAssets/BinaryVersion.bytes",
    "ClientConfig.bytes": "StarRail_Data/StreamingAssets/ClientConfig.bytes",
}


def _md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def discover(game_root: Path, output_dir: Path) -> dict[str, Any]:
    if not game_root.is_dir():
        raise NotADirectoryError(f"game root does not exist: {game_root}")
    core = {}
    for label, rel in CORE_FILES.items():
        path = game_root / rel
        if path.is_file():
            core[label] = {
                "path": str(path),
                "relative_path": rel,
                "exists": True,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        else:
            core[label] = {"path": str(path), "relative_path": rel, "exists": False}

    design_dirs = []
    for rel in DESIGNDATA_DIRS:
        path = game_root / rel
        if path.is_dir():
            design_dirs.append({"path": str(path), "relative_path": rel})

    design_files = []
    seen: set[str] = set()
    for entry in design_dirs:
        root = Path(entry["path"])
        for path in sorted(root.rglob("*.bytes")):
            key = str(path).lower()
            if key in seen or not path.is_file():
                continue
            seen.add(key)
            name = path.name
            stem = path.stem.lower()
            design_files.append({
                "file_name": name,
                "path": str(path),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
                "md5_name_match": (
                    len(stem) == 32 and all(c in "0123456789abcdef" for c in stem)
                    and _md5_file(path) == stem
                ),
                "channel": _classify_channel(name),
            })
    design_files.sort(key=lambda r: (-r["size"], r["file_name"]))

    inventory = {
        "schema": "unpack_pipeline_asset_inventory/1",
        "generated_at": utc_now(),
        "game_root": str(game_root),
        "core_files": core,
        "design_data_directories": design_dirs,
        "design_data_files": design_files,
        "design_data_file_count": len(design_files),
        "missing_required": [
            label for label, item in core.items()
            if label in ("GameAssembly.dll", "global-metadata.dat") and not item.get("exists")
        ],
    }
    write_json(output_dir / "asset_inventory.json", inventory)
    return inventory


def _classify_channel(name: str) -> str:
    lowered = name.lower()
    if lowered.startswith("m_designv"):
        return "manifest_index"
    if lowered.startswith("designv_"):
        return "design_archive_index"
    if lowered == "m_nativedatav.bytes":
        return "native_manifest_index"
    if len(lowered.split(".")[0]) == 32:
        return "hash_named_chunk"
    return "other"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-root", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()
    inv = discover(args.game_root, args.output_dir)
    print(f"wrote {args.output_dir / 'asset_inventory.json'}")
    print(f"core={len(inv['core_files'])} design_files={len(inv['design_data_files'])}")
