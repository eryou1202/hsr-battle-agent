#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detect plaintext structured u32-triple regions in MHY metadata files.

The observed schema-stable pattern is 12-byte records:
  a += 4, b += 1, c == constant (0x47 in both 4.4.0 and 4.4.54).
This tool finds maximal such runs and outputs their boundaries, record
counts, first/last values and value ranges as JSON evidence.
"""
import argparse
import json
import os
import numpy as np


def find_runs(vals: np.ndarray, base_offset: int, min_len: int = 16):
    out = []
    n = vals.size // 3
    a = vals[0::3]
    b = vals[1::3]
    c = vals[2::3]
    da = np.diff(a.astype(np.int64))
    db = np.diff(b.astype(np.int64))
    same_c = c[1:] == c[:-1]
    i = 0
    while i < n - 1:
        # start a run when next record continues with strides (+4,+1) and same c
        if da[i] != 4 or db[i] != 1 or not same_c[i]:
            i += 1
            continue
        j = i
        const = int(c[i])
        while j + 1 < n - 1 and da[j + 1] == 4 and db[j + 1] == 1 and int(c[j + 1]) == const:
            j += 1
        length = j - i + 2  # records
        if length >= min_len:
            out.append({
                "start_offset": base_offset + i * 12,
                "end_offset": base_offset + (j + 2) * 12,
                "record_count": length,
                "byte_length": length * 12,
                "a_first": int(a[i]),
                "a_last": int(a[j + 1]),
                "b_first": int(b[i]),
                "b_last": int(b[j + 1]),
                "c_constant": const,
                "c_constant_hex": f"0x{const:X}",
            })
        i = j + 1
    out.sort(key=lambda x: -x["record_count"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--min-run", type=int, default=16)
    args = ap.parse_args()
    data = np.fromfile(args.input, dtype=np.uint8)
    result = {
        "schema": "mhy_metadata_structured_tables/1",
        "input": os.path.abspath(args.input),
        "file_size": int(data.size),
        "u32_triple_runs": {},
    }
    n4 = data.size - (data.size % 4)
    vals = data[:n4].view(np.uint32)
    for phase in range(12):
        # record starts at every byte phase; require 12-byte alignment from there
        avail = vals[phase // 4 :].size if phase % 4 == 0 else vals.size
        _ = avail
        # easiest: shift byte stream by phase and reinterpret u32s
        if phase % 4 != 0:
            continue
        base = phase
        shift = vals[phase // 4 :]
        runs = find_runs(shift, base, min_len=args.min_run)
        result["u32_triple_runs"][f"phase_{phase}"] = runs[:50]
    total_top = []
    for phase, runs in result["u32_triple_runs"].items():
        for r in runs:
            r["phase"] = int(phase.split("_")[1])
            total_top.append(r)
    total_top.sort(key=lambda x: -x["record_count"])
    result["top_runs"] = total_top[:60]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {args.output}")
    for r in total_top[:20]:
        print(f"phase={r['phase']:2d} off=0x{r['start_offset']:X}-0x{r['end_offset']:X} "
              f"count={r['record_count']} a=0x{r['a_first']:X}->0x{r['a_last']:X} "
              f"b=0x{r['b_first']:X}->0x{r['b_last']:X} c={r['c_constant_hex']}")


if __name__ == "__main__":
    main()
