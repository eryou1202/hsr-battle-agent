"""Version-locked Nanoka snapshot, Canonical content, and SQLite query tools.

This module deliberately separates three concerns:

* raw public-oracle snapshots are immutable local inputs;
* Canonical JSONL is deterministic and auditable;
* SQLite is a rebuildable query layer, never the sole content source.

It contains static content only.  It must not be imported by battle runtime
code and it makes no claim about dynamic battle-event semantics.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


NANOKA_BASE_URL = "https://static.nanoka.cc"
DEFAULT_LOCALE = "zh"
SUPPORTED_VERSION = "4.4.54"
COLLECTIONS = (
    "character",
    "lightcone",
    "relicset",
    "monster",
    "maze",
    "maze_extra",
    "maze_boss",
)
DETAIL_COLLECTIONS: Mapping[str, str] = {
    "character": "character",
    "lightcone": "lightcone",
    "relicset": "relicset",
    "monster": "monster",
    "maze": "maze",
    "maze_extra": "story",
    "maze_boss": "boss",
}


class SnapshotError(RuntimeError):
    """A raw snapshot cannot be fetched or violates immutability."""


class ContentDatabaseError(RuntimeError):
    """Canonical or SQLite data fails its stable content contract."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def stable_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def stable_hash(value: Any) -> str:
    return sha256(stable_bytes(value)).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        + b"\n"
    )


def write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=lambda row: str(row["entity_id"]))
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in ordered
        ),
        encoding="utf-8",
    )


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_snapshot_root(version: str) -> Path:
    return project_root() / "data" / "external" / "nanoka" / version


def default_canonical_root(version: str) -> Path:
    return project_root() / "data" / "content" / version / "nanoka"


def default_db_path(version: str) -> Path:
    return project_root() / "data" / "db" / f"hsr_content_{version}.sqlite"


def _numeric_key(value: str) -> tuple[int, str]:
    try:
        return (0, f"{int(value):020d}")
    except ValueError:
        return (1, value)


@dataclass(frozen=True)
class FetchResult:
    relative_path: str
    url: str
    sha256: str
    size: int
    etag: str | None
    last_modified: str | None
    fetched_at: str | None
    status: str
    locale: str | None
    category: str
    entity_id: str | None


class NanokaSnapshotFetcher:
    """Low-concurrency, resumable downloader for a version-locked snapshot."""

    def __init__(
        self,
        version: str,
        *,
        locale: str = DEFAULT_LOCALE,
        root: Path | None = None,
        workers: int = 3,
        timeout_seconds: int = 45,
        retries: int = 3,
        refresh: bool = False,
    ) -> None:
        if not version:
            raise ValueError("version must not be empty")
        if workers < 1 or workers > 4:
            raise ValueError("workers must be between 1 and 4")
        self.version = version
        self.locale = locale
        self.root = root or default_snapshot_root(version)
        self.workers = workers
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.refresh = refresh
        self._index_path = self.root / "provenance" / "index.json"
        self._index: dict[str, dict[str, Any]] = (
            read_json(self._index_path) if self._index_path.exists() else {}
        )
        self._records_since_checkpoint = 0
        self.errors: list[dict[str, str]] = []

    def _url(self, suffix: str) -> str:
        return f"{NANOKA_BASE_URL}/{suffix.lstrip('/')}"

    def _fetch_one(
        self,
        *,
        relative_path: str,
        url: str,
        category: str,
        entity_id: str | None = None,
        locale: str | None = None,
    ) -> FetchResult:
        destination = self.root / relative_path
        previous = self._index.get(relative_path)
        if destination.exists() and previous and not self.refresh:
            payload = destination.read_bytes()
            actual_hash = sha256(payload).hexdigest()
            if actual_hash != previous.get("raw_sha256"):
                raise SnapshotError(
                    f"raw snapshot hash changed locally: {relative_path}; refuse overwrite"
                )
            return FetchResult(
                relative_path=relative_path,
                url=url,
                sha256=actual_hash,
                size=len(payload),
                etag=previous.get("etag"),
                last_modified=previous.get("last_modified"),
                fetched_at=(
                    None
                    if previous.get("fetch_time") in {None, "None"}
                    else str(previous.get("fetch_time"))
                ),
                status="CACHED",
                locale=locale,
                category=category,
                entity_id=entity_id,
            )
        if destination.exists() and not previous and not self.refresh:
            # An interrupted run may have written immutable raw bytes before
            # its final provenance checkpoint.  Preserve them and record the
            # honest state instead of refetching/overwriting unknown bytes.
            payload = destination.read_bytes()
            json.loads(payload.decode("utf-8"))
            return FetchResult(
                relative_path=relative_path,
                url=url,
                sha256=sha256(payload).hexdigest(),
                size=len(payload),
                etag=None,
                last_modified=None,
                fetched_at=None,
                status="RECOVERED_UNINDEXED",
                locale=locale,
                category=category,
                entity_id=entity_id,
            )

        headers = {"User-Agent": "HSR-Battle-Agent/0.0 content-snapshot"}
        if previous:
            if previous.get("etag"):
                headers["If-None-Match"] = str(previous["etag"])
            if previous.get("last_modified"):
                headers["If-Modified-Since"] = str(previous["last_modified"])
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                request = Request(url, headers=headers)
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = response.read()
                    content_type = response.headers.get("Content-Type", "")
                    if "json" not in content_type.lower():
                        raise SnapshotError(f"unexpected content type {content_type!r} for {url}")
                    json.loads(payload.decode("utf-8"))
                    payload_hash = sha256(payload).hexdigest()
                    if destination.exists() and previous and not self.refresh:
                        raise SnapshotError(f"immutable snapshot would overwrite: {relative_path}")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    temporary = destination.with_suffix(destination.suffix + ".part")
                    temporary.write_bytes(payload)
                    temporary.replace(destination)
                    return FetchResult(
                        relative_path=relative_path,
                        url=url,
                        sha256=payload_hash,
                        size=len(payload),
                        etag=response.headers.get("ETag"),
                        last_modified=response.headers.get("Last-Modified"),
                        fetched_at=utc_now(),
                        status="FETCHED",
                        locale=locale,
                        category=category,
                        entity_id=entity_id,
                    )
            except HTTPError as exc:
                if exc.code == 304 and destination.exists() and previous:
                    payload = destination.read_bytes()
                    return FetchResult(
                        relative_path=relative_path,
                        url=url,
                        sha256=sha256(payload).hexdigest(),
                        size=len(payload),
                        etag=previous.get("etag"),
                        last_modified=previous.get("last_modified"),
                        fetched_at=utc_now(),
                        status="NOT_MODIFIED",
                        locale=locale,
                        category=category,
                        entity_id=entity_id,
                    )
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
            except (URLError, TimeoutError, SnapshotError, UnicodeDecodeError) as exc:
                last_error = exc
                if isinstance(exc, SnapshotError):
                    break
            time.sleep(1.25 * (attempt + 1))
        raise SnapshotError(f"fetch failed for {url}: {last_error}")

    def _record(self, result: FetchResult) -> None:
        self._index[result.relative_path] = {
            "source": "nanoka",
            "source_version": self.version if "/hsr/" in result.url else None,
            "source_url": result.url,
            "source_category": result.category,
            "source_entity_id": result.entity_id,
            "locale": result.locale,
            "etag": result.etag,
            "last_modified": result.last_modified,
            "fetch_time": result.fetched_at,
            "raw_sha256": result.sha256,
            "raw_size": result.size,
            "fetch_status": result.status,
        }
        self._records_since_checkpoint += 1
        if self._records_since_checkpoint >= 25:
            self._checkpoint_index()

    def _checkpoint_index(self) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(self._index_path, dict(sorted(self._index.items())))
        self._records_since_checkpoint = 0

    def _safe_fetch(self, **kwargs: Any) -> None:
        try:
            self._record(self._fetch_one(**kwargs))
        except SnapshotError as exc:
            self.errors.append(
                {
                    "relative_path": str(kwargs["relative_path"]),
                    "url": str(kwargs["url"]),
                    "error": str(exc),
                }
            )

    def fetch(self, *, include_details: bool = True) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        self._safe_fetch(
            relative_path="manifest.json",
            url=self._url("manifest.json"),
            category="manifest",
            locale=None,
        )
        for collection in COLLECTIONS:
            self._safe_fetch(
                relative_path=f"collections/{collection}.json",
                url=self._url(f"hsr/{self.version}/{collection}.json"),
                category=collection,
                locale=None,
            )
        self._safe_fetch(
            relative_path="auxiliary/item.json",
            url=self._url(f"hsr/{self.version}/{self.locale}/item.json"),
            category="item",
            locale=self.locale,
        )
        for name in ("EliteGroup", "HardLevelGroup"):
            self._safe_fetch(
                relative_path=f"auxiliary/{name}.json",
                url=self._url(f"hsr/{name}.json"),
                category=name,
                locale=None,
            )

        if include_details:
            jobs: list[dict[str, Any]] = []
            for collection, endpoint in DETAIL_COLLECTIONS.items():
                collection_path = self.root / "collections" / f"{collection}.json"
                if not collection_path.exists():
                    continue
                payload = read_json(collection_path)
                if not isinstance(payload, Mapping):
                    self.errors.append(
                        {"relative_path": str(collection_path), "url": "", "error": "not a mapping"}
                    )
                    continue
                for entity_id in sorted((str(key) for key in payload), key=_numeric_key):
                    jobs.append(
                        {
                            "relative_path": f"detail/{endpoint}/{entity_id}.json",
                            "url": self._url(
                                f"hsr/{self.version}/{self.locale}/{endpoint}/{entity_id}.json"
                            ),
                            "category": endpoint,
                            "entity_id": entity_id,
                            "locale": self.locale,
                        }
                    )
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = [executor.submit(self._fetch_one, **job) for job in jobs]
                for future in as_completed(futures):
                    try:
                        self._record(future.result())
                    except Exception as exc:  # preserve a resumable fetch after worker I/O failures
                        self.errors.append({"relative_path": "detail", "url": "", "error": f"{type(exc).__name__}: {exc}"})

            # A real stage may cite _BindingMazeBuff IDs not present in the
            # public maze collection.  These requests are reference-led, not a
            # numerical scan, and failed lookups remain explicit provenance.
            for buff_id in self._discover_stage_buff_ids():
                path = f"detail/maze/{buff_id}.json"
                if path in self._index and (self.root / path).exists():
                    continue
                self._safe_fetch(
                    relative_path=path,
                    url=self._url(f"hsr/{self.version}/{self.locale}/maze/{buff_id}.json"),
                    category="maze_binding_buff",
                    entity_id=buff_id,
                    locale=self.locale,
                )

        self._checkpoint_index()
        write_json(self.root / "provenance" / "errors.json", self.errors)
        return {
            "version": self.version,
            "snapshot_root": str(self.root),
            "records": len(self._index),
            "errors": len(self.errors),
            "raw_size": sum(int(row.get("raw_size", 0)) for row in self._index.values()),
        }

    def _discover_stage_buff_ids(self) -> list[str]:
        values: set[str] = set()
        for path in sorted((self.root / "detail" / "boss").glob("*.json")):
            try:
                payload = read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            for node in _walk(payload):
                if not isinstance(node, Mapping):
                    continue
                if node.get("jdkamoanicm") == "_BindingMazeBuff":
                    value = node.get("mojjbfbkbnc")
                    if value is not None:
                        values.add(str(value))
        return sorted(values, key=_numeric_key)


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _raw_provenance(index: Mapping[str, Any], relative_path: str) -> dict[str, Any]:
    source = _mapping(index.get(relative_path))
    return {
        "source": source.get("source", "nanoka"),
        "source_version": source.get("source_version"),
        "source_category": source.get("source_category"),
        "source_entity_id": source.get("source_entity_id"),
        "source_url": source.get("source_url"),
        "locale": source.get("locale"),
        "etag": source.get("etag"),
        "last_modified": source.get("last_modified"),
        "fetch_time": source.get("fetch_time"),
        "raw_sha256": source.get("raw_sha256"),
        "raw_relative_path": relative_path,
    }


