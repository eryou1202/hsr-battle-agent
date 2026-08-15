# find_il2cpp_api_table.py
#
# 跨小版本 IL2CPP API Function Table 结构定位器（无硬编码 table offset）。
#
# 目标：
#   在 UnityPlayer.dll 的只读数据节中自动、唯一、高置信地定位
#   IL2CPP API function table（函数指针数组，每个元素 8 字节）。
#   table 位置随版本变化；本工具只依赖跨版本稳定的结构指纹，不依赖版本分支。
#
# 结构依据（4.4.54 实测，E2 级证据，详见 docs/reverse/il2cpp_api_table.md）：
#   1. table 位于 UnityPlayer 只读数据节（4.4.54 为 .rdata）。
#   2. 27 个 honkai-dumper 已知索引（标准 il2cpp api 顺序）必须全部指向
#      UnityPlayer 可执行节内的 wrapper stub。
#   3. wrapper stub 只有三类可识别 prologue（shape A/B/C）：
#        A: 45 33 C0 | 48 8D 0D <desc> | 33 D2 | E9 <dispatcher>
#           （xor r8d; lea rcx,[desc]; xor edx; jmp dispatcher）
#        B: 48 83 EC 38 | 45 33 C9 | 48 C7 44 24 20 00.. | 45 33 C0
#           | 48 8D 15 <stub> | 48 8D 0D <desc> | E8 <call>
#        C: 66 0F 6F ...（SIMD prologue，极少数槽位）
#   4. descriptor 位于 UnityPlayer 可写数据节；A/B descriptor 前 11 个 qword
#      包含可执行节指针（descriptor[5] / [2]）与相邻 descriptor 交叉链接，
#      可据此验证 descriptor 结构与 wrapper 的对应关系。
#   5. 双子对关系：slot 63/65 的 wrapper 相距 0x20 且同 shape A；
#      slot 10/12 的 wrapper 相距 0x40 且同 shape B；两对 descriptor 各距 0x58。
#   6. 组间距约束：class_*/domain_*/field_*/method_*/type_*/image_* 各自家族
#      的 wrapper 落在紧密簇内。
#
# 结构先验（非 offset，可被 --prior-json 覆盖）：
#   - EXPECTED_WRAPPER_SHAPES：27 个已知槽位各自的 wrapper shape。
#     这是 wrapper 生成器按 API 函数签名分类的结构指纹（E2），
#     与具体 RVA 无关；跨小版本默认假设稳定（版本原则），不匹配时降低置信度。
#   - EXPECTED_DESC_DELTAS：已知槽位 descriptor 地址相对首槽的间隔向量（E2）。
#     仅作为次权重加分，不参与候选淘汰。
#
# 边界：
#   - 本进程内 LoadLibrary 加载 UnityPlayer.dll，只读扫描，不调用任何函数、
#     不修改内存、不写文件（除可选的 --json 输出）。
#   - 不加载反作弊组件；不注入；不 hook。
#
# 用法：
#   python tools/reverse/scripts/find_il2cpp_api_table.py \
#       --unity <UnityPlayer.dll> [--game <GameAssembly.dll>]
#       [--expect-rva <KNOWN_TABLE_RVA>] [--json result.json] [--top 40]
#
# --expect-rva 仅用于验证 locator 是否正确；绝不参与候选生成或评分。

import argparse
import ctypes
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# honkai-dumper 已知 slot 索引（标准 il2cpp api 顺序，E2：跨版本 27/27 对齐）
# ---------------------------------------------------------------------------
KNOWN_SLOTS = [
    22, 31, 33, 35, 37, 39, 40, 43, 45, 49, 53,
    63, 65, 72, 73, 75, 76,
    116, 117, 123, 124,
    161, 162, 163,
    168, 169, 170,
]

