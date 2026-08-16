from __future__ import annotations

import argparse
import csv
import mmap
from pathlib import Path


def parse_number(value: str) -> int:
    return int(value, 0)


def decode_uleb128(
    data: mmap.mmap,
    offset: int,
    limit: int,
    max_bytes: int = 5,
) -> tuple[int, int] | None:
    value = 0
    shift = 0

    for index in range(max_bytes):
        position = offset + index

        if position >= limit:
            return None

        byte = data[position]
        value |= (byte & 0x7F) << shift

        if byte & 0x80 == 0:
            return value, index + 1

        shift += 7

    return None


def encode_uleb128(value: int) -> bytes:
    result = bytearray()

    while True:
        byte = value & 0x7F
        value >>= 7

        if value:
            result.append(byte | 0x80)
        else:
            result.append(byte)
            return bytes(result)


def is_printable_ascii(raw: bytes) -> bool:
    if not raw:
        return False

    return all(
        0x20 <= byte <= 0x7E
        for byte in raw
    )


def classify(value: str) -> str:
    if (
        "/" in value
        or value.endswith(
            (
                ".prefab",
                ".playable",
                ".png",
                ".json",
                ".asset",
            )
        )
    ):
        return "resource"

    if value.startswith("MDF_"):
        return "dynamic_field"

    if value.startswith(
        (
            "Avatar_",
            "MAvatar_",
            "M_",
            "TAvatar_",
            "StageAbility_",
            "BattleEvent_",
        )
    ):
        return "mechanic_symbol"

    if value in {
        "Caster",
        "AbilityTargetEntity",
        "AbilityTargetAdjoinEntity",
        "ModifierOwnerEntity",
        "ParamEntity",
        "AllLightTeam",
        "AllDarkTeam",
    }:
        return "entity_selector"

    return "other"


def hex_bytes(raw: bytes) -> str:
    return " ".join(
        f"{byte:02X}"
        for byte in raw
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--start",
        required=True,
        type=parse_number,
    )
    parser.add_argument(
        "--end",
        required=True,
        type=parse_number,
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=512,
    )

    args = parser.parse_args()

    if not args.input.is_file():
        raise FileNotFoundError(args.input)

    file_size = args.input.stat().st_size

    start = max(0, args.start)
    end = min(file_size, args.end)

    if start >= end:
        raise ValueError(
            f"无效范围：0x{start:X} - 0x{end:X}"
        )

    rows: list[dict[str, object]] = []

    with args.input.open("rb") as file:
        with mmap.mmap(
            file.fileno(),
            0,
            access=mmap.ACCESS_READ,
        ) as data:
            for prefix_offset in range(start, end):
                decoded = decode_uleb128(
                    data,
                    prefix_offset,
                    end,
                )

                if decoded is None:
                    continue

                length, prefix_size = decoded

                if not (
                    args.min_length
                    <= length
                    <= args.max_length
                ):
                    continue

                prefix = bytes(
                    data[
                        prefix_offset:
                        prefix_offset + prefix_size
                    ]
                )

                # 排除非规范的冗余 VLQ 编码。
                if prefix != encode_uleb128(length):
                    continue

                string_offset = (
                    prefix_offset + prefix_size
                )
                string_end = string_offset + length

                if string_end > end:
                    continue

                raw = bytes(
                    data[string_offset:string_end]
                )

                if not is_printable_ascii(raw):
                    continue

                try:
                    value = raw.decode("ascii")
                except UnicodeDecodeError:
                    continue

                if not any(
                    character.isalpha()
                    for character in value
                ):
                    continue

                before_start = max(
                    start,
                    prefix_offset - 32,
                )
                after_end = min(
                    end,
                    string_end + 32,
                )

                rows.append(
                    {
                        "category": classify(value),
                        "prefix_offset_decimal": (
                            prefix_offset
                        ),
                        "prefix_offset_hex": (
                            f"0x{prefix_offset:X}"
                        ),
                        "string_offset_decimal": (
                            string_offset
                        ),
                        "string_offset_hex": (
                            f"0x{string_offset:X}"
                        ),
                        "prefix_size": prefix_size,
                        "prefix_hex": hex_bytes(prefix),
                        "length": length,
                        "string_end_hex": (
                            f"0x{string_end:X}"
                        ),
                        "before_hex": hex_bytes(
                            bytes(
                                data[
                                    before_start:
                                    prefix_offset
                                ]
                            )
                        ),
                        "after_hex": hex_bytes(
                            bytes(
                                data[
                                    string_end:
                                    after_end
                                ]
                            )
                        ),
                        "value": value,
                    }
                )

    rows.sort(
        key=lambda row: int(
            row["prefix_offset_decimal"]
        )
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.output.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "category",
                "prefix_offset_decimal",
                "prefix_offset_hex",
                "string_offset_decimal",
                "string_offset_hex",
                "prefix_size",
                "prefix_hex",
                "length",
                "string_end_hex",
                "before_hex",
                "after_hex",
                "value",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    print(
        f"扫描范围：0x{start:X} - 0x{end:X}"
    )
    print(f"候选字符串：{len(rows)}")
    print(f"报告位置：{args.output}")


if __name__ == "__main__":
    main()