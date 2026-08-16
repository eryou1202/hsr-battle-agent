from __future__ import annotations

import argparse
import csv
import mmap
import re
from collections import defaultdict
from pathlib import Path


ASCII_STRING = re.compile(rb"[\x20-\x7E]{4,}")

RESOURCE_MARKERS = (
    "Effects/",
    "SpriteOutput/",
    "Camera/",
    "Characters/",
    "UI/",
    ".prefab",
    ".playable",
    ".png",
    ".asset",
    ".anim",
)

MECHANIC_MARKERS = (
    "MDF_",
    "Modifier",
    "Ability",
    "Caster",
    "Target",
    "Skill",
    "Passive",
    "Normal",
    "Ultra",
    "Maze",
    "Arcana",
    "Count",
    "Damage",
    "Attack",
    "HPRatio",
)


def classify(value: str) -> str:
    if any(marker in value for marker in RESOURCE_MARKERS):
        return "resource"

    if any(marker in value for marker in MECHANIC_MARKERS):
        return "mechanic"

    return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
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
        "--max-offsets",
        type=int,
        default=20,
    )
    args = parser.parse_args()

    if not args.input.is_file():
        raise FileNotFoundError(args.input)

    lowered_tokens = [
        token.lower()
        for token in args.tokens
    ]

    # value -> occurrence data
    values: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "count": 0,
            "offsets": [],
        }
    )

    with args.input.open("rb") as file:
        with mmap.mmap(
            file.fileno(),
            0,
            access=mmap.ACCESS_READ,
        ) as data:
            for match in ASCII_STRING.finditer(data):
                raw = match.group(0)

                try:
                    value = raw.decode("utf-8")
                except UnicodeDecodeError:
                    value = raw.decode(
                        "ascii",
                        errors="ignore",
                    )

                lowered_value = value.lower()

                if not any(
                    token in lowered_value
                    for token in lowered_tokens
                ):
                    continue

                item = values[value]
                item["count"] = int(item["count"]) + 1

                offsets = item["offsets"]

                if len(offsets) < args.max_offsets:
                    offsets.append(match.start())

    rows: list[dict[str, object]] = []

    for value, item in values.items():
        offsets = item["offsets"]

        rows.append(
            {
                "category": classify(value),
                "count": item["count"],
                "first_offset_decimal": (
                    offsets[0]
                    if offsets
                    else ""
                ),
                "first_offset_hex": (
                    f"0x{offsets[0]:X}"
                    if offsets
                    else ""
                ),
                "offsets": ",".join(
                    f"0x{offset:X}"
                    for offset in offsets
                ),
                "value": value,
            }
        )

    category_order = {
        "mechanic": 0,
        "unknown": 1,
        "resource": 2,
    }

    rows.sort(
        key=lambda row: (
            category_order.get(
                str(row["category"]),
                9,
            ),
            -int(row["count"]),
            str(row["value"]),
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
                "count",
                "first_offset_decimal",
                "first_offset_hex",
                "offsets",
                "value",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Unique matching strings: {len(rows)}")
    print(f"Report: {args.output}")

    summary: dict[str, int] = defaultdict(int)

    for row in rows:
        summary[str(row["category"])] += 1

    print("\nSummary:")

    for category in (
        "mechanic",
        "unknown",
        "resource",
    ):
        print(
            f"  {category}: "
            f"{summary.get(category, 0)}"
        )


if __name__ == "__main__":
    main()