def _entity(
    entity_type: str,
    entity_id: str,
    *,
    version: str,
    payload: Mapping[str, Any],
    provenance: list[Mapping[str, Any]],
    confidence: str = "C0_EXTERNAL_ONLY",
    reconstruction_status: str = "PARTIAL",
    original_game_id: Any | None = None,
    game_id_status: str = "PRESERVED",
) -> dict[str, Any]:
    stable_payload = {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "game_version": version,
        "original_game_id": original_game_id if original_game_id is not None else entity_id,
        "game_id_status": game_id_status,
        "confidence": confidence,
        "reconstruction_status": reconstruction_status,
        "data": payload,
        "provenance": provenance,
    }
    stable_payload["canonical_sha256"] = stable_hash(stable_payload)
    return stable_payload


@dataclass
class CanonicalBuild:
    version: str
    records: dict[str, list[dict[str, Any]]]
    relations: dict[str, list[dict[str, Any]]]
    validation: list[dict[str, Any]]
    static_gaps: list[dict[str, Any]]
    dynamic_gaps: list[dict[str, Any]]


class CanonicalBuilder:
    """Normalize a raw Nanoka snapshot without replacing unknown facts."""

    def __init__(self, snapshot_root: Path, version: str) -> None:
        self.snapshot_root = snapshot_root
        self.version = version
        index_path = snapshot_root / "provenance" / "index.json"
        if not index_path.exists():
            raise ContentDatabaseError(f"missing snapshot provenance: {index_path}")
        self.index = _mapping(read_json(index_path))
        self.records: dict[str, list[dict[str, Any]]] = {}
        self.relations: dict[str, list[dict[str, Any]]] = {}
        self.validation: list[dict[str, Any]] = []
        self.static_gaps: list[dict[str, Any]] = []
        self._static_gap_ids: set[str] = set()
        self.dynamic_gaps = _dynamic_gaps(version)

    def _load(self, relative_path: str) -> Any | None:
        path = self.snapshot_root / relative_path
        if not path.exists():
            return None
        return read_json(path)

    def _provenance(self, *relative_paths: str) -> list[dict[str, Any]]:
        return [_raw_provenance(self.index, path) for path in relative_paths if path in self.index]

    def _add(self, record: dict[str, Any]) -> None:
        bucket = self.records.setdefault(str(record["entity_type"]), [])
        identifier = str(record["entity_id"])
        existing = next((row for row in bucket if str(row["entity_id"]) == identifier), None)
        if existing is None:
            bucket.append(record)
            return
        existing_without_provenance = {
            key: value
            for key, value in existing.items()
            if key not in {"provenance", "canonical_sha256"}
        }
        record_without_provenance = {
            key: value
            for key, value in record.items()
            if key not in {"provenance", "canonical_sha256"}
        }
        if existing_without_provenance == record_without_provenance:
            merged_provenance = {
                stable_hash(reference): reference
                for reference in [*existing["provenance"], *record["provenance"]]
            }
            existing["provenance"] = sorted(merged_provenance.values(), key=stable_bytes)
            canonical_payload = {key: value for key, value in existing.items() if key != "canonical_sha256"}
            existing["canonical_sha256"] = stable_hash(canonical_payload)
            return
        if existing["canonical_sha256"] != record["canonical_sha256"]:
            gap_id = f"CONFLICT:{record['entity_type']}:{identifier}"
            if gap_id not in self._static_gap_ids:
                self._static_gap_ids.add(gap_id)
                self.static_gaps.append(
                    {
                    "gap_id": gap_id,
                    "category": "canonical_conflict",
                    "entity_type": record["entity_type"],
                    "entity_id": identifier,
                    "status": "CONFLICT",
                    "detail": "multiple external records normalize to one canonical key",
                    }
                )

    def _rel(self, relation_type: str, **row: Any) -> None:
        row = {"game_version": self.version, "relation_type": relation_type, **row}
        self.relations.setdefault(relation_type, []).append(row)

    def build(self) -> CanonicalBuild:
        self._build_avatars()
        self._build_lightcones()
        self._build_relic_sets()
        self._build_monsters()
        self._build_stages()
        self._build_validation()
        self._build_static_gaps()
        return CanonicalBuild(
            version=self.version,
            records=self.records,
            relations=self.relations,
            validation=self.validation,
            static_gaps=self.static_gaps,
            dynamic_gaps=self.dynamic_gaps,
        )

    def _build_avatars(self) -> None:
        collection_path = "collections/character.json"
        collection = _mapping(self._load(collection_path))
        for avatar_id in sorted((str(value) for value in collection), key=_numeric_key):
            detail_path = f"detail/character/{avatar_id}.json"
            detail = _mapping(self._load(detail_path))
            collection_row = _mapping(collection.get(avatar_id))
            merged = {"collection": collection_row, "detail": detail}
            ready = bool(detail.get("stats") and detail.get("skills") and detail.get("ranks") and detail.get("skill_trees"))
            self._add(
                _entity(
                    "avatar", avatar_id, version=self.version, payload=merged,
                    provenance=self._provenance(collection_path, detail_path),
                    reconstruction_status="RECONSTRUCTION_READY" if ready else "PARTIAL",
                    original_game_id=int(avatar_id) if avatar_id.isdigit() else avatar_id,
                )
            )
            for skill_id, skill in sorted(_mapping(detail.get("skills")).items(), key=lambda item: _numeric_key(str(item[0]))):
                skill_path = dict(_mapping(skill))
                skill_path["owner_avatar_id"] = int(avatar_id) if avatar_id.isdigit() else avatar_id
                self._add(
                    _entity(
                        "skill", str(skill_id), version=self.version, payload=skill_path,
                        provenance=self._provenance(detail_path),
                        reconstruction_status="RECONSTRUCTION_READY",
                        original_game_id=int(skill_id) if str(skill_id).isdigit() else skill_id,
                    )
                )
                self._rel("avatar_skill", avatar_id=avatar_id, skill_id=str(skill_id))
            for anchor, levels in sorted(_mapping(detail.get("skill_trees")).items()):
                for level_key, trace in sorted(_mapping(levels).items(), key=lambda item: _numeric_key(str(item[0]))):
                    trace_data = dict(_mapping(trace))
                    trace_id = f"{avatar_id}:{anchor}:{level_key}"
                    trace_data["owner_avatar_id"] = int(avatar_id) if avatar_id.isdigit() else avatar_id
                    trace_data["trace_anchor"] = anchor
                    trace_data["trace_level"] = str(level_key)
                    self._add(
                        _entity(
                            "trace", trace_id, version=self.version, payload=trace_data,
                            provenance=self._provenance(detail_path),
                            reconstruction_status="RECONSTRUCTION_READY",
                            original_game_id=trace_data.get("point_id"),
                            game_id_status="PRESERVED" if trace_data.get("point_id") is not None else "UNKNOWN",
                        )
                    )
                    self._rel("avatar_trace", avatar_id=avatar_id, trace_id=trace_id)
            for rank, eidolon in sorted(_mapping(detail.get("ranks")).items(), key=lambda item: _numeric_key(str(item[0]))):
                eidolon_data = dict(_mapping(eidolon))
                eidolon_data["owner_avatar_id"] = int(avatar_id) if avatar_id.isdigit() else avatar_id
                eidolon_data["rank"] = str(rank)
                raw_id = eidolon_data.get("id")
                eidolon_id = str(raw_id) if raw_id is not None else f"{avatar_id}:rank:{rank}"
                self._add(
                    _entity(
                        "eidolon", eidolon_id, version=self.version, payload=eidolon_data,
                        provenance=self._provenance(detail_path),
                        reconstruction_status="RECONSTRUCTION_READY",
                        original_game_id=raw_id,
                        game_id_status="PRESERVED" if raw_id is not None else "UNKNOWN",
                    )
                )
                self._rel("avatar_eidolon", avatar_id=avatar_id, rank=str(rank), eidolon_id=eidolon_id)

    def _build_lightcones(self) -> None:
        collection_path = "collections/lightcone.json"
        collection = _mapping(self._load(collection_path))
        for lightcone_id in sorted((str(value) for value in collection), key=_numeric_key):
            detail_path = f"detail/lightcone/{lightcone_id}.json"
            detail = _mapping(self._load(detail_path))
            collection_row = _mapping(collection.get(lightcone_id))
            ready = bool(detail.get("stats") and detail.get("refinements"))
            self._add(
                _entity(
                    "lightcone", lightcone_id, version=self.version,
                    payload={"collection": collection_row, "detail": detail},
                    provenance=self._provenance(collection_path, detail_path),
                    reconstruction_status="RECONSTRUCTION_READY" if ready else "PARTIAL",
                    original_game_id=int(lightcone_id) if lightcone_id.isdigit() else lightcone_id,
                )
            )
            for promotion_index, row in enumerate(_list(detail.get("stats"))):
                promotion = _mapping(row)
                promotion_id = f"{lightcone_id}:{promotion.get('promotion', promotion_index)}"
                self._add(
                    _entity(
                        "lightcone_promotion", promotion_id, version=self.version,
                        payload={"lightcone_id": lightcone_id, **promotion},
                        provenance=self._provenance(detail_path),
                        reconstruction_status="RECONSTRUCTION_READY",
                        original_game_id=promotion.get("equipment_id"),
                    )
                )
                self._rel("lightcone_promotion", lightcone_id=lightcone_id, promotion_id=promotion_id)
            refinements = _mapping(_mapping(detail.get("refinements")).get("level"))
            for rank, row in sorted(refinements.items(), key=lambda item: _numeric_key(str(item[0]))):
                superimposition_id = f"{lightcone_id}:superimposition:{rank}"
                self._add(
                    _entity(
                        "lightcone_superimposition", superimposition_id, version=self.version,
                        payload={"lightcone_id": lightcone_id, "rank": str(rank), **_mapping(row)},
                        provenance=self._provenance(detail_path),
                        reconstruction_status="RECONSTRUCTION_READY",
                        original_game_id=lightcone_id,
                    )
                )
                self._rel("lightcone_superimposition", lightcone_id=lightcone_id, rank=str(rank), superimposition_id=superimposition_id)

    def _build_relic_sets(self) -> None:
        collection_path = "collections/relicset.json"
        collection = _mapping(self._load(collection_path))
        for relicset_id in sorted((str(value) for value in collection), key=_numeric_key):
            detail_path = f"detail/relicset/{relicset_id}.json"
            detail = _mapping(self._load(detail_path))
            ready = bool(detail.get("parts") and detail.get("require_num"))
            self._add(
                _entity(
                    "relic_set", relicset_id, version=self.version,
                    payload={"collection": _mapping(collection.get(relicset_id)), "detail": detail},
                    provenance=self._provenance(collection_path, detail_path),
                    reconstruction_status="RECONSTRUCTION_READY" if ready else "PARTIAL",
                    original_game_id=int(relicset_id) if relicset_id.isdigit() else relicset_id,
                )
            )
            for part_id, part in sorted(_mapping(detail.get("parts")).items(), key=lambda item: _numeric_key(str(item[0]))):
                item_id = f"{relicset_id}:{part_id}"
                self._add(
                    _entity(
                        "relic_item", item_id, version=self.version,
                        payload={"relic_set_id": relicset_id, "original_item_id": part_id, **_mapping(part)},
                        provenance=self._provenance(detail_path),
                        reconstruction_status="RECONSTRUCTION_READY",
                        original_game_id=int(part_id) if str(part_id).isdigit() else part_id,
                    )
                )
                self._rel("relic_set_item", relic_set_id=relicset_id, relic_item_id=item_id)

    def _build_monsters(self) -> None:
        collection_path = "collections/monster.json"
        collection = _mapping(self._load(collection_path))
        for monster_id in sorted((str(value) for value in collection), key=_numeric_key):
            detail_path = f"detail/monster/{monster_id}.json"
            detail = _mapping(self._load(detail_path))
            ready = bool(detail.get("hp_base") is not None and detail.get("child"))
            self._add(
                _entity(
                    "monster", monster_id, version=self.version,
                    payload={"collection": _mapping(collection.get(monster_id)), "detail": detail},
                    provenance=self._provenance(collection_path, detail_path),
                    reconstruction_status="RECONSTRUCTION_READY" if ready else "PARTIAL",
                    original_game_id=int(monster_id) if monster_id.isdigit() else monster_id,
                )
            )
            for variant in _list(detail.get("child")):
                variant_data = _mapping(variant)
                variant_raw_id = variant_data.get("id")
                if variant_raw_id is None:
                    continue
                variant_id = str(variant_raw_id)
                self._add(
                    _entity(
                        "monster_variant", variant_id, version=self.version,
                        payload={"monster_id": monster_id, **variant_data},
                        provenance=self._provenance(detail_path),
                        reconstruction_status="RECONSTRUCTION_READY",
                        original_game_id=variant_raw_id,
                    )
                )
                self._rel("monster_variant", monster_id=monster_id, variant_id=variant_id)
                for skill in _list(variant_data.get("skill_list")):
                    skill_data = _mapping(skill)
                    skill_raw_id = skill_data.get("id")
                    if skill_raw_id is None:
                        continue
                    occurrence_id = f"{variant_id}:{skill_raw_id}"
                    self._add(
                        _entity(
                            "monster_skill", occurrence_id, version=self.version,
                            payload={"monster_id": monster_id, "variant_id": variant_id, "original_skill_id": skill_raw_id, **skill_data},
                            provenance=self._provenance(detail_path),
                            reconstruction_status="RECONSTRUCTION_READY",
                            original_game_id=skill_raw_id,
                        )
                    )
                    self._rel("monster_variant_skill", monster_id=monster_id, variant_id=variant_id, monster_skill_id=occurrence_id, original_skill_id=str(skill_raw_id))

    def _build_stages(self) -> None:
        for collection_name in ("maze", "maze_extra", "maze_boss"):
            collection_path = f"collections/{collection_name}.json"
            collection = _mapping(self._load(collection_path))
            for entity_id, data in sorted(collection.items(), key=lambda item: _numeric_key(str(item[0]))):
                detail_endpoint = DETAIL_COLLECTIONS.get(collection_name)
                detail_path = (
                    f"detail/{detail_endpoint}/{entity_id}.json"
                    if detail_endpoint is not None
                    else None
                )
                self._add(
                    _entity(
                        "mode_metadata", f"{collection_name}:{entity_id}", version=self.version,
                        payload={
                            "collection": collection_name,
                            "collection_entry": _mapping(data),
                            "detail": self._load(detail_path) if detail_path else None,
                        },
                        provenance=self._provenance(
                            collection_path,
                            *([detail_path] if detail_path else []),
                        ),
                        reconstruction_status="RECONSTRUCTION_READY",
                        original_game_id=entity_id,
                    )
                )
        boss_dir = self.snapshot_root / "detail" / "boss"
        for detail_path in sorted(boss_dir.glob("*.json"), key=lambda path: _numeric_key(path.stem)) if boss_dir.exists() else []:
            boss_id = detail_path.stem
            detail = _mapping(read_json(detail_path))
            relative = str(detail_path.relative_to(self.snapshot_root)).replace("\\", "/")
            for difficulty in _list(detail.get("level")):
                difficulty_row = _mapping(difficulty)
                for lane_key in ("event_id_list1", "event_id_list2"):
                    for event_index, event in enumerate(_list(difficulty_row.get(lane_key))):
                        event_row = _mapping(event)
                        self._register_stage_event(
                            event_row,
                            relative,
                            source_context={
                                "source_mode": "boss",
                                "boss_id": boss_id,
                                "difficulty_id": difficulty_row.get("id"),
                                "difficulty_name": difficulty_row.get("name"),
                                "lane": lane_key,
                                "event_index": event_index,
                            },
                        )

        maze_dir = self.snapshot_root / "detail" / "maze"
        for detail_path in sorted(maze_dir.glob("*.json"), key=lambda path: _numeric_key(path.stem)) if maze_dir.exists() else []:
            raw_payload = read_json(detail_path)
            if not isinstance(raw_payload, list):
                # Maze records used as binding details are handled only when a
                # Stage references them; they are not encounter lists.
                continue
            maze_id = detail_path.stem
            relative = str(detail_path.relative_to(self.snapshot_root)).replace("\\", "/")
            for record_index, record in enumerate(raw_payload):
                record_row = _mapping(record)
                record_context = {
                    key: value
                    for key, value in record_row.items()
                    if key not in {"event_id_list1", "event_id_list2"}
                }
                for lane_key in ("event_id_list1", "event_id_list2"):
                    for event_index, event in enumerate(_list(record_row.get(lane_key))):
                        self._register_stage_event(
                            _mapping(event),
                            relative,
                            source_context={
                                "source_mode": "maze",
                                "maze_id": maze_id,
                                "maze_record_id": record_row.get("id"),
                                "maze_record_index": record_index,
                                "maze_context": record_context,
                                "lane": lane_key,
                                "event_index": event_index,
                            },
                        )

        story_dir = self.snapshot_root / "detail" / "story"
        for detail_path in sorted(story_dir.glob("*.json"), key=lambda path: _numeric_key(path.stem)) if story_dir.exists() else []:
            story = _mapping(read_json(detail_path))
            story_id = detail_path.stem
            relative = str(detail_path.relative_to(self.snapshot_root)).replace("\\", "/")
            story_metadata = {key: value for key, value in story.items() if key != "level"}
            for level_index, level in enumerate(_list(story.get("level"))):
                level_row = _mapping(level)
                level_context = {
                    key: value
                    for key, value in level_row.items()
                    if key not in {"event_id_list1", "event_id_list2"}
                }
                for lane_key in ("event_id_list1", "event_id_list2"):
                    for event_index, event in enumerate(_list(level_row.get(lane_key))):
                        self._register_stage_event(
                            _mapping(event),
                            relative,
                            source_context={
                                "source_mode": "story",
                                "story_id": story_id,
                                "story_name": story.get("name"),
                                "story_level_id": level_row.get("id"),
                                "story_level_index": level_index,
                                "story_metadata": story_metadata,
                                "story_level_context": level_context,
                                "lane": lane_key,
                                "event_index": event_index,
                            },
                        )

    def _register_stage_event(
        self,
        event: Mapping[str, Any],
        relative: str,
        *,
        source_context: Mapping[str, Any],
    ) -> None:
        raw_stage_id = event.get("stage_id")
        if raw_stage_id is None:
            return
        stage_id = str(raw_stage_id)
        source_mode = str(source_context.get("source_mode", "unknown"))
        encounter_id = ":".join(
            str(value)
            for value in (
                source_mode,
                source_context.get(
                    "boss_id",
                    source_context.get("maze_id", source_context.get("story_id", "unknown")),
                ),
                source_context.get(
                    "difficulty_id",
                    source_context.get("maze_record_id", source_context.get("story_level_id", "unknown")),
                ),
                source_context.get("lane", "unknown"),
                source_context.get("event_index", "unknown"),
            )
        )
        encounter_payload = {**source_context, "stage_id": raw_stage_id}
        self._add(
            _entity(
                "encounter", encounter_id, version=self.version,
                payload=encounter_payload,
                provenance=self._provenance(relative),
                reconstruction_status="RECONSTRUCTION_READY",
                original_game_id=None,
                game_id_status="DERIVED_FROM_PARENT",
            )
        )
        self._rel("encounter_stage", encounter_id=encounter_id, stage_id=stage_id)
        self._add(
            _entity(
                "stage", stage_id, version=self.version, payload=dict(event),
                provenance=self._provenance(relative),
                reconstruction_status="RECONSTRUCTION_READY" if event.get("monster_list") else "PARTIAL",
                original_game_id=raw_stage_id,
            )
        )
        self._build_stage_wave(stage_id, event, relative)

    def _build_stage_wave(self, stage_id: str, event: Mapping[str, Any], relative: str) -> None:
        wave_index = 1
        buff_ids: list[str] = []
        for item in _list(event.get("stage_config_data")):
            row = _mapping(item)
            if row.get("jdkamoanicm") == "_Wave":
                try:
                    wave_index = int(row.get("mojjbfbkbnc", 1))
                except (TypeError, ValueError):
                    pass
            if row.get("jdkamoanicm") == "_BindingMazeBuff" and row.get("mojjbfbkbnc") is not None:
                buff_ids.append(str(row["mojjbfbkbnc"]))
        wave_id = f"{stage_id}:{wave_index}"
        self._add(
            _entity(
                "wave", wave_id, version=self.version,
                payload={"stage_id": stage_id, "wave_index": wave_index, "source_monster_list": _list(event.get("monster_list")), "level": event.get("level")},
                provenance=self._provenance(relative),
                reconstruction_status="RECONSTRUCTION_READY" if event.get("monster_list") else "PARTIAL",
                original_game_id=None,
                game_id_status="DERIVED_FROM_STAGE",
            )
        )
        self._rel("stage_wave", stage_id=stage_id, wave_id=wave_id, wave_index=wave_index)
        for group_index, group in enumerate(_list(event.get("monster_list"))):
            group_row = _mapping(group)
            for slot, value in sorted(group_row.items()):
                if not str(slot).startswith("monster") or value is None:
                    continue
                occurrence_id = f"{wave_id}:{group_index}:{slot}"
                self._add(
                    _entity(
                        "wave_monster", occurrence_id, version=self.version,
                        payload={"stage_id": stage_id, "wave_id": wave_id, "wave_index": wave_index, "group_index": group_index, "slot": slot, "monster_id": value, "level": event.get("level")},
                        provenance=self._provenance(relative),
                        reconstruction_status="RECONSTRUCTION_READY",
                        original_game_id=value,
                    )
                )
                self._rel("wave_monster", stage_id=stage_id, wave_id=wave_id, wave_monster_id=occurrence_id, monster_id=str(value), level=event.get("level"))
        for buff_id in sorted(set(buff_ids), key=_numeric_key):
            buff_detail_path = f"detail/maze/{buff_id}.json"
            buff_detail = _mapping(self._load(buff_detail_path))
            resolved = bool(buff_detail)
            self._add(
                _entity(
                    "stage_buff", buff_id, version=self.version,
                    payload={"binding_id": buff_id, "detail": buff_detail, "source": "_BindingMazeBuff"},
                    # A Buff is one versioned entity even when many Stages bind
                    # it.  The Stage-specific source belongs to the relation.
                    provenance=self._provenance(buff_detail_path),
                    reconstruction_status="RECONSTRUCTION_READY" if resolved else "PARTIAL",
                    original_game_id=int(buff_id) if buff_id.isdigit() else buff_id,
                )
            )
            self._rel(
                "stage_buff",
                stage_id=stage_id,
                buff_id=buff_id,
                resolved=resolved,
                source_refs=self._provenance(relative, buff_detail_path),
            )

    def _build_validation(self) -> None:
        artifact = project_root() / "data" / "raw" / self.version / "natasha_skill02_healhp_content_30.json"
        if artifact.exists():
            self.validation.append(
                {
                    "validation_id": "avatar:1105:Natasha:local-ability-name",
                    "entity_type": "avatar",
                    "entity_id": "1105",
                    "field": "identity",
                    "status": "TRANSFORM_EQUIVALENT",
                    "external_value": "Natasha",
                    "local_value": "Avatar_Natasha_00_Skill02_Phase02",
                    "local_evidence_ref": str(artifact.relative_to(project_root())).replace("\\", "/"),
                    "confidence_after": "C1_MULTI_SOURCE_MATCH",
                }
            )
        else:
            self.validation.append(
                {
                    "validation_id": "local-design-data-presence",
                    "entity_type": "snapshot",
                    "entity_id": self.version,
                    "field": "local_evidence",
                    "status": "LOCAL_MISSING",
                    "external_value": "Nanoka snapshot",
                    "local_value": None,
                    "local_evidence_ref": None,
                    "confidence_after": "C0_EXTERNAL_ONLY",
                }
            )

    def _build_static_gaps(self) -> None:
        item = _mapping(self._load("auxiliary/item.json"))
        has_affix_schema = any(
            isinstance(node, Mapping) and any("affix" in str(key).lower() for key in node)
            for node in _walk(item)
        )
        if not has_affix_schema:
            self.static_gaps.append(
                {
                    "gap_id": "RELIC_AFFIX_SCHEMA",
                    "category": "relic_affix",
                    "status": "NEEDS_STATIC_RECOVERY",
                    "detail": "Nanoka item payload does not expose a recognized main/sub-affix schema to the adapter.",
                }
            )
        for auxiliary_name in ("EliteGroup", "HardLevelGroup"):
            if not (self.snapshot_root / "auxiliary" / f"{auxiliary_name}.json").exists():
                self.static_gaps.append(
                    {
                        "gap_id": f"AUXILIARY_{auxiliary_name.upper()}",
                        "category": "monster_stage_auxiliary",
                        "status": "EXTERNAL_MISSING",
                        "detail": f"Nanoka's documented {auxiliary_name}.json endpoint was unavailable for this snapshot.",
                    }
                )
        for monster in self.records.get("monster", []):
            detail = _mapping(_mapping(monster.get("data")).get("detail"))
            if detail and not _list(detail.get("child")):
                self.static_gaps.append(
                    {
                        "gap_id": f"MONSTER_VARIANT_LIST:{monster['entity_id']}",
                        "category": "monster_variant",
                        "status": "PARTIAL",
                        "detail": "Monster detail has base stats but no child/variant list to establish its ability relation.",
                    }
                )
        stage_buff_relations = self.relations.get("stage_buff", [])
        unresolved = [row for row in stage_buff_relations if not row.get("resolved")]
        if unresolved:
            self.static_gaps.append(
                {
                    "gap_id": "STAGE_BUFF_DETAIL",
                    "category": "stage_buff",
                    "status": "PARTIAL",
                    "detail": "Stage bindings exist but some referenced maze-buff detail records are unavailable.",
                    "affected_count": len(unresolved),
                }
            )
        story_dir = self.snapshot_root / "detail" / "story"
        if not story_dir.exists():
            self.static_gaps.append(
                {
                    "gap_id": "STORY_STAGE_DETAIL",
                    "category": "stage",
                    "status": "NEEDS_STATIC_RECOVERY",
                    "detail": "No story collection endpoint was provided by the fetched 4.4.54 collection set; story detail coverage is unknown.",
                }
            )
        else:
            story_has_stage_link = any(
                isinstance(node, Mapping) and "stage_id" in node
                for path in story_dir.glob("*.json")
                for node in _walk(read_json(path))
            )
            if not story_has_stage_link:
                self.static_gaps.append(
                    {
                        "gap_id": "STORY_STAGE_ENCOUNTER_LINK",
                        "category": "stage",
                        "status": "NEEDS_STATIC_RECOVERY",
                        "detail": "Fetched Story detail records expose mode/buff/option metadata but no direct Stage→Wave encounter link.",
                    }
                )


