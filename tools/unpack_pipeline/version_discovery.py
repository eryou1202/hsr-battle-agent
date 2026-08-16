# -*- coding: utf-8 -*-
"""STAGE 1 - VERSION_DISCOVERY.

Game version is read from the client's self-reported BinaryVersion.bytes
(`StarRail_Data\\StreamingAssets\\BinaryVersion.bytes`), never from the
installation directory name.  The manifest records both the reported game
version and the raw build string so the two can never be confused.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import sha256_file, utc_now, write_json
from . import PIPELINE_SCHEMA_VERSION, PIPELINE_VERSION

VERSION_RE = re.compile(r"(?<!\d)(\d+\.\d+\.\d+(?:\.\d+)?)(?!\d)")
BUILD_RE = re.compile(r"\d{8}-\d{4}-[A-Za-z0-9]+-\d+-[A-Za-z0-9]+(?:\d+\.\d+\.\d+)?-[A-Za-z0-9]+")


def read_binary_version(game_root: Path) -> dict[str, Any]:
    """Read BinaryVersion.bytes and extract version + build string."""
    candidate = game_root / "StarRail_Data" / "StreamingAssets" / "BinaryVersion.bytes"
    if not candidate.is_file():
        raise FileNotFoundError(
            "BinaryVersion.bytes not found under "
            f"{game_root / 'StarRail_Data' / 'StreamingAssets'}")
    raw = candidate.read_bytes()
    text = raw.decode("latin-1", "replace")
    versions = [m.group(1) for m in VERSION_RE.finditer(text)]
    builds = BUILD_RE.findall(text)
    if not versions:
        raise ValueError(
            f"no x.y.z version token found in {candidate}; refusing to infer "
            "the version from the directory name")
    version = versions[0]
    # Prefer the longest version-looking token (handles 4.4.53 vs 4.4.53.1).
    for token in versions[1:]:
        if len(token) > len(version):
            version = token
    build_string = builds[0] if builds else None
    return {
        "game_version": version,
        "binary_version": version,
        "build_string": build_string,
        "version_source": str(candidate),
        "version_source_rel": str(candidate.relative_to(game_root)) if _is_relative(candidate, game_root) else str(candidate),
        "version_source_size": candidate.stat().st_size,
        "version_source_sha256": sha256_file(candidate),
        "raw_utf8_preview": raw.decode("utf-8", "replace")[:256],
    }


def _is_relative(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def build_manifest(game_root: Path, output_dir: Path) -> dict[str, Any]:
    info = read_binary_version(game_root)
    game_assembly = game_root / "GameAssembly.dll"
    metadata = game_root / "StarRail_Data" / "il2cpp_data" / "Metadata" / "global-metadata.dat"
    manifest: dict[str, Any] = {
        "schema": "unpack_pipeline_manifest/1",
        "pipeline_schema_version": PIPELINE_SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": utc_now(),
        "game_root": str(game_root),
        "game_version": info["game_version"],
        "binary_version": info["binary_version"],
        "build_string": info["build_string"],
        "platform": "windows",
        "version_source": info["version_source_rel"],
        "version_source_sha256": info["version_source_sha256"],
        "version_source_size": info["version_source_size"],
        "version_discovery_rule": "BinaryVersion.bytes token only; directory name is never trusted",
    }
    manifest["GameAssembly"] = {
        "path": str(game_assembly),
        "exists": game_assembly.is_file(),
    }
    if game_assembly.is_file():
        manifest["GameAssembly"].update({
            "size": game_assembly.stat().st_size,
            "sha256": sha256_file(game_assembly),
        })
    manifest["global_metadata"] = {
        "path": str(metadata),
        "exists": metadata.is_file(),
    }
    if metadata.is_file():
        manifest["global_metadata"].update({
            "size": metadata.stat().st_size,
            "sha256": sha256_file(metadata),
        })
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    return manifest


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-root", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()
    manifest = build_manifest(args.game_root, args.output_dir)
    print(f"wrote {args.output_dir / 'manifest.json'}")
    print(f"game_version={manifest['game_version']} "
          f"source={manifest['version_source']} build={manifest['build_string']}")
