from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path


HASH_NAME = re.compile(r"^[0-9a-fA-F]{32}$")


def md5_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.md5()

    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)

    return digest.hexdigest()


def all_offsets(data: bytes, pattern: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0

    while True:
        offset = data.find(pattern, start)

        if offset < 0:
            return offsets

        offsets.append(offset)
        start = offset + 1


def guid_byte_order(raw: bytes) -> bytes:
    """
    常见 GUID 二进制字节序：
    前 4、2、2 字节分别反转，最后 8 字节保持。
    """
    if len(raw) != 16:
        raise ValueError("MD5/GUID must be 16 bytes")

    return (
        raw[0:4][::-1]
        + raw[4:6][::-1]
        + raw[6:8][::-1]
        + raw[8:16]
    )


def reversed_u32_blocks(raw: bytes) -> bytes:
    return b"".join(
        raw[offset : offset + 4][::-1]
        for offset in range(0, len(raw), 4)
    )


def printable_context(data: bytes, offset: int, radius: int = 32) -> str:
    start = max(0, offset - radius)
    end = min(len(data), offset + radius)

    return "".join(
        chr(value) if 32 <= value <= 126 else "."
        for value in data[start:end]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--persistent",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--streaming",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--index",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    index_data = args.index.read_bytes()

    rows: list[dict[str, object]] = []

    for layer, root in (
        ("Persistent", args.persistent),
        ("StreamingAssets", args.streaming),
    ):
        for path in sorted(root.glob("*.bytes")):
            if not HASH_NAME.fullmatch(path.stem):
                continue

            expected_md5 = path.stem.lower()
            actual_md5 = md5_file(path)

            raw_hash = bytes.fromhex(expected_md5)

            patterns = {
                "ascii_hex": expected_md5.encode("ascii"),
                "raw_16": raw_hash,
                "raw_reversed": raw_hash[::-1],
                "guid_order": guid_byte_order(raw_hash),
                "u32_blocks_reversed": reversed_u32_blocks(raw_hash),
            }

            found: list[str] = []
            context: list[str] = []

            for pattern_name, pattern in patterns.items():
                offsets = all_offsets(index_data, pattern)

                if offsets:
                    found.append(
                        f"{pattern_name}:{','.join(map(str, offsets))}"
                    )

                    for offset in offsets[:3]:
                        context.append(
                            f"{pattern_name}@0x{offset:X}:"
                            f"{printable_context(index_data, offset)}"
                        )

            rows.append(
                {
                    "layer": layer,
                    "file_name": path.name,
                    "size": path.stat().st_size,
                    "expected_md5": expected_md5,
                    "actual_md5": actual_md5,
                    "md5_matches": expected_md5 == actual_md5,
                    "index_references": " | ".join(found),
                    "context": " | ".join(context),
                }
            )

    output_csv = args.output / "design_index_probe.csv"

    with output_csv.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "layer",
                "file_name",
                "size",
                "expected_md5",
                "actual_md5",
                "md5_matches",
                "index_references",
                "context",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Index: {args.index}")
    print(f"Index size: {len(index_data):,} bytes")
    print(f"Chunks inspected: {len(rows)}")
    print(f"Report: {output_csv}")

    print("\nReferenced chunks:")

    for row in rows:
        if row["index_references"]:
            print(
                row["layer"],
                row["file_name"],
                row["index_references"],
            )


if __name__ == "__main__":
    main()