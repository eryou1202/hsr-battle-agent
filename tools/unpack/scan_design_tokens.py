from __future__ import annotations

import argparse
import csv
import mmap
from pathlib import Path


def find_all(data: mmap.mmap, needle: bytes):
    start = 0

    while True:
        offset = data.find(needle, start)

        if offset < 0:
            return

        yield offset
        start = offset + 1


def text_context(
    data: mmap.mmap,
    offset: int,
    token_length: int,
    before: int = 128,
    after: int = 384,
) -> str:
    start = max(0, offset - before)
    end = min(
        len(data),
        offset + token_length + after,
    )

    raw = data[start:end]

    return "".join(
        chr(value) if 32 <= value <= 126 else "."
        for value in raw
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--tokens",
        required=True,
        nargs="+",
    )
    parser.add_argument(
        "--max-per-token",
        type=int,
        default=200,
    )
    args = parser.parse_args()

    if not args.root.is_dir():
        raise NotADirectoryError(args.root)

    rows: list[dict[str, object]] = []

    chunks = sorted(args.root.glob("*.bytes"))

    for number, path in enumerate(chunks, start=1):
        size = path.stat().st_size

        print(
            f"[{number}/{len(chunks)}] "
            f"{path.name} "
            f"({size / 1024 / 1024:.2f} MiB)"
        )

        if size == 0:
            continue

        with path.open("rb") as file:
            with mmap.mmap(
                file.fileno(),
                0,
                access=mmap.ACCESS_READ,
            ) as data:
                for token in args.tokens:
                    needle = token.encode("utf-8")
                    hit_count = 0

                    for offset in find_all(data, needle):
                        rows.append(
                            {
                                "token": token,
                                "chunk_name": path.name,
                                "chunk_path": str(path),
                                "chunk_size": size,
                                "offset_decimal": offset,
                                "offset_hex": f"0x{offset:X}",
                                "context": text_context(
                                    data,
                                    offset,
                                    len(needle),
                                ),
                            }
                        )

                        hit_count += 1

                        if hit_count >= args.max_per_token:
                            break

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
                "token",
                "chunk_name",
                "chunk_path",
                "chunk_size",
                "offset_decimal",
                "offset_hex",
                "context",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"匹配总数：{len(rows)}")
    print(f"报告位置：{args.output}")


if __name__ == "__main__":
    main()