KNOWN_SLOT_NAMES = {
    22: "assembly_get_image",
    31: "class_get_fields",
    33: "class_get_interfaces",
    35: "class_get_methods",
    37: "class_get_name",
    39: "class_get_namespace",
    40: "class_get_parent",
    43: "class_is_valuetype",
    45: "class_get_flags",
    49: "class_from_type",
    53: "class_is_enum",
    63: "domain_get",
    65: "domain_get_assemblies",
    72: "field_get_flags",
    73: "field_get_name",
    75: "field_get_offset",
    76: "field_get_type",
    116: "method_get_return_type",
    117: "method_get_name",
    123: "method_get_param_count",
    124: "method_get_param",
    161: "type_get_name",
    162: "type_is_byref",
    163: "type_get_attrs",
    168: "image_get_name",
    169: "image_get_class_count",
    170: "image_get_class",
}

# 结构先验：已知槽位 wrapper shape（E2，来自 4.4.54 结构指纹）。
# 这不是 offset，也不是版本分支；跨版本若 wrapper 代码生成不变则稳定。
EXPECTED_WRAPPER_SHAPES = {
    22: "B", 31: "A", 33: "A", 35: "A", 37: "A", 39: "A",
    40: "B", 43: "A", 45: "A", 49: "A", 53: "A",
    63: "A", 65: "A", 72: "B", 73: "A", 75: "A", 76: "B",
    116: "A", 117: "B", 123: "B", 124: "A",
    161: "B", 162: "A", 163: "B",
    168: "A", 169: "B", 170: "C",
}

# 结构先验：已知槽位 descriptor 地址相对 slot 22 的间隔（E2，次权重加分）。
EXPECTED_DESC_DELTAS = {
    22: 0x0, 31: 0x1A0, 33: 0x1F8, 35: 0x250, 37: 0x2A8, 39: 0x300,
    40: 0x318, 43: 0x3B0, 45: 0x408, 49: 0x4B8, 53: 0x568,
    63: 0x720, 65: 0x778, 72: 0x898, 73: 0x8D8, 75: 0x930, 76: 0x948,
    116: 0x10E8, 117: 0x1100, 123: 0x1208, 124: 0x1248,
    161: 0x18A8, 162: 0x18E8, 163: 0x1900,
    168: 0x19F0, 169: 0x1A08,
}

SENTINEL = 0xFFFFFFFFFFFFFFFF

# 判别组约束（家族内 wrapper 必须彼此接近；宽度为 4.4.54 实测值并留余量）
FAMILY_GROUPS = [
    ("domain_pair", [63, 65], 0x100),
    ("twin_pair", [10, 12], 0x100),
    ("image", [168, 169, 170], 0x800),
    ("method", [116, 117, 123, 124], 0x1000),
    ("type", [161, 162, 163], 0x1000),
    ("class", [31, 33, 35, 37, 39, 40, 43, 45, 49, 53], 0x4000),
]

FULL_SLOT_COUNT = 240  # 4.4.54 实测完整 table 长度；用于覆盖率评分

# 评分权重（合计 100）
W_SHAPE_PROFILE = 45.0
W_DESC_PROFILE = 20.0
W_TWIN = 15.0
W_WRAPPER_COVERAGE = 10.0
W_DESC_COVERAGE = 5.0
W_LINK_COVERAGE = 5.0


@dataclass
class PeSection:
    name: str
    rva: int
    vsize: int
    raw_size: int
    raw_offset: int
    characteristics: int

    @property
    def size(self) -> int:
        return max(self.vsize, self.raw_size, 0x1000)

    @property
    def is_executable(self) -> bool:
        return bool(self.characteristics & 0x20000000)

    @property
    def is_writable(self) -> bool:
        return bool(self.characteristics & 0x80000000)

    @property
    def is_readonly_data(self) -> bool:
        return bool(self.characteristics & 0x40000000) and not self.is_executable \
            and not self.is_writable


