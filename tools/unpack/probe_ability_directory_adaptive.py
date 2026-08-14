from __future__ import annotations

# probe_ability_directory_adaptive.py
#
# 自适应能力目录探测：不依赖 4.4.53 的已知偏移，从目标归档中反解
# payload_base 与目录表。
#
# 原理（基于 4.4.53 确认的结构 F2/F3/F4，见 docs/reverse/ability_type_registry.md）：
#   - 目录条目布局: [uleb name_len][name][0x01 marker][uleb zigzag offset][tail byte]
#   - 记录起点 = payload_base + decoded(offset)
#   - 记录内 name 位于 record_start + delta（delta ∈ 2..4，见旧数据）
# 因此对每个 name 出现点 o：
#   base = o - delta - decoded
# 对全部 name 聚类 base，取支持最多的候选；随后回代验证每个条目。
#
# 用法:
#   python tools/unpack/probe_ability_directory_adaptive.py \
#       --input <archive.bytes> --output <dir.csv> [--names ...]
#
# 产出列（与旧 black_swan_ability_directory.csv 对齐的子集）:
#   entry_offset_hex, name, name_len, marker, encoded, encoded_hex,
#   encoded_size, tail, decoded, record_start_hex, base_solved, delta,
#   context_hex, context_ascii

import argparse
import csv
from pathlib import Path

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


