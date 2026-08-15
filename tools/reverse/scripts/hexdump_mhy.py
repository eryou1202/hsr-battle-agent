#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small hexdump/region inspector for MHY metadata files."""
import argparse
import os

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--offset", type=lambda x: int(x, 0), default=0)
    ap.add_argument("--length", type=lambda x: int(x, 0), default=0x200)
    ap.add_argument("--columns", type=int, default=16)
    args = ap.parse_args()
    data = np.fromfile(args.input, dtype=np.uint8)
    off = args.offset
    end = min(off + args.length, data.size)
    for base in range(off, end, args.columns):
        chunk = data[base : min(base + args.columns, end)]
        hexs = " ".join(f"{b:02X}" for b in chunk)
        ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"{base:08X}  {hexs:<{args.columns*3}}  {ascii_}")


if __name__ == "__main__":
    main()