class PeImage:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if self.data[:2] != b"MZ":
            raise ValueError(f"not a PE file: {path}")
        e_lfanew = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            raise ValueError(f"bad PE signature: {path}")
        coff = self.data[e_lfanew + 4:e_lfanew + 24]
        num_sections = struct.unpack_from("<H", coff, 2)[0]
        opt_size = struct.unpack_from("<H", coff, 16)[0]
        opt_off = e_lfanew + 24
        magic = struct.unpack_from("<H", self.data, opt_off)[0]
        if magic != 0x20B:
            raise ValueError(f"not PE32+: {path}")
        self.image_base = struct.unpack_from("<Q", self.data, opt_off + 24)[0]
        sec_off = opt_off + opt_size
        self.sections: list[PeSection] = []
        for i in range(num_sections):
            s = self.data[sec_off + i * 40:sec_off + (i + 1) * 40]
            name = s[:8].rstrip(b"\0").decode("latin1")
            vsize, rva = struct.unpack_from("<II", s, 8)
            raw_size, raw_offset = struct.unpack_from("<II", s, 16)
            chars = struct.unpack_from("<I", s, 36)[0]
            self.sections.append(PeSection(name, rva, vsize, raw_size, raw_offset, chars))

    def section_at_rva(self, rva: int) -> PeSection | None:
        for s in self.sections:
            if s.rva <= rva < s.rva + s.size:
                return s
        return None

    def rva_to_file_offset(self, rva: int) -> int | None:
        s = self.section_at_rva(rva)
        if s is None:
            return None
        return s.raw_offset + (rva - s.rva)


