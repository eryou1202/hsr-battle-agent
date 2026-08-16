from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_uleb128(
    data: bytes,
    offset: int,
    max_bytes: int = 10,
) -> tuple[int, int]:
    value = 0
    shift = 0

    for index in range(max_bytes):
        position = offset + index

        if position >= len(data):
            raise EOFError(
                f"ULEB128 越界：0x{offset:X}"
            )

        byte = data[position]
        value |= (byte & 0x7F) << shift

        if byte & 0x80 == 0:
            return value, index + 1

        shift += 7

    raise ValueError(
        f"ULEB128 过长：0x{offset:X}"
    )


def read_string(
    data: bytes,
    offset: int,
) -> tuple[str, int, int, int]:
    length, prefix_size = read_uleb128(
        data,
        offset,
    )

    string_start = offset + prefix_size
    string_end = string_start + length

    if string_end > len(data):
        raise EOFError(
            "字符串超出记录范围："
            f"offset=0x{offset:X}, "
            f"length={length}"
        )

    raw = data[string_start:string_end]

    value = raw.decode("utf-8")

    return (
        value,
        string_end,
        length,
        prefix_size,
    )


def read_value(
    data: bytes,
    offset: int,
) -> tuple[int, int]:
    value, size = read_uleb128(
        data,
        offset,
    )

    return value, offset + size


def hex_bytes(data: bytes) -> str:
    return " ".join(
        f"{byte:02X}"
        for byte in data
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--headers-csv",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--output-csv",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--output-json",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    if not args.headers_csv.is_file():
        raise FileNotFoundError(
            args.headers_csv
        )

    with args.headers_csv.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        header_rows = list(
            csv.DictReader(file)
        )

    type2_rows = [
        row
        for row in header_rows
        if row.get("first_mixin_type") == "2"
    ]

    if not type2_rows:
        raise RuntimeError(
            "没有找到 Mixin Type 2 记录。"
        )

    output_rows: list[dict[str, object]] = []

    for row in type2_rows:
        record_path = Path(
            row["record_file"]
        )

        if not record_path.is_file():
            raise FileNotFoundError(
                record_path
            )

        data = record_path.read_bytes()

        offset = int(
            row["mixin_data_offset"]
        )

        mixin_start = offset

        mixin_flags, offset = read_value(
            data,
            offset,
        )

        opcode_a, offset = read_value(
            data,
            offset,
        )

        opcode_b, offset = read_value(
            data,
            offset,
        )

        selector_tag, offset = read_value(
            data,
            offset,
        )

        selector_mode, offset = read_value(
            data,
            offset,
        )

        (
            selector,
            offset,
            selector_length,
            selector_prefix_size,
        ) = read_string(
            data,
            offset,
        )

        name_field_tag, offset = read_value(
            data,
            offset,
        )

        (
            referenced_name,
            offset,
            referenced_name_length,
            referenced_name_prefix_size,
        ) = read_string(
            data,
            offset,
        )

        expected_prefix = (
            opcode_a == 0x31
            and opcode_b == 0x0A
            and selector_tag == 0x0C
            and selector_mode == 0x01
            and selector == "Caster"
            and name_field_tag == 0x04
        )

        output_rows.append(
            {
                "parsed_name": row["parsed_name"],
                "record_length": len(data),
                "mixin_start_decimal": mixin_start,
                "mixin_start_hex": (
                    f"0x{mixin_start:X}"
                ),
                "mixin_flags": mixin_flags,
                "mixin_flags_hex": (
                    f"0x{mixin_flags:X}"
                ),
                "opcode_a": opcode_a,
                "opcode_a_hex": (
                    f"0x{opcode_a:X}"
                ),
                "opcode_b": opcode_b,
                "opcode_b_hex": (
                    f"0x{opcode_b:X}"
                ),
                "selector_tag": selector_tag,
                "selector_tag_hex": (
                    f"0x{selector_tag:X}"
                ),
                "selector_mode": selector_mode,
                "selector_mode_hex": (
                    f"0x{selector_mode:X}"
                ),
                "selector": selector,
                "selector_length": selector_length,
                "selector_prefix_size": (
                    selector_prefix_size
                ),
                "name_field_tag": (
                    name_field_tag
                ),
                "name_field_tag_hex": (
                    f"0x{name_field_tag:X}"
                ),
                "referenced_name": (
                    referenced_name
                ),
                "referenced_name_length": (
                    referenced_name_length
                ),
                "referenced_name_prefix_size": (
                    referenced_name_prefix_size
                ),
                "parsed_prefix_end_decimal": (
                    offset
                ),
                "parsed_prefix_end_hex": (
                    f"0x{offset:X}"
                ),
                "parsed_prefix_length": (
                    offset - mixin_start
                ),
                "prefix_matches_common_pattern": (
                    expected_prefix
                ),
                "remaining_length": (
                    len(data) - offset
                ),
                "remaining_preview_hex": (
                    hex_bytes(
                        data[
                            offset:
                            min(
                                offset + 64,
                                len(data),
                            )
                        ]
                    )
                ),
                "record_file": str(record_path),
            }
        )

    args.output_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.output_csv.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(
                output_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(output_rows)

    args.output_json.write_text(
        json.dumps(
            output_rows,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"{'Ability':46} "
        f"{'Flags':>7} "
        f"{'Opcode':>8} "
        f"{'Selector':>10} "
        f"{'Referenced name':42} "
        f"{'OK':>5}"
    )

    for item in output_rows:
        print(
            f"{str(item['parsed_name']):46} "
            f"{str(item['mixin_flags_hex']):>7} "
            f"{str(item['opcode_a_hex']):>8} "
            f"{str(item['selector']):>10} "
            f"{str(item['referenced_name']):42} "
            f"{str(item['prefix_matches_common_pattern']):>5}"
        )

    print()
    print(
        f"Type 2 记录数量：{len(output_rows)}"
    )
    print(
        f"CSV：{args.output_csv}"
    )
    print(
        f"JSON：{args.output_json}"
    )


if __name__ == "__main__":
    main()