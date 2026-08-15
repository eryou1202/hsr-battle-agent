#!/usr/bin/env python3
"""Generate the C++ locator-prior header from the canonical Python locator.

This keeps the C++ runtime probe and tools/reverse/scripts/find_il2cpp_api_table.py
in sync: KNOWN_SLOTS / KNOWN_SLOT_NAMES / EXPECTED_WRAPPER_SHAPES /
EXPECTED_DESC_DELTAS / FAMILY_GROUPS / scoring weights are imported from the
Python module and serialised as C++ constexpr data.

Boundary: importing find_il2cpp_api_table does NOT load UnityPlayer.dll
(LoadLibrary only happens inside Locator.__init__), so this generator is a
pure offline operation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PY_LOCATOR_DIR = REPO / "tools" / "reverse" / "scripts"
sys.path.insert(0, str(PY_LOCATOR_DIR))

import find_il2cpp_api_table as locator_mod  # noqa: E402


def _cpp_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _cpp_char(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def generate() -> str:
    known_slots = list(locator_mod.KNOWN_SLOTS)
    known_names = dict(locator_mod.KNOWN_SLOT_NAMES)
    expected_shapes = dict(locator_mod.EXPECTED_WRAPPER_SHAPES)
    expected_deltas = dict(locator_mod.EXPECTED_DESC_DELTAS)
    family_groups = list(locator_mod.FAMILY_GROUPS)

    lines: list[str] = []
    add = lines.append
    add("// locator_prior.h")
    add("//")
    add("// GENERATED FILE - DO NOT EDIT BY HAND.")
    add("// Regenerate with:")
    add("//   python tools/runtime_probe/scripts/gen_locator_prior.py")
    add("//")
    add("// The values below are structural priors (slot indices, wrapper shape")
    add("// profiles, relative descriptor-spacing fingerprints and scoring weights)")
    add("// imported from tools/reverse/scripts/find_il2cpp_api_table.py.")
    add("// They are NOT version branches and contain NO api-table offsets.")
    add("")
    add("#pragma once")
    add("")
    add("#include <array>")
    add("#include <cstdint>")
    add("")
    add("namespace hsr_probe {")
    add("namespace locator_prior {")
    add("")

    add("inline constexpr int kKnownSlots[] = {")
    add("    " + ", ".join(str(v) for v in known_slots) + ",")
    add("};")
    add("inline constexpr int kKnownSlotCount = "
        f"{len(known_slots)};")
    add("")
    add("struct KnownSlot {")
    add("    int index;")
    add("    const char* name;")
    add("    char shape;")
    add("};")
    add("inline constexpr KnownSlot kKnownSlotsDetailed[] = {")
    for slot in known_slots:
        shape = expected_shapes[slot]
        add(f"    {{{slot}, {_cpp_string(known_names[slot])}, "
            f"{_cpp_char(shape)}}},")
    add("};")
    add("")
    add("inline constexpr int kExpectedDescDeltaKeys[] = {")
    add("    " + ", ".join(str(v) for v in expected_deltas.keys()) + ",")
    add("};")
    add("inline constexpr int kExpectedDescDeltaValues[] = {")
    add("    " + ", ".join(f"0x{v:X}" for v in expected_deltas.values()) + ",")
    add("};")
    add("inline constexpr int kExpectedDescDeltaCount = "
        f"{len(expected_deltas)};")
    add("")
    add("struct FamilyGroup {")
    add("    const char* name;")
    add("    int span;")
    add("    int count;")
    add("    std::array<int, 10> indices;")
    add("};")
    add("inline constexpr FamilyGroup kFamilyGroups[] = {")
    for name, indices, span in family_groups:
        padded = list(indices) + [0] * (10 - len(indices))
        add(f"    {{{_cpp_string(name)}, 0x{span:X}, {len(indices)}, "
            f"{{{', '.join(str(v) for v in padded)}}}}},")
    add("};")
    add("inline constexpr int kFamilyGroupCount = "
        f"{len(family_groups)};")
    add("")
    add("inline constexpr int kMaxKnownSlot = "
        f"{max(known_slots)};")
    add("inline constexpr int kFullSlotCount = "
        f"{locator_mod.FULL_SLOT_COUNT};")
    add("inline constexpr std::uint64_t kSentinel = "
        f"0x{locator_mod.SENTINEL:X}ULL;")
    add("")
    add("inline constexpr double kWShapeProfile = "
        f"{locator_mod.W_SHAPE_PROFILE};")
    add("inline constexpr double kWDescProfile = "
        f"{locator_mod.W_DESC_PROFILE};")
    add("inline constexpr double kWTwin = "
        f"{locator_mod.W_TWIN};")
    add("inline constexpr double kWWrapperCoverage = "
        f"{locator_mod.W_WRAPPER_COVERAGE};")
    add("inline constexpr double kWDescCoverage = "
        f"{locator_mod.W_DESC_COVERAGE};")
    add("inline constexpr double kWLinkCoverage = "
        f"{locator_mod.W_LINK_COVERAGE};")
    add("")
    add("}  // namespace locator_prior")
    add("}  // namespace hsr_probe")
    add("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO / "tools" / "runtime_probe" / "gen" / "locator_prior.h",
        help="output header path (default: tools/runtime_probe/gen/locator_prior.h)",
    )
    args = parser.parse_args()

    content = generate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists() and args.out.read_text(encoding="utf-8") == content:
        print(f"locator prior already up to date: {args.out}")
        return 0
    args.out.write_text(content, encoding="utf-8")
    print(f"wrote locator prior header: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
