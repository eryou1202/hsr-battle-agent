#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-version structure comparison for MHY global-metadata.dat.

Only real files on disk are compared.  Outputs stable-prefix evidence,
4 KiB block equality runs, low-entropy region boundaries and plaintext
tail structure for two versions.

Usage:
  analyze/compare current metadata vs reference metadata:
    python compare_mhy_metadata.py <current> <reference> -o out.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np


def hash_block(data: np.ndarray, start: int, size: int) -> str:
    return hashlib.sha256(data[start : start + size].tobytes()).hexdigest()


def entropy(data: np.ndarray) -> float:
    counts = np.bincount(data, minlength=256).astype(np.float64)
    p = counts / data.size
    return float(-np.sum(p[p > 0] * np.log2(p[p > 0])))


def longest_common_prefix(a: np.ndarray, b: np.ndarray, max_check: int | None = None) -> int:
    n = min(a.size, b.size)
    if max_check is not None:
        n = min(n, max_check)
    # Vectorized chunk search to avoid a Python loop over every byte.
    step = 1 << 20
    common = 0
    while common < n:
        take = min(step, n - common)
        x = a[common : common + take]
        y = b[common : common + take]
        ne = np.flatnonzero(x != y)
        if ne.size == 0:
            common += take
        else:
            common += int(ne[0])
            break
    return common


def block_equality_runs(a: np.ndarray, b: np.ndarray, block: int = 0x1000,
                        max_runs: int = 500) -> list[dict]:
    n = min(a.size, b.size) // block
    runs: list[dict] = []
    i = 0
    while i < n:
        eq = bool(np.array_equal(a[i * block : (i + 1) * block],
                                 b[i * block : (i + 1) * block]))
        j = i
        while j + 1 < n:
            eq_next = bool(np.array_equal(a[(j + 1) * block : (j + 2) * block],
                                          b[(j + 1) * block : (j + 2) * block]))
            if eq_next != eq:
                break
            j += 1
        runs.append({"kind": "equal" if eq else "different",
                     "start_offset": i * block,
                     "end_offset": (j + 1) * block,
                     "block_count": j - i + 1})
        i = j + 1
        if len(runs) >= max_runs:
            break
    return runs


def low_entropy_regions(data: np.ndarray, block: int = 0x1000,
                        threshold: float = 4.0, max_runs: int = 200) -> list[dict]:
    n = data.size // block
    out = []
    i = 0
    while i < n:
        ent = entropy(data[i * block : (i + 1) * block])
        if ent >= threshold:
            i += 1
            continue
        j = i
        while j + 1 < n and entropy(data[(j + 1) * block : (j + 2) * block]) < threshold:
            j += 1
        out.append({"start_offset": i * block,
                    "end_offset": min((j + 1) * block, int(data.size)),
                    "block_count": j - i + 1,
                    "entropy_first": round(ent, 4),
                    "entropy_last": round(entropy(data[j * block : (j + 1) * block]), 4)})
        i = j + 1
        if len(out) >= max_runs:
            break
    out.sort(key=lambda x: -x["block_count"])
    return out


def tail_u32_run_profile(data: np.ndarray, window: int = 0x8000) -> dict:
    tail = data[-window:]
    vals = tail[: tail.size - (tail.size % 4)].view(np.uint32)
    runs = []
    i = 0
    while i < vals.size:
        j = i
        while j + 1 < vals.size and vals[j + 1] == vals[i]:
            j += 1
        ln = j - i + 1
        if ln >= 2:
            runs.append({"value": int(vals[i]), "count": ln,
                         "start_relative": i * 4})
        i = j + 1
    return {
        "window": window,
        "run_count": len(runs),
        "total_run_entries": sum(r["count"] for r in runs),
        "runs": runs[:300],
        "first_u32": int(vals[0]),
        "last_u32": int(vals[-1]),
    }


def tail_low_entropy_boundary(data: np.ndarray, block: int = 0x1000,
                              threshold: float = 3.5) -> dict:
    """Walk backwards from EOF to find the contiguous low-entropy tail."""
    n_blocks = data.size // block
    last = n_blocks - 1
    while last >= 0 and entropy(data[last * block : min((last + 1) * block, data.size)]) < threshold:
        last -= 1
    return {
        "contiguous_low_entropy_tail_start": (last + 1) * block,
        "tail_length": int(data.size) - (last + 1) * block,
        "last_high_entropy_block_offset": last * block,
    }


