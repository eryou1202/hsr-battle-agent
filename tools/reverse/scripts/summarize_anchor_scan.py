#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print compact hit summary from scan_metadata_anchors.py JSON output."""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--min-hit", action="store_true", dest="min_hit",
                    help="show patterns with zero hits too")
    args = ap.parse_args()
    with open(args.input, encoding="utf-8") as f:
        results = json.load(f)
    for r in results:
        print(f"== {r['input']}")
        pe = r.get("pe")
        if pe:
            print(f"   image_base=0x{pe['image_base']:X} size_of_image=0x{pe['size_of_image']:X}")
        else:
            print(f"   pe_error={r.get('pe_error')}")
        for name, p in r["patterns"].items():
            hits = [h for h in p["hits"] if not h.get("truncated")]
            if not hits and not args.min_hit:
                continue
            print(f"   {name}: {p['count_capped']}")
            for h in hits[:20]:
                rva = h.get("rva")
                sec = h.get("section")
                s = f"      file+0x{h['file_offset']:X}"
                if rva is not None:
                    s += f" rva=0x{rva:X}"
                if sec:
                    s += f" sec={sec}"
                print(s)
                for ps in h["context"]["printable_strings"][:8]:
                    print(f"        +0x{ps['offset']:X} {ps['text']!r}")


if __name__ == "__main__":
    main()
