# find_il2cpp_api_table.py
#
# 自动定位 IL2CPP API Function Table（跨小版本自适应，无硬编码偏移）。
#
# 原理（来自 4.4.54 实测确认的结构，见 docs/reverse/il2cpp_api_table.md）：
#   - api table 位于 UnityPlayer.dll .rdata，是一个函数指针数组；
#   - slot 索引固定为 il2cpp api 顺序（honkai-dumper 索引表：22=assembly_get_image,
#     37=class_get_name, 63=domain_get, 65=domain_get_assemblies, ...）；
#   - 4.4.54 的 table 条目是 32 字节间隔的 wrapper stub（descriptor + 共享 dispatcher）；
#   - 判别签名：
#       a) 全部 27 个已知索引的 slot 都是代码指针（UnityPlayer .text 内）
#       b) slot 63/65（domain 双子）是相邻函数（间距 <= 0x100）
#       c) slot 10/12（另一双子）相邻
#       d) method_*(116,117,123,124)、type_*(161-163)、image_*(168-170)
#          组内跨度小（<= 0x1000）
#       e) class_*(31..53) 组内跨度 <= 0x4000
#
# 用法（Windows，加载模块到本进程以利用重定位后的真实 VA）：
#   python tools/reverse/scripts/find_il2cpp_api_table.py \
#       --unity <UnityPlayer.dll> --game <GameAssembly.dll>
# 输出：候选 table 的 RVA（相对 UnityPlayer）与命中分数。
#
# 边界：仅本进程加载 DLL + 只读扫描；不调用任何函数、不修改内存。

import argparse
import ctypes
import struct
from pathlib import Path

import numpy as np

# 已知索引（honkai-dumper functions.rs 索引表，标准 il2cpp api 顺序）
CHECK = [22, 31, 33, 35, 37, 39, 40, 43, 45, 49, 53, 63, 65,
         72, 73, 75, 76, 116, 117, 123, 124, 161, 162, 163, 168, 169, 170]

# 判别组（每组内的函数必须彼此接近）
GROUPS = [
    ([63, 65], 0x100),        # domain_get / domain_get_assemblies
    ([10, 12], 0x100),        # 双子对（4.4.54 实测为 0x453AA0/0x453AE0 形）
    ([168, 169, 170], 0x200),  # image_get_name / class_count / class
    ([116, 117, 123, 124], 0x1000),  # method_*
    ([161, 162, 163], 0x1000),       # type_*
    ([31, 33, 35, 37, 39, 40, 43, 45, 49, 53], 0x4000),  # class_*
]


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
    parser.add_argument("--unity", required=True, type=Path, help="UnityPlayer.dll")
    parser.add_argument("--game", required=True, type=Path, help="GameAssembly.dll")
    parser.add_argument("--max-slots", type=int, default=220)
    args = parser.parse_args()

    unity = ctypes.CDLL(str(args.unity.resolve()))
    game = ctypes.CDLL(str(args.game.resolve()))
    u_base, g_base = int(unity._handle), int(game._handle)
    u_secs = load_pe(args.unity)
    g_secs = load_pe(args.game)

    def is_unity_code(ptr: int) -> bool:
        rva = ptr - u_base
        if not (0 <= rva < 0x2756000):
            return False
        for s in u_secs:
            if s["rva"] <= rva < s["rva"] + max(s["vsize"], 0x1000):
                return s["name"] in (".text", ".upx0", "il2cpp")
        return False

    rd = next(s for s in u_secs if s["name"] == ".rdata")
    size = min(rd["vsize"], 0x6000000)
    size -= size % 8
    arr = np.frombuffer(
        (ctypes.c_char * size).from_address(u_base + rd["rva"]), dtype="<u8"
    )
    n = len(arr)

    results = []
    for start in range(0, n - max(CHECK) - 2):
        # 快速预筛：63/65 双子（相邻代码指针）
        v63 = int(arr[start + 63])
        v65 = int(arr[start + 65])
        if not (is_unity_code(v63) and is_unity_code(v65)):
            continue
        if not (0 < v65 - v63 <= 0x100):
            continue
        # 组约束
        ok = True
        for idxs, span in GROUPS:
            vals = [int(arr[start + k]) for k in idxs]
            if not all(is_unity_code(v) for v in vals):
                ok = False
                break
            if max(vals) - min(vals) > span:
                ok = False
                break
        if not ok:
            continue
        # 全量检查
        if not all(is_unity_code(int(arr[start + k])) for k in CHECK):
            continue
        results.append(start)

    print(f"candidates: {len(results)}")
    for start in results[:20]:
        rva = rd["rva"] + start * 8
        s63 = int(arr[start + 63]) - u_base
        s65 = int(arr[start + 65]) - u_base
        s170 = int(arr[start + 170]) - u_base
        print(f"  table @ UnityPlayer rva 0x{rva:X}  "
              f"slot63=0x{s63:X} slot65=0x{s65:X} slot170=0x{s170:X}")
    if len(results) == 1:
        start = results[0]
        print(f"\nRESULT: api table at UnityPlayer RVA 0x{rd['rva'] + start * 8:X} "
              f"({(rd['rva'] + start * 8) / 1024:.1f} KiB into image, "
              f"{start * 8} bytes into .rdata)")
    else:
        print(f"\nRESULT: {len(results)} candidates (ambiguous)")


if __name__ == "__main__":
    main()
