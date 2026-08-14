# probe_api_table_veh.py
#
# 在隔离进程中加载 GameAssembly.dll 并调用 il2cpp_get_api_table。
# 安装 VEH 捕获访问违例，打印故障指令 RIP / 读取地址 / 寄存器，
# 用于分析混淆 stub 的守卫逻辑（为什么在裸进程中返回 -1 读取）。
#
# 边界：仅本进程内 LoadLibrary + 调用导出 + 读异常上下文；
# 不修改任何内存/文件，不涉及游戏运行进程与反作弊驱动。

import ctypes
import struct
from pathlib import Path

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

EXCEPTION_CONTINUE_SEARCH = 0
EXCEPTION_ACCESS_VIOLATION = 0xC0000005

class VEHHandler:
    def __init__(self):
        self.fired = []

    def handle(self, ep_ptr):
        # EXCEPTION_POINTERS: +0 ExceptionRecord*, +8 ContextRecord*
        rec = ctypes.cast(ctypes.c_void_p(ep_ptr), ctypes.POINTER(ctypes.c_void_p))
        ctx = ctypes.cast(ctypes.c_void_p(rec[1]), ctypes.POINTER(ctypes.c_void_p))
        rec_ptr = int(rec[0])
        ctx_ptr = int(rec[1])
        code = ctypes.c_uint32.from_address(rec_ptr).value
        exc_addr = ctypes.c_uint64.from_address(rec_ptr + 8).value
        # x64 CONTEXT 布局（关键字段）
        rax = ctypes.c_uint64.from_address(ctx_ptr + 0x78).value
        rcx = ctypes.c_uint64.from_address(ctx_ptr + 0x80).value
        rdx = ctypes.c_uint64.from_address(ctx_ptr + 0x88).value
        rbx = ctypes.c_uint64.from_address(ctx_ptr + 0x90).value
        rsp = ctypes.c_uint64.from_address(ctx_ptr + 0x98).value
        rbp = ctypes.c_uint64.from_address(ctx_ptr + 0xA0).value
        rsi = ctypes.c_uint64.from_address(ctx_ptr + 0xA8).value
        rdi = ctypes.c_uint64.from_address(ctx_ptr + 0xB0).value
        r8 = ctypes.c_uint64.from_address(ctx_ptr + 0xB8).value
        r9 = ctypes.c_uint64.from_address(ctx_ptr + 0xC0).value
        r10 = ctypes.c_uint64.from_address(ctx_ptr + 0xC8).value
        r11 = ctypes.c_uint64.from_address(ctx_ptr + 0xD0).value
        r12 = ctypes.c_uint64.from_address(ctx_ptr + 0xD8).value
        r13 = ctypes.c_uint64.from_address(ctx_ptr + 0xE0).value
        r14 = ctypes.c_uint64.from_address(ctx_ptr + 0xE8).value
        r15 = ctypes.c_uint64.from_address(ctx_ptr + 0xF0).value
        rip = ctypes.c_uint64.from_address(ctx_ptr + 0xF8).value
        self.fired.append({
            "code": code, "exc_addr": exc_addr, "rip": rip,
            "rax": rax, "rcx": rcx, "rdx": rdx, "rbx": rbx,
            "rsp": rsp, "rbp": rbp, "rsi": rsi, "rdi": rdi,
            "r8": r8, "r9": r9, "r10": r10, "r11": r11,
            "r12": r12, "r13": r13, "r14": r14, "r15": r15,
        })
        if code == EXCEPTION_ACCESS_VIOLATION:
            # ExceptionInformation[0]=操作 (0=读 1=写), [1]=地址
            op = ctypes.c_uint64.from_address(rec_ptr + 24).value
            addr = ctypes.c_uint64.from_address(rec_ptr + 32).value
            self.fired[-1]["violation_op"] = op
            self.fired[-1]["violation_addr"] = addr
        # 打印后继续搜索（让进程按原样崩溃，不做任何处理）
        return EXCEPTION_CONTINUE_SEARCH


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", required=True, type=Path)
    parser.add_argument("--max-veh", type=int, default=3)
    args = parser.parse_args()

    game_path = str(args.game.resolve())
    handler = VEHHandler()
    CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)
    cb = CALLBACK(handler.handle)
    kernel32.AddVectoredExceptionHandler.argtypes = [ctypes.c_uint32, CALLBACK]
    kernel32.AddVectoredExceptionHandler.restype = ctypes.c_void_p
    handle = kernel32.AddVectoredExceptionHandler(1, cb)
    print(f"[probe] VEH installed: 0x{handle:X}")

    print(f"[probe] loading {game_path}")
    game = ctypes.CDLL(game_path)
    g_base = int(game._handle)
    print(f"[probe] GameAssembly base=0x{g_base:X}")

    get_proc = kernel32.GetProcAddress
    get_proc.restype = ctypes.c_void_p
    get_proc.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    export = get_proc(game._handle, b"il2cpp_get_api_table")
    print(f"[probe] export @ 0x{export:X} (rva 0x{export - g_base:X})")

    fn = ctypes.CFUNCTYPE(ctypes.c_void_p)(export)
    try:
        table = fn()
        print(f"[probe] SUCCESS: table @ 0x{table:X}")
    except OSError as e:
        print(f"[probe] call raised: {e}")

    print(f"\n[probe] VEH events: {len(handler.fired)}")
    for i, ev in enumerate(handler.fired[: args.max_veh]):
        print(f"  event {i}: code=0x{ev['code']:08X} rip=0x{ev['rip']:X} "
              f"(rva 0x{ev['rip'] - g_base:X})")
        if "violation_addr" in ev:
            print(f"    violation: op={'read' if ev['violation_op'] == 0 else 'write'} "
                  f"addr=0x{ev['violation_addr']:X}")
        for reg in ("rax", "rcx", "rdx", "rbx", "r12", "r13", "r14", "r15", "rsp", "rbp"):
            print(f"    {reg}=0x{ev[reg]:X}")
        # 打印故障指令字节
        try:
            code_bytes = ctypes.string_at(ev["rip"], 16)
            print("    bytes:", code_bytes.hex(" "))
        except Exception:
            pass

    print("[probe] done")


if __name__ == "__main__":
    main()
