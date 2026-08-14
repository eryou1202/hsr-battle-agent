# scan_api_table_loaded.py
#
# 在"已加载映像"上做 api table 指纹扫描（利用重定位后的真实 VA）。
#
# 指纹（比纯指针合法性强得多）：
#   il2cpp api table 中 class_* 系列函数（slot 31..53）在标准 il2cpp 中
#   是同一编译单元（vm/Class.cpp）的相邻小函数；domain_*（63/65）在
#   vm/Domain.cpp。因此候选 table 的 slot 37/39/40（class_get_name/
#   namespace/parent）应彼此非常接近（同一函数簇）。
#   而巨型 methodPointers 数组的任意 3 个指针落在 4KB 内的概率极低。
#
# 扫描范围：UnityPlayer.dll 与 GameAssembly.dll 的 .rdata（已加载内存）。
# 边界：只读本进程内存；不修改任何内容。

import argparse
import ctypes
import struct
from pathlib import Path

import numpy as np

CLUSTER = [37, 39, 40]          # class_get_name / namespace / parent
CHECK = [22, 31, 33, 35, 37, 39, 40, 43, 45, 49, 53, 63, 65,
         72, 73, 75, 76, 116, 117, 123, 124, 161, 162, 163, 168, 169, 170]
CLUSTER_MAX_SPAN = 0x4000       # class_* 函数簇最大跨度


def load_pe(path: Path):
    data = path.read_bytes()
    e = struct.unpack_from("<I", data, 0x3C)[0]
    ns = struct.unpack_from("<H", data, e + 6)[0]
    osz = struct.unpack_from("<H", data, e + 20)[0]
    so = e + 24 + osz
    secs = []
    for i in range(ns):
        s = data[so + i * 40: so + (i + 1) * 40]
        name = s[:8].rstrip(b"\0").decode("latin1")
        vs, va = struct.unpack_from("<II", s, 8)
        secs.append({"name": name, "rva": va, "vsize": vs})
    return secs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", required=True, type=Path)
    parser.add_argument("--unity", required=True, type=Path)
    parser.add_argument("--cluster-span", type=lambda v: int(v, 0), default=CLUSTER_MAX_SPAN)
    parser.add_argument("--adjacent-span", type=lambda v: int(v, 0), default=0x1000)
    parser.add_argument("--slots", type=int, default=200)
    args = parser.parse_args()

    game = ctypes.CDLL(str(args.game.resolve()))
    unity = ctypes.CDLL(str(args.unity.resolve()))
    g_base, u_base = int(game._handle), int(unity._handle)
    g_secs = load_pe(args.game)
    u_secs = load_pe(args.unity)
    print(f"GameAssembly base=0x{g_base:X}  UnityPlayer base=0x{u_base:X}")

    def is_code(ptr, base, secs):
        if not (base <= ptr < base + 0x2080C000):
            return False
        rva = ptr - base
        for s in secs:
            if s["rva"] <= rva < s["rva"] + max(s["vsize"], 0x1000):
                return s["name"] in (".text", "il2cpp", ".upx0")
        return False

    # 相邻簇组：同一 vm 源文件的 api 函数在标准 il2cpp 中相邻
    ADJ_GROUPS = [
        [116, 117, 123, 124],   # vm/Method.cpp
        [161, 162, 163],        # vm/Type.cpp
        [168, 169, 170],        # vm/Image.cpp
        [31, 33, 35, 37, 39, 40, 43, 45, 49, 53],  # vm/Class.cpp
        [72, 73, 75, 76],       # vm/Field.cpp
        [63, 65],               # vm/Domain.cpp
        [22],                   # vm/Assembly.cpp
    ]

    def scan(module_handle, secs, label):
        # 只扫 .rdata
        rd = next(s for s in secs if s["name"] == ".rdata")
        size = min(rd["vsize"], 0x6000000)
        size -= size % 8  # numpy frombuffer 要求 8 字节对齐
        addr = module_handle + rd["rva"]
        buf = (ctypes.c_char * size).from_address(addr)
        arr = np.frombuffer(buf, dtype="<u8")
        n = len(arr)
        hits = []
        for start in range(0, n - max(CHECK) - 1):
            ok_all = True
            for grp in ADJ_GROUPS:
                if not all(is_code(int(arr[start + k]), g_base, g_secs)
                           or is_code(int(arr[start + k]), u_base, u_secs)
                           for k in grp):
                    ok_all = False
                    break
                ptrs = [int(arr[start + k]) for k in grp]
                if max(ptrs) - min(ptrs) > args.adjacent_span:
                    ok_all = False
                    break
            if not ok_all:
                continue
            # 全量检查
            ok = True
            for k in CHECK:
                p = int(arr[start + k])
                if not (is_code(p, g_base, g_secs) or is_code(p, u_base, u_secs)):
                    ok = False
                    break
            if ok:
                hits.append(start)
        print(f"{label}: candidates = {len(hits)}")
        for start in hits[:10]:
            rva = rd["rva"] + start * 8
            s22 = int(arr[start + 22])
            s37 = int(arr[start + 37])
            s63 = int(arr[start + 63])
            s170 = int(arr[start + 170])
            print(f"  table @ {label} rva 0x{rva:X}  "
                  f"slot22=0x{s22 - g_base:X} slot37=0x{s37 - g_base:X} "
                  f"slot63=0x{s63 - g_base:X} slot170=0x{s170 - g_base:X}")

    scan(unity._handle, u_secs, "UnityPlayer")
    scan(game._handle, g_secs, "GameAssembly")


if __name__ == "__main__":
    main()