class Locator:
    """UnityPlayer IL2CPP API table structural locator."""

    def __init__(self, unity_path: Path, prior: dict | None = None,
                 max_full_slots: int = FULL_SLOT_COUNT):
        self.unity_pe = PeImage(unity_path)
        self.unity_path = unity_path
        self.max_full_slots = max_full_slots
        self.expected_shapes = dict(EXPECTED_WRAPPER_SHAPES)
        self.expected_desc_deltas = dict(EXPECTED_DESC_DELTAS)
        if prior:
            if "wrapper_shapes" in prior:
                self.expected_shapes = {int(k): v for k, v in prior["wrapper_shapes"].items()}
            if "desc_deltas" in prior:
                self.expected_desc_deltas = {int(k): int(v) for k, v in prior["desc_deltas"].items()}
        self.unity = ctypes.CDLL(str(unity_path.resolve()))
        self.u_base = int(self.unity._handle)

    # -- memory helpers -----------------------------------------------------
    def read_mem(self, rva: int, size: int) -> bytes | None:
        try:
            return bytes((ctypes.c_char * size).from_address(self.u_base + rva))
        except Exception:
            return None

    def read_qword(self, rva: int) -> int | None:
        b = self.read_mem(rva, 8)
        return struct.unpack("<Q", b)[0] if b is not None else None

    def is_exec_rva(self, rva: int) -> bool:
        s = self.unity_pe.section_at_rva(rva)
        return s is not None and s.is_executable

    def is_data_rva(self, rva: int) -> bool:
        s = self.unity_pe.section_at_rva(rva)
        return s is not None and s.is_writable

    # -- wrapper / descriptor structure ------------------------------------
    def wrapper_probe(self, wrva: int) -> tuple[str | None, int | None]:
        """识别 wrapper prologue；返回 (shape, descriptor_rva)。

        A: 45 33 C0 | 48 8D 0D <desc> | 33 D2 | E9 <disp>
        B: 48 83 EC 38 | ... | 48 8D 15 <stub> | 48 8D 0D <desc> | E8 <disp>
        C: 66 0F 6F ...（SIMD，无 lea-rcx descriptor）
        """
        b = self.read_mem(wrva, 48)
        if b is None:
            return None, None
        if (len(b) >= 16 and b[:3] == b"\x45\x33\xc0" and b[3:6] == b"\x48\x8d\x0d"
                and b[10:12] == b"\x33\xd2" and b[12] == 0xE9):
            disp = struct.unpack_from("<i", b, 6)[0]
            return "A", wrva + 10 + disp
        if (len(b) >= 38 and b[:4] == b"\x48\x83\xec\x38" and b[4:7] == b"\x45\x33\xc9"
                and b[7:16] == b"\x48\xc7\x44\x24\x20\x00\x00\x00\x00"
                and b[16:19] == b"\x45\x33\xc0"
                and b[19:22] == b"\x48\x8d\x15" and b[26:29] == b"\x48\x8d\x0d"
                and b[33] == 0xE8):
            disp = struct.unpack_from("<i", b, 29)[0]
            return "B", wrva + 33 + disp
        if len(b) >= 4 and b[:3] == b"\x66\x0f\x6f":
            return "C", None
        return None, None

    def descriptor_probe(self, shape: str, desc_rva: int) -> dict[str, Any] | None:
        """校验 descriptor 前 11 个 qword 的结构指纹。

        A: q[1] == -1, q[5] 为可执行指针, q[8]/q[9] 为数据指针。
        B: q[2] 为可执行指针, q[5]/q[6] 为数据指针, q[9] 通常为 -1
           （家族边界槽位的 B descriptor 允许 q[9] != -1，如 slot 76/155/169/200/216）。
        soft：只要发现可执行指针与数据指针即视为结构成立。
        """
        if shape not in ("A", "B") or not self.is_data_rva(desc_rva):
            return None
        q = []
        for j in range(11):
            v = self.read_qword(desc_rva + j * 8)
            if v is None:
                return None
            q.append(v)
        any_code = any(self.is_exec_rva(v - self.u_base) for v in q)
        any_data = any(self.is_data_rva(v - self.u_base) for v in q)
        sentinel = q[1] == SENTINEL if shape == "A" else q[9] == SENTINEL
        strong = False
        if shape == "A":
            strong = (q[1] == SENTINEL
                      and self.is_exec_rva(q[5] - self.u_base)
                      and self.is_data_rva(q[8] - self.u_base)
                      and self.is_data_rva(q[9] - self.u_base))
        else:
            strong = (self.is_exec_rva(q[2] - self.u_base)
                      and self.is_data_rva(q[5] - self.u_base)
                      and self.is_data_rva(q[6] - self.u_base)
                      and q[9] == SENTINEL)
        return {"soft": any_code and any_data, "strong": strong,
                "sentinel": sentinel, "q": q}

    def descriptor_links(self, shape: str, desc_rva: int) -> dict[str, int | None]:
        """descriptor 内的相邻 descriptor 交叉链接（A: q8/q9, B: q5/q6）。"""
        out: dict[str, int | None] = {"prev": None, "next": None}
        if shape == "A":
            prev = self.read_qword(desc_rva + 8 * 8)
            nxt = self.read_qword(desc_rva + 9 * 8)
        elif shape == "B":
            prev = self.read_qword(desc_rva + 5 * 8)
            nxt = self.read_qword(desc_rva + 6 * 8)
        else:
            return out
        if prev is not None and self.is_data_rva(prev - self.u_base):
            out["prev"] = prev - self.u_base
        if nxt is not None and self.is_data_rva(nxt - self.u_base):
            out["next"] = nxt - self.u_base
        return out

    # -- candidate scanning ------------------------------------------------
    def _value_mask(self, values: np.ndarray, sections: list[PeSection]) -> np.ndarray:
        mask = np.zeros(values.shape, dtype=bool)
        for s in sections:
            mask |= (values >= s.rva) & (values < s.rva + s.size)
        return mask

    def collect_candidates(self) -> list[int]:
        """扫描只读数据节，返回通过硬性预筛的候选 table RVA。"""
        ro_sections = [s for s in self.unity_pe.sections if s.is_readonly_data]
        exec_sections = [s for s in self.unity_pe.sections if s.is_executable]
        candidates: list[int] = []
        for sec in ro_sections:
            if sec.vsize < (max(KNOWN_SLOTS) + 2) * 8:
                continue
            buf_size = sec.vsize - (sec.vsize % 8)
            try:
                arr = np.frombuffer(
                    (ctypes.c_char * buf_size).from_address(self.u_base + sec.rva),
                    dtype="<u8",
                )
            except Exception:
                continue
            n = len(arr)
            if n <= max(KNOWN_SLOTS) + 1:
                continue
            n_cand = n - max(KNOWN_SLOTS)
            arr_rva = arr - self.u_base
            exec_mask = self._value_mask(arr_rva, exec_sections)

            def shifted(k: int) -> np.ndarray:
                return arr[k:n_cand + k]

            # 硬性约束：slot 63/65 双子（代码指针，0 < delta <= 0x100）
            v63 = shifted(63)
            v65 = shifted(65)
            mask = exec_mask[63:n_cand + 63] & exec_mask[65:n_cand + 65]
            mask &= (v65 > v63) & (v65 - v63 <= 0x100)

            # 家族组间距约束（向量化）+ 组内全部为代码指针
            for _, idxs, span in FAMILY_GROUPS:
                vals = [shifted(k) for k in idxs]
                mask &= np.maximum.reduce(vals) - np.minimum.reduce(vals) <= span
                for v in vals:
                    mask &= self._value_mask(v - self.u_base, exec_sections)

            # 27 个已知槽位全部必须为代码指针（向量化）
            for k in KNOWN_SLOTS:
                mask &= self._value_mask(shifted(k) - self.u_base, exec_sections)

            for idx in np.flatnonzero(mask):
                candidates.append(sec.rva + int(idx) * 8)
        return candidates

    # -- scoring -----------------------------------------------------------
    def score_candidate(self, table_rva: int) -> dict[str, Any]:
        slots = []
        for i in range(self.max_full_slots):
            v = self.read_qword(table_rva + i * 8)
            slots.append((v - self.u_base) if v is not None else None)

        shapes: dict[int, str] = {}
        descs: dict[int, int] = {}
        shape_count = 0
        desc_soft_count = 0
        desc_strong_count = 0
        for i, wrva in enumerate(slots):
            if wrva is None or not self.is_exec_rva(wrva):
                continue
            shape, desc = self.wrapper_probe(wrva)
            if shape is None:
                continue
            shape_count += 1
            shapes[i] = shape
            if desc is not None:
                res = self.descriptor_probe(shape, desc)
                if res is not None:
                    descs[i] = desc
                    if res["soft"]:
                        desc_soft_count += 1
                    if res["strong"]:
                        desc_strong_count += 1

        # descriptor 交叉链接验证（全 240 槽）
        link_ok = 0
        link_checked = 0
        for i, shape in shapes.items():
            if shape not in ("A", "B") or i not in descs:
                continue
            links = self.descriptor_links(shape, descs[i])
            if shape == "A":
                neighbors = ((i - 1, "prev"), (i + 1, "next"))
            else:
                neighbors = ((i - 2, "prev"), (i + 2, "next"))
            for target_idx, key in neighbors:
                if target_idx < 0 or target_idx not in descs:
                    continue
                link_checked += 1
                if links.get(key) == descs[target_idx]:
                    link_ok += 1

        # 27 个已知槽位
        known_descs = {}
        known_matched = 0
        known_shape_ok = 0
        known_unique = len({slots[k] for k in KNOWN_SLOTS if slots[k] is not None})
        known_align20 = 0
        profile_matches = 0
        for k in KNOWN_SLOTS:
            wrva = slots[k]
            if wrva is None or not self.is_exec_rva(wrva):
                continue
            if (wrva & 0x1F) == 0:
                known_align20 += 1
            shape, desc = self.wrapper_probe(wrva)
            if shape is not None:
                known_shape_ok += 1
            if shape == self.expected_shapes.get(k):
                profile_matches += 1
            desc_valid = False
            if desc is not None:
                res = self.descriptor_probe(shape, desc) if shape in ("A", "B") else None
                if res is not None:
                    known_descs[k] = desc
                    desc_valid = res["soft"]
            if shape is not None and (shape == "C" or desc_valid):
                known_matched += 1

        desc_profile_matches = 0
        if known_descs:
            first_desc = known_descs.get(22)
            if first_desc is not None:
                for k, delta in self.expected_desc_deltas.items():
                    if k in known_descs and known_descs[k] - first_desc == delta:
                        desc_profile_matches += 1
            else:
                ref_key, ref_desc = min(known_descs.items())
                expected_ref = self.expected_desc_deltas.get(ref_key)
                if expected_ref is not None:
                    for k, delta in self.expected_desc_deltas.items():
                        if k in known_descs:
                            actual = known_descs[k] - ref_desc
                            want = delta - expected_ref
                            if actual == want:
                                desc_profile_matches += 1

        # 双子对与组间距
        twin_checks = 0
        if shapes.get(63) == "A" and shapes.get(65) == "A":
            if slots[65] is not None and slots[63] is not None \
                    and slots[65] - slots[63] == 0x20 \
                    and descs.get(65, 0) - descs.get(63, 0) == 0x58:
                twin_checks += 1
        if shapes.get(10) == "B" and shapes.get(12) == "B":
            if slots[12] is not None and slots[10] is not None \
                    and slots[12] - slots[10] == 0x40 \
                    and descs.get(12, 0) - descs.get(10, 0) == 0x58:
                twin_checks += 1
        if 10 in descs and 63 in descs and descs[63] - descs[10] == 0x930:
            twin_checks += 1

        group_ok = 0
        group_total = len(FAMILY_GROUPS)
        for _, idxs, span in FAMILY_GROUPS:
            vals = [slots[k] for k in idxs if slots[k] is not None]
            if len(vals) == len(idxs) and max(vals) - min(vals) <= span:
                group_ok += 1

        failed = []
        if profile_matches < len(KNOWN_SLOTS):
            failed.append(f"known_slot_shape_profile={profile_matches}/{len(KNOWN_SLOTS)}")
        if desc_profile_matches < len(self.expected_desc_deltas):
            failed.append(f"known_slot_desc_spacing_profile={desc_profile_matches}/{len(self.expected_desc_deltas)}")
        if twin_checks < 3:
            failed.append(f"twin_pair_relations={twin_checks}/3")
        if group_ok < group_total:
            failed.append(f"family_group_spacing={group_ok}/{group_total}")
        if known_unique < len(KNOWN_SLOTS):
            failed.append(f"known_slot_unique={known_unique}/{len(KNOWN_SLOTS)}")
        if known_align20 < len(KNOWN_SLOTS):
            failed.append(f"known_slot_align20={known_align20}/{len(KNOWN_SLOTS)}")
        if shape_count < int(self.max_full_slots * 0.9):
            failed.append(f"wrapper_coverage={shape_count}/{self.max_full_slots}")
        if desc_soft_count < int((self.max_full_slots - 3) * 0.9):
            failed.append(f"descriptor_coverage={desc_soft_count}/{self.max_full_slots}")

        link_rate = link_ok / link_checked if link_checked else 0.0
        score = (
            W_SHAPE_PROFILE * profile_matches / len(KNOWN_SLOTS)
            + W_DESC_PROFILE * desc_profile_matches / max(1, len(self.expected_desc_deltas))
            + W_TWIN * twin_checks / 3.0
            + W_WRAPPER_COVERAGE * shape_count / self.max_full_slots
            + W_DESC_COVERAGE * desc_soft_count / self.max_full_slots
            + W_LINK_COVERAGE * link_rate
        )

        return {
            "table_rva": table_rva,
            "score": round(score, 2),
            "known_slots_matched": known_matched,
            "known_shape_profile_matches": profile_matches,
            "known_desc_profile_matches": desc_profile_matches,
            "known_shape_ok": known_shape_ok,
            "known_unique": known_unique,
            "known_align20": known_align20,
            "known_descs": {k: descs[k] for k in sorted(descs) if k in KNOWN_SLOTS},
            "wrapper_matches": shape_count,
            "descriptor_matches": desc_soft_count,
            "descriptor_strong": desc_strong_count,
            "link_ok": link_ok,
            "link_checked": link_checked,
            "twin_relations": twin_checks,
            "family_group_ok": group_ok,
            "failed_constraints": failed,
        }

    # -- entry -------------------------------------------------------------
    def locate(self, top_n: int = 40) -> dict[str, Any]:
        candidates = self.collect_candidates()
        if not candidates:
            return {"best_candidate": None, "runner_up": None, "score": 0.0,
                    "known_slots_matched": 0, "wrapper_matches": 0,
                    "descriptor_matches": 0, "failed_constraints": ["no candidates"],
                    "confidence": "none", "candidates": 0}

        # 对所有通过硬性预筛的候选做全量结构评分（4.4.54：958 候选 < 1s）
        scored = []
        for rva in candidates:
            res = self.score_candidate(rva)
            scored.append(res)
        scored.sort(key=lambda r: (
            r["known_shape_profile_matches"],
            r["known_desc_profile_matches"],
            r["twin_relations"],
            r["known_slots_matched"],
            r["known_shape_ok"],
            r["known_unique"],
            r["known_align20"],
            r["score"],
        ), reverse=True)
        top = scored[:top_n]

        best = top[0] if top else None
        runner_up = top[1] if len(top) > 1 else None
        confidence = "low"
        if best is not None:
            full = best
            if (full["known_shape_profile_matches"] == len(KNOWN_SLOTS)
                    and full["twin_relations"] == 3
                    and runner_up is not None
                    and full["score"] >= runner_up["score"] + 1.0):
                confidence = "high"
            elif (full["known_shape_profile_matches"] >= 24
                  and (runner_up is None or full["score"] > runner_up["score"])):
                confidence = "medium"

        best_rva = best["table_rva"] if best else None
        return {
            "best_candidate": {
                "module": self.unity_path.name,
                "rva": f"0x{best_rva:X}" if best_rva is not None else None,
                "va": f"0x{self.u_base + best_rva:X}" if best_rva is not None else None,
                "file_offset": (
                    f"0x{self.unity_pe.rva_to_file_offset(best_rva):X}"
                    if best_rva is not None
                    and self.unity_pe.rva_to_file_offset(best_rva) is not None else None
                ),
                "section": (
                    self.unity_pe.section_at_rva(best_rva).name
                    if best_rva is not None and self.unity_pe.section_at_rva(best_rva) else None
                ),
                **({k: v for k, v in best.items() if k != "table_rva"} if best else {}),
            } if best else None,
            "runner_up": {
                "module": self.unity_path.name,
                "rva": f"0x{runner_up['table_rva']:X}",
                "score": runner_up["score"],
                "known_shape_profile_matches": runner_up["known_shape_profile_matches"],
                "known_desc_profile_matches": runner_up["known_desc_profile_matches"],
                "failed_constraints": runner_up["failed_constraints"],
            } if runner_up else None,
            "score": best["score"] if best else 0.0,
            "known_slots_matched": best["known_slots_matched"] if best else 0,
            "wrapper_matches": best["wrapper_matches"] if best else 0,
            "descriptor_matches": best["descriptor_matches"] if best else 0,
            "failed_constraints": best["failed_constraints"] if best else ["no candidates"],
            "confidence": confidence,
            "candidates_scanned": len(candidates),
            "candidates_scored": len(scored),
            "top_candidates": [
                {
                    "rva": f"0x{r['table_rva']:X}",
                    "score": r["score"],
                    "known_shape_profile_matches": r["known_shape_profile_matches"],
                    "known_desc_profile_matches": r["known_desc_profile_matches"],
                    "twin_relations": r["twin_relations"],
                    "wrapper_matches": r["wrapper_matches"],
                    "descriptor_matches": r["descriptor_matches"],
                }
                for r in top[:10]
            ],
        }