def decode_zigzag(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def read_uleb128(data: bytes, offset: int, limit: int, max_bytes: int = 10) -> tuple[int, int] | None:
    value = 0
    shift = 0
    for index in range(max_bytes):
        position = offset + index
        if position >= limit:
            return None
        byte = data[position]
        value |= (byte & 0x7F) << shift
        if byte & 0x80 == 0:
            return value, index + 1
        shift += 7
    return None


def find_all(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    position = 0
    while True:
        position = data.find(needle, position)
        if position < 0:
            return offsets
        offsets.append(position)
        position += 1


def ascii_context(data: bytes, offset: int, before: int = 24, after: int = 64) -> str:
    start = max(0, offset - before)
    end = min(len(data), offset + after)
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data[start:end])


def hex_context(data: bytes, offset: int, before: int = 24, after: int = 64) -> str:
    start = max(0, offset - before)
    end = min(len(data), offset + after)
    return " ".join(f"{b:02X}" for b in data[start:end])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--names", nargs="*", default=DEFAULT_NAMES)
    parser.add_argument("--marker", type=lambda v: int(v, 0), default=0x01)
    parser.add_argument("--max-decoded", type=int, default=0x40000)
    args = parser.parse_args()

    data = args.input.read_bytes()
    print(f"file: {args.input}  size: {len(data)} ({len(data)/1024/1024:.1f} MiB)")

    # step 1: collect candidate directory entries + record occurrences
    entries: list[dict] = []          # directory-entry candidates
    record_hits: list[dict] = []      # name occurrences (any)
    name_patterns = [(n, n.encode("ascii")) for n in args.names]

    for name, raw in name_patterns:
        pattern = bytes([len(raw)]) + raw
        for occ in find_all(data, pattern):
            rec = {"name": name, "occ": occ, "occ_hex": f"0x{occ:X}"}
            # look for marker + uleb after the name
            marker_pos = occ + len(pattern)
            if data[marker_pos:marker_pos + 1] == bytes([args.marker]):
                parsed = read_uleb128(data, marker_pos + 1, len(data))
                if parsed is not None:
                    enc, enc_size = parsed
                    dec = decode_zigzag(enc)
                    tail_pos = marker_pos + 1 + enc_size
                    if tail_pos < len(data) and 0 <= dec <= args.max_decoded:
                        rec["is_entry"] = True
                        rec["enc"] = enc
                        rec["enc_size"] = enc_size
                        rec["dec"] = dec
                        rec["tail"] = data[tail_pos]
                        rec["tail_pos"] = tail_pos
                        entries.append(rec)
                    else:
                        rec["is_entry"] = False
                else:
                    rec["is_entry"] = False
            else:
                rec["is_entry"] = False
            record_hits.append(rec)

    n_entry = sum(1 for e in entries if e.get("is_entry"))
    print(f"name occurrences: {len(record_hits)}  directory-entry candidates: {n_entry}")

    # step 2: solve payload base per (entry, occurrence) pair with delta 2..4
    base_votes: dict[int, list[tuple]] = {}
    for e in entries:
        for rec in record_hits:
            if rec["name"] != e["name"]:
                continue
            for delta in (2, 3, 4):
                base = rec["occ"] - delta - e["dec"]
                if 0 <= base < len(data):
                    base_votes.setdefault(base, []).append(
                        (e["name"], e["occ"], rec["occ"], delta, e["dec"])
                    )

    ranked = sorted(base_votes.items(), key=lambda kv: -len(kv[1]))
    print("top base candidates:")
    for base, votes in ranked[:8]:
        names = sorted({v[0] for v in votes})
        print(f"  base=0x{base:X}  votes={len(votes)}  names({len(names)}): {', '.join(names[:6])}")

    if not ranked:
        print("ERROR: no base candidate found")
        return

    best_base, best_votes = ranked[0]
    if len(best_votes) < max(3, len(args.names) // 3):
        print(f"WARNING: weak base support ({len(best_votes)} votes)")
        best_base = None

    # step 3: emit rows (use best base if found; else per-entry solved base)
    rows: list[dict[str, object]] = []
    # 仅保留目录块：找出条目偏移中构成最长连续块的子集
    # （记录体内的伪条目 decoded 很小且不构成连续块）
    entry_offs = sorted(e["occ"] for e in entries if e.get("is_entry"))
    best_block: list[int] = []
    current: list[int] = []
    for off in entry_offs:
        if current and off - current[-1] > 64:  # 目录条目间距通常 ~0x27
            if len(current) > len(best_block):
                best_block = current
            current = []
        current.append(off)
    if len(current) > len(best_block):
        best_block = current
    block_set = set(best_block)
    print(f"directory block: {len(best_block)} entries "
          f"0x{best_block[0]:X}..0x{best_block[-1]:X} (contiguous)")

    for e in entries:
        if not e.get("is_entry"):
            continue
        if e["occ"] not in block_set:
            continue
        base = best_base
        delta = None
        record_start = None
        if base is None:
            # fallback: solve from same-name nearest occurrence
            for rec in record_hits:
                if rec["name"] != e["name"]:
                    continue
                for d in (2, 3, 4):
                    b = rec["occ"] - d - e["dec"]
                    if 0 <= b < len(data):
                        base, delta = b, d
                        record_start = base + e["dec"]
                        break
                if base is not None:
                    break
        else:
            record_start = base + e["dec"]
            # nearest same-name occurrence to validate
            best_delta = None
            for rec in record_hits:
                if rec["name"] != e["name"]:
                    continue
                d = rec["occ"] - record_start
                if 2 <= d <= 4:
                    best_delta = d
                    break
            delta = best_delta if best_delta is not None else 0

        rows.append({
            "game_version": "4.4.54",
            "name": e["name"],
            "name_len": len(e["name"]),
            "entry_offset_hex": f"0x{e['occ']:X}",
            "marker": f"0x{e['enc']:02X}" if False else "0x01",
            "encoded": e["enc"],
            "encoded_hex": f"0x{e['enc']:X}",
            "encoded_size": e["enc_size"],
            "tail_hex": f"0x{e['tail']:02X}",
            "decoded": e["dec"],
            "decoded_hex": f"0x{e['dec']:X}",
            "base_solved_hex": f"0x{base:X}" if base is not None else "",
            "record_start_hex": f"0x{record_start:X}" if record_start is not None else "",
            "name_delta": delta if delta else "",
            "record_context_hex": hex_context(data, record_start) if record_start is not None else "",
            "record_context_ascii": ascii_context(data, record_start) if record_start is not None else "",
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"rows: {len(rows)} -> {args.output}")


if __name__ == "__main__":
    main()
