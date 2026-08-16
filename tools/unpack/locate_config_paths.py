from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


EXCLUDED_CHUNK = "edd7d527b0962f4ec2e49789746fb0d2.bytes"


def find_all(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0

    while True:
        offset = data.find(needle, start)

        if offset < 0:
            return offsets

        offsets.append(offset)
        start = offset + 1


def hex_context(data: bytes, offset: int, radius: int = 64) -> str:
    start = max(0, offset - radius)
    end = min(len(data), offset + radius)

    return " ".join(f"{value:02X}" for value in data[start:end])


def text_context(data: bytes, offset: int, radius: int = 96) -> str:
    start = max(0, offset - radius)
    end = min(len(data), offset + radius)

    return "".join(
        chr(value) if 32 <= value <= 126 else "."
        for value in data[start:end]
    )


def load_index(path: Path) -> dict[str, list[str]]:
    with path.open("r", encoding="utf-8-sig") as file:
        value = json.load(file)

    if not isinstance(value, dict):
        raise ValueError("路径索引顶层不是 JSON 对象")

    result: dict[str, list[str]] = {}

    for section, entries in value.items():
        if not isinstance(entries, list):
            continue

        string_entries = [
            entry
            for entry in entries
            if isinstance(entry, str)
        ]

        result[section] = string_entries

    return result


def collect_samples(
    index: dict[str, list[str]],
    per_section: int,
) -> list[tuple[str, str]]:
    sections = (
        "TurnBasedAbilityConfig",
        "GlobalModifierConfig",
        "ComplexSkillAIGlobalGroupConfig",
        "CommonSkillPoolConfig",
        "AdventureModifierConfig",
    )

    samples: list[tuple[str, str]] = []

    for section in sections:
        for path in index.get(section, [])[:per_section]:
            samples.append((section, path))

    return samples


def build_patterns(config_path: str) -> dict[str, bytes]:
    normalized = config_path.replace("\\", "/")
    path = Path(normalized)

    patterns = {
        "full_path_utf8": normalized.encode("utf-8"),
        "full_path_no_ext": str(path.with_suffix("")).encode("utf-8"),
        "file_name": path.name.encode("utf-8"),
        "file_stem": path.stem.encode("utf-8"),
    }

    # 避免重复模式，例如路径无扩展名时可能相同。
    unique: dict[str, bytes] = {}
    seen: set[bytes] = set()

    for name, pattern in patterns.items():
        if pattern and pattern not in seen:
            unique[name] = pattern
            seen.add(pattern)

    return unique


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-json", required=True, type=Path)
    parser.add_argument(
        "--roots",
        required=True,
        nargs="+",
        type=Path,
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--per-section", type=int, default=5)
    args = parser.parse_args()

    if not args.index_json.is_file():
        raise FileNotFoundError(args.index_json)

    index = load_index(args.index_json)
    samples = collect_samples(index, args.per_section)

    chunks: list[Path] = []

    for root in args.roots:
        if not root.exists():
            print(f"跳过不存在的目录：{root}")
            continue

        for path in root.rglob("*.bytes"):
            if path.name == EXCLUDED_CHUNK:
                continue

            chunks.append(path)

    chunks = sorted(set(chunks))

    print(f"代表性配置路径：{len(samples)}")
    print(f"待扫描数据块：{len(chunks)}")

    rows: list[dict[str, object]] = []

    for chunk_number, chunk in enumerate(chunks, start=1):
        print(
            f"[{chunk_number}/{len(chunks)}] "
            f"{chunk.name} "
            f"({chunk.stat().st_size / 1024 / 1024:.2f} MiB)"
        )

        data = chunk.read_bytes()

        for section, config_path in samples:
            for pattern_type, pattern in build_patterns(
                config_path
            ).items():
                offsets = find_all(data, pattern)

                for offset in offsets[:10]:
                    rows.append(
                        {
                            "section": section,
                            "config_path": config_path,
                            "pattern_type": pattern_type,
                            "chunk_name": chunk.name,
                            "chunk_path": str(chunk),
                            "chunk_size": len(data),
                            "offset_decimal": offset,
                            "offset_hex": f"0x{offset:X}",
                            "text_context": text_context(
                                data,
                                offset,
                            ),
                            "hex_context": hex_context(
                                data,
                                offset,
                            ),
                        }
                    )

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "section",
                "config_path",
                "pattern_type",
                "chunk_name",
                "chunk_path",
                "chunk_size",
                "offset_decimal",
                "offset_hex",
                "text_context",
                "hex_context",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"匹配数量：{len(rows)}")
    print(f"报告位置：{args.output}")

    if not rows:
        print(
            "没有在其他分块中发现明文路径。"
            "下一步应分析路径哈希或索引映射。"
        )
        return

    print("\n命中的分块：")

    hit_chunks = sorted(
        {
            (row["chunk_name"], row["pattern_type"])
            for row in rows
        }
    )

    for chunk_name, pattern_type in hit_chunks:
        print(f"  {chunk_name}: {pattern_type}")


if __name__ == "__main__":
    main()