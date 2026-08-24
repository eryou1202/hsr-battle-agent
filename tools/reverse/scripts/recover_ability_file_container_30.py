#!/usr/bin/env python3
"""Recover one file-local TurnBasedAbilityConfigList from DesignData.

The DesignData ability archive stores a file-local object collection followed
by a name/offset directory.  This tool deliberately does not parse ability
actions.  It recovers only the generic outer framing:

* the contiguous directory for an ability-name prefix;
* its ZigZag-relative object anchors;
* the shared payload base;
* the outer presence bitmap and collection count; and
* each object's field-presence bitmap/name boundary.

All offsets are derived from the supplied archive.  Character names are input
data, not parser constants.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mmap
from collections import defaultdict
from pathlib import Path


NAME_BYTES = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
)


def read_uleb(data: mmap.mmap, offset: int, limit: int, max_bytes: int = 10) -> tuple[int, int] | None:
    value = 0
    shift = 0
    for index in range(max_bytes):
        pos = offset + index
        if pos >= limit:
            return None
        byte = data[pos]
        value |= (byte & 0x7F) << shift
        if byte & 0x80 == 0:
            return value, index + 1
        shift += 7
    return None


def encode_uleb(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def zigzag(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_named_strings(data: mmap.mmap, prefix: bytes) -> list[dict]:
    hits: list[dict] = []
    cursor = 0
    limit = len(data)
    while True:
        string_start = data.find(prefix, cursor)
        if string_start < 0:
            break
        string_end = string_start + len(prefix)
        while string_end < limit and data[string_end] in NAME_BYTES:
            string_end += 1
        raw = bytes(data[string_start:string_end])
        prefix_offset = None
        prefix_size = None
        for size in range(1, 6):
            candidate = string_start - size
            if candidate < 0:
                continue
            parsed = read_uleb(data, candidate, string_start)
            if parsed == (len(raw), size) and bytes(data[candidate:string_start]) == encode_uleb(len(raw)):
                prefix_offset = candidate
                prefix_size = size
                break
        if prefix_offset is not None:
            hits.append(
                {
                    "name": raw.decode("ascii"),
                    "prefix_offset": prefix_offset,
                    "prefix_size": prefix_size,
                    "string_start": string_start,
                    "string_end": string_end,
                }
            )
        cursor = string_start + 1
    return hits


def directory_candidates(data: mmap.mmap, hits: list[dict]) -> list[dict]:
    out: list[dict] = []
    limit = len(data)
    for hit in hits:
        marker_offset = hit["string_end"]
        if marker_offset >= limit or data[marker_offset] != 1:
            continue
        parsed = read_uleb(data, marker_offset + 1, limit)
        if parsed is None:
            continue
        encoded, encoded_size = parsed
        decoded = zigzag(encoded)
        tail_offset = marker_offset + 1 + encoded_size
        if not (0 <= decoded < limit and tail_offset < limit):
            continue
        out.append(
            {
                **hit,
                "entry_start": hit["prefix_offset"],
                "marker_offset": marker_offset,
                "encoded": encoded,
                "encoded_size": encoded_size,
                "decoded": decoded,
                "tail_offset": tail_offset,
                "tail": data[tail_offset],
                "entry_end": tail_offset + 1,
            }
        )
    return out


def contiguous_runs(candidates: list[dict]) -> list[list[dict]]:
    ordered = sorted(candidates, key=lambda row: row["entry_start"])
    by_start = {row["entry_start"]: row for row in ordered}
    used: set[int] = set()
    runs: list[list[dict]] = []
    for row in ordered:
        if row["entry_start"] in used:
            continue
        run = [row]
        used.add(row["entry_start"])
        cursor = row["entry_end"]
        while cursor in by_start:
            nxt = by_start[cursor]
            run.append(nxt)
            used.add(cursor)
            cursor = nxt["entry_end"]
        runs.append(run)
    return runs


def solve_payload_base(run: list[dict], hits: list[dict]) -> tuple[int, dict]:
    occurrences: dict[str, list[int]] = defaultdict(list)
    directory_offsets = {row["prefix_offset"] for row in run}
    directory_start = min(row["entry_start"] for row in run)
    for hit in hits:
        if hit["prefix_offset"] not in directory_offsets:
            occurrences[hit["name"]].append(hit["prefix_offset"])

    votes: dict[int, list[tuple[str, int, int]]] = defaultdict(list)
    for entry in run:
        for occurrence in occurrences.get(entry["name"], []):
            if occurrence >= directory_start:
                continue
            for delta in range(1, 9):
                base = occurrence - delta - entry["decoded"]
                if 0 <= base < directory_start:
                    votes[base].append((entry["name"], occurrence, delta))

    if not votes:
        raise RuntimeError("no payload-base candidate has name/offset support")

    ranked = sorted(
        votes.items(),
        key=lambda item: (len({vote[0] for vote in item[1]}), len(item[1])),
        reverse=True,
    )
    base, support = ranked[0]
    detail = {
        "distinct_name_support": len({vote[0] for vote in support}),
        "vote_count": len(support),
        "runner_up_distinct_name_support": (
            len({vote[0] for vote in ranked[1][1]}) if len(ranked) > 1 else 0
        ),
    }
    return base, detail


def hex_at(data: mmap.mmap, start: int, end: int) -> str:
    return bytes(data[max(0, start):min(len(data), end)]).hex(" ").upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--name-prefix", required=True)
    parser.add_argument("--version", default="4.4.54")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    prefix = args.name_prefix.encode("ascii")
    with args.input.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        hits = find_named_strings(data, prefix)
        candidates = directory_candidates(data, hits)
        runs = [run for run in contiguous_runs(candidates) if len(run) >= 2]
        if not runs:
            raise RuntimeError(f"no contiguous directory run for {args.name_prefix!r}")

        solved: list[tuple[int, int, int, list[dict], dict]] = []
        for run in runs:
            try:
                base, support = solve_payload_base(run, hits)
            except RuntimeError:
                continue
            solved.append((support["distinct_name_support"], len(run), base, run, support))
        if not solved:
            raise RuntimeError("directory runs found, but none has a supported payload base")
        solved.sort(key=lambda item: (item[0], item[1]), reverse=True)
        _, _, payload_base, run, support = solved[0]

        run.sort(key=lambda row: row["entry_start"])
        entries = []
        matched = 0
        first_anchor = payload_base + run[0]["decoded"]
        # The directory points at the first object's field bitmap.  The list
        # count is the canonical ULEB ending immediately before that anchor;
        # the root field bitmap ends immediately before the count.
        count_offset = None
        count_size = None
        item_count = None
        for size in range(1, 6):
            candidate = first_anchor - size
            parsed = read_uleb(data, candidate, first_anchor)
            if parsed is None or parsed[1] != size:
                continue
            value, _ = parsed
            if bytes(data[candidate:first_anchor]) != encode_uleb(value):
                continue
            if value >= len(run):
                count_offset, count_size, item_count = candidate, size, value
                break
        if count_offset is None or count_size is None or item_count is None:
            raise RuntimeError("cannot read collection count before first object anchor")
        root_offset = count_offset - 1
        root_read = read_uleb(data, root_offset, count_offset)
        root_bitmap = root_read[0] if root_read and root_read[1] == 1 else None

        for index, entry in enumerate(run):
            anchor = payload_base + entry["decoded"]
            payload_hit = None
            for hit in hits:
                if hit["name"] == entry["name"] and 0 < hit["prefix_offset"] - anchor <= 8:
                    payload_hit = hit
                    break
            if payload_hit is not None:
                matched += 1
            object_bitmap_offset = anchor
            object_bitmap_read = read_uleb(data, object_bitmap_offset, len(data))
            entries.append(
                {
                    "ordinal": index,
                    "name": entry["name"],
                    "directory_entry_offset": f"0x{entry['entry_start']:X}",
                    "encoded_offset": entry["encoded"],
                    "decoded_offset": entry["decoded"],
                    "payload_anchor": f"0x{anchor:X}",
                    "payload_name_prefix_offset": (
                        f"0x{payload_hit['prefix_offset']:X}" if payload_hit else None
                    ),
                    "name_prefix_delta": (
                        payload_hit["prefix_offset"] - anchor if payload_hit else None
                    ),
                    "field_presence_bitmap_offset": f"0x{object_bitmap_offset:X}",
                    "field_presence_bitmap": object_bitmap_read[0] if object_bitmap_read else None,
                    "field_presence_bitmap_size": object_bitmap_read[1] if object_bitmap_read else None,
                    "anchor_preview_hex": hex_at(data, anchor, anchor + 16),
                    "directory_tail": entry["tail"],
                }
            )

        result = {
            "schema": "ability_file_container_recovery/1",
            "game_version": args.version,
            "status": (
                "GENERIC_OUTER_CONTAINER_CONFIRMED"
                if item_count >= len(run) and matched == len(run) and root_bitmap is not None
                else "GENERIC_OUTER_CONTAINER_PARTIAL"
            ),
            "source": {
                "archive": str(args.input.resolve()),
                "archive_size": len(data),
                "archive_sha256": sha256_file(args.input),
            },
            "query": {"name_prefix": args.name_prefix},
            "runtime_type_chain": [
                "RPG.GameCore.TurnBasedAbilityConfigList.AbilityList",
                "RPG.GameCore.TurnBasedAbilityConfig",
                "RPG.GameCore.AbilityConfig.Name",
            ],
            "payload_base": f"0x{payload_base:X}",
            "payload_base_support": support,
            "outer_container": {
                "root_offset": f"0x{root_offset:X}",
                "field_presence_bitmap": root_bitmap,
                "collection_count_offset": f"0x{count_offset:X}",
                "collection_count": item_count,
                "directory_entry_count": len(run),
                "payload_name_match_count": matched,
            },
            "directory": {
                "start": f"0x{run[0]['entry_start']:X}",
                "end": f"0x{run[-1]['entry_end']:X}",
                "entry_count": len(run),
            },
            "entries": entries,
            "claims_not_made": [
                "ability action-node semantics",
                "task-list child boundaries",
                "damage or healing arithmetic",
            ],
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output} status={result['status']} "
        f"entries={len(run)} matches={matched} count={item_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