def _dynamic_gaps(version: str) -> list[dict[str, Any]]:
    return [
        {"gap_id": identifier, "game_version": version, "status": "NEEDS_DYNAMIC_SEMANTICS", "detail": detail}
        for identifier, detail in (
            ("DAMAGE_REQUEST_AND_FORMULA", "Damage request construction, field binding, formula ordering, and dispatch."),
            ("HEALDATA_CONSUMER", "HealData listener/consumer chain and positive CurrentHP mutation."),
            ("SKILL_POINT_BOUNDARY", "Skill Point holder, mutation, clamp, and action ordering."),
            ("ENERGY_AND_ULT_GATE", "Energy mutation, cap, and Ultimate legality timing."),
            ("TURN_RECHARGE", "Post-action Property 38 writer and next-delay formula."),
            ("EVENT_ORDERING", "Concrete event listener ordering and callback effects."),
            ("MODIFIER_LIFECYCLE", "Refresh/replace/cleanup behavior outside already proven slices."),
            ("DEATH_AND_VICTORY", "Death state and GameMode terminal predicates."),
            ("TARGET_AND_ACTION_LEGALITY", "Target filtering and player-action bridge."),
            ("BREAK_FOLLOWUP_SUMMON", "Break, follow-up, extra action, and summon runtime sequencing."),
        )
    ]


