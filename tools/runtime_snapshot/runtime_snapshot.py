# runtime_snapshot.py
#
# RO-RUNTIME external reader (first PoC).
#
# Read-only boundary:
#   - OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ);
#   - PSAPI EnumProcessModulesEx for module discovery;
#   - ReadProcessMemory only for:
#       * known UnityPlayer / GameAssembly module ranges;
#       * the static-derived API table -> wrapper -> descriptor chain;
#       * optional bounded probes of pointer values stored in that chain.
#   - no writes, no remote code, no VirtualAllocEx/WriteProcessMemory,
#     no full address-space scans, no PEB/NtQueryInformationProcess.
#
# Usage:
#   python tools/runtime_snapshot/runtime_snapshot.py \
#       --pid 36268 \
#       --unity-file D:\StarRail_4.4.53\UnityPlayer.dll \
#       --game-file D:\StarRail_4.4.53\GameAssembly.dll \
#       --table-rva 0x1A36480 --slot 63 \
#       --game-version 4.4.54 \
#       --json data\raw\4.4.54\il2cpp\runtime_snapshot_domain_4.4.54.json

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import struct
import sys
from pathlib import Path

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
LIST_MODULES_ALL = 0x03
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = wt.HANDLE(-1).value
MAX_PATH = 4096

CANONICAL_USER_MAX = 0x00007FFFFFFFFFFF
MIN_USER_POINTER = 0x10000

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("Psapi", use_last_error=True)

