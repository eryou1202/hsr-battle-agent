# probe_il2cpp_api_table.py
#
# 最小只读 Runtime Probe（隔离进程，不启动游戏，不加载反作弊驱动）：
#   1. LoadLibrary 加载 GameAssembly.dll（其同目录 UnityPlayer.dll 作为依赖自动加载）
#   2. GetProcAddress 取得导出 il2cpp_get_api_table
#   3. 调用它，取得 IL2CPP API function table 指针
#   4. 读取前 N 个 slot，用 honkai-dumper 已知索引命名，并验证指针落在
#      GameAssembly / UnityPlayer 映像的代码段内
#
# 边界：本进程 = 普通本地进程；不做任何写操作、不注入、不 hook、
#       不修改文件；仅调用一个导出函数并读取其返回值指向的只读数据。
#
# 用法:
#   python tools/reverse/scripts/probe_il2cpp_api_table.py --game <GameAssembly.dll> [--slots N]

import argparse
import ctypes
import struct
from ctypes import wintypes
from pathlib import Path

# honkai-dumper (target 3.7.0) 的已知 slot 索引（functions.rs）
KNOWN_SLOTS = {
    22: "il2cpp_assembly_get_image",
    31: "il2cpp_class_get_fields",
    33: "il2cpp_class_get_interfaces",
    35: "il2cpp_class_get_methods",
    37: "il2cpp_class_get_name",
    39: "il2cpp_class_get_namespace",
    40: "il2cpp_class_get_parent",
    43: "il2cpp_class_is_valuetype",
    45: "il2cpp_class_get_flags",
    49: "il2cpp_class_from_type",
    53: "il2cpp_class_is_enum",
    63: "il2cpp_domain_get",
    65: "il2cpp_domain_get_assemblies",
    72: "il2cpp_field_get_flags",
    73: "il2cpp_field_get_name",
    75: "il2cpp_field_get_offset",
    76: "il2cpp_field_get_type",
    116: "il2cpp_method_get_return_type",
    117: "il2cpp_method_get_name",
    123: "il2cpp_method_get_param_count",
    124: "il2cpp_method_get_param",
    161: "il2cpp_type_get_name",
    162: "il2cpp_type_is_byref",
    163: "il2cpp_type_get_attrs",
    168: "il2cpp_image_get_name",
    169: "il2cpp_image_get_class_count",
    170: "il2cpp_image_get_class",
}

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

MODULEINFO = ctypes.c_ubyte * 24  # lpBaseOfDll, SizeOfImage, EntryPoint

def get_module_range(handle):
    """HMODULE == 模块基址；SizeOfImage 用 GetModuleInformation 获取。"""
    base = int(handle)
    info = MODULEINFO()
    psapi.GetModuleInformation.restype = wintypes.BOOL
    psapi.GetModuleInformation.argtypes = [
        wintypes.HANDLE, wintypes.HMODULE,
        ctypes.POINTER(MODULEINFO), wintypes.DWORD,
    ]
    ok = psapi.GetModuleInformation(
        kernel32.GetCurrentProcess(),
        ctypes.c_void_p(base),
        ctypes.byref(info),
        ctypes.sizeof(MODULEINFO),
    )
    if not ok:
        return base, None
    size = struct.unpack_from("<I", info, 8)[0]
    return base, size

def load_pe_sections(path: Path):
    data = path.read_bytes()
    e = struct.unpack_from("<I", data, 0x3C)[0]
    ns = struct.unpack_from("<H", data, e + 6)[0]
    osz = struct.unpack_from("<H", data, e + 20)[0]
    so = e + 24 + osz
    secs = []
    for i in range(ns):
        s = data[so + i * 40: so + (i + 1) * 40]
        name = s[:8].rstrip(b"\0").decode("latin1")
        vs, va, rs, ro = struct.unpack_from("<IIII", s, 8)
        chars = struct.unpack_from("<I", s, 36)[0]
        secs.append({"name": name, "rva": va, "vsize": vs, "chars": chars})
    return secs

def section_of(secs, rva):
    for s in secs:
        if s["rva"] <= rva < s["rva"] + max(s["vsize"], 0x1000):
            return s["name"]
    return None

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", required=True, type=Path)
    parser.add_argument("--slots", type=int, default=200)
    args = parser.parse_args()

    game_path = str(args.game.resolve())
    print(f"[probe] loading {game_path}")
    try:
        game = ctypes.CDLL(game_path)
    except OSError as e:
        print(f"[FAIL] LoadLibrary error: {e}")
        return

    g_base, g_size = get_module_range(game._handle)
    print(f"[probe] GameAssembly handle=0x{g_base:X} size=0x{g_size:X}")

    # UnityPlayer 若已作为依赖加载
    unity = None
    try:
        unity = ctypes.CDLL(str(Path(game_path).parent / "UnityPlayer.dll"))
        u_base, u_size = get_module_range(unity._handle)
        print(f"[probe] UnityPlayer handle=0x{u_base:X} size=0x{u_size:X}")
    except OSError:
        print("[probe] UnityPlayer not loaded / load failed (ok)")

    get_proc = kernel32.GetProcAddress
    get_proc.restype = ctypes.c_void_p
    get_proc.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

    export = get_proc(game._handle, b"il2cpp_get_api_table")
    if not export:
        print("[FAIL] GetProcAddress(il2cpp_get_api_table) = NULL")
        return
    print(f"[probe] il2cpp_get_api_table @ 0x{export:X}")

    fn = ctypes.CFUNCTYPE(ctypes.c_void_p)(export)
    table = fn()
    print(f"[probe] call il2cpp_get_api_table() -> table @ 0x{table:X}")

    if not table:
        print("[FAIL] table pointer is NULL")
        return

    raw = ctypes.string_at(table, args.slots * 8)
    ptrs = struct.unpack(f"<{args.slots}Q", raw)

    print(f"\n[probe] table slots 0..{args.slots - 1} (slot, target, module, section, known_name):")
    for i, p in enumerate(ptrs):
        name = KNOWN_SLOTS.get(i, "")
        if p == 0:
            print(f"  [{i:3}] 0x0000000000000000  NULL")
            continue
        mod = "?"
        sec = "?"
        if g_base and g_base <= p < g_base + g_size:
            mod = "GameAssembly"
            sec = section_of(load_pe_sections(args.game), p - g_base) or "?"
        elif unity and u_base and u_base <= p < u_base + u_size:
            mod = "UnityPlayer"
        print(f"  [{i:3}] 0x{p:016X}  {mod:12s} {sec:10s} {name}")

    # 汇总
    valid = sum(1 for p in ptrs if p)
    in_game = sum(1 for p in ptrs if g_base and g_base <= p < g_base + g_size)
    named_ok = sum(1 for i, p in enumerate(ptrs) if i in KNOWN_SLOTS and p)
    print(f"\n[probe] slots={len(ptrs)} non-null={valid} in-GameAssembly={in_game} "
          f"named-slots-nonnull={named_ok}/{len(KNOWN_SLOTS)}")
    print("[probe] done")

if __name__ == "__main__":
    main()