def emit_canonical(build: CanonicalBuild, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    for entity_type, rows in sorted(build.records.items()):
        write_jsonl(output_root / f"{entity_type}.jsonl", rows)
    for relation_type, rows in sorted(build.relations.items()):
        write_json(output_root / "relations" / f"{relation_type}.json", sorted(rows, key=stable_bytes))
    write_json(output_root / "validation" / "local_validation.json", build.validation)
    write_json(output_root / "validation" / "nanoka_static_gaps.json", build.static_gaps)
    write_json(output_root / "validation" / "dynamic_semantic_gaps.json", build.dynamic_gaps)
    coverage = coverage_report(build)
    write_json(output_root / "validation" / "reconstruction_coverage.json", coverage)
    write_json(output_root / "validation" / "database_health.json", database_health_report(build))
    return coverage


def coverage_report(build: CanonicalBuild) -> dict[str, Any]:
    def status_counts(entity_type: str) -> dict[str, int]:
        rows = build.records.get(entity_type, [])
        return {
            "total": len(rows),
            "reconstruction_ready": sum(row["reconstruction_status"] == "RECONSTRUCTION_READY" for row in rows),
            "partial": sum(row["reconstruction_status"] == "PARTIAL" for row in rows),
            "failed": 0,
        }
    report = {
        "schema": "hsr_battle_agent.reconstruction_coverage/1",
        "game_version": build.version,
        "families": {
            "avatar": status_counts("avatar"),
            "skill": status_counts("skill"),
            "trace": status_counts("trace"),
            "eidolon": status_counts("eidolon"),
            "lightcone": status_counts("lightcone"),
            "relic_set": status_counts("relic_set"),
            "relic_affix": {"total": 0, "reconstruction_ready": 0, "partial": 0, "failed": 0},
            "monster": status_counts("monster"),
        "monster_skill": status_counts("monster_skill"),
            "encounter": status_counts("encounter"),
            "stage": status_counts("stage"),
            "wave": status_counts("wave"),
            "wave_monster": status_counts("wave_monster"),
            "stage_buff": status_counts("stage_buff"),
            "stage_to_buff": {
                "total": len(build.relations.get("stage_buff", [])),
                "reconstruction_ready": sum(bool(row.get("resolved")) for row in build.relations.get("stage_buff", [])),
                "partial": sum(not bool(row.get("resolved")) for row in build.relations.get("stage_buff", [])),
                "failed": 0,
            },
        },
    }
    report["canonical_sha256"] = stable_hash(report)
    return report


def database_health_report(build: CanonicalBuild) -> dict[str, Any]:
    """Explicit integrity findings; unresolved source facts are never hidden."""
    entity_ids = {
        entity_type: {str(row["entity_id"]) for row in rows}
        for entity_type, rows in build.records.items()
    }

    def relation_rows(name: str) -> list[Mapping[str, Any]]:
        return build.relations.get(name, [])

    def missing_owner(relation: str, owner_key: str, owner_type: str) -> list[str]:
        owners = entity_ids.get(owner_type, set())
        return sorted({str(row[owner_key]) for row in relation_rows(relation) if str(row[owner_key]) not in owners}, key=_numeric_key)

    avatar_skills = relation_rows("avatar_skill")
    attached_skills = {str(row["skill_id"]) for row in avatar_skills}
    orphan_skills = sorted(entity_ids.get("skill", set()) - attached_skills, key=_numeric_key)
    rank_counts: dict[str, int] = {}
    for row in relation_rows("avatar_eidolon"):
        rank_counts[str(row["avatar_id"])] = rank_counts.get(str(row["avatar_id"]), 0) + 1
    not_six_eidolons = sorted(
        avatar_id for avatar_id in entity_ids.get("avatar", set()) if rank_counts.get(avatar_id, 0) != 6
    )
    known_monsters = entity_ids.get("monster", set()) | entity_ids.get("monster_variant", set())
    unknown_monster_refs = sorted(
        {str(row["monster_id"]) for row in relation_rows("wave_monster") if str(row["monster_id"]) not in known_monsters},
        key=_numeric_key,
    )
    known_stages = entity_ids.get("stage", set())
    known_waves = entity_ids.get("wave", set())
    wave_without_stage = sorted(
        {str(row["wave_id"]) for row in relation_rows("stage_wave") if str(row["stage_id"]) not in known_stages}, key=_numeric_key
    )
    stage_without_wave = sorted(
        known_stages - {str(row["stage_id"]) for row in relation_rows("stage_wave")}, key=_numeric_key
    )
    unknown_buff_refs = sorted(
        {str(row["buff_id"]) for row in relation_rows("stage_buff") if not bool(row.get("resolved"))}, key=_numeric_key
    )
    relation_duplicates = {
        relation_type: len(rows) - len({stable_hash(row) for row in rows})
        for relation_type, rows in build.relations.items()
    }
    version_contamination = {
        "entity_records": sum(
            1 for rows in build.records.values() for row in rows if row.get("game_version") != build.version
        ),
        "relations": sum(
            1 for rows in build.relations.values() for row in rows if row.get("game_version") != build.version
        ),
    }
    report = {
        "schema": "hsr_battle_agent.content_database_health/1",
        "game_version": build.version,
        "duplicate_entity_ids": [],  # CanonicalBuilder keying prevents silent duplicates.
        "duplicate_relation_rows": relation_duplicates,
        "missing_owners": {
            "avatar_skill": missing_owner("avatar_skill", "avatar_id", "avatar"),
            "avatar_trace": missing_owner("avatar_trace", "avatar_id", "avatar"),
            "avatar_eidolon": missing_owner("avatar_eidolon", "avatar_id", "avatar"),
        },
        "orphan_skill_ids": orphan_skills,
        "avatars_without_exactly_six_eidolons": not_six_eidolons,
        "unknown_monster_refs": unknown_monster_refs,
        "unknown_stage_buff_refs": unknown_buff_refs,
        "stage_wave_consistency": {
            "stage_without_wave": stage_without_wave,
            "wave_without_stage": wave_without_stage,
            "wave_entity_count": len(known_waves),
        },
        "version_contamination": version_contamination,
    }
    report["health_sha256"] = stable_hash(report)
    return report


def diff_collection_snapshots(
    from_root: Path,
    to_root: Path,
    *,
    from_version: str,
    to_version: str,
) -> dict[str, Any]:
    """Describe a collection-level version delta without mixing its values.

    This intentionally compares only raw collection entries.  It is a compact
    discovery/validation report, not a request to import newer detail data.
    """
    collections: dict[str, Any] = {}
    for collection_name in COLLECTIONS:
        old = _mapping(read_json(from_root / "collections" / f"{collection_name}.json"))
        new = _mapping(read_json(to_root / "collections" / f"{collection_name}.json"))
        old_ids = {str(identifier) for identifier in old}
        new_ids = {str(identifier) for identifier in new}
        shared = sorted(old_ids & new_ids, key=_numeric_key)
        changed = [
            identifier
            for identifier in shared
            if stable_hash(old.get(identifier)) != stable_hash(new.get(identifier))
        ]
        old_keys = sorted({str(key) for row in old.values() if isinstance(row, Mapping) for key in row})
        new_keys = sorted({str(key) for row in new.values() if isinstance(row, Mapping) for key in row})
        collections[collection_name] = {
            "from_count": len(old_ids),
            "to_count": len(new_ids),
            "added_ids": sorted(new_ids - old_ids, key=_numeric_key),
            "removed_ids": sorted(old_ids - new_ids, key=_numeric_key),
            "changed_ids": changed,
            "schema_keys_added": sorted(set(new_keys) - set(old_keys)),
            "schema_keys_removed": sorted(set(old_keys) - set(new_keys)),
        }
    result = {
        "schema": "hsr_battle_agent.nanoka_collection_delta/1",
        "from_version": from_version,
        "to_version": to_version,
        "collections": collections,
    }
    result["delta_sha256"] = stable_hash(result)
    return result


ENTITY_TABLES: Mapping[str, str] = {
    "avatar": "avatars",
    "skill": "skills",
    "trace": "traces",
    "eidolon": "eidolons",
    "lightcone": "lightcones",
    "lightcone_promotion": "lightcone_promotions",
    "lightcone_superimposition": "lightcone_superimpositions",
    "relic_set": "relic_sets",
    "relic_item": "relic_items",
    "monster": "monsters",
    "monster_variant": "monster_variants",
    "monster_skill": "monster_skills",
    "encounter": "encounters",
    "mode_metadata": "mode_metadata",
    "stage": "stages",
    "wave": "waves",
    "wave_monster": "wave_monsters",
    "stage_buff": "stage_buffs",
}

RELATION_TABLES: Mapping[str, str] = {
    "avatar_skill": "avatar_skills",
    "avatar_trace": "avatar_traces",
    "avatar_eidolon": "avatar_eidolons",
    "lightcone_promotion": "lightcone_promotion_relations",
    "lightcone_superimposition": "lightcone_superimposition_relations",
    "relic_set_item": "relic_set_items",
    "monster_variant": "monster_relations",
    "monster_variant_skill": "monster_skill_relations",
    "encounter_stage": "encounter_stage_relations",
    "stage_wave": "stage_waves",
    "wave_monster": "wave_monster_relations",
    "stage_buff": "stage_buff_relations",
}


def _create_database_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        PRAGMA journal_mode = DELETE;
        PRAGMA synchronous = FULL;
        CREATE TABLE content_versions (
          game_version TEXT PRIMARY KEY, build_schema TEXT NOT NULL, canonical_sha256 TEXT NOT NULL
        );
        CREATE TABLE source_snapshots (
          game_version TEXT NOT NULL, raw_relative_path TEXT NOT NULL, source_url TEXT,
          source_category TEXT, source_entity_id TEXT, locale TEXT, etag TEXT,
          last_modified TEXT, fetch_time TEXT, raw_sha256 TEXT, raw_size INTEGER,
          PRIMARY KEY (game_version, raw_relative_path)
        );
        CREATE TABLE validation_results (
          game_version TEXT NOT NULL, validation_id TEXT NOT NULL, entity_type TEXT,
          entity_id TEXT, field_name TEXT, status TEXT NOT NULL, external_value_json TEXT,
          local_value_json TEXT, local_evidence_ref TEXT, confidence_after TEXT,
          PRIMARY KEY (game_version, validation_id)
        );
        CREATE TABLE content_gaps (
          game_version TEXT NOT NULL, gap_id TEXT NOT NULL, gap_kind TEXT NOT NULL,
          status TEXT NOT NULL, detail_json TEXT NOT NULL,
          PRIMARY KEY (game_version, gap_kind, gap_id)
        );
        """
    )
    for table in ENTITY_TABLES.values():
        connection.execute(
            f"CREATE TABLE {table} (game_version TEXT NOT NULL, entity_id TEXT NOT NULL, original_game_id TEXT, game_id_status TEXT NOT NULL, confidence TEXT NOT NULL, reconstruction_status TEXT NOT NULL, payload_json TEXT NOT NULL, provenance_json TEXT NOT NULL, canonical_sha256 TEXT NOT NULL, PRIMARY KEY (game_version, entity_id))"
        )
    for table in RELATION_TABLES.values():
        connection.execute(
            f"CREATE TABLE {table} (game_version TEXT NOT NULL, relation_key TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY (game_version, relation_key))"
        )


def build_sqlite(
    build: CanonicalBuild,
    *,
    snapshot_root: Path,
    database_path: Path,
) -> dict[str, Any]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = database_path.with_suffix(database_path.suffix + ".part")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    try:
        _create_database_schema(connection)
        coverage = coverage_report(build)
        connection.execute(
            "INSERT INTO content_versions VALUES (?, ?, ?)",
            (build.version, "hsr_battle_agent.nanoka_content/1", coverage["canonical_sha256"]),
        )
        index = _mapping(read_json(snapshot_root / "provenance" / "index.json"))
        for relative_path, row in sorted(index.items()):
            source = _mapping(row)
            connection.execute(
                "INSERT INTO source_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (build.version, relative_path, source.get("source_url"), source.get("source_category"), source.get("source_entity_id"), source.get("locale"), source.get("etag"), source.get("last_modified"), source.get("fetch_time"), source.get("raw_sha256"), source.get("raw_size")),
            )
        for entity_type, rows in build.records.items():
            table = ENTITY_TABLES[entity_type]
            for record in sorted(rows, key=lambda row: str(row["entity_id"])):
                connection.execute(
                    f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (record["game_version"], record["entity_id"], str(record.get("original_game_id")), record["game_id_status"], record["confidence"], record["reconstruction_status"], json.dumps(record["data"], ensure_ascii=False, sort_keys=True), json.dumps(record["provenance"], ensure_ascii=False, sort_keys=True), record["canonical_sha256"]),
                )
        for relation_type, rows in build.relations.items():
            table = RELATION_TABLES[relation_type]
            seen_relation_keys: set[str] = set()
            for row in sorted(rows, key=stable_bytes):
                relation_key = stable_hash(row)
                if relation_key in seen_relation_keys:
                    # Identical source rows are collection-level duplicates,
                    # not separate game relationships.  Health output reports
                    # their count; SQLite keeps the logical relation once.
                    continue
                seen_relation_keys.add(relation_key)
                connection.execute(
                    f"INSERT INTO {table} VALUES (?, ?, ?)",
                    (build.version, relation_key, json.dumps(row, ensure_ascii=False, sort_keys=True)),
                )
        for row in build.validation:
            connection.execute(
                "INSERT INTO validation_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (build.version, row["validation_id"], row.get("entity_type"), row.get("entity_id"), row.get("field"), row["status"], json.dumps(row.get("external_value"), ensure_ascii=False), json.dumps(row.get("local_value"), ensure_ascii=False), row.get("local_evidence_ref"), row.get("confidence_after")),
            )
        for gap_kind, gaps in (("NANOKA_STATIC_GAPS", build.static_gaps), ("DYNAMIC_SEMANTIC_GAPS", build.dynamic_gaps)):
            for row in gaps:
                connection.execute(
                    "INSERT INTO content_gaps VALUES (?, ?, ?, ?, ?)",
                    (build.version, row["gap_id"], gap_kind, row["status"], json.dumps(row, ensure_ascii=False, sort_keys=True)),
                )
        connection.commit()
        connection.execute("VACUUM")
        connection.commit()
    finally:
        connection.close()
    temporary.replace(database_path)
    logical_hash = sqlite_logical_hash(database_path)
    return {"sqlite_path": str(database_path), "logical_sha256": logical_hash, "coverage": coverage_report(build)}


def sqlite_logical_hash(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        content: dict[str, list[tuple[Any, ...]]] = {}
        for table in tables:
            names = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
            order = ", ".join(names)
            content[table] = list(connection.execute(f"SELECT {order} FROM {table} ORDER BY {order}"))
        return stable_hash(content)
    finally:
        connection.close()


class ContentDatabase:
    """Read-only stable query facade for Canonical SQLite content."""

    def __init__(self, database_path: Path, game_version: str) -> None:
        self.database_path = database_path
        self.game_version = game_version

    def _entity(self, table: str, entity_id: str | int) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                f"SELECT entity_id, original_game_id, game_id_status, confidence, reconstruction_status, payload_json, provenance_json, canonical_sha256 FROM {table} WHERE game_version=? AND entity_id=?",
                (self.game_version, str(entity_id)),
            ).fetchone()
        if row is None:
            return None
        return {
            "game_version": self.game_version,
            "entity_id": row[0],
            "original_game_id": row[1],
            "game_id_status": row[2],
            "confidence": row[3],
            "reconstruction_status": row[4],
            "data": json.loads(row[5]),
            "provenance": json.loads(row[6]),
            "canonical_sha256": row[7],
        }

    def get_avatar(self, avatar_id: str | int) -> dict[str, Any] | None:
        return self._entity("avatars", avatar_id)

    def get_skill(self, skill_id: str | int) -> dict[str, Any] | None:
        return self._entity("skills", skill_id)

    def get_lightcone(self, lightcone_id: str | int) -> dict[str, Any] | None:
        return self._entity("lightcones", lightcone_id)

    def get_relic_set(self, relic_set_id: str | int) -> dict[str, Any] | None:
        return self._entity("relic_sets", relic_set_id)

    def get_monster(self, monster_id: str | int) -> dict[str, Any] | None:
        return self._entity("monsters", monster_id)

    def get_encounter(self, encounter_id: str) -> dict[str, Any] | None:
        return self._entity("encounters", encounter_id)

    def get_stage(self, stage_id: str | int) -> dict[str, Any] | None:
        return self._entity("stages", stage_id)

    def get_stage_package(self, stage_id: str | int) -> dict[str, Any] | None:
        stage = self.get_stage(stage_id)
        if stage is None:
            return None
        stage_id_text = str(stage_id)
        with closing(sqlite3.connect(self.database_path)) as connection:
            wave_rows = connection.execute(
                "SELECT entity_id, payload_json, provenance_json FROM waves WHERE game_version=? AND json_extract(payload_json, '$.stage_id')=? ORDER BY CAST(json_extract(payload_json, '$.wave_index') AS INTEGER), entity_id",
                (self.game_version, stage_id_text),
            ).fetchall()
            buff_rows = connection.execute(
                "SELECT payload_json FROM stage_buff_relations WHERE game_version=?", (self.game_version,)
            ).fetchall()
            encounter_relation_rows = connection.execute(
                "SELECT payload_json FROM encounter_stage_relations WHERE game_version=? AND json_extract(payload_json, '$.stage_id')=?",
                (self.game_version, stage_id_text),
            ).fetchall()
        waves: list[dict[str, Any]] = []
        source_refs = list(stage["provenance"])
        unresolved: list[dict[str, Any]] = []
        for wave_id, payload_json, provenance_json in wave_rows:
            wave_data = json.loads(payload_json)
            source_refs.extend(json.loads(provenance_json))
            monsters: list[dict[str, Any]] = []
            with closing(sqlite3.connect(self.database_path)) as connection:
                rows = connection.execute(
                    "SELECT payload_json, provenance_json FROM wave_monsters WHERE game_version=? AND json_extract(payload_json, '$.wave_id')=? ORDER BY CAST(json_extract(payload_json, '$.group_index') AS INTEGER), json_extract(payload_json, '$.slot')",
                    (self.game_version, wave_id),
                ).fetchall()
            for monster_payload, monster_provenance in rows:
                monster_data = json.loads(monster_payload)
                monster_id = str(monster_data["monster_id"])
                resolution = self.get_monster(monster_id) or self._entity("monster_variants", monster_id)
                if resolution is None:
                    unresolved.append({"kind": "monster", "monster_id": monster_id, "status": "UNKNOWN"})
                monsters.append({
                    "monster_id": monster_data["monster_id"],
                    "level": monster_data.get("level"),
                    "group_index": monster_data["group_index"],
                    "slot": monster_data["slot"],
                    "resolution_status": "RESOLVED" if resolution else "UNKNOWN",
                })
                source_refs.extend(json.loads(monster_provenance))
            waves.append({"wave_id": wave_id, "wave_index": wave_data["wave_index"], "enemy_groups": monsters})
        buffs: list[dict[str, Any]] = []
        for (payload_json,) in buff_rows:
            row = json.loads(payload_json)
            if str(row.get("stage_id")) != stage_id_text:
                continue
            source_refs.extend(row.get("source_refs", []))
            buff = self._entity("stage_buffs", row["buff_id"])
            if buff is None or not row.get("resolved"):
                unresolved.append({"kind": "stage_buff", "buff_id": row["buff_id"], "status": "UNKNOWN"})
            buffs.append({"buff_id": row["buff_id"], "resolution_status": "RESOLVED" if buff and row.get("resolved") else "UNKNOWN"})
        encounter_contexts: list[dict[str, Any]] = []
        for (payload_json,) in encounter_relation_rows:
            relation = json.loads(payload_json)
            encounter = self.get_encounter(relation["encounter_id"])
            if encounter is None:
                unresolved.append({"kind": "encounter", "encounter_id": relation["encounter_id"], "status": "UNKNOWN"})
                continue
            source_refs.extend(encounter["provenance"])
            encounter_contexts.append(
                {
                    "encounter_id": encounter["entity_id"],
                    "source_mode": encounter["data"].get("source_mode"),
                    "context": encounter["data"],
                }
            )
        unique_source_refs = {
            stable_hash(reference): reference for reference in source_refs
        }
        package = {
            "schema": "hsr_battle_agent.stage_package/1",
            "game_version": self.game_version,
            "stage_id": stage["original_game_id"],
            "mode": stage["data"].get("stage_type"),
            "waves": waves,
            "stage_buffs": buffs,
            "encounter_contexts": sorted(encounter_contexts, key=lambda row: str(row["encounter_id"])),
            "rule_metadata": {
                "win_conditions": stage["data"].get("level_win_condition", []),
                "lose_conditions": stage["data"].get("level_lose_condition", []),
                "stage_config_data": stage["data"].get("stage_config_data", []),
            },
            "source_refs": sorted(unique_source_refs.values(), key=stable_bytes),
            "unknown_references": unresolved,
        }
        package["package_sha256"] = stable_hash(package)
        return package


def build_from_snapshot(
    version: str,
    *,
    snapshot_root: Path | None = None,
    canonical_root: Path | None = None,
    database_path: Path | None = None,
) -> dict[str, Any]:
    snapshot = snapshot_root or default_snapshot_root(version)
    canonical = canonical_root or default_canonical_root(version)
    database = database_path or default_db_path(version)
    build = CanonicalBuilder(snapshot, version).build()
    coverage = emit_canonical(build, canonical)
    sqlite = build_sqlite(build, snapshot_root=snapshot, database_path=database)
    return {
        "game_version": version,
        "snapshot_root": str(snapshot),
        "canonical_root": str(canonical),
        "database": sqlite,
        "coverage": coverage,
        "static_gaps": build.static_gaps,
        "dynamic_gaps": build.dynamic_gaps,
    }
