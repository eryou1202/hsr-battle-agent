from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_number(value: str) -> int:
    return int(value, 0)

def decode_zigzag(value: int) -> int:
    return (value >> 1) ^ -(value & 1)

def read_uleb128(
    data: bytes,
    offset: int,
    limit: int,
    max_bytes: int = 10,
) -> tuple[int, int]:
    value = 0
    shift = 0

    for index in range(max_bytes):
        position = offset + index

        if position >= limit:
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


def find_all(
    data: bytes,
    needle: bytes,
    start: int,
    end: int,
) -> list[int]:
    offsets: list[int] = []
    position = start

    while True:
        position = data.find(
            needle,
            position,
            end,
        )

        if position < 0:
            return offsets

        offsets.append(position)
        position += 1


def context_hex(
    data: bytes,
    offset: int,
    before: int = 24,
    after: int = 48,
) -> str:
    start = max(0, offset - before)
    end = min(len(data), offset + after)

    return " ".join(
        f"{byte:02X}"
        for byte in data[start:end]
    )


def ascii_context(
    data: bytes,
    offset: int,
    before: int = 32,
    after: int = 96,
) -> str:
    start = max(0, offset - before)
    end = min(len(data), offset + after)

    return "".join(
        chr(byte)
        if 32 <= byte <= 126
        else "."
        for byte in data[start:end]
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--table-start",
        required=True,
        type=parse_number,
    )
    parser.add_argument(
        "--table-end",
        required=True,
        type=parse_number,
    )
    parser.add_argument(
        "--payload-start",
        required=True,
        type=parse_number,
    )
    parser.add_argument(
        "--payload-end",
        required=True,
        type=parse_number,
    )
    parser.add_argument(
        "--payload-base",
        required=True,
        type=parse_number,
        help="Ability 正文区域的相对偏移基址",
    )
    parser.add_argument(
        "--name-prefix",
        default="Avatar_BlackSwan_00_",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    if not args.input.is_file():
        raise FileNotFoundError(args.input)

    data = args.input.read_bytes()
    file_size = len(data)

    table_start = args.table_start
    table_end = min(
        args.table_end,
        file_size,
    )

    payload_start = args.payload_start
    payload_end = min(
        args.payload_end,
        file_size,
    )

    rows: list[dict[str, object]] = []
    position = table_start

    while position < table_end:
        entry_start = position

        try:
            name_length, length_size = (
                read_uleb128(
                    data,
                    position,
                    table_end,
                )
            )
        except (EOFError, ValueError):
            break

        position += length_size

        if not 3 <= name_length <= 256:
            break

        name_end = position + name_length

        if name_end > table_end:
            break

        raw_name = data[position:name_end]

        try:
            name = raw_name.decode("ascii")
        except UnicodeDecodeError:
            break

        if not name.startswith(args.name_prefix):
            break

        position = name_end

        if position >= table_end:
            break

        marker = data[position]
        position += 1

        try:
            encoded_value, encoded_size = (
                read_uleb128(
                    data,
                    position,
                    table_end,
                )
            )
        except (EOFError, ValueError):
            break

        encoded_offset = position
        position += encoded_size

        if position >= table_end:
            break

        tail = data[position]
        position += 1

        decoded_offset = decode_zigzag(
            encoded_value
        )

        exact_pattern = (
            bytes([name_length])
            + raw_name
        )

        occurrences = find_all(
            data,
            exact_pattern,
            payload_start,
            payload_end,
        )

        prefix_occurrences = [
            occurrence
            for occurrence in occurrences
        ]

        first_occurrence = (
            prefix_occurrences[0]
            if prefix_occurrences
            else None
        )

        rows.append(
            {
                "entry_start_hex": (
                    f"0x{entry_start:X}"
                ),
                "name": name,
                "name_length": name_length,
                "marker_hex": f"0x{marker:02X}",
                "encoded_offset_hex": (
                    f"0x{encoded_offset:X}"
                ),
                "encoded_value": encoded_value,
                "encoded_value_hex": (
                    f"0x{encoded_value:X}"
                ),
                "encoded_size": encoded_size,
                "tail_hex": f"0x{tail:02X}",
                "entry_end_hex": (
                    f"0x{position:X}"
                ),
                "occurrence_count": len(
                    prefix_occurrences
                ),
                "first_occurrence_hex": (
                    f"0x{first_occurrence:X}"
                    if first_occurrence is not None
                    else ""
                ),
                "decoded_offset": decoded_offset,
                "decoded_offset_hex": (
                    f"0x{decoded_offset:X}"
                ),
                "occurrences": ",".join(
                    f"0x{item:X}"
                    for item in prefix_occurrences
                ),
            }
        )

    if not rows:
        raise RuntimeError(
            "没有解析到目录条目，请检查范围。"
        )

    candidate_base = args.payload_base

    for row in rows:
        decoded_offset = int(
            row["decoded_offset"]
        )

        # 目录偏移指向 Ability 记录起点。
        record_start = (
            candidate_base
            + decoded_offset
        )

        name = str(row["name"])

        pattern = (
            bytes([int(row["name_length"])])
            + name.encode("ascii")
        )

        occurrences = [
            int(item, 16)
            for item in str(
                row["occurrences"]
            ).split(",")
            if item
        ]

        # 同一个名称可能既有定义，也有引用。
        # 选择距离目录计算出的记录起点最近的一处。
        if occurrences:
            name_prefix_offset = min(
                occurrences,
                key=lambda item: abs(
                    item - record_start
                ),
            )

            record_header_size = (
                name_prefix_offset
                - record_start
            )

            # 当前样本中记录头通常是 2～3 字节。
            record_alignment_ok = (
                0 <= record_header_size <= 16
                and data[
                    name_prefix_offset:
                    name_prefix_offset + len(pattern)
                ] == pattern
            )

            if record_header_size >= 0:
                record_header = data[
                    record_start:
                    name_prefix_offset
                ]
            else:
                record_header = b""
        else:
            name_prefix_offset = None
            record_header_size = None
            record_alignment_ok = False
            record_header = b""

        row["candidate_base_hex"] = (
            f"0x{candidate_base:X}"
        )

        row["record_start_decimal"] = (
            record_start
        )
        row["record_start_hex"] = (
            f"0x{record_start:X}"
        )

        row["name_prefix_offset_hex"] = (
            f"0x{name_prefix_offset:X}"
            if name_prefix_offset is not None
            else ""
        )

        row["record_header_size"] = (
            record_header_size
            if record_header_size is not None
            else ""
        )

        row["record_header_hex"] = " ".join(
            f"{byte:02X}"
            for byte in record_header
        )

        row["record_alignment_ok"] = (
            record_alignment_ok
        )

        # 保留旧字段名，避免已有 PowerShell 命令报错。
        row["candidate_target_hex"] = (
            f"0x{record_start:X}"
        )
        row["target_matches_name"] = (
            record_alignment_ok
        )
        row["nearest_occurrence_delta"] = (
            record_header_size
            if record_header_size is not None
            else ""
        )

        row["target_hex_context"] = context_hex(
            data,
            record_start,
        )

        row["target_ascii_context"] = (
            ascii_context(
                data,
                record_start,
            )
        )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = list(rows[0].keys())

    with args.output.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"目录条目：{len(rows)}")

    if candidate_base is not None:
        print(
            "首条推导候选基址："
            f"0x{candidate_base:X}"
        )

    print()
    print(
        f"{'Name':55} "
        f"{'Encoded':>9} "
        f"{'Decoded':>9} "
        f"{'RecordStart':>12} "
        f"{'NamePrefix':>12} "
        f"{'Header':>6} "
        f"{'OK':>6}"
    )

    for row in rows:
        print(
            f"{str(row['name']):55} "
            f"{int(row['encoded_value']):9} "
            f"{int(row['decoded_offset']):9} "
            f"{str(row['record_start_hex']):>12} "
            f"{str(row['name_prefix_offset_hex']):>12} "
            f"{str(row['record_header_size']):>6} "
            f"{str(row['record_alignment_ok']):>6}"
        )

    print()
    print(f"报告位置：{args.output}")


if __name__ == "__main__":
    main()