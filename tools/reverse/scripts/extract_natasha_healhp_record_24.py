#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract a bounded Natasha HealHP-bearing ability record window.

This is a targeted binary-format probe, not a full DesignData parser.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UNPACK = HERE.parents[1] / "unpack"
if UNPACK.exists():
    sys.path.insert(0, str(UNPACK))

from inspect_ability_headers import read_string, read_uleb128  # noqa: E402


def find_candidate_records(data: bytes, name_prefix: str) -> list[dict]:
    out = []
    pattern = name_prefix.encode("ascii")
    for m in re.finditer(re.escape(pattern), data):
        name_start = m.start()
        for cand in range(max(0, name_start - 16), name_start):
            try:
                wrapper, s1 = read_uleb128(data, cand)
                bit, s2 = read_uleb128(data, cand + s1)
            except Exception:
                continue
            if cand + s1 + s2 > name_start:
                continue
            if not (bit & 1):
                continue
            try:
                name, end, _ = read_string(data, cand + s1 + s2)
            except Exception:
                continue
            if end == name_start + len(name) and name.startswith(name_prefix):
                out.append({
                    "start": cand,
                    "name_offset": name_start,
                    "wrapper": wrapper,
                    "bitfield": bit,
                    "name": name,
                    "header_size": name_start - cand,
                })
                break
    return out


def record_end(data: bytes, records: list[dict], index: int, fallback: int) -> int:
    if index + 1 < len(records):
        return records[index + 1]["start"]
    return min(len(data), records[index]["start"] + fallback)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True, type=Path)
    ap.add_argument("--name-prefix", default="Avatar_Natasha_00_")
    ap.add_argument("--record-name", default="Avatar_Natasha_00_Skill02_Phase02")
    ap.add_argument("--fallback-length", type=lambda x: int(x, 0), default=0x1000)
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()

    data = args.archive.read_bytes()
    records = find_candidate_records(data, args.name_prefix)
    matches = [r for r in records if r["name"] == args.record_name]
    if not matches:
        raise SystemExit(f"record not found: {args.record_name}")
    rec = matches[0]
    idx = records.index(rec)
    end = record_end(data, records, idx, args.fallback_length)
    body = data[rec["start"]:end]

    tokens = []
    for token in [b"HealHP", b"Heal", b"AllTeammate", b"AllTeamMember",
                  b"SkillTargetEntityList", b"TargetEntity", b"HPByMaxHP",
                  b"MaxHP", b"AbilityTargetEntity"]:
        for mm in re.finditer(re.escape(token), body):
            tokens.append({
                "token": token.decode(),
                "offset": rec["start"] + mm.start(),
                "offset_hex": f"0x{rec['start'] + mm.start():X}",
            })

    result = {
        "schema": "natasha_healhp_record_window/1",
        "archive": str(args.archive.resolve()),
        "record_name": rec["name"],
        "record_start": f"0x{rec['start']:X}",
        "record_end": f"0x{end:X}",
        "record_length": end - rec["start"],
        "wrapper_type": rec["wrapper"],
        "bitfield": rec["bitfield"],
        "header_size": rec["header_size"],
        "tokens": tokens,
        "note": "Bounded record window only. Exact HealHP polymorphic config tag is not decoded by this probe.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
