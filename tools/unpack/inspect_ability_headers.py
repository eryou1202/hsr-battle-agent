from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ABILITY_FIELDS = {
    0: "ability_name",
    1: "ability_mixins",
    2: "field_2_unknown",
    3: "field_3_unknown",
    4: "field_4_probable_default_modifier",
    5: "field_5_unknown",
    6: "field_6_unknown",
    7: "field_7_unknown",
    8: "field_8_unknown",
    9: "field_9_unknown",
    10: "field_10_unknown",
    11: "field_11_unknown",
    12: "field_12_unknown",
    13: "field_13_unknown",
    14: "field_14_unknown",
    15: "field_15_unknown",
    16: "field_16_unknown",
    17: "field_17_unknown",
    18: "field_18_unknown",
    19: "field_19_unknown",
    20: "field_20_unknown",
    21: "field_21_unknown",
}


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
) -> tuple[str, int, int]:
    length, prefix_size = read_uleb128(
        data,
        offset,
    )

    string_start = offset + prefix_size
    string_end = string_start + length

    if string_end > len(data):
        raise EOFError(
            "字符串超出记录边界："
            f"offset=0x{offset:X}, "
            f"length={length}"
        )

    value = data[
        string_start:string_end
    ].decode("utf-8")

    return value, string_end, length


def enabled_fields(bit_field: int) -> list[str]:
    result: list[str] = []

    for bit, name in ABILITY_FIELDS.items():
        if bit_field & (1 << bit):
            result.append(name)

    return result


def hex_bytes(data: bytes) -> str:
    return " ".join(
        f"{byte:02X}"
        for byte in data
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--manifest",
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

    if not args.manifest.is_file():
        raise FileNotFoundError(
            args.manifest
        )

    with args.manifest.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        manifest_rows = list(
            csv.DictReader(file)
        )

    output_rows: list[dict[str, object]] = []

    for manifest_row in manifest_rows:
        record_path = Path(
            manifest_row["output_file"]
        )

        if not record_path.is_file():
            raise FileNotFoundError(
                record_path
            )

        data = record_path.read_bytes()
        offset = 0

        wrapper_type_code, size = read_uleb128(
            data,
            offset,
        )
        offset += size

        ability_bit_field, size = read_uleb128(
            data,
            offset,
        )
        offset += size

        fields = enabled_fields(
            ability_bit_field
        )

        ability_name = ""
        name_length = 0

        if "ability_name" in fields:
            (
                ability_name,
                offset,
                name_length,
            ) = read_string(
                data,
                offset,
            )

        mixin_count: int | str = ""
        first_mixin_type: int | str = ""
        mixin_data_offset: int | str = ""

        if "ability_mixins" in fields:
            mixin_count, size = read_uleb128(
                data,
                offset,
            )
            offset += size

            if mixin_count > 0:
                first_mixin_type, size = (
                    read_uleb128(
                        data,
                        offset,
                    )
                )
                offset += size
                mixin_data_offset = offset

        expected_name = manifest_row["name"]

        output_rows.append(
            {
                "index": manifest_row["index"],
                "expected_name": expected_name,
                "parsed_name": ability_name,
                "name_matches": (
                    ability_name == expected_name
                ),
                "record_length": len(data),
                "wrapper_type_code": (
                    wrapper_type_code
                ),
                "wrapper_type_hex": (
                    f"0x{wrapper_type_code:X}"
                ),
                "ability_bit_field": (
                    ability_bit_field
                ),
                "ability_bit_field_hex": (
                    f"0x{ability_bit_field:X}"
                ),
                "enabled_fields": ",".join(
                    fields
                ),
                "name_length": name_length,
                "mixin_count": mixin_count,
                "first_mixin_type": (
                    first_mixin_type
                ),
                "first_mixin_type_hex": (
                    f"0x{first_mixin_type:X}"
                    if isinstance(
                        first_mixin_type,
                        int,
                    )
                    else ""
                ),
                "mixin_data_offset": (
                    mixin_data_offset
                ),
                "mixin_data_offset_hex": (
                    f"0x{mixin_data_offset:X}"
                    if isinstance(
                        mixin_data_offset,
                        int,
                    )
                    else ""
                ),
                "body_preview_hex": hex_bytes(
                    data[
                        offset:
                        min(offset + 32, len(data))
                    ]
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
        f"{'Name':52} "
        f"{'Wrap':>5} "
        f"{'BitField':>9} "
        f"{'Mixins':>6} "
        f"{'MixinType':>9} "
        f"{'OK':>5}"
    )

    for row in output_rows:
        print(
            f"{str(row['parsed_name']):52} "
            f"{int(row['wrapper_type_code']):5} "
            f"{str(row['ability_bit_field_hex']):>9} "
            f"{str(row['mixin_count']):>6} "
            f"{str(row['first_mixin_type']):>9} "
            f"{str(row['name_matches']):>5}"
        )

    print()
    print(
        f"CSV：{args.output_csv}"
    )
    print(
        f"JSON：{args.output_json}"
    )


if __name__ == "__main__":
    main()