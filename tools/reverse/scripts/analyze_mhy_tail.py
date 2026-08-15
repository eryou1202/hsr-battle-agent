#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tail/plaintext-table inspector for MHY global-metadata.dat.

Finds the contiguous low-entropy tail, profiles its aligned u32/u16/u8
interpretations, and tests candidate structural interpretations
(offset bases, sortedness, pair grouping, RLE).  Machine-readable JSON.
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np


def ent(data: np.ndarray) -> float:
    c = np.bincount(data, minlength=256).astype(np.float64)
    p = c / data.size
    return float(-np.sum(p[p > 0] * np.log2(p[p > 0])))


def find_tail(data: np.ndarray, block: int = 0x1000, threshold: float = 4.0) -> int:
    n = data.size // block
    i = n - 1
    while i >= 0 and ent(data[i * block : (i + 1) * block]) < threshold:
        i -= 1
    return (i + 1) * block


def profile_u32(vals: np.ndarray, file_size: int) -> dict:
    uniq, counts = np.unique(vals, return_counts=True)
    order = np.argsort(-counts)
    top = [{"value": int(uniq[i]), "value_hex": f"0x{int(uniq[i]):X}", "count": int(counts[i])}
           for i in order[:40]]
    hist = {}
    edges = [0, 0x100, 0x1000, 0x10000, 0x100000, 0x1000000, 0x10000000, 0xFFFFFFFF]
    for a, b in zip(edges[:-1], edges[1:]):
        hist[f"0x{a:X}-0x{b:X}"] = int(((vals >= a) & (vals < b)).sum())
    return {
        "count": int(vals.size),
        "unique": int(uniq.size),
        "min": int(vals.min()),
        "max": int(vals.max()),
        "top_values": top,
        "histogram": hist,
        "sorted_nondec_ratio": float(np.mean(np.diff(vals.astype(np.int64)) >= 0)),
        "mean_step": float(np.mean(np.diff(vals.astype(np.int64)))),
        "median_step": float(np.median(np.diff(vals.astype(np.int64)))),
    }


def test_offset_bases(vals: np.ndarray, file_size: int, tail_start: int) -> list[dict]:
    bases = {
        "0": 0,
        "0x1000": 0x1000,
        "tail_start": tail_start,
        "file_size_minus_max": file_size - int(vals.max()),
        "file_end_minus_value": None,
    }
    out = []
    for name, base in bases.items():
        if base is None:
            t = file_size - vals.astype(np.int64)
            in_file = (t >= 0) & (t < file_size)
            out.append({"interpretation": "file_end_minus_value",
                        "in_file_ratio": float(in_file.mean()),
                        "sample": [int(x) for x in t[:5]]})
        else:
            t = base + vals.astype(np.int64)
            in_file = (t >= 0) & (t < file_size)
            out.append({"interpretation": f"base_{name}",
                        "in_file_ratio": float(in_file.mean()),
                        "sample": [int(x) for x in t[:5]]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--block-size", type=lambda x: int(x, 0), default=0x1000)
    ap.add_argument("--threshold", type=float, default=4.0)
    args = ap.parse_args()
    data = np.fromfile(args.input, dtype=np.uint8)
    tail_start = find_tail(data, block=args.block_size, threshold=args.threshold)
    tail = data[tail_start:]
    n4 = tail.size - (tail.size % 4)
    vals = tail[:n4].view(np.uint32)
    n2 = tail.size - (tail.size % 2)
    vals16 = tail[:n2].view(np.uint16)
    result = {
        "schema": "mhy_metadata_tail_profile/1",
        "input": os.path.abspath(args.input),
        "file_size": int(data.size),
        "tail_start": tail_start,
        "tail_length": int(tail.size),
        "tail_entropy": round(ent(tail), 6),
        "first_tail_bytes_hex": tail[:64].tobytes().hex(" ").upper(),
        "last_tail_bytes_hex": tail[-64:].tobytes().hex(" ").upper(),
        "u32": profile_u32(vals, int(data.size)),
        "u16": {"count": int(vals16.size), "unique": int(np.unique(vals16).size),
                "min": int(vals16.min()), "max": int(vals16.max())},
        "offset_base_tests": test_offset_bases(vals, int(data.size), tail_start),
        "u32_runs_min2": _runs(vals, min_len=2, limit=200),
    }
    out = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out}")
    print(f"tail_start=0x{tail_start:X} len=0x{tail.size:X} ent={result['tail_entropy']}")
    p = result["u32"]
    print(f"u32: count={p['count']} unique={p['unique']} min=0x{p['min']:X} max=0x{p['max']:X}")
    print(f"sorted_nondec_ratio={p['sorted_nondec_ratio']:.6f} mean_step={p['mean_step']:.1f} median_step={p['median_step']:.1f}")
    for t in result["offset_base_tests"]:
        print(f"offset test {t['interpretation']}: in_file={t['in_file_ratio']:.6f}")
    print("top values:")
    for x in p["top_values"][:20]:
        print(f"  0x{x['value']:X} x {x['count']}")
    return 0


def _runs(vals: np.ndarray, min_len: int, limit: int) -> list[dict]:
    out = []
    i = 0
    while i < vals.size and len(out) < limit:
        j = i
        while j + 1 < vals.size and vals[j + 1] == vals[i]:
            j += 1
        if j - i + 1 >= min_len:
            out.append({"start": int(i), "value": int(vals[i]),
                        "value_hex": f"0x{int(vals[i]):X}", "count": int(j - i + 1)})
        i = j + 1
    return out


if __name__ == "__main__":
    raise SystemExit(main())
