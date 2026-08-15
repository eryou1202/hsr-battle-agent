#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static structure profiler for miHoYo custom IL2CPP global-metadata.dat.

The tool deliberately does NOT assume standard IL2CPP metadata layout
(0xAF1BB1FA).  It produces machine-readable structural evidence:
header/footer, entropy by block, zero regions, repeated regions,
ASCII/UTF-8 string islands, alignment statistics and candidate
integer/table regions (offset-like / length-like / RVA-like /
monotonic sequences).

Usage (use the repo Python resolver, never bare `python`):
  & .\scripts\python\resolve_python.ps1 -Resolve   # get $Py
  & $Py tools\reverse\scripts\analyze_mhy_metadata.py <input> -o <out.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter

import numpy as np

PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{4,}")
NONZERO_RE = re.compile(rb"[^\x00]{1,}")


def sha256_hex(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def block_entropy_series(data: np.ndarray, block_size: int) -> list[float]:
    n = data.size
    nb = n // block_size
    out: list[float] = []
    arr = data[: nb * block_size].reshape(nb, block_size)
    # bincount per block is fine for the intended ~100 MB inputs
    for row in arr:
        counts = np.bincount(row, minlength=256).astype(np.float64)
        p = counts / block_size
        ent = -np.sum(p[p > 0] * np.log2(p[p > 0]))
        out.append(round(float(ent), 6))
    if n % block_size:
        tail = data[nb * block_size:]
        counts = np.bincount(tail, minlength=256).astype(np.float64)
        p = counts / tail.size
        ent = -np.sum(p[p > 0] * np.log2(p[p > 0]))
        out.append(round(float(ent), 6))
    return out


def zero_runs(data: np.ndarray, min_len: int = 16) -> list[dict]:
    z = data == 0
    if z.all():
        return [{"start": 0, "length": int(data.size)}]
    edges = np.flatnonzero(np.diff(z.astype(np.int8))) + 1
    bounds = np.concatenate(([0], edges, [data.size]))
    starts = bounds[:-1]
    lengths = np.diff(bounds)
    mask = z[starts.astype(int)] & (lengths >= min_len)
    out = []
    for s, ln in zip(starts[mask], lengths[mask]):
        s = int(s)
        ln = int(ln)
        out.append({"start": s, "length": ln, "end": s + ln})
    return out


def printable_strings(data: np.ndarray, min_len: int = 4, limit: int = 2000) -> dict:
    raw = data.tobytes()
    islands = []
    total_len = 0
    for m in PRINTABLE_RE.finditer(raw):
        s = m.start()
        e = m.end()
        if e - s < min_len:
            continue
        islands.append({"offset": s, "length": e - s, "text": raw[s:e].decode("ascii", "replace")})
        total_len += e - s
        if len(islands) >= limit:
            break
    return {
        "count_capped": len(islands),
        "limit": limit,
        "total_printable_bytes_in_capped_islands": total_len,
        "islands": islands,
    }


def repeated_blocks(data: np.ndarray, block_size: int, min_count: int = 2, top: int = 50) -> list[dict]:
    n = data.size
    nb = n // block_size
    hashes: dict[bytes, list[int]] = {}
    for i in range(nb):
        start = i * block_size
        raw = data[start : start + block_size].tobytes()
        h = hashlib.sha256(raw).digest()
        hashes.setdefault(h, []).append(start)
    out = []
    for h, starts in hashes.items():
        if len(starts) >= min_count:
            out.append({"block_size": block_size, "count": len(starts), "offsets": starts[:100]})
    out.sort(key=lambda x: (-x["count"], x["offsets"][0]))
    return out[:top]


def repeated_integers(data: np.ndarray, width: int, min_count: int, top: int = 30) -> list[dict]:
    n = data.size - (data.size % width)
    if width == 4:
        vals = data[:n].view(np.uint32)
    elif width == 8:
        vals = data[:n].view(np.uint64)
    else:
        raise ValueError("width must be 4 or 8")
    uniq, counts = np.unique(vals, return_counts=True)
    order = np.argsort(-counts)[:top]
    out = []
    for idx in order:
        c = int(counts[idx])
        if c < min_count:
            break
        out.append({"width": width, "value": int(uniq[idx]), "value_hex": f"0x{int(uniq[idx]):X}",
                    "count": c})
    return out


def constant_stride_runs(vals: np.ndarray, min_len: int, max_runs: int = 200) -> list[dict]:
    """Runs where consecutive u32/u64 entries have a constant difference."""
    if vals.size < 2:
        return []
    d = np.diff(vals.astype(np.int64))
    same = np.empty(d.size, dtype=bool)
    same[0] = False
    same[1:] = d[1:] == d[:-1]
    # same[i] True -> stride d[i] equals stride d[i-1]; runs must be >= min_len-1
    out = []
    i = 0
    while i < same.size:
        if not same[i]:
            i += 1
            continue
        j = i
        stride = int(d[i])
        while j + 1 < same.size and same[j + 1] and int(d[j + 1]) == stride:
            j += 1
        # d indices i..j equal -> entries i..j+1 form constant stride
        length = (j + 1) - i + 1
        if length >= min_len:
            out.append({
                "entry_index": i,
                "entry_offset": i * (4 if vals.dtype == np.uint32 else 8),
                "entry_count": length,
                "stride": stride,
                "first_value": int(vals[i]),
                "last_value": int(vals[j + 1]),
            })
        i = j + 1
        if len(out) >= max_runs:
            break
    out.sort(key=lambda x: -x["entry_count"])
    return out


def monotonic_runs(vals: np.ndarray, min_len: int, max_runs: int = 100) -> list[dict]:
    if vals.size < 2:
        return []
    d = np.diff(vals.astype(np.int64))
    nondec = d >= 0
    out = []
    i = 0
    while i < nondec.size:
        if not nondec[i]:
            i += 1
            continue
        j = i
        while j + 1 < nondec.size and nondec[j + 1]:
            j += 1
        length = j - i + 2
        if length >= min_len:
            out.append({
                "entry_index": i,
                "entry_offset": i * (4 if vals.dtype == np.uint32 else 8),
                "entry_count": length,
                "first_value": int(vals[i]),
                "last_value": int(vals[j + 1]),
            })
        i = j + 1
        if len(out) >= max_runs:
            break
    out.sort(key=lambda x: -x["entry_count"])
    return out


def category_density_by_region(data: np.ndarray, vals: np.ndarray, file_size: int,
                               image_sizes: list[tuple[str, int]],
                               region_size: int = 0x1000, top: int = 40) -> dict:
    """Count categorized aligned u32 values per region and report hot regions."""
    width = 4
    masks = {
        "offset_in_file": vals < file_size,
        "zero": vals == 0,
        "small_u32": vals < 0x10000,
        "u32_aligned_value": (vals & 0x3) == 0,
        "u32_16_aligned_value": (vals & 0xF) == 0,
        "u32_256_aligned_value": (vals & 0xFF) == 0,
    }
    for name, img in image_sizes:
        masks[f"rva_in_{name}"] = (vals >= 0x1000) & (vals < img)

    n_regions = (data.size + region_size - 1) // region_size
    # value index -> region index
    region_of = np.arange(vals.size, dtype=np.int64) // (region_size // width)
    reports = {}
    for name, mask in masks.items():
        region_counts = np.bincount(region_of[mask], minlength=n_regions).astype(np.int64)
        order = np.argsort(-region_counts)[:top]
        hot = []
        for r in order:
            c = int(region_counts[r])
            if c == 0:
                break
            hot.append({"region_offset": int(r) * region_size,
                        "region_end": min(int(r + 1) * region_size, int(data.size)),
                        "count": c})
        reports[name] = {"total": int(mask.sum()), "hot_regions": hot}
    return reports


def region_value_stats(vals: np.ndarray, region_start: int, region_size: int, width: int) -> dict:
    a = int(region_start // width)
    b = int(min(region_start + region_size, vals.size * width) // width)
    if b <= a:
        return {}
    v = vals[a:b]
    return {
        "entry_count": int(v.size),
        "min": int(v.min()),
        "max": int(v.max()),
        "unique_count": int(np.unique(v).size),
        "zero_count": int((v == 0).sum()),
        "mean": float(v.mean()),
    }


def tail_plaintext_analysis(data: np.ndarray, tail_window: int = 0x4000) -> dict:
    tail = data[-tail_window:]
    # Longest run of identical u32 values in the tail (aligned).
    vals = tail[: tail.size - (tail.size % 4)].view(np.uint32)
    out: list[dict] = []
    i = 0
    while i < vals.size:
        j = i
        while j + 1 < vals.size and vals[j + 1] == vals[i]:
            j += 1
        ln = j - i + 1
        if ln >= 8:
            out.append({"value": int(vals[i]), "value_hex": f"0x{int(vals[i]):X}",
                        "count": ln, "tail_relative_offset": i * 4,
                        "file_offset": int(data.size) - tail_window + i * 4})
        i = j + 1
    return {
        "tail_window": tail_window,
        "first_non_zero_from_end": _first_nonzero_from_end(data),
        "last_non_zero": _last_nonzero(data),
        "aligned_u32_runs_min8": out,
        "last64_hex": data[-64:].tobytes().hex(" ").upper(),
    }


def _first_nonzero_from_end(data: np.ndarray) -> int:
    nz = np.flatnonzero(data != 0)
    if nz.size == 0:
        return -1
    return int(nz[-1])


def _last_nonzero(data: np.ndarray) -> int:
    return _first_nonzero_from_end(data)


def analyze(path: str, block_size: int, image_sizes: list[tuple[str, int]],
            min_zero: int, min_monotonic: int, min_stride: int,
            string_min: int, string_limit: int) -> dict:
    t0 = time.time()
    size = os.path.getsize(path)
    result: dict = {
        "schema": "mhy_metadata_profile/1",
        "input": os.path.abspath(path),
        "file_size": size,
        "sha256": sha256_hex(path),
        "block_size": block_size,
        "parameters": {
            "min_zero_run": min_zero,
            "min_monotonic_run": min_monotonic,
            "min_stride_run": min_stride,
            "string_min_len": string_min,
            "string_limit": string_limit,
            "image_sizes": [{"name": n, "size": s} for n, s in image_sizes],
        },
    }
    data = np.fromfile(path, dtype=np.uint8)
    if data.size != size:
        raise RuntimeError(f"short read: {data.size} != {size}")
    result["first64_hex"] = data[:64].tobytes().hex(" ").upper()
    result["last64_hex"] = data[-64:].tobytes().hex(" ").upper()
    result["entropy"] = {
        "whole_file_bits_per_byte": round(_entropy(data), 6),
        "blocks": block_entropy_series(data, block_size),
    }
    ents = result["entropy"]["blocks"]
    result["entropy"]["block_entropy_min"] = min(ents)
    result["entropy"]["block_entropy_max"] = max(ents)
    result["entropy"]["block_entropy_mean"] = round(sum(ents) / len(ents), 6)
    low = [(i * block_size, e) for i, e in enumerate(ents) if e < 2.0]
    result["entropy"]["low_entropy_blocks"] = [
        {"offset": o, "end": min(o + block_size, size), "entropy": e} for o, e in low[:200]
    ]

    result["zero_regions"] = zero_runs(data, min_len=min_zero)
    result["repeated_blocks_0x1000"] = repeated_blocks(data, 0x1000, min_count=2, top=20)
    result["repeated_u32_values_top"] = repeated_integers(data, 4, min_count=64, top=30)
    result["repeated_u64_values_top"] = repeated_integers(data, 8, min_count=32, top=30)
    result["printable_ascii_islands"] = printable_strings(data, min_len=string_min, limit=string_limit)

    # Alignment / integer evidence over every 4-byte aligned slot.
    n4 = size - (size % 4)
    vals = data[:n4].view(np.uint32)
    result["u32_aligned"] = {
        "count": int(vals.size),
        "min": int(vals.min()),
        "max": int(vals.max()),
        "unique_count": int(np.unique(vals).size),
        "zero_count": int((vals == 0).sum()),
        "in_file_count": int((vals < size).sum()),
        "equal_to_file_size_count": int((vals == size).sum()),
        "equal_to_size_minus_1_count": int((vals == size - 1).sum()),
    }
    n8 = size - (size % 8)
    vals64 = data[:n8].view(np.uint64)
    result["u64_aligned"] = {
        "count": int(vals64.size),
        "min": int(vals64.min()),
        "max": int(vals64.max()),
        "unique_count": int(np.unique(vals64).size),
        "zero_count": int((vals64 == 0).sum()),
        "in_file_count": int((vals64 < size).sum()),
    }

    result["monotonic_u32_runs"] = monotonic_runs(vals, min_len=min_monotonic, max_runs=100)
    result["constant_stride_u32_runs"] = constant_stride_runs(vals, min_len=min_stride, max_runs=150)
    result["monotonic_u64_runs"] = monotonic_runs(vals64, min_len=min_monotonic // 2, max_runs=50)
    result["constant_stride_u64_runs"] = constant_stride_runs(vals64, min_len=min_stride // 2, max_runs=50)
    result["category_density"] = category_density_by_region(data, vals, size, image_sizes, top=40)
    result["tail_plaintext"] = tail_plaintext_analysis(data)
    result["elapsed_seconds"] = round(time.time() - t0, 3)
    return result


def _entropy(data: np.ndarray) -> float:
    counts = np.bincount(data, minlength=256).astype(np.float64)
    p = counts / data.size
    return float(-np.sum(p[p > 0] * np.log2(p[p > 0])))


def _strip_footer_keys(d: dict) -> dict:
    # Keep the JSON human-manageable: drop per-block entropy from the text
    # summary only; JSON keeps everything.
    return d


def render_summary(r: dict) -> str:
    lines = [
        f"input           = {r['input']}",
        f"size            = {r['file_size']}",
        f"sha256          = {r['sha256']}",
        f"first64         = {r['first64_hex']}",
        f"last64          = {r['last64_hex']}",
        f"whole entropy   = {r['entropy']['whole_file_bits_per_byte']} bits/byte",
        f"block entropy   = min {r['entropy']['block_entropy_min']} / mean {r['entropy']['block_entropy_mean']} / max {r['entropy']['block_entropy_max']}",
        f"zero regions    = {len(r['zero_regions'])} (>= {r['parameters']['min_zero_run']} B)",
        f"ascii islands   = {r['printable_ascii_islands']['count_capped']} (capped at {r['printable_ascii_islands']['limit']})",
    ]
    u32 = r["u32_aligned"]
    lines.append(f"aligned u32     = {u32['count']} slots, {u32['unique_count']} unique, {u32['in_file_count']} < file_size")
    lines.append("top repeated u32:")
    for x in r["repeated_u32_values_top"][:12]:
        lines.append(f"  {x['value_hex']:>12} x {x['count']}")
    lines.append("tail u32 runs:")
    for x in r["tail_plaintext"]["aligned_u32_runs_min8"][:12]:
        lines.append(f"  {x['value_hex']:>12} x {x['count']} @ file+0x{x['file_offset']:X}")
    lines.append("top monotonic u32 runs:")
    for x in r["monotonic_u32_runs"][:10]:
        lines.append(f"  entry_offset=0x{x['entry_offset']:X} count={x['entry_count']} first=0x{x['first_value']:X} last=0x{x['last_value']:X}")
    lines.append("top constant-stride u32 runs:")
    for x in r["constant_stride_u32_runs"][:10]:
        lines.append(f"  entry_offset=0x{x['entry_offset']:X} count={x['entry_count']} stride=0x{x['stride']:X} first=0x{x['first_value']:X} last=0x{x['last_value']:X}")
    for name, rep in sorted(r["category_density"].items()):
        lines.append(f"category {name}: total={rep['total']}")
        for h in rep["hot_regions"][:5]:
            lines.append(f"  @0x{h['region_offset']:X} count={h['count']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="global-metadata.dat path")
    ap.add_argument("-o", "--output", help="output JSON path (required)", required=True)
    ap.add_argument("--summary", action="store_true", help="print text summary to stdout")
    ap.add_argument("--block-size", type=lambda x: int(x, 0), default=0x1000)
    ap.add_argument("--image-size", action="append", default=[],
                    help="name=size RVA window, e.g. GameAssembly=0x2080C000; repeatable")
    ap.add_argument("--min-zero", type=lambda x: int(x, 0), default=16)
    ap.add_argument("--min-monotonic", type=int, default=8)
    ap.add_argument("--min-stride", type=int, default=6)
    ap.add_argument("--string-min", type=int, default=4)
    ap.add_argument("--string-limit", type=int, default=2000)
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"input not found: {args.input}", file=sys.stderr)
        return 2

    image_sizes: list[tuple[str, int]] = []
    for spec in args.image_size:
        if "=" not in spec:
            ap.error("--image-size expects name=size")
        name, val = spec.split("=", 1)
        image_sizes.append((name, int(val, 0)))

    result = analyze(
        args.input,
        block_size=args.block_size,
        image_sizes=image_sizes,
        min_zero=args.min_zero,
        min_monotonic=args.min_monotonic,
        min_stride=args.min_stride,
        string_min=args.string_min,
        string_limit=args.string_limit,
    )
    out = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out}")
    if args.summary:
        print(render_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
