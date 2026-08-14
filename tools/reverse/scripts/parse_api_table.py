# parse_api_table.py
#
# 静态解析 IL2CPP api table（完全离线，不加载游戏）。
#
# 依据：honkai-dumper (lanylow) 的 Il2CppFunctions::new() 在运行时读取
#   UnityPlayer.dll + 0x1eed6a8 处的函数指针数组（其 base 为 UnityPlayer
#   模块基址），并用标准 il2cpp api 顺序索引（il2cpp_class_get_name=37 等）。
#
# 本脚本：
#   1. 解析 UnityPlayer.dll / GameAssembly.dll 的 PE 头（节表、ImageBase）；
#   2. 反汇编 GameAssembly.dll 导出 il2cpp_get_api_table 的前若干字节，
#      寻找 lea rax,[rip+disp32] 以定位 api table 的 VA（自验证）；
#      若失败，回退使用 honkai-dumper 硬编码 RVA（UnityPlayer + 0x1eed6a8）；
#   3. 读取指针数组（0..N），把每个 VA 归一到 (module, RVA, section, file_offset)；
#   4. 用已知索引映射命名，输出 CSV/JSON。

import argparse
import csv
import json
import struct
from pathlib import Path

# 来自 honkai-dumper src/il2cpp/functions.rs（global 4.4.x 时代）
API_INDEX_NAMES = {
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

DEFAULT_RVA_FALLBACK = 0x1EED6A8  # UnityPlayer.dll, honkai-dumper 硬编码
MAX_ENTRIES = 256


class Pe:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if self.data[:2] != b"MZ":
            raise ValueError(f"not a PE: {path}")
        e_lfanew = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            raise ValueError(f"bad PE signature: {path}")
        coff = self.data[e_lfanew + 4:e_lfanew + 24]
        self.num_sections = struct.unpack_from("<H", coff, 2)[0]
        opt_size = struct.unpack_from("<H", coff, 16)[0]
        opt_off = e_lfanew + 24
        opt = self.data[opt_off:opt_off + opt_size]
        magic = struct.unpack_from("<H", opt, 0)[0]
        if magic != 0x20B:
            raise ValueError(f"not PE32+: {path} (magic={magic:#x})")
        self.image_base = struct.unpack_from("<Q", opt, 24)[0]
        self.image_size = struct.unpack_from("<I", opt, 56)[0]
        dd_off = opt_off + 112
        self.export_rva, self.export_size = struct.unpack_from(
            "<II", self.data, dd_off
        )
        sec_off = opt_off + opt_size
        self.sections = []
        for i in range(self.num_sections):
            s = self.data[sec_off + i * 40: sec_off + (i + 1) * 40]
            name = s[:8].rstrip(b"\0").decode("latin1")
            vsize, vaddr, rsize, roff = struct.unpack_from("<IIII", s, 8)
            self.sections.append(
                {"name": name, "vsize": vsize, "vaddr": vaddr,
                 "rsize": rsize, "roff": roff}
            )

    def rva_to_off(self, rva: int) -> int | None:
        for s in self.sections:
            if s["vaddr"] <= rva < s["vaddr"] + max(s["vsize"], 0x1000):
                return s["roff"] + (rva - s["vaddr"])
        return None

    def read(self, rva: int, size: int) -> bytes | None:
        off = self.rva_to_off(rva)
        if off is None:
            return None
        return self.data[off:off + size]

    def exports(self) -> dict[str, int]:
        """name -> RVA"""
        off = self.rva_to_off(self.export_rva)
        if off is None:
            return {}
        ed = self.data[off:off + self.export_size]
        n_names = struct.unpack_from("<I", ed, 24)[0]
        addr_names = struct.unpack_from("<I", ed, 32)[0]
        addr_ordinals = struct.unpack_from("<I", ed, 36)[0]
        addr_funcs = struct.unpack_from("<I", ed, 28)[0]
        out = {}
        for i in range(n_names):
            name_rva = struct.unpack_from("<I", self.data, self.rva_to_off(addr_names) + i * 4)[0]
            ord_idx = struct.unpack_from("<H", self.data, self.rva_to_off(addr_ordinals) + i * 2)[0]
            fn_rva = struct.unpack_from("<I", self.data, self.rva_to_off(addr_funcs) + ord_idx * 4)[0]
            off = self.rva_to_off(name_rva)
            end = self.data.find(b"\0", off)
            out[self.data[off:end].decode("latin1")] = fn_rva
        return out


def find_lea_rip(data: bytes, start: int, limit: int = 64):
    """在导出函数起始处查找 lea reg,[rip+disp32]（48 8D 05/0D/15/1D/25/2D/35/3D xx xx xx xx）。"""
    for i in range(start, min(start + limit, len(data) - 7)):
        b = data[i]
        if b == 0x48 and data[i + 1] == 0x8D and data[i + 2] in (0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D):
            disp = struct.unpack_from("<i", data, i + 3)[0]
            return i + 7 + disp  # VA (image-relative)
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", required=True, type=Path, help="GameAssembly.dll")
    parser.add_argument("--unity", required=True, type=Path, help="UnityPlayer.dll")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-entries", type=int, default=MAX_ENTRIES)
    parser.add_argument("--fallback-rva", type=lambda v: int(v, 0), default=DEFAULT_RVA_FALLBACK)
    args = parser.parse_args()

    game = Pe(args.game)
    unity = Pe(args.unity)
    print(f"GameAssembly: image_base=0x{game.image_base:X} size=0x{game.image_size:X} sections={game.num_sections}")
    print(f"UnityPlayer:  image_base=0x{unity.image_base:X} size=0x{unity.image_size:X} sections={unity.num_sections}")

    # 1) 通过导出函数自验证表位置
    exps = game.exports()
    print(f"GameAssembly exports: {list(exps.keys())}")
    table_va = None
    getter_rva = exps.get("il2cpp_get_api_table")
    if getter_rva is not None:
        fn_bytes = game.read(getter_rva, 96)
        if fn_bytes:
            table_va = find_lea_rip(fn_bytes, 0)
            print(f"il2cpp_get_api_table @ RVA 0x{getter_rva:X} -> table VA hint 0x{table_va:X}" if table_va else
                  f"il2cpp_get_api_table @ RVA 0x{getter_rva:X} (no lea-rip found in first 96B)")
            # 解析 lea 到的地址属于哪个模块
            if table_va is not None:
                for mod, name in ((game, "GameAssembly"), (unity, "UnityPlayer")):
                    if mod.image_base <= table_va < mod.image_base + mod.image_size:
                        print(f"  table VA 0x{table_va:X} -> {name} RVA 0x{table_va - mod.image_base:X}")
                        table_rva = table_va - mod.image_base
                        table_mod = mod
                        break

    # 2) 若导出解析失败，回退 honkai-dumper 硬编码位置
    if table_va is None:
        table_rva = args.fallback_rva
        table_mod = unity
        print(f"fallback: UnityPlayer RVA 0x{table_rva:X} (honkai-dumper hardcoded)")

    # 3) 读取指针数组
    rows = []
    for idx in range(args.max_entries):
        ptr_bytes = table_mod.read(table_rva + idx * 8, 8)
        if ptr_bytes is None:
            break
        (ptr,) = struct.unpack("<Q", ptr_bytes)
        name = API_INDEX_NAMES.get(idx, "")
        if ptr == 0:
            rows.append({"index": idx, "name": name, "ptr": 0, "module": "", "rva": "",
                         "section": "", "file_offset": "", "in_image": False})
            continue
        target = None
        for mod, mname in ((game, "GameAssembly"), (unity, "UnityPlayer")):
            if mod.image_base <= ptr < mod.image_base + mod.image_size:
                target = (mod, mname)
                break
        if target is None:
            rows.append({"index": idx, "name": name, "ptr": f"0x{ptr:X}", "module": "OUTSIDE",
                         "rva": "", "section": "", "file_offset": "", "in_image": False})
            continue
        mod, mname = target
        rva = ptr - mod.image_base
        off = mod.rva_to_off(rva)
        sec = ""
        for s in mod.sections:
            if s["vaddr"] <= rva < s["vaddr"] + max(s["vsize"], 0x1000):
                sec = s["name"]
                break
        rows.append({"index": idx, "name": name, "ptr": f"0x{ptr:X}", "module": mname,
                     "rva": f"0x{rva:X}", "section": sec,
                     "file_offset": f"0x{off:X}" if off is not None else "",
                     "in_image": True})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    named = [r for r in rows if r["name"]]
    resolved = [r for r in named if r["in_image"]]
    print(f"rows: {len(rows)}  named: {len(named)}  named+resolved: {len(resolved)}")
    for r in named:
        print(f"  [{r['index']:3}] {r['name']:32s} -> {r['module']:12s} {r['rva']:12s} {r['section']}")
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
