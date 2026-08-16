from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path


def parse_number(value: str) -> int:
    return int(value, 0)


def safe_filename(value: str) -> str:
    value = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        value,
    )

    return value.strip("_")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="包含 Ability 数据的 bytes 分块",
    )
    parser.add_argument(
        "--directory-csv",
        required=True,
        type=Path,
        help="probe_ability_directory.py 生成的 CSV",
    )
    parser.add_argument(
        "--payload-end",
        required=True,
        type=parse_number,
        help="最后一条记录的结束地址",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    if not args.input.is_file():
        raise FileNotFoundError(
            f"输入分块不存在：{args.input}"
        )

    if not args.directory_csv.is_file():
        raise FileNotFoundError(
            f"目录 CSV 不存在：{args.directory_csv}"
        )

    with args.directory_csv.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    if not rows:
        raise RuntimeError(
            "目录 CSV 中没有记录。"
        )

    for row in rows:
        if not row.get("record_start_decimal"):
            raise RuntimeError(
                "目录 CSV 缺少 record_start_decimal。"
                "请先运行修改后的 probe_ability_directory.py。"
            )

    rows.sort(
        key=lambda row: int(
            row["record_start_decimal"]
        )
    )

    source_size = args.input.stat().st_size

    if args.payload_end > source_size:
        raise ValueError(
            "payload-end 超出输入文件长度："
            f"0x{args.payload_end:X}"
        )

    source = args.input.read_bytes()

    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_rows: list[dict[str, object]] = []

    for index, row in enumerate(rows):
        start = int(
            row["record_start_decimal"]
        )

        if index + 1 < len(rows):
            end = int(
                rows[index + 1][
                    "record_start_decimal"
                ]
            )
        else:
            end = args.payload_end

        if not 0 <= start < end <= len(source):
            raise ValueError(
                "记录边界错误："
                f"{row['name']} "
                f"0x{start:X}-0x{end:X}"
            )

        data = source[start:end]

        filename = (
            f"{index + 1:02d}_"
            f"{safe_filename(row['name'])}.bin"
        )

        output_path = (
            args.output_dir / filename
        )

        output_path.write_bytes(data)

        sha256 = hashlib.sha256(
            data
        ).hexdigest()

        manifest_rows.append(
            {
                "index": index + 1,
                "name": row["name"],
                "start_decimal": start,
                "start_hex": f"0x{start:X}",
                "end_decimal": end,
                "end_hex": f"0x{end:X}",
                "length": len(data),
                "length_hex": f"0x{len(data):X}",
                "record_header_size": row.get(
                    "record_header_size",
                    "",
                ),
                "record_header_hex": row.get(
                    "record_header_hex",
                    "",
                ),
                "name_prefix_offset_hex": row.get(
                    "name_prefix_offset_hex",
                    "",
                ),
                "sha256": sha256,
                "output_file": str(output_path),
            }
        )

        print(
            f"[{index + 1:02d}/{len(rows):02d}] "
            f"{row['name']} "
            f"0x{start:X}-0x{end:X} "
            f"({len(data)} bytes)"
        )

    args.manifest.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.manifest.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(
                manifest_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(manifest_rows)

    print()
    print(
        f"导出记录数量：{len(manifest_rows)}"
    )
    print(
        f"输出目录：{args.output_dir}"
    )
    print(
        f"清单文件：{args.manifest}"
    )


if __name__ == "__main__":
    main()