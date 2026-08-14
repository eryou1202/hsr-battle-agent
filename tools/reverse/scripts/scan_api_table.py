# scan_api_table.py
#
# 指纹扫描定位 IL2CPP api table（4.4.54 的 getter 已被混淆，无法直接反汇编）。
#
# 指纹：api table 是函数指针数组，其中大量已知索引（来自 honkai-dumper
# functions.rs 的 il2cpp api 顺序）指向 GameAssembly.dll 的 il2cpp 段
# （RVA 0xB0E3000, 0x13E9DCA0, image base 0x180000000）。
# 在 UnityPlayer.dll / GameAssembly.dll 全文件扫描 8 字节对齐位置，
# 命中"索引 0,37,63 与全部 27 个已知索引都指向 il2cpp 段"的数组起点。

import argparse
from pathlib import Path

import numpy as np

# GameAssembly il2cpp 段（4.4.54 实测）
IL2CPP_RVA = 0xB0E3000
IL2CPP_SIZE = 0x13E9DCA0
IMAGE_BASE = 0x180000000
LO = IMAGE_BASE + IL2CPP_RVA
HI = LO + IL2CPP_SIZE

KNOWN = [22, 31, 33, 35, 37, 39, 40, 43, 45, 49, 53, 63, 65, 72, 73, 75, 76,
         116, 117, 123, 124, 161, 162, 163, 168, 169, 170]
MAXIDX = 171


def scan(path: Path, label: str, verbose: bool) -> list[int]:
    data = path.read_bytes()
    arr = np.frombuffer(data, dtype="<u8")
    n = len(arr)
    if n <= MAXIDX:
        print(f"{label}: file too small")
        return []
    mask = (arr >= LO) & (arr < HI)
    cand = np.flatnonzero(mask[: n - MAXIDX])
    if len(cand) == 0:
        print(f"{label}: no pointers into il2cpp section")
        return []
    # 预过滤：索引 37 (class_get_name) 与 63 (domain_get) 也必须在段内
    cand = cand[mask[cand + 37] & mask[cand + 63]]
    print(f"{label}: prefiltered candidates = {len(cand)}")
    hits = []
    for c in cand[:200]:
        ok = all(bool(mask[c + k]) for k in KNOWN)
        if verbose:
            print(f"  file_off=0x{c*8:X} all27={ok}")
        if ok:
            hits.append(int(c) * 8)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", required=True, type=Path)
    parser.add_argument("--unity", required=True, type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    for path, label in ((args.unity, "UnityPlayer"), (args.game, "GameAssembly")):
        hits = scan(path, label, args.verbose)
        for h in hits:
            print(f"{label}: *** MATCH file_off=0x{h:X}")


if __name__ == "__main__":
    main()
