# -*- coding: utf-8 -*-
"""STAGE 3 - DESIGNDATA_STRUCTURAL_PARSE.

Structural, semantic-neutral parse of the DesignData archive currently
installed on disk.  It reuses the adaptive ability-directory algorithm from
`tools/unpack/probe_ability_directory_adaptive.py` and preserves unknown
ULEB/bitfield values under neutral field names.

No new reverse work is performed here.  Values such as the historical Black
Swan structural codes 2/8/14/16 are retained as `structural_code` with
`semantic_status = UNKNOWN`; registry-range membership is never promoted to
serializer identity.
"""
from __future__ import annotations

import csv
import mmap
import struct
from pathlib import Path
from typing import Any

from .common import utc_now, write_json

DEFAULT_NAMES = [
    "Avatar_BlackSwan_00_Skill01_Phase01",
    "Avatar_BlackSwan_00_Skill01_Phase02",
    "Avatar_BlackSwan_00_Skill02_Phase01",
    "Avatar_BlackSwan_00_Skill02_Phase02",
    "Avatar_BlackSwan_00_Skill03_Cutin",
    "Avatar_BlackSwan_00_Skill03_Phase01",
    "Avatar_BlackSwan_00_Skill03_Phase02",
    "Avatar_BlackSwan_00_PassiveSkill01",
    "Avatar_BlackSwan_00_SkillMazeInLevel",
    "Avatar_BlackSwan_00_SkillMazeInLevel_Insert",
    "Avatar_BlackSwan_00_SkillTree02",
    "Avatar_BlackSwan_00_SkillTree03",
    "Avatar_BlackSwan_00_Rank01",
    "Avatar_BlackSwan_00_Rank02",
    "Avatar_BlackSwan_00_Rank06",
]


def _decode_zigzag(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def _read_uleb128(data: bytes, offset: int, max_bytes: int = 10) -> tuple[int, int] | None:
    value = 0
    shift = 0
    for index in range(max_bytes):
        position = offset + index
        if position >= len(data):
            return None
        byte = data[position]
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return value, index + 1
        shift += 7
    return None


def _find_all(data: mmap.mmap, needle: bytes):
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            return
        yield offset
        start = offset + 1


def _ascii_context(data: mmap.mmap, offset: int, before: int = 24, after: int = 64) -> str:
    start = max(0, offset - before)
    end = min(len(data), offset + after)
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data[start:end])


def _hex_context(data: mmap.mmap, offset: int, before: int = 24, after: int = 64) -> str:
    start = max(0, offset - before)
    end = min(len(data), offset + after)
    return " ".join(f"{b:02X}" for b in data[start:end])


def _locate_archive(inventory: dict[str, Any]) -> tuple[Path, dict[str, int]]:
    """Select the DesignData chunk carrying the known ability-directory names."""
    scored: list[tuple[int, Path, dict[str, int]]] = []
    for row in inventory.get("design_data_files", []):
        if row.get("channel") not in ("hash_named_chunk", "design_archive_index"):
            continue
        path = Path(row["path"])
        try:
            with path.open("rb") as fh:
                with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
                    hits: dict[str, int] = {}
                    for name in DEFAULT_NAMES:
                        pattern = bytes([len(name.encode("ascii"))]) + name.encode("ascii")
                        hits[name] = sum(1 for _ in _find_all(data, pattern))
        except (OSError, ValueError):
            continue
        score = sum(1 for count in hits.values() if count > 0)
        if score:
            scored.append((score, path, hits))
    if not scored:
        raise FileNotFoundError(
            "no DesignData chunk contains the known ability-directory structural names")
    scored.sort(key=lambda item: (-item[0], -item[1].stat().st_size))
    path, hits = scored[0][1], scored[0][2]
    return path, hits