def _load_prior(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="IL2CPP API table structural locator")
    parser.add_argument("--unity", required=True, type=Path, help="UnityPlayer.dll")
    parser.add_argument("--game", type=Path, help="GameAssembly.dll（可选；本版本定位不需要，保留接口）")
    parser.add_argument("--expect-rva", type=lambda v: int(v, 0), default=None,
                        help="仅验证用：已知正确 table RVA；不参与定位")
    parser.add_argument("--prior-json", type=Path, default=None,
                        help="覆盖结构先验的 JSON（wrapper_shapes / desc_deltas）")
    parser.add_argument("--json", type=Path, default=None, help="结果 JSON 输出路径")
    parser.add_argument("--top", type=int, default=40, help="best/runner_up 选择前 N 个已评分候选")
    parser.add_argument("--max-slots", type=int, default=FULL_SLOT_COUNT,
                        help="全量 wrapper 覆盖率评分使用的槽位数量")
    args = parser.parse_args()

    prior = _load_prior(args.prior_json) if args.prior_json else None
    locator = Locator(args.unity, prior=prior, max_full_slots=args.max_slots)
    result = locator.locate(top_n=args.top)

    print(f"UnityPlayer: {args.unity}  base=0x{locator.u_base:X}")
    print(f"candidates scanned: {result['candidates_scanned']}")
    print(f"confidence: {result['confidence']}")
    print(f"score: {result['score']}")
    if result["best_candidate"]:
        b = result["best_candidate"]
        print(f"\nbest_candidate: module={b['module']} rva={b['rva']} va={b['va']} "
              f"file_offset={b['file_offset']} section={b['section']}")
        print(f"  known_slots_matched: {result['known_slots_matched']}/{len(KNOWN_SLOTS)}")
        print(f"  wrapper_matches:     {result['wrapper_matches']}/{args.max_slots}")
        print(f"  descriptor_matches:  {result['descriptor_matches']}/{args.max_slots}")
        print(f"  known shape profile: {b['known_shape_profile_matches']}/{len(KNOWN_SLOTS)}")
        print(f"  known desc spacing:  {b['known_desc_profile_matches']}/{len(EXPECTED_DESC_DELTAS)}")
        print(f"  twin relations:      {b['twin_relations']}/3")
        print(f"  descriptor links:    {b['link_ok']}/{b['link_checked']}")
        print(f"  failed_constraints:  {result['failed_constraints']}")
        if args.expect_rva is not None:
            ok = best_rva_matches = (int(b["rva"], 16) == args.expect_rva)
            print(f"\nVALIDATION (expect-rva only, not used as input): "
                  f"expected=0x{args.expect_rva:X} actual={b['rva']} -> "
                  f"{'MATCH' if ok else 'MISMATCH'}")
            result["expect_rva_matches"] = ok
    if result["runner_up"]:
        r = result["runner_up"]
        print(f"\nrunner_up: rva={r['rva']} score={r['score']} "
              f"shape={r['known_shape_profile_matches']} desc={r['known_desc_profile_matches']} "
              f"failed={r['failed_constraints']}")
    print(f"\ntop candidates:")
    for r in result["top_candidates"]:
        print(f"  {r['rva']}  score={r['score']}  shape={r['known_shape_profile_matches']} "
              f"desc={r['known_desc_profile_matches']}  twin={r['twin_relations']}  "
              f"wrapper={r['wrapper_matches']}  descriptor={r['descriptor_matches']}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\njson: {args.json}")


if __name__ == "__main__":
    main()