SIZE_T = ctypes.c_size_t
DWORD = wt.DWORD
HANDLE = wt.HANDLE
HMODULE = wt.HMODULE


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("cntUsage", DWORD),
        ("th32ProcessID", DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", DWORD),
        ("cntThreads", DWORD),
        ("th32ParentProcessID", DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


class PeFile:
    """Minimal PE32+ section model parsed from the on-disk file."""

    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if self.data[:2] != b"MZ":
            raise ValueError(f"not a PE file: {path}")
        e_lfanew = struct.unpack_from("<I", self.data, 0x3C)[0]
        coff = self.data[e_lfanew+4:e_lfanew+24]
        nsec = struct.unpack_from("<H", coff, 2)[0]
        opt_size = struct.unpack_from("<H", coff, 16)[0]
        opt_off = e_lfanew + 24
        self.image_base = struct.unpack_from("<Q", self.data, opt_off + 24)[0]
        self.image_size = struct.unpack_from("<I", self.data, opt_off + 56)[0]
        sec_off = opt_off + opt_size
        self.sections = []
        for i in range(nsec):
            s = self.data[sec_off+i*40:sec_off+(i+1)*40]
            name = s[:8].rstrip(b"\0").decode("latin1")
            vsize, rva = struct.unpack_from("<II", s, 8)
            rsize, roff = struct.unpack_from("<II", s, 16)
            chars = struct.unpack_from("<I", s, 36)[0]
            self.sections.append({
                "name": name, "rva": rva, "vsize": vsize,
                "rsize": rsize, "roff": roff, "chars": chars,
            })

    def section(self, rva):
        for s in self.sections:
            if s["rva"] <= rva < s["rva"] + max(s["vsize"], 0x1000):
                return s
        return None

    def contains_rva(self, rva):
        return self.section(rva) is not None


class RemoteModule:
    def __init__(self, name, base, path, pe: PeFile):
        self.name = name
        self.base = base
        self.path = path
        self.pe = pe
        self.size = pe.image_size

    def contains(self, va):
        return self.base <= va < self.base + self.size


def set_api():
    kernel32.OpenProcess.restype = HANDLE
    kernel32.OpenProcess.argtypes = [DWORD, wt.BOOL, DWORD]
    kernel32.CloseHandle.argtypes = [HANDLE]
    kernel32.ReadProcessMemory.restype = wt.BOOL
    kernel32.ReadProcessMemory.argtypes = [
        HANDLE, ctypes.c_void_p, ctypes.c_void_p, SIZE_T, ctypes.POINTER(SIZE_T)]
    kernel32.CreateToolhelp32Snapshot.restype = HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [DWORD, DWORD]
    kernel32.Process32FirstW.argtypes = [HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.argtypes = [HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    psapi.EnumProcessModulesEx.restype = wt.BOOL
    psapi.EnumProcessModulesEx.argtypes = [
        HANDLE, ctypes.POINTER(HMODULE), DWORD, ctypes.POINTER(DWORD), DWORD]
    psapi.GetModuleFileNameExW.restype = DWORD
    psapi.GetModuleFileNameExW.argtypes = [HANDLE, HMODULE, ctypes.c_wchar_p, DWORD]


def win_error():
    return ctypes.get_last_error()


def find_process_pid(name="StarRail.exe"):
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        return None
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    pids = []
    if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
        while True:
            if entry.szExeFile.lower() == name.lower():
                pids.append(entry.th32ProcessID)
            if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                break
    kernel32.CloseHandle(snap)
    return pids


def rpm(handle, addr, size, module=None):
    if size <= 0:
        return None
    if module is not None and not module.contains(addr):
        return None
    chunks = []
    done = 0
    while done < size:
        want = min(size - done, 0x10000)
        buf = ctypes.create_string_buffer(want)
        got = SIZE_T(0)
        ok = kernel32.ReadProcessMemory(
            handle, ctypes.c_void_p(addr + done), buf, want, ctypes.byref(got))
        if not ok or got.value == 0:
            return None
        chunks.append(buf.raw[:got.value])
        done += got.value
    return b"".join(chunks)


def read_qword(handle, addr, module=None):
    b = rpm(handle, addr, 8, module=module)
    return struct.unpack("<Q", b)[0] if b else None


def is_canonical_user(va):
    return MIN_USER_POINTER <= va <= CANONICAL_USER_MAX


def describe_pointer(va, modules):
    for mod in modules:
        if mod.contains(va):
            rva = va - mod.base
            sec = mod.pe.section(rva)
            return {
                "module": mod.name,
                "rva": rva,
                "section": sec["name"] if sec else None,
                "is_executable": bool(sec and (sec["chars"] & 0x20000000)),
                "in_known_module": True,
            }
    return {
        "module": "OUTSIDE", "rva": None, "section": None,
        "is_executable": False, "in_known_module": False,
    }


def enumerate_modules(handle):
    needed = DWORD(0)
    psapi.EnumProcessModulesEx(handle, None, 0, ctypes.byref(needed), LIST_MODULES_ALL)
    if needed.value == 0:
        return []
    count = needed.value // ctypes.sizeof(HMODULE)
    arr = (HMODULE * count)()
    if not psapi.EnumProcessModulesEx(handle, arr, needed, ctypes.byref(needed), LIST_MODULES_ALL):
        return []
    out = []
    for i in range(needed.value // ctypes.sizeof(HMODULE)):
        buf = ctypes.create_unicode_buffer(MAX_PATH)
        psapi.GetModuleFileNameExW(handle, arr[i], buf, MAX_PATH)
        path = buf.value
        if not path:
            continue
        name = Path(path).name
        if name.lower() in ("unityplayer.dll", "gameassembly.dll", "starrail.exe"):
            out.append({"name": name.lower(), "base": arr[i] or 0, "path": path})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--unity-file", required=True, type=Path)
    parser.add_argument("--game-file", required=True, type=Path)
    parser.add_argument("--table-rva", type=lambda v: int(v, 0), required=True)
    parser.add_argument("--slot", type=int, default=63)
    parser.add_argument("--game-version", default="4.4.54")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--probe-heap-fields", action="store_true",
                        help="bounded RPM probes of non-module descriptor qwords")
    args = parser.parse_args()

    set_api()
    result = {
        "schema": "runtime_snapshot/1",
        "tool": "tools/runtime_snapshot/runtime_snapshot.py",
        "game_version": args.game_version,
        "slot": args.slot,
        "api_table_rva": args.table_rva,
        "api_table_rva_semantic_status": "disproven_as_il2cpp_api_table",
        "structural_artifact_type": "unity_native_proxy_registration_table",
        "final_status": None,
        "read_result": {},
        "pointer_chain": [],
        "validation": [],
    }

    unity_pe = PeFile(args.unity_file)
    game_pe = PeFile(args.game_file)

    pid = args.pid
    if pid == 0:
        pids = find_process_pid()
        if not pids:
            result["final_status"] = "REMOTE_READ_FAILED"
            result["error"] = "StarRail.exe not running"
            _write_json(args, result)
            print("BLOCKED: StarRail.exe not running")
            return 1
        pid = pids[0]
    result["target_pid"] = pid

    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        result["final_status"] = "REMOTE_READ_FAILED"
        result["error"] = f"OpenProcess failed win32_error={win_error()}"
        _write_json(args, result)
        print(f"BLOCKED: OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ) failed error={win_error()}")
        return 1

    try:
        found = enumerate_modules(handle)
        modules = []
        for rec in found:
            if rec["name"] == "unityplayer.dll":
                modules.append(RemoteModule("UnityPlayer", rec["base"], rec["path"], unity_pe))
            elif rec["name"] == "gameassembly.dll":
                modules.append(RemoteModule("GameAssembly", rec["base"], rec["path"], game_pe))
        unity = next((m for m in modules if m.name == "UnityPlayer"), None)
        game = next((m for m in modules if m.name == "GameAssembly"), None)
        result["modules"] = {
            "UnityPlayer": {"base": unity.base, "size": unity.size} if unity else None,
            "GameAssembly": {"base": game.base, "size": game.size} if game else None,
        }
        if not unity or not game:
            result["final_status"] = "REMOTE_READ_FAILED"
            result["error"] = "UnityPlayer/GameAssembly not found via PSAPI"
            _write_json(args, result)
            print("BLOCKED: modules not found via PSAPI")
            return 1

        # 1. table entry -> wrapper
        entry = read_qword(handle, unity.base + args.table_rva + args.slot * 8, module=unity)
        if entry is None:
            result["final_status"] = "POINTER_VALIDATION_FAILED"
            result["error"] = "api table slot unreadable"
            _write_json(args, result)
            return 1
        wrapper = describe_pointer(entry, modules)
        if not wrapper["in_known_module"] or not wrapper["is_executable"]:
            result["final_status"] = "POINTER_VALIDATION_FAILED"
            result["error"] = f"wrapper pointer invalid: {wrapper}"
            _write_json(args, result)
            return 1
        result["wrapper_rva"] = wrapper["rva"]
        result["pointer_chain"].append({"level": "table_entry", "va": entry, **wrapper})

        # 2. wrapper shape A -> descriptor rva
        wb = rpm(handle, entry, 16, module=unity)
        if not wb or wb[:3] != b"\x45\x33\xc0" or wb[3:6] != b"\x48\x8d\x0d":
            result["final_status"] = "POINTER_VALIDATION_FAILED"
            result["error"] = "wrapper shape A mismatch"
            _write_json(args, result)
            return 1
        disp = struct.unpack_from("<i", wb, 6)[0]
        desc_rva = wrapper["rva"] + 10 + disp
        result["descriptor_rva"] = desc_rva
        result["pointer_chain"].append({
            "level": "descriptor", "rva": desc_rva,
            "section": unity.pe.section(desc_rva)["name"] if unity.pe.section(desc_rva) else None,
        })

        # 3. descriptor qwords with validation
        qs = [read_qword(handle, unity.base + desc_rva + i * 8, module=unity) for i in range(12)]
        described = [describe_pointer(q, modules) if q else None for q in qs]
        result["descriptor_qwords"] = described
        result["read_result"]["descriptor_qwords_raw"] = qs

        q5 = qs[5]
        if q5 is None:
            result["final_status"] = "POINTER_VALIDATION_FAILED"
            result["error"] = "descriptor q[5] null"
            _write_json(args, result)
            return 1
        q5d = describe_pointer(q5, modules)
        if not q5d["in_known_module"] or not q5d["is_executable"]:
            result["final_status"] = "POINTER_VALIDATION_FAILED"
            result["error"] = f"real-target q[5] pointer invalid: {q5d}"
            _write_json(args, result)
            return 1
        result["real_target_rva"] = q5d["rva"]
        result["real_target_module"] = q5d["module"]
        result["pointer_chain"].append({"level": "real_target_q5", "va": q5, **q5d})

        # 4. runtime global: NOT resolved by static analysis.
        result["runtime_global_rva"] = None
        result["domain_source"] = None

        # 5. bounded probes of descriptor-owned non-module pointers.
        probes = {}
        if args.probe_heap_fields:
            for idx in (2, 10):
                p = qs[idx]
                if not p or not is_canonical_user(p):
                    probes[str(idx)] = {"pointer": p, "probe": "SKIPPED (non-canonical/null)"}
                    continue
                buf = rpm(handle, p, 0x80)
                if buf is None:
                    probes[str(idx)] = {"pointer": p, "probe": "RPM_FAILED"}
                    continue
                probes[str(idx)] = {
                    "pointer": p,
                    "probe": "READABLE",
                    "first_qwords": [struct.unpack_from("<Q", buf, o)[0]
                                     for o in range(0, min(len(buf) - 7, 0x40), 8)],
                }
        result["read_result"]["heap_field_probes"] = probes

        result["validation"].append("OpenProcess read-only: PASS")
        result["validation"].append("PSAPI module discovery: PASS")
        result["validation"].append("table->wrapper->descriptor->q5 chain: readable")
        result["validation"].append("runtime global for domain_get: NOT RESOLVED by static analysis")
        result["final_status"] = "STATIC_TARGET_UNRESOLVED"
        result["failure_class"] = "STATIC_TARGET_UNRESOLVED"
        result["failure_detail"] = (
            "slot-level static chain resolves, but the q[5] real-target stub is a "
            "Unity proxy registration thunk, not an il2cpp_domain_get implementation; "
            "the runtime global used by domain_get was not recovered."
        )
        _write_json(args, result)
        print(f"final_status: {result['final_status']}")
        return 2 if args.json is None else 0
    finally:
        kernel32.CloseHandle(handle)


def _write_json(args, result):
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"json: {args.json}")


if __name__ == "__main__":
    sys.exit(main())
