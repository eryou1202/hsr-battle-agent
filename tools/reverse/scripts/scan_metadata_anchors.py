#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static anchor scanner: find MHY metadata loader evidence in PE binaries.

Searches exact byte patterns (MHY magic, metadata file names, standard
IL2CPP magic) in GameAssembly.dll / UnityPlayer.dll and reports file
offset, PE RVA when mappable, and surrounding printable context.

This is evidence collection for the MHY global-metadata.dat format;
it does not decode any protected dispatcher.
"""

from __future__ import annotations

import argparse
import json
import mmap
import os
import re
import struct
import sys

PATTERNS = {
    "mhy_magic_le_bytes": b"MHY\x00",
    "mhy_magic_swapped_le": b"YHM\x00",
    "std_il2cpp_magic_v24_be_file": b"\xAF\x1B\xB1\xFA",
    "std_il2cpp_magic_v24_le_imm": b"\xFA\xB1\x1B\xAF",
    "global-metadata.dat": b"global-metadata.dat",
    "global-metadata": b"global-metadata",
    "startup-metadata.dat": b"startup-metadata.dat",
    "startup-metadata": b"startup-metadata",
    "il2cpp_data": b"il2cpp_data",
    "Metadata/global-metadata.dat": b"Metadata/global-metadata.dat",
}

PRINT_RE = re.compile(rb"[\x20-\x7e]{4,}")


class PE:
    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            self.f = f
            self.m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        dos = self.m[:0x40]
        if dos[:2] != b"MZ":
            raise ValueError("not a PE (MZ)")
        pe_off = struct.unpack_from("<I", dos, 0x3C)[0]
        if self.m[pe_off : pe_off + 4] != b"PE\x00\x00":
            raise ValueError("PE signature not found")
        self.pe_off = pe_off
        opt = pe_off + 24
        magic = struct.unpack_from("<H", self.m, opt)[0]
        self.is64 = magic == 0x20B
        if not self.is64 and magic != 0x10B:
            raise ValueError(f"unexpected PE optional-header magic 0x{magic:X}")
        nsec = struct.unpack_from("<H", self.m, pe_off + 6)[0]
        size_opt = struct.unpack_from("<H", self.m, pe_off + 20)[0]
        self.image_base = struct.unpack_from("<Q" if self.is64 else "<I", self.m,
                                             opt + 24 if self.is64 else opt + 28)[0]
        sec_off = opt + size_opt
        self.sections = []
        for i in range(nsec):
            off = sec_off + i * 40
            name = self.m[off:off + 8].rstrip(b"\x00").decode("ascii", "replace")
            vsize, rva, rawsize, rawptr = struct.unpack_from("<IIII", self.m, off + 8)
            self.sections.append({
                "name": name, "rva": rva, "vsize": vsize,
                "raw_size": rawsize, "raw_ptr": rawptr,
            })
        self.size_of_image = struct.unpack_from("<I", self.m, opt + 56 if self.is64 else opt + 52)[0]

    def rva_for_offset(self, off: int):
        for s in self.sections:
            if s["raw_ptr"] <= off < s["raw_ptr"] + s["raw_size"]:
                return s["rva"] + (off - s["raw_ptr"]), s
        return None, None


def context(m: mmap.mmap, pos: int, radius: int = 96) -> dict:
    a = max(0, pos - radius)
    b = min(len(m), pos + radius)
    raw = m[a:b]
    strings = []
    for sm in PRINT_RE.finditer(raw):
        strings.append({"offset": a + sm.start(), "text": sm.group().decode("ascii", "replace")})
    return {
        "window_offset": a,
        "hex": raw.hex(" ").upper(),
        "printable_strings": strings[:32],
    }


def scan(path: str, max_hits_per_pattern: int = 200) -> dict:
    out = {
        "schema": "mhy_metadata_anchor_scan/1",
        "input": os.path.abspath(path),
        "file_size": os.path.getsize(path),
        "pe": None,
        "patterns": {},
    }
    try:
        pe = PE(path)
        out["pe"] = {
            "is64": pe.is64,
            "image_base": pe.image_base,
            "size_of_image": pe.size_of_image,
            "sections": [
                {k: v for k, v in s.items()} for s in pe.sections
            ],
        }
    except Exception as e:  # noqa: BLE001 - report and continue as raw file
        pe = None
        out["pe_error"] = repr(e)

    with open(path, "rb") as f:
        m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        for name, needle in PATTERNS.items():
            hits = []
            pos = 0
            while True:
                p = m.find(needle, pos)
                if p < 0:
                    break
                hit = {"file_offset": p, "context": context(m, p)}
                if pe is not None:
                    rva, sec = pe.rva_for_offset(p)
                    if rva is not None:
                        hit["rva"] = rva
                        hit["va"] = pe.image_base + rva
                        hit["section"] = sec["name"]
                hits.append(hit)
                pos = p + 1
                if len(hits) >= max_hits_per_pattern:
                    hits.append({"truncated": True})
                    break
            out["patterns"][name] = {
                "count_capped": len(hits),
                "limit": max_hits_per_pattern,
                "hits": hits,
            }
        m.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--max-hits", type=int, default=200)
    args = ap.parse_args()
    results = []
    for path in args.inputs:
        if not os.path.isfile(path):
            print(f"not found: {path}", file=sys.stderr)
            return 2
        print(f"scanning {path} ...", file=sys.stderr)
        results.append(scan(path, max_hits_per_pattern=args.max_hits))
    out = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"wrote {out}")
    for r in results:
        print(f"{r['input']}:")
        for name, p in r["patterns"].items():
            n = p["count_capped"]
            mark = " (capped)" if p["hits"] and p["hits"][-1].get("truncated") else ""
            print(f"  {name}: {n}{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
