# probe_getter_patch.py
#
# 对 GameAssembly.dll 导出 il2cpp_get_api_table 做"崩溃点 NOP 化"动态分析：
# 混淆 stub 在裸进程中因缺失游戏启动期初始化而崩溃（写 0x0）。
# 本脚本用 VEH 捕获访问违例，把"写指令"原地 NOP 化后继续执行，
# 观察解码链能否继续并最终返回 api table 指针。
#
# 边界说明：全部修改仅发生在当前隔离进程自身的内存里（等效调试器
# 单步/补丁），不修改任何文件、不启动游戏、不加载反作弊驱动、
# 不连接网络、不涉及战斗逻辑。

import ctypes
import struct
from pathlib import Path

from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

EXCEPTION_CONTINUE_EXECUTION = 0xFFFFFFFF
EXCEPTION_CONTINUE_SEARCH = 0
EXCEPTION_ACCESS_VIOLATION = 0xC0000005


class Patcher:
    def __init__(self, max_patches: int = 24, game_base: int = 0):
        self.max_patches = max_patches
        self.patches = 0
        self.events = []
        self.game_base = game_base

    def handle(self, ep_ptr):
        rec = ctypes.cast(ctypes.c_void_p(ep_ptr), ctypes.POINTER(ctypes.c_void_p))
        ctx = ctypes.cast(ctypes.c_void_p(rec[1]), ctypes.POINTER(ctypes.c_void_p))
        rec_ptr, ctx_ptr = int(rec[0]), int(rec[1])
        code = ctypes.c_uint32.from_address(rec_ptr).value
        rip = ctypes.c_uint64.from_address(ctx_ptr + 0xF8).value
        if code != EXCEPTION_ACCESS_VIOLATION:
            return EXCEPTION_CONTINUE_SEARCH
        op = ctypes.c_uint64.from_address(rec_ptr + 32 - 8).value  # NumberParameters(24)+pad
        # ExceptionInformation[0] 在 +32
        addr = ctypes.c_uint64.from_address(rec_ptr + 32).value
        rva = rip - self.game_base
        self.events.append((rva, addr))
        print(f"[veh] AV rip_rva=0x{rva:X} addr=0x{addr:X} patches={self.patches}")
        if self.patches >= self.max_patches:
            print("[veh] patch cap reached, search")
            return EXCEPTION_CONTINUE_SEARCH
        # 读指令字节；仅处理"写指令" 48 89 / 48 8B (mov [mem],reg 形式)
        try:
            b = ctypes.string_at(rip, 8)
        except Exception:
            return EXCEPTION_CONTINUE_SEARCH
        print(f"[veh] bytes: {b.hex(' ')}")
        patched = False
        # mov [r/m64], reg : (REX.W) 89 /r 且 mod != 3（内存写）
        if b[1] == 0x89 and (b[0] == 0x89 or 0x40 <= b[0] <= 0x4F):
            modrm = b[2]
            mod = (modrm >> 6) & 3
            if mod != 3:
                # 长度估算: opcode(+REX) + ModRM + 可选 SIB + 可选 disp
                length = 3
                rm = modrm & 7
                if rm == 4:
                    length += 1
                    sib = b[3]
                    base = sib & 7
                    idx = (sib >> 3) & 7
                    if mod == 0 and base == 5:
                        length += 4
                    elif idx == 5:
                        length += 4
                if mod == 1:
                    length += 1
                elif mod == 2:
                    length += 4
                elif mod == 0 and rm == 5:
                    length += 4
                # 覆盖为 NOP（先确保页可写）
                PAGE_EXECUTE_READWRITE = 0x40
                old = ctypes.c_uint32()
                page_start = rip & ~0xFFF
                kernel32.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
                kernel32.VirtualProtect.restype = wintypes.BOOL
                kernel32.VirtualProtect(ctypes.c_void_p(page_start), 0x1000, PAGE_EXECUTE_READWRITE, ctypes.byref(old))
                ctypes.memset(ctypes.c_void_p(rip), 0x90, length)
                self.patches += 1
                patched = True
                print(f"[veh] NOPed {length} bytes at rva 0x{rva:X}")
        if patched:
            return EXCEPTION_CONTINUE_EXECUTION
        print("[veh] not a write instruction, search")
        return EXCEPTION_CONTINUE_SEARCH


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", required=True, type=Path)
    parser.add_argument("--max-patches", type=int, default=24)
    args = parser.parse_args()

    game = ctypes.CDLL(str(args.game.resolve()))
    g_base = int(game._handle)
    print(f"[probe] GameAssembly base=0x{g_base:X}")

    patcher = Patcher(max_patches=args.max_patches, game_base=g_base)
    CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)
    cb = CALLBACK(patcher.handle)
    kernel32.AddVectoredExceptionHandler.argtypes = [ctypes.c_uint32, CALLBACK]
    kernel32.AddVectoredExceptionHandler.restype = ctypes.c_void_p
    kernel32.AddVectoredExceptionHandler(1, cb)
    print("[probe] VEH installed")

    get_proc = kernel32.GetProcAddress
    get_proc.restype = ctypes.c_void_p
    get_proc.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    export = get_proc(game._handle, b"il2cpp_get_api_table")
    print(f"[probe] export @ 0x{export:X} (rva 0x{export - g_base:X})")

    fn = ctypes.CFUNCTYPE(ctypes.c_void_p)(export)
    try:
        table = fn()
        print(f"[probe] CALL RETURNED: table @ 0x{table:X} (rva 0x{table - g_base:X})")
        if table:
            raw = ctypes.string_at(table, 200 * 8)
            ptrs = struct.unpack("<200Q", raw)
            valid = sum(1 for p in ptrs if p)
            print(f"[probe] first 200 slots: non-null={valid}")
            for i in range(0, 180):
                p = ptrs[i]
                if p:
                    print(f"  [{i:3}] 0x{p:016X} rva(0x{p - g_base:X})")
    except OSError as e:
        print(f"[probe] call raised: {e}")
    print(f"[probe] total VEH events: {len(patcher.events)}")
    print("[probe] done")


if __name__ == "__main__":
    main()