def compare(current: str, reference: str, block: int = 0x1000,
            entropy_threshold: float = 4.0) -> dict:
    t0 = time.time()
    a = np.fromfile(current, dtype=np.uint8)
    b = np.fromfile(reference, dtype=np.uint8)
    prefix = longest_common_prefix(a, b)
    out = {
        "schema": "mhy_metadata_compare/1",
        "current": {"path": os.path.abspath(current), "size": int(a.size),
                    "sha256": hashlib.sha256(a.tobytes()).hexdigest()},
        "reference": {"path": os.path.abspath(reference), "size": int(b.size),
                      "sha256": hashlib.sha256(b.tobytes()).hexdigest()},
        "parameters": {"block_size": block, "low_entropy_threshold": entropy_threshold},
        "longest_common_prefix": prefix,
        "common_prefix_hex": a[: min(prefix, 128)].tobytes().hex(" ").upper(),
        "first_differing_offset": prefix if prefix < min(a.size, b.size) else None,
        "size_delta": int(a.size) - int(b.size),
        "block_equality_runs": block_equality_runs(a, b, block=block, max_runs=400),
        "low_entropy_regions_current": low_entropy_regions(a, block=block,
                                                            threshold=entropy_threshold,
                                                            max_runs=120),
        "low_entropy_regions_reference": low_entropy_regions(b, block=block,
                                                              threshold=entropy_threshold,
                                                              max_runs=120),
        "tail_boundary_current": tail_low_entropy_boundary(a, block=block),
        "tail_boundary_reference": tail_low_entropy_boundary(b, block=block),
        "tail_u32_profile_current": tail_u32_run_profile(a),
        "tail_u32_profile_reference": tail_u32_run_profile(b),
        "elapsed_seconds": round(time.time() - t0, 3),
    }
    return out


def render_summary(r: dict) -> str:
    lines = [
        f"current   = {r['current']['path']} ({r['current']['size']})",
        f"reference = {r['reference']['path']} ({r['reference']['size']})",
        f"common prefix = {r['longest_common_prefix']} (0x{r['longest_common_prefix']:X})",
        f"first differ  = {r['first_differing_offset']} (0x{r['first_differing_offset']:X})" if r["first_differing_offset"] is not None else "first differ = none",
        f"size delta    = {r['size_delta']}",
        "block equality runs (offset:kind x blocks):",
    ]
    for run in r["block_equality_runs"][:40]:
        lines.append(f"  0x{run['start_offset']:08X}-0x{run['end_offset']:08X} {run['kind']} x{run['block_count']}")
    for tag in ("current", "reference"):
        lines.append(f"low entropy regions ({tag}):")
        for x in r[f"low_entropy_regions_{tag}"][:12]:
            lines.append(f"  0x{x['start_offset']:08X}-0x{x['end_offset']:08X} blocks={x['block_count']}")
        tb = r[f"tail_boundary_{tag}"]
        lines.append(f"  tail low-entropy start = 0x{tb['contiguous_low_entropy_tail_start']:X}, len = {tb['tail_length']} (0x{tb['tail_length']:X})")
    for tag in ("current", "reference"):
        prof = r[f"tail_u32_profile_{tag}"]
        lines.append(f"tail u32 profile ({tag}): {prof['run_count']} runs; first 20:")
        for x in prof["runs"][:20]:
            lines.append(f"  +0x{x['start_relative']:X}: 0x{x['value']:X} x {x['count']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("current")
    ap.add_argument("reference")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--block-size", type=lambda x: int(x, 0), default=0x1000)
    ap.add_argument("--entropy-threshold", type=float, default=4.0)
    args = ap.parse_args()
    for p in (args.current, args.reference):
        if not os.path.isfile(p):
            print(f"not found: {p}", file=sys.stderr)
            return 2
    result = compare(args.current, args.reference, block=args.block_size,
                     entropy_threshold=args.entropy_threshold)
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