def _directory_rows(archive: Path, game_version: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Adaptive directory decode (same CONFIRMED structural algorithm as the
    historical probe, with the game version injected from the manifest)."""
    with archive.open("rb") as fh:
        data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        entries: list[dict[str, Any]] = []
        record_hits: list[dict[str, Any]] = []
        for name in DEFAULT_NAMES:
            raw = name.encode("ascii")
            pattern = bytes([len(raw)]) + raw
            for occ in _find_all(data, pattern):
                rec: dict[str, Any] = {"name": name, "occ": occ}
                marker_pos = occ + len(pattern)
                if data[marker_pos:marker_pos + 1] == b"\x01":
                    parsed = _read_uleb128(data, marker_pos + 1)
                    if parsed is not None:
                        enc, enc_size = parsed
                        dec = _decode_zigzag(enc)
                        if dec <= 0x40000:
                            rec["is_entry"] = True
                            rec.update(enc=enc, enc_size=enc_size, dec=dec,
                                       tail=data[marker_pos + 1 + enc_size])
                            entries.append(rec)
                        else:
                            rec["is_entry"] = False
                    else:
                        rec["is_entry"] = False
                else:
                    rec["is_entry"] = False
                record_hits.append(rec)

        base_votes: dict[int, list[tuple]] = {}
        for entry in entries:
            for rec in record_hits:
                if rec["name"] != entry["name"]:
                    continue
                for delta in (2, 3, 4):
                    base = rec["occ"] - delta - entry["dec"]
                    if 0 <= base < len(data):
                        base_votes.setdefault(base, []).append(
                            (entry["name"], entry["occ"], rec["occ"], delta, entry["dec"]))
        ranked = sorted(base_votes.items(), key=lambda kv: -len(kv[1]))
        if not ranked:
            return [], {"status": "FAILED", "reason": "no base candidate"}
        best_base, best_votes = ranked[0]
        strong = len(best_votes) >= max(3, len(DEFAULT_NAMES) // 3)

        entry_offs = sorted(e["occ"] for e in entries if e.get("is_entry"))
        best_block: list[int] = []
        current: list[int] = []
        for off in entry_offs:
            if current and off - current[-1] > 64:
                if len(current) > len(best_block):
                    best_block = current
                current = []
            current.append(off)
        if len(current) > len(best_block):
            best_block = current
        block_set = set(best_block)

        rows: list[dict[str, Any]] = []
        for entry in entries:
            if not entry.get("is_entry") or entry["occ"] not in block_set:
                continue
            base = best_base
            record_start = base + entry["dec"]
            delta = None
            for rec in record_hits:
                if rec["name"] != entry["name"]:
                    continue
                d = rec["occ"] - record_start
                if 2 <= d <= 4:
                    delta = d
                    break
            rows.append({
                "game_version": game_version,
                "name": entry["name"],
                "name_len": len(entry["name"]),
                "entry_offset_hex": f"0x{entry['occ']:X}",
                "marker": "0x01",
                "encoded": entry["enc"],
                "encoded_hex": f"0x{entry['enc']:X}",
                "encoded_size": entry["enc_size"],
                "tail_hex": f"0x{entry['tail']:02X}",
                "decoded": entry["dec"],
                "decoded_hex": f"0x{entry['dec']:X}",
                "base_solved_hex": f"0x{base:X}",
                "record_start_hex": f"0x{record_start:X}",
                "name_delta": delta if delta is not None else "",
                "record_context_hex": _hex_context(data, record_start),
                "record_context_ascii": _ascii_context(data, record_start),
            })
        stats = {
            "status": "OK" if rows else "FAILED",
            "base_solved_hex": f"0x{best_base:X}",
            "base_votes": len(best_votes),
            "base_strong": strong,
            "entry_candidates": len(entries),
            "directory_rows": len(rows),
            "directory_block_entries": len(best_block),
        }
        return rows, stats


def _record_prefixes(archive: Path, rows: list[dict[str, Any]], records_dir: Path) -> list[dict[str, Any]]:
    """Preserve unknown structural values with neutral names.

    The first two ULEBs are field-presence bitfields and the value after the
    name marker is recorded as `structural_code`.  No semantic name is
    assigned.
    """
    records_dir.mkdir(parents=True, exist_ok=True)
    data = archive.read_bytes()
    prefixes: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        start = int(row["record_start_hex"], 16)
        name = row["name"]
        outer = _read_uleb128(data, start)
        bitfield = _read_uleb128(data, start + (outer[1] if outer else 0))
        if outer is None or bitfield is None:
            continue
        name_offset = start + outer[1] + bitfield[1]
        name_len = data[name_offset] if name_offset < len(data) else 0
        parsed_name_bytes = data[name_offset + 1: name_offset + 1 + name_len]
        parsed_name = parsed_name_bytes.decode("utf-8", "replace")
        marker_pos = name_offset + 1 + name_len
        marker = data[marker_pos] if marker_pos < len(data) else None
        structural = _read_uleb128(data, marker_pos + 1) if marker == 0x01 else None
        raw = data[start:start + 64]
        record = {
            "record_index": index,
            "record_name": name,
            "record_start_hex": f"0x{start:X}",
            "field_0_uleb": outer[0],
            "field_0_uleb_size": outer[1],
            "field_1_uleb": bitfield[0],
            "field_1_uleb_size": bitfield[1],
            "parsed_name": parsed_name,
            "name_matches": parsed_name == name,
            "name_marker": f"0x{marker:02X}" if marker is not None else None,
            "structural_code": structural[0] if structural is not None else None,
            "structural_code_size": structural[1] if structural is not None else None,
            "raw_value_prefix_hex": raw[:32].hex(" "),
            "structure_status": "STRUCTURAL_VALUE_CONFIRMED",
            "semantic_status": "UNKNOWN",
            "note": ("ULEB values are preserved as structural values. "
                     "Registry-range membership does not imply serializer identity."),
        }
        out = records_dir / f"{index:02d}_{name}.bin"
        out.write_bytes(raw)
        record["raw_prefix_file"] = str(out)
        prefixes.append(record)
    return prefixes


def discover(game_root: Path, inventory: dict[str, Any], manifest: dict[str, Any],
             output_dir: Path) -> dict[str, Any]:
    if not inventory.get("design_data_files"):
        raise ValueError("asset inventory contains no DesignData files")
    archive, name_hits = _locate_archive(inventory)
    version = manifest["game_version"]
    rows, stats = _directory_rows(archive, version)
    prefixes = _record_prefixes(archive, rows, output_dir / "black_swan_records") if rows else []

    result: dict[str, Any] = {
        "schema": "unpack_pipeline_design_structural/1",
        "generated_at": utc_now(),
        "game_version": version,
        "ability_archive": {
            "path": str(archive),
            "name_hit_count": sum(1 for v in name_hits.values() if v),
            "name_hits": name_hits,
        },
        "directory": stats,
        "directory_rows": rows,
        "unknown_field_policy": {
            "rule": ("unresolved outer tags / bitfields / structural values are kept with "
                     "neutral field names (field_x, structural_code, raw_value)"),
            "semantic_status": "UNKNOWN",
            "black_swan_2_8_14_16_status": "STRUCTURAL_VALUE_CONFIRMED / SERIALIZER_SEMANTIC_UNRESOLVED",
        },
        "record_prefixes": prefixes,
    }
    design_dir = output_dir
    design_dir.mkdir(parents=True, exist_ok=True)
    if rows:
        csv_path = output_dir / "ability_directory.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        result["ability_directory_csv"] = str(csv_path)
    write_json(output_dir / "design_structural.json", result)
    return result


if __name__ == "__main__":
    import argparse
    from .asset_discovery import discover as asset_discover
    from .version_discovery import build_manifest
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-root", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()
    manifest = build_manifest(args.game_root, args.output_dir)
    inventory = asset_discover(args.game_root, args.output_dir)
    result = discover(args.game_root, inventory, manifest, args.output_dir / "design")
    print(f"archive={result['ability_archive']['path']} rows={len(result['directory_rows'])}")
