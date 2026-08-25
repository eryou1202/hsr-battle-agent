"""Auditable external static reconstruction and pure numeric reference helpers.

This module is intentionally outside ``battle_runtime``.  It consumes a small,
pinned snapshot of four public repositories and can augment the version-locked
Nanoka SQLite database with *external* facts.  It never claims local runtime
proof, never reads local DesignData/reverse artifacts, and never mutates a
BattleState.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import base64
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .nanoka_content import ContentDatabase, _entity, read_json, stable_hash, write_json, write_jsonl


CONTENT_VERSION = "4.4.54"
GITHUB_API = "https://api.github.com"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _stable_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, Mapping):
        value = value.get("Value", default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class ExternalSource:
    """A selected, pinned upstream; this is not a claim of exact game parity."""

    name: str
    repository_url: str
    selected_commit: str
    selected_branch: str
    commit_date: str
    declared_game_version: str | None
    declared_game_build: str | None
    version_match: str
    license: str
    source_role: str
    usage_scope: str
    license_note: str


# These commits were selected from each repository's actual public history.
# The 4.4.54 Nanoka baseline remains the only exact-content oracle.  "CLOSE"
# data is retained as a separately-provenanced external fact, never an overwrite.
EXTERNAL_SOURCES: tuple[ExternalSource, ...] = (
    ExternalSource(
        name="TurnBasedGameData",
        repository_url="https://github.com/DimbreathBot/TurnBasedGameData",
        selected_commit="b11066beacc4de454b625fafc7ea3dd540c5bbf3",
        selected_branch="main",
        commit_date="2026-08-17T11:43:54Z",
        declared_game_version="4.4.0",
        declared_game_build="OSPRODWin4.4.0_D16085003_A16085003_L16155460",
        version_match="CLOSE",
        license="NOASSERTION",
        source_role="CLIENT_DUMP_REFERENCE",
        usage_scope="STATIC_FACT_REFERENCE",
        license_note="No repository LICENSE was declared at the selected source. Store only hashes/provenance and independently implement adapters; do not vendor source or data.",
    ),
    ExternalSource(
        name="StarRailRes",
        repository_url="https://github.com/Mar-7th/StarRailRes",
        selected_commit="02bdd75e1e3cf4272cea94165275c98a17ff1719",
        selected_branch="master",
        commit_date="2026-07-17T15:00:22Z",
        declared_game_version="4.4",
        declared_game_build=None,
        version_match="CLOSE",
        license="AGPL-3.0-only",
        source_role="CLIENT_DUMP_DERIVED",
        usage_scope="STRUCTURED_STATIC_CROSS_CHECK",
        license_note="AGPL-3.0 source is inspected as a data/schema reference only. This project does not copy or link its code/data tree.",
    ),
    ExternalSource(
        name="HSR-Mapping-DATA",
        repository_url="https://github.com/nathacks/HSR-Mapping-DATA",
        selected_commit="245f286185f5274609be264b6ef6dbc15e8a27ad",
        selected_branch="main",
        commit_date="2026-07-17T10:49:38Z",
        declared_game_version="4.0 (repository README; selected later maintenance commit)",
        declared_game_build=None,
        version_match="SCHEMA_ONLY",
        license="NOASSERTION",
        source_role="AUDITABLE_MAPPING",
        usage_scope="MAPPING_REFERENCE",
        license_note="No repository LICENSE was declared at the selected source. Its transformations are documented as evidence, then independently reimplemented.",
    ),
    ExternalSource(
        name="hsr-optimizer",
        repository_url="https://github.com/fribbels/hsr-optimizer",
        selected_commit="47ae66d8abac80b1f485a06fc11fe5e54c349c60",
        selected_branch="main",
        commit_date="2026-06-26T03:13:36Z",
        declared_game_version="4.4v5",
        declared_game_build=None,
        version_match="ALGORITHM_ONLY",
        license="MIT",
        source_role="MATURE_IMPLEMENTATION",
        usage_scope="NUMERIC_ALGORITHM_REFERENCE",
        license_note="MIT allows reuse with notice, but this project deliberately uses an independently-written, narrow reference evaluator rather than vendoring source.",
    ),
)


SOURCE_FILES: Mapping[str, tuple[str, ...]] = {
    "TurnBasedGameData": (
        "ExcelOutput/RelicConfig.json",
        "ExcelOutput/RelicMainAffixConfig.json",
        "ExcelOutput/RelicSubAffixConfig.json",
        "ExcelOutput/RelicMainAffixBaseValue.json",
        "ExcelOutput/RelicSubAffixBaseValue.json",
        "ExcelOutput/EliteGroup.json",
        "ExcelOutput/HardLevelGroup.json",
        "ExcelOutput/MazeBuff.json",
        "ExcelOutput/MonsterConfig.json",
        "ExcelOutput/MonsterTemplateConfig.json",
        "ExcelOutput/AvatarPromotionConfig.json",
        "ExcelOutput/EquipmentPromotionConfig.json",
        # Semantic-corpus vertical-slice inputs. These are exact, reviewed
        # paths at the pinned CLOSE 4.4.0 commit and remain isolated from the
        # exact-version Nanoka records. They are not a repository mirror.
        "Config/ConfigAbility/Avatar/Avatar_Natasha_00_Ability.json",
        "Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json",
        "Config/ConfigCharacter/Avatar/Avatar_Natasha_00_Config.json",
        "Config/ConfigCharacter/Avatar/Avatar_BlackSwan_00_Config.json",
        "Config/ConfigAbility/Monster/Monster_AML_Minion01_00_Ability.json",
        "Config/ConfigAbility/Level/Level_MazeBuff_Ability.json",
        "Config/ConfigAdventureModifier/AdventureModifier_MazeChallenge.json",
        "Config/ConfigAdventureModifier/AdventureModifier_MazeEnvi.json",
        "Config/ConfigGlobalModifier/GlobalModifier_Common_Property.json",
        "Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json",
    ),
    "StarRailRes": (
        "index_new/cn/relic_main_affixes.json",
        "index_new/cn/relic_sub_affixes.json",
        "index_new/cn/relics.json",
        "index_new/cn/relic_sets.json",
        "index_new/cn/characters.json",
        "index_new/cn/character_promotions.json",
        "index_new/cn/light_cones.json",
        "index_new/cn/light_cone_promotions.json",
    ),
    "HSR-Mapping-DATA": (
        "README.md",
        "src/loaders/relic_loader.py",
        "src/transformers/relic_transformer.py",
        "src/transformers/characters_transformer.py",
        "src/transformers/light_cone_transformer.py",
        "src/utils/field_mapping.py",
    ),
    "hsr-optimizer": (
        "LICENSE.md",
        "src/lib/optimization/engine/damage/damageCalculator.ts",
        "src/lib/relics/statCalculator.ts",
        "src/lib/constants/constants.ts",
    ),
}


class ExternalReferenceError(RuntimeError):
    """A pinned external snapshot cannot be read or fails its hash contract."""


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_external_root() -> Path:
    return project_root() / ".external_refs"


def default_external_canonical_root(version: str = CONTENT_VERSION) -> Path:
    return project_root() / "data" / "content" / version / "external_reconstruction"


def default_external_artifact_root(version: str = CONTENT_VERSION) -> Path:
    return project_root() / "data" / "semantics" / version / "external_reconstruction"


def _source_by_name(name: str) -> ExternalSource:
    for source in EXTERNAL_SOURCES:
        if source.name == name:
            return source
    raise KeyError(name)


class ExternalReferenceFetcher:
    """Fetch a deliberately small, commit-addressed external source snapshot.

    Git transport is intentionally not required.  GitHub's public contents/blob
    API gives every cached file both a source commit and content hash, avoiding
    a full third-party checkout or a blind mirror.
    """

    def __init__(self, root: Path | None = None, *, timeout_seconds: int = 45, retries: int = 3) -> None:
        self.root = root or default_external_root()
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    @staticmethod
    def _repository_path(source: ExternalSource) -> str:
        prefix = "https://github.com/"
        if not source.repository_url.startswith(prefix):
            raise ExternalReferenceError(f"unsupported repository URL: {source.repository_url}")
        return source.repository_url.removeprefix(prefix)

    def _request_json(self, url: str) -> Mapping[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "HSR-Battle-Agent/0.0 external-reference"})
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    return _mapping(json.loads(response.read().decode("utf-8")))
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if isinstance(exc, HTTPError) and exc.code not in {429, 500, 502, 503, 504}:
                    break
                time.sleep(1.0 * (attempt + 1))
        raise ExternalReferenceError(f"GitHub API request failed: {url}: {last_error}")

    def _fetch_file(self, source: ExternalSource, path: str) -> tuple[bytes, dict[str, Any]]:
        repo = self._repository_path(source)
        encoded_path = "/".join(quote(segment) for segment in path.split("/"))
        contents_url = f"{GITHUB_API}/repos/{repo}/contents/{encoded_path}?ref={source.selected_commit}"
        contents: Mapping[str, Any] = {}
        raw_url = f"https://raw.githubusercontent.com/{repo}/{source.selected_commit}/{encoded_path}"
        try:
            contents = self._request_json(contents_url)
            content = contents.get("content")
            if isinstance(content, str) and contents.get("encoding") == "base64":
                payload = base64.b64decode(content)
            else:
                blob_url = contents.get("git_url")
                if not isinstance(blob_url, str):
                    raise ExternalReferenceError(f"missing content/blob URL for {source.name}:{path}")
                blob = self._request_json(blob_url)
                if blob.get("encoding") != "base64" or not isinstance(blob.get("content"), str):
                    raise ExternalReferenceError(f"unsupported blob encoding for {source.name}:{path}")
                payload = base64.b64decode(str(blob["content"]))
        except ExternalReferenceError:
            # Raw is still commit-addressed, and is deliberately only a
            # rate-limit fallback.  Its absent Git blob metadata stays null
            # rather than being fabricated.
            try:
                request = Request(raw_url, headers={"User-Agent": "HSR-Battle-Agent/0.0 external-reference"})
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = response.read()
            except (HTTPError, URLError, TimeoutError) as exc:
                raise ExternalReferenceError(f"raw fallback failed for {source.name}:{path}: {exc}") from exc
        metadata = {
            "path": path,
            "contents_api_url": contents_url,
            "download_url": contents.get("download_url") or raw_url,
            "git_blob_url": contents.get("git_url"),
            "git_blob_sha": contents.get("sha"),
            "raw_sha256": _sha256_bytes(payload),
            "raw_size": len(payload),
            "fetched_at": _utc_now(),
        }
        return payload, metadata

    def fetch(self, source_names: Iterable[str] | None = None) -> dict[str, Any]:
        wanted = set(source_names or (source.name for source in EXTERNAL_SOURCES))
        results: dict[str, Any] = {}
        for source in EXTERNAL_SOURCES:
            if source.name not in wanted:
                continue
            base = self.root / source.name
            files: dict[str, Any] = {}
            previous_path = base / "manifest.json"
            previous = _mapping(read_json(previous_path)) if previous_path.exists() else {}
            previous_files = _mapping(previous.get("files"))
            def checkpoint() -> None:
                manifest = {
                    "schema": "hsr_battle_agent.external_reference_snapshot/1",
                    "source": source.name,
                    "repository_url": source.repository_url,
                    "selected_commit": source.selected_commit,
                    "selected_branch": source.selected_branch,
                    "commit_date": source.commit_date,
                    "declared_game_version": source.declared_game_version,
                    "declared_game_build": source.declared_game_build,
                    "version_match": source.version_match,
                    "license": source.license,
                    "source_role": source.source_role,
                    "usage_scope": source.usage_scope,
                    "license_note": source.license_note,
                    "local_clone_path": None,
                    "local_snapshot_path": str(base),
                    "files": dict(sorted(files.items())),
                }
                manifest["manifest_sha256"] = stable_hash(manifest)
                write_json(previous_path, manifest)
            for path in SOURCE_FILES[source.name]:
                destination = base / "files" / path
                old = _mapping(previous_files.get(path))
                if destination.exists() and old.get("raw_sha256"):
                    payload = destination.read_bytes()
                    if _sha256_bytes(payload) != old.get("raw_sha256"):
                        raise ExternalReferenceError(f"immutable external snapshot hash changed: {destination}")
                    files[path] = dict(old)
                    files[path]["fetch_status"] = "CACHED"
                    continue
                if destination.exists() and not old:
                    payload = destination.read_bytes()
                    files[path] = {
                        "path": path,
                        "contents_api_url": None,
                        "download_url": None,
                        "git_blob_url": None,
                        "git_blob_sha": None,
                        "raw_sha256": _sha256_bytes(payload),
                        "raw_size": len(payload),
                        "fetched_at": None,
                        "fetch_status": "RECOVERED_UNINDEXED",
                    }
                    checkpoint()
                    continue
                payload, metadata = self._fetch_file(source, path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(payload)
                metadata["fetch_status"] = "FETCHED"
                files[path] = metadata
                checkpoint()
            checkpoint()
            current_manifest = _mapping(read_json(previous_path))
            results[source.name] = {"files": len(files), "snapshot": str(base), "manifest_sha256": current_manifest.get("manifest_sha256")}
        return {"schema": "hsr_battle_agent.external_reference_fetch/1", "sources": results}

    def discover_paths(self, source_name: str, query_terms: Iterable[str]) -> dict[str, Any]:
        """Record a bounded, commit-addressed search of one repository tree.

        Discovery is intentionally separate from ``fetch``: it obtains only
        Git tree metadata and writes the matched paths plus their Git blob
        identities.  A later reviewed retrieval profile decides which payloads
        to cache.  This avoids both filename guesswork and broad repository
        mirroring.
        """
        source = _source_by_name(source_name)
        repo = self._repository_path(source)
        tree_url = f"{GITHUB_API}/repos/{repo}/git/trees/{source.selected_commit}?recursive=1"
        response = self._request_json(tree_url)
        entries = [
            {
                "path": str(raw.get("path")),
                "type": raw.get("type"),
                "git_blob_sha": raw.get("sha"),
                "size": raw.get("size"),
            }
            for raw in _list(response.get("tree"))
            if isinstance(raw, Mapping) and raw.get("type") == "blob" and isinstance(raw.get("path"), str)
        ]
        normalized_terms = [str(term) for term in query_terms if str(term).strip()]
        query_matches: dict[str, list[dict[str, Any]]] = {}
        for term in normalized_terms:
            # A query such as ``AvatarSkillConfig`` stays a literal substring;
            # whitespace-delimited terms use an all-token search to remain
            # useful across underscore/camel-case file naming.
            tokens = [token.casefold() for token in term.replace("_", " ").replace("-", " ").split()]
            needle = term.casefold()
            matches = [
                entry for entry in entries
                if needle in str(entry["path"]).casefold()
                or (tokens and all(token in str(entry["path"]).casefold() for token in tokens))
            ]
            query_matches[term] = sorted(matches, key=lambda item: str(item["path"]))
        artifact = {
            "schema": "hsr_battle_agent.external_reference_discovery/1",
            "source": source.name,
            "repository_url": source.repository_url,
            "selected_commit": source.selected_commit,
            "tree_url": tree_url,
            "fetched_at": _utc_now(),
            "tree_truncated": bool(response.get("truncated")),
            "tree_blob_count": len(entries),
            "queries": normalized_terms,
            "matches": query_matches,
        }
        artifact["artifact_sha256"] = stable_hash(artifact)
        write_json(self.root / source.name / "semantic_discovery_v1.json", artifact)
        return artifact


def _source_manifest(root: Path, source: ExternalSource) -> Mapping[str, Any]:
    path = root / source.name / "manifest.json"
    if not path.exists():
        raise ExternalReferenceError(f"missing pinned source snapshot: {path}")
    manifest = _mapping(read_json(path))
    if manifest.get("selected_commit") != source.selected_commit:
        raise ExternalReferenceError(f"selected commit mismatch in {path}")
    return manifest


def _source_payload(root: Path, source: ExternalSource, path: str) -> Any:
    file_path = root / source.name / "files" / path
    if not file_path.exists():
        raise ExternalReferenceError(f"missing selected source file: {file_path}")
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExternalReferenceError(f"expected JSON source file: {file_path}") from exc


def _source_ref(root: Path, source: ExternalSource, path: str) -> dict[str, Any]:
    manifest = _source_manifest(root, source)
    file_meta = _mapping(_mapping(manifest.get("files")).get(path))
    if not file_meta:
        raise ExternalReferenceError(f"source manifest has no hash for {source.name}:{path}")
    return {
        "source": source.name,
        "source_role": source.source_role,
        "repository_url": source.repository_url,
        "selected_commit": source.selected_commit,
        "source_version": source.declared_game_version,
        "source_build": source.declared_game_build,
        "version_match": source.version_match,
        "source_path": path,
        "source_url": file_meta.get("download_url") or file_meta.get("contents_api_url"),
        "git_blob_sha": file_meta.get("git_blob_sha"),
        "raw_sha256": file_meta.get("raw_sha256"),
        "raw_size": file_meta.get("raw_size"),
    }


@dataclass
class ExternalReconstructionBuild:
    version: str
    records: dict[str, list[dict[str, Any]]]
    static_gaps: list[dict[str, Any]]
    cross_source_checks: list[dict[str, Any]]
    source_manifest: list[dict[str, Any]]


class ExternalReconstructionBuilder:
    """Normalize only externally evidenced static facts; preserve uncertainty."""

    def __init__(self, source_root: Path, version: str = CONTENT_VERSION, *, database_path: Path | None = None) -> None:
        if version != CONTENT_VERSION:
            raise ExternalReferenceError(
                f"external reconstruction is pinned to {CONTENT_VERSION}; refusing requested version {version}"
            )
        self.source_root = source_root
        self.version = version
        self.database_path = database_path
        self.records: dict[str, list[dict[str, Any]]] = {}
        self.static_gaps: list[dict[str, Any]] = []
        self.cross_source_checks: list[dict[str, Any]] = []

    def _add(self, record: dict[str, Any]) -> None:
        rows = self.records.setdefault(str(record["entity_type"]), [])
        if any(row["entity_id"] == record["entity_id"] for row in rows):
            raise ExternalReferenceError(f"duplicate external entity: {record['entity_type']}:{record['entity_id']}")
        rows.append(record)

    def _required_stage_buffs(self) -> set[str]:
        if self.database_path is None or not self.database_path.exists():
            return set()
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT payload_json FROM stage_buff_relations WHERE game_version=?", (self.version,)
            ).fetchall()
        return {str(_mapping(json.loads(row[0])).get("buff_id")) for row in rows if _mapping(json.loads(row[0])).get("buff_id") is not None}

    def _manifest_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for source in EXTERNAL_SOURCES:
            manifest = _source_manifest(self.source_root, source)
            rows.append({
                "source_name": source.name,
                "repository_url": source.repository_url,
                "selected_commit": source.selected_commit,
                "selected_branch": source.selected_branch,
                "commit_date": source.commit_date,
                "declared_game_version": source.declared_game_version,
                "declared_game_build": source.declared_game_build,
                "version_match": source.version_match,
                "license": source.license,
                "source_role": source.source_role,
                "local_clone_path": None,
                "local_snapshot_path": manifest.get("local_snapshot_path"),
                "source_manifest_sha256": manifest.get("manifest_sha256"),
            })
        return rows

    def _build_relic_affixes(self) -> None:
        tbg = _source_by_name("TurnBasedGameData")
        main_path = "ExcelOutput/RelicMainAffixConfig.json"
        sub_path = "ExcelOutput/RelicSubAffixConfig.json"
        template_path = "ExcelOutput/RelicConfig.json"
        main_rows = _list(_source_payload(self.source_root, tbg, main_path))
        sub_rows = _list(_source_payload(self.source_root, tbg, sub_path))
        for kind, rows, source_path in (("main", main_rows, main_path), ("sub", sub_rows, sub_path)):
            source_ref = _source_ref(self.source_root, tbg, source_path)
            for row in rows:
                raw = _mapping(row)
                group_id, affix_id = raw.get("GroupID"), raw.get("AffixID")
                if group_id is None or affix_id is None:
                    continue
                base_value = _number(raw.get("BaseValue"))
                increment_key = "LevelAdd" if kind == "main" else "StepValue"
                increment = _number(raw.get(increment_key))
                step_num = int(_number(raw.get("StepNum"), 0)) if kind == "sub" else None
                roll_values = (
                    [base_value + increment * index for index in range(step_num + 1)]
                    if step_num is not None else []
                )
                entity_id = f"{kind}:{group_id}:{affix_id}"
                self._add(_entity(
                    "relic_affix", entity_id, version=self.version,
                    payload={
                        "affix_kind": kind,
                        "group_id": str(group_id),
                        "affix_id": str(affix_id),
                        "property": raw.get("Property"),
                        "base_value": base_value,
                        "level_add": increment if kind == "main" else None,
                        "step_value": increment if kind == "sub" else None,
                        "step_num": step_num,
                        "roll_tier_values": roll_values,
                        "raw_config": raw,
                        "external_version_match": tbg.version_match,
                    },
                    provenance=[source_ref], confidence="R1_CLIENT_DUMP_DERIVED",
                    reconstruction_status="RECONSTRUCTION_READY",
                    original_game_id={"group_id": group_id, "affix_id": affix_id},
                    game_id_status="PRESERVED_COMPOSITE",
                ))
        template_ref = _source_ref(self.source_root, tbg, template_path)
        for row in _list(_source_payload(self.source_root, tbg, template_path)):
            raw = _mapping(row)
            template_id = raw.get("ID")
            if template_id is None:
                continue
            self._add(_entity(
                "relic_template", str(template_id), version=self.version,
                payload={
                    "relic_id": str(template_id), "set_id": raw.get("SetID"), "slot": raw.get("Type"),
                    "rarity": raw.get("Rarity"), "max_level": raw.get("MaxLevel"),
                    "main_affix_group_id": raw.get("MainAffixGroup"),
                    "sub_affix_group_id": raw.get("SubAffixGroup"), "raw_config": raw,
                    "external_version_match": tbg.version_match,
                },
                provenance=[template_ref], confidence="R1_CLIENT_DUMP_DERIVED",
                reconstruction_status="RECONSTRUCTION_READY", original_game_id=template_id,
            ))
        self.static_gaps.append({
            "gap_id": "RELIC_AFFIX_SCHEMA", "status": "CLOSED_EXTERNAL",
            "evidence_level": "R3_CROSS_SOURCE_RECONSTRUCTED",
            "version_scope": "CLOSE", "detail": "TurnBasedGameData provides RelicConfig plus main/sub Affix config; StarRailRes and HSR-Mapping-DATA provide independently structured/mapping evidence. Exact 4.4.54 local validation remains future work.",
        })

    def _build_stage_buffs_and_auxiliary(self) -> None:
        tbg = _source_by_name("TurnBasedGameData")
        required = self._required_stage_buffs()
        maze_path = "ExcelOutput/MazeBuff.json"
        maze_ref = _source_ref(self.source_root, tbg, maze_path)
        matched: set[str] = set()
        for row in _list(_source_payload(self.source_root, tbg, maze_path)):
            raw = _mapping(row)
            buff_id = raw.get("MazeBuffID", raw.get("ID"))
            if buff_id is None or (required and str(buff_id) not in required):
                continue
            matched.add(str(buff_id))
            self._add(_entity(
                "stage_buff", str(buff_id), version=self.version,
                payload={"buff_id": str(buff_id), "raw_config": raw, "external_version_match": tbg.version_match},
                provenance=[maze_ref], confidence="R1_CLIENT_DUMP_DERIVED",
                reconstruction_status="RECONSTRUCTION_READY", original_game_id=buff_id,
            ))
        self.static_gaps.append({
            "gap_id": "STAGE_BUFF_DETAIL", "status": "CLOSED_EXTERNAL" if required and required == matched else "PARTIAL_EXTERNAL",
            "evidence_level": "R1_CLIENT_DUMP_DERIVED", "version_scope": "CLOSE",
            "required_count": len(required), "resolved_count": len(matched), "missing_ids": sorted(required - matched),
            "detail": "Stage-to-Buff bindings remain from Nanoka; public MazeBuff records supply raw Buff configuration without runtime semantic interpretation.",
        })
        for family, path in (("EliteGroup", "ExcelOutput/EliteGroup.json"), ("HardLevelGroup", "ExcelOutput/HardLevelGroup.json")):
            source_ref = _source_ref(self.source_root, tbg, path)
            rows = _list(_source_payload(self.source_root, tbg, path))
            for index, row in enumerate(rows):
                raw = _mapping(row)
                raw_id = raw.get("ID", raw.get(f"{family}ID", index))
                self._add(_entity(
                    "external_auxiliary_group", f"{family}:{raw_id}", version=self.version,
                    payload={"family": family, "group_id": str(raw_id), "raw_config": raw, "external_version_match": tbg.version_match},
                    provenance=[source_ref], confidence="R1_CLIENT_DUMP_DERIVED",
                    reconstruction_status="PARTIAL", original_game_id=raw_id,
                ))
            self.static_gaps.append({
                "gap_id": f"AUXILIARY_{family.upper()}", "status": "PARTIAL_EXTERNAL",
                "evidence_level": "R1_CLIENT_DUMP_DERIVED", "version_scope": "CLOSE", "record_count": len(rows),
                "detail": "The public source table is preserved. A version-aligned Stage/Mode join has not been claimed by this external-only pass.",
            })

    def _build_monster_candidate(self) -> None:
        tbg = _source_by_name("TurnBasedGameData")
        target = "4034020"
        candidate_rows: list[tuple[str, Mapping[str, Any]]] = []
        for path in ("ExcelOutput/MonsterConfig.json", "ExcelOutput/MonsterTemplateConfig.json"):
            for row in _list(_source_payload(self.source_root, tbg, path)):
                raw = _mapping(row)
                values = {str(value) for value in raw.values() if isinstance(value, (str, int))}
                if target in values:
                    candidate_rows.append((path, raw))
        for index, (path, raw) in enumerate(candidate_rows):
            self._add(_entity(
                "external_monster_candidate", f"{target}:{index}", version=self.version,
                payload={"monster_id": target, "source_table": path.rsplit("/", 1)[-1], "raw_config": raw, "external_version_match": tbg.version_match},
                provenance=[_source_ref(self.source_root, tbg, path)], confidence="R1_CLIENT_DUMP_DERIVED",
                reconstruction_status="PARTIAL", original_game_id=target,
            ))
        self.static_gaps.append({
            "gap_id": "MONSTER_VARIANT_LIST:4034020", "status": "PARTIAL_EXTERNAL" if candidate_rows else "NOT_FOUND_EXTERNAL",
            "evidence_level": "R1_CLIENT_DUMP_DERIVED" if candidate_rows else "R0_HYPOTHESIS", "version_scope": "CLOSE",
            "candidate_record_count": len(candidate_rows),
            "detail": "Public MonsterConfig/MonsterTemplate candidates are preserved, but no complete parent-to-child variant enumeration is inferred without an explicit join.",
        })

    def _cross_check_relic_affixes(self) -> None:
        tbg = _source_by_name("TurnBasedGameData")
        srr = _source_by_name("StarRailRes")
        tbg_rows = _list(_source_payload(self.source_root, tbg, "ExcelOutput/RelicMainAffixConfig.json"))
        srr_rows = _mapping(_source_payload(self.source_root, srr, "index_new/cn/relic_main_affixes.json"))
        exact, missing = 0, 0
        for row in tbg_rows:
            raw = _mapping(row)
            group, affix = str(raw.get("GroupID")), str(raw.get("AffixID"))
            normalized_group = _mapping(srr_rows.get(group))
            normalized_affix = _mapping(_mapping(normalized_group.get("affixes")).get(affix))
            if not normalized_affix:
                missing += 1
                continue
            external_base = _number(raw.get("BaseValue"))
            external_step = _number(raw.get("LevelAdd"))
            if normalized_affix.get("property") == raw.get("Property") and _number(normalized_affix.get("base")) == external_base and _number(normalized_affix.get("step")) == external_step:
                exact += 1
        non_exact = len(tbg_rows) - exact - missing
        # These are close-version public references.  Presence alone does not
        # establish an exact numeric match when normalized values differ.
        status = "EXACT" if not missing and not non_exact else ("MISSING" if missing else "SOURCE_CONFLICT")
        self.cross_source_checks.append({
            "check_id": "relic_main_affix.tbg_to_starrailres", "status": status,
            "left_source": tbg.name, "right_source": srr.name, "left_count": len(tbg_rows),
            "exact_count": exact, "non_exact_count": non_exact, "missing_count": missing,
            "detail": "Comparison is structural/numeric within independently selected public sources; it is not a Nanoka 4.4.54 overwrite or local proof.",
        })

    def build(self) -> ExternalReconstructionBuild:
        for source in EXTERNAL_SOURCES:
            _source_manifest(self.source_root, source)
        self._build_relic_affixes()
        self._build_stage_buffs_and_auxiliary()
        self._build_monster_candidate()
        self._cross_check_relic_affixes()
        return ExternalReconstructionBuild(
            version=self.version,
            records={kind: sorted(rows, key=lambda row: str(row["entity_id"])) for kind, rows in sorted(self.records.items())},
            static_gaps=sorted(self.static_gaps, key=lambda row: str(row["gap_id"])),
            cross_source_checks=list(self.cross_source_checks), source_manifest=self._manifest_rows(),
        )


EXTERNAL_ENTITY_TABLES: Mapping[str, str] = {
    "relic_affix": "relic_affixes",
    "relic_template": "relic_templates",
    # Keep an external detail alongside the Nanoka binding/placeholder instead
    # of overwriting an exact-version record with a CLOSE-version source.
    "stage_buff": "external_stage_buffs",
    "external_auxiliary_group": "external_auxiliary_groups",
    "external_monster_candidate": "external_monster_candidates",
}


def _ensure_external_schema(connection: sqlite3.Connection) -> None:
    for table in EXTERNAL_ENTITY_TABLES.values():
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {table} (game_version TEXT NOT NULL, entity_id TEXT NOT NULL, original_game_id TEXT, game_id_status TEXT NOT NULL, confidence TEXT NOT NULL, reconstruction_status TEXT NOT NULL, payload_json TEXT NOT NULL, provenance_json TEXT NOT NULL, canonical_sha256 TEXT NOT NULL, PRIMARY KEY (game_version, entity_id))"
        )
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS external_reference_sources (
          game_version TEXT NOT NULL, source_name TEXT NOT NULL, repository_url TEXT NOT NULL,
          selected_commit TEXT NOT NULL, version_match TEXT NOT NULL, license TEXT NOT NULL,
          source_role TEXT NOT NULL, manifest_json TEXT NOT NULL,
          PRIMARY KEY (game_version, source_name)
        );
        CREATE TABLE IF NOT EXISTS external_reconstruction_gaps (
          game_version TEXT NOT NULL, gap_id TEXT NOT NULL, status TEXT NOT NULL, detail_json TEXT NOT NULL,
          PRIMARY KEY (game_version, gap_id)
        );
        CREATE TABLE IF NOT EXISTS external_cross_source_checks (
          game_version TEXT NOT NULL, check_id TEXT NOT NULL, status TEXT NOT NULL, detail_json TEXT NOT NULL,
          PRIMARY KEY (game_version, check_id)
        );
        CREATE TABLE IF NOT EXISTS external_conflicts (
          game_version TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
          existing_sha256 TEXT NOT NULL, incoming_sha256 TEXT NOT NULL, detail_json TEXT NOT NULL,
          PRIMARY KEY (game_version, entity_type, entity_id, incoming_sha256)
        );
        """
    )


def _insert_record(connection: sqlite3.Connection, table: str, record: Mapping[str, Any]) -> None:
    existing = connection.execute(
        f"SELECT canonical_sha256 FROM {table} WHERE game_version=? AND entity_id=?", (record["game_version"], record["entity_id"])
    ).fetchone()
    if existing and existing[0] != record["canonical_sha256"]:
        connection.execute(
            "INSERT OR IGNORE INTO external_conflicts VALUES (?, ?, ?, ?, ?, ?)",
            (record["game_version"], record["entity_type"], record["entity_id"], existing[0], record["canonical_sha256"], json.dumps({"existing_source": "preexisting_database", "incoming_provenance": record["provenance"]}, ensure_ascii=False, sort_keys=True)),
        )
        return
    connection.execute(
        f"INSERT OR IGNORE INTO {table} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (record["game_version"], record["entity_id"], json.dumps(record.get("original_game_id"), ensure_ascii=False, sort_keys=True), record["game_id_status"], record["confidence"], record["reconstruction_status"], json.dumps(record["data"], ensure_ascii=False, sort_keys=True), json.dumps(record["provenance"], ensure_ascii=False, sort_keys=True), record["canonical_sha256"]),
    )


def emit_external_canonical(build: ExternalReconstructionBuild, canonical_root: Path) -> dict[str, Any]:
    canonical_root.mkdir(parents=True, exist_ok=True)
    for kind, rows in build.records.items():
        write_jsonl(canonical_root / f"{kind}s.jsonl", rows)
    write_json(canonical_root / "static_reconstruction_gaps.json", build.static_gaps)
    write_json(canonical_root / "cross_source_checks.json", build.cross_source_checks)
    write_json(canonical_root / "external_reference_manifest.json", build.source_manifest)
    content = {kind: [row["canonical_sha256"] for row in rows] for kind, rows in sorted(build.records.items())}
    return {"canonical_root": str(canonical_root), "canonical_sha256": stable_hash(content), "record_counts": {kind: len(rows) for kind, rows in build.records.items()}}


def augment_content_database(build: ExternalReconstructionBuild, database_path: Path) -> dict[str, Any]:
    if not database_path.exists():
        raise ExternalReferenceError(f"Nanoka content database is required before augmentation: {database_path}")
    with sqlite3.connect(database_path) as connection:
        _ensure_external_schema(connection)
        for source in build.source_manifest:
            connection.execute(
                "INSERT OR REPLACE INTO external_reference_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (build.version, source["source_name"], source["repository_url"], source["selected_commit"], source["version_match"], source["license"], source["source_role"], json.dumps(source, ensure_ascii=False, sort_keys=True)),
            )
        for kind, rows in build.records.items():
            table = EXTERNAL_ENTITY_TABLES[kind]
            for record in rows:
                _insert_record(connection, table, record)
        for gap in build.static_gaps:
            connection.execute(
                "INSERT OR REPLACE INTO external_reconstruction_gaps VALUES (?, ?, ?, ?)",
                (build.version, gap["gap_id"], gap["status"], json.dumps(gap, ensure_ascii=False, sort_keys=True)),
            )
        for check in build.cross_source_checks:
            connection.execute(
                "INSERT OR REPLACE INTO external_cross_source_checks VALUES (?, ?, ?, ?)",
                (build.version, check["check_id"], check["status"], json.dumps(check, ensure_ascii=False, sort_keys=True)),
            )
        connection.commit()
    return {
        "sqlite_path": str(database_path), "logical_sha256": sqlite_logical_hash(database_path),
        "record_counts": {kind: len(rows) for kind, rows in build.records.items()},
    }


def sqlite_logical_hash(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        content: dict[str, list[tuple[Any, ...]]] = {}
        for table in tables:
            names = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
            order = ", ".join(names)
            content[table] = list(connection.execute(f"SELECT {order} FROM {table} ORDER BY {order}"))
    return stable_hash(content)


PROPERTY_KEYS: Mapping[str, tuple[str, str]] = {
    "HPDelta": ("hp", "flat"), "HPAddedRatio": ("hp", "percent"),
    "AttackDelta": ("atk", "flat"), "AttackAddedRatio": ("atk", "percent"),
    "DefenceDelta": ("def", "flat"), "DefenceAddedRatio": ("def", "percent"),
    "SpeedDelta": ("spd", "flat"), "SpeedAddedRatio": ("spd", "percent"),
    "CriticalChanceBase": ("crit_rate", "flat"), "CriticalDamageBase": ("crit_dmg", "flat"),
    "StatusProbabilityBase": ("effect_hit_rate", "flat"), "StatusResistanceBase": ("effect_res", "flat"),
    "BreakDamageAddedRatioBase": ("break_effect", "flat"), "HealRatioBase": ("outgoing_heal_boost", "flat"),
    "SPRatioBase": ("energy_regen_rate", "flat"),
    "PhysicalAddedRatio": ("physical_dmg_boost", "flat"), "FireAddedRatio": ("fire_dmg_boost", "flat"),
    "IceAddedRatio": ("ice_dmg_boost", "flat"), "ThunderAddedRatio": ("lightning_dmg_boost", "flat"),
    "WindAddedRatio": ("wind_dmg_boost", "flat"), "QuantumAddedRatio": ("quantum_dmg_boost", "flat"),
    "ImaginaryAddedRatio": ("imaginary_dmg_boost", "flat"), "AllDamageTypeAddedRatio": ("all_dmg_boost", "flat"),
}


def _entity_data(database: ContentDatabase, table: str, entity_id: str | int) -> dict[str, Any] | None:
    return database._entity(table, entity_id)


def _add_property(totals: dict[str, dict[str, float]], property_name: str, value: float) -> None:
    mapped = PROPERTY_KEYS.get(property_name)
    if mapped is None:
        totals.setdefault("unknown", {})[property_name] = totals.setdefault("unknown", {}).get(property_name, 0.0) + value
        return
    stat, kind = mapped
    totals.setdefault(kind, {})[stat] = totals.setdefault(kind, {}).get(stat, 0.0) + value


class ReferenceEvaluator:
    """Pure, deterministic numeric helper.  It does not execute battle semantics."""

    def __init__(self, database: ContentDatabase) -> None:
        self.database = database

    def get_relic_affix(self, entity_id: str) -> dict[str, Any] | None:
        return _entity_data(self.database, "relic_affixes", entity_id)

    def get_relic_template(self, entity_id: str | int) -> dict[str, Any] | None:
        return _entity_data(self.database, "relic_templates", entity_id)

    def materialize_loadout(self, loadout: Mapping[str, Any]) -> dict[str, Any]:
        """Materialize only explicit static contributions from an ID-preserving loadout.

        Contextual LightCone/RelicSet effects and Eidolon mechanics are retained as
        metadata, not guessed into properties.  A caller may provide independently
        evidenced ``static_modifiers`` for effects that are already known to be
        unconditional numeric properties.
        """
        avatar_id = str(loadout["avatar_id"])
        avatar = self.database.get_avatar(avatar_id)
        if avatar is None:
            raise KeyError(f"unknown avatar: {avatar_id}")
        avatar_detail = _mapping(_mapping(avatar.get("data")).get("detail"))
        level = int(loadout.get("level", 80))
        promotion = int(loadout.get("promotion", 6))
        raw_avatar_stats = avatar_detail.get("stats")
        if isinstance(raw_avatar_stats, Mapping):
            avatar_stats = _mapping(raw_avatar_stats.get(str(promotion)))
        else:
            avatar_stats = _mapping(next(
                (item for item in _list(raw_avatar_stats) if int(_number(_mapping(item).get("promotion"), 0)) == promotion),
                None,
            ))
        if not avatar_stats:
            raise ValueError(f"avatar {avatar_id} has no promotion {promotion}")
        base = {
            "hp": _number(avatar_stats.get("hp_base", avatar_stats.get("hp"))) + _number(avatar_stats.get("hp_add")) * (level - 1),
            "atk": _number(avatar_stats.get("attack_base", avatar_stats.get("atk"))) + _number(avatar_stats.get("attack_add")) * (level - 1),
            "def": _number(avatar_stats.get("defence_base", avatar_stats.get("def"))) + _number(avatar_stats.get("defence_add")) * (level - 1),
            "spd": _number(avatar_stats.get("speed_base", avatar_stats.get("speed"))),
        }
        totals: dict[str, dict[str, float]] = {"flat": {}, "percent": {}, "unknown": {}}
        lightcone_id = loadout.get("lightcone_id")
        lightcone_context: dict[str, Any] | None = None
        if lightcone_id is not None:
            lightcone = self.database.get_lightcone(str(lightcone_id))
            if lightcone is None:
                raise KeyError(f"unknown lightcone: {lightcone_id}")
            lc_detail = _mapping(_mapping(lightcone.get("data")).get("detail"))
            avatar_path, lightcone_path = avatar_detail.get("base_type"), lc_detail.get("base_type")
            if avatar_path and lightcone_path and avatar_path != lightcone_path:
                raise ValueError(f"lightcone {lightcone_id} path {lightcone_path} is incompatible with avatar {avatar_id} path {avatar_path}")
            lc_level = int(loadout.get("lightcone_level", level))
            lc_promotion = int(loadout.get("lightcone_promotion", promotion))
            stats = _list(lc_detail.get("stats"))
            lc_stat = next((item for item in stats if int(_number(_mapping(item).get("promotion"), 0)) == lc_promotion), None)
            if lc_stat is None and lc_promotion == 0:
                lc_stat = next((item for item in stats if "promotion" not in _mapping(item)), None)
            if lc_stat is None:
                raise ValueError(f"lightcone {lightcone_id} has no promotion {lc_promotion}")
            lc_raw = _mapping(lc_stat)
            base["hp"] += _number(lc_raw.get("base_hp", lc_raw.get("hp"))) + _number(lc_raw.get("base_hp_add")) * (lc_level - 1)
            base["atk"] += _number(lc_raw.get("base_attack", lc_raw.get("atk"))) + _number(lc_raw.get("base_attack_add")) * (lc_level - 1)
            base["def"] += _number(lc_raw.get("base_defence", lc_raw.get("def"))) + _number(lc_raw.get("base_defence_add")) * (lc_level - 1)
            lightcone_context = {"lightcone_id": str(lightcone_id), "path": lightcone_path, "superimposition": int(loadout.get("lightcone_superimposition", 1))}
        for trace_id in loadout.get("trace_ids", []):
            trace = _entity_data(self.database, "traces", str(trace_id))
            if trace is None:
                raise KeyError(f"unknown trace: {trace_id}")
            for addition in _list(_mapping(trace.get("data")).get("status_add_list")):
                data = _mapping(addition)
                _add_property(totals, str(data.get("property_type")), _number(data.get("value")))
        relic_provenance: list[dict[str, Any]] = []
        relic_set_counts: dict[str, int] = {}
        used_slots: set[str] = set()
        for piece in loadout.get("relics", []):
            relic = _mapping(piece)
            template_id = relic.get("template_id")
            template_data: Mapping[str, Any] = {}
            if template_id is not None:
                template = self.get_relic_template(str(template_id))
                if template is None:
                    raise KeyError(f"unknown relic template: {template_id}")
                template_data = _mapping(template.get("data"))
                slot = str(template_data.get("slot"))
                if slot in used_slots:
                    raise ValueError(f"duplicate relic slot {slot}")
                used_slots.add(slot)
                max_level = template_data.get("max_level")
                if max_level is not None and not 0 <= int(relic.get("level", 0)) <= int(_number(max_level)):
                    raise ValueError(f"relic level is outside the template range for {template_id}")
                set_id = template_data.get("set_id")
                if set_id is not None:
                    relic_set_counts[str(set_id)] = relic_set_counts.get(str(set_id), 0) + 1
            main = self.get_relic_affix(str(relic["main_affix_id"]))
            if main is None or _mapping(main.get("data")).get("affix_kind") != "main":
                raise KeyError(f"unknown main affix: {relic.get('main_affix_id')}")
            main_data = _mapping(main["data"])
            expected_main_group = template_data.get("main_affix_group_id")
            if expected_main_group is not None and str(expected_main_group) != str(main_data.get("group_id")):
                raise ValueError(
                    f"main affix {relic.get('main_affix_id')} is not valid for relic template {template_id}"
                )
            main_value = _number(main_data.get("base_value")) + _number(main_data.get("level_add")) * int(relic.get("level", 0))
            _add_property(totals, str(main_data.get("property")), main_value)
            for sub in relic.get("sub_affixes", []):
                sub_input = _mapping(sub)
                affix = self.get_relic_affix(str(sub_input["affix_id"]))
                if affix is None or _mapping(affix.get("data")).get("affix_kind") != "sub":
                    raise KeyError(f"unknown sub affix: {sub_input.get('affix_id')}")
                affix_data = _mapping(affix["data"])
                expected_sub_group = template_data.get("sub_affix_group_id")
                if expected_sub_group is not None and str(expected_sub_group) != str(affix_data.get("group_id")):
                    raise ValueError(
                        f"sub affix {sub_input.get('affix_id')} is not valid for relic template {template_id}"
                    )
                base_value, step = _number(affix_data.get("base_value")), _number(affix_data.get("step_value"))
                for tier in sub_input.get("roll_tiers", []):
                    tier_number = int(tier)
                    if tier_number < 0 or tier_number > int(_number(affix_data.get("step_num"))):
                        raise ValueError(f"invalid roll tier {tier_number} for {sub_input.get('affix_id')}")
                    _add_property(totals, str(affix_data.get("property")), base_value + step * tier_number)
            relic_provenance.append({
                "template_id": template_id, "slot": template_data.get("slot"),
                "set_id": template_data.get("set_id"),
                "main_affix_id": relic["main_affix_id"],
                "sub_affix_count": len(_list(relic.get("sub_affixes"))),
            })
        for modifier in loadout.get("static_modifiers", []):
            modifier_data = _mapping(modifier)
            _add_property(totals, str(modifier_data["property"]), _number(modifier_data["value"]))
        final = {stat: base_value * (1.0 + totals["percent"].get(stat, 0.0)) + totals["flat"].get(stat, 0.0) for stat, base_value in base.items()}
        for stat, value in totals["flat"].items():
            if stat not in final:
                final[stat] = value
        eidolon_rank = int(loadout.get("eidolon_rank", 0))
        if not 0 <= eidolon_rank <= 6:
            raise ValueError("eidolon_rank must be in [0, 6]")
        unapplied_contextual_effects: list[dict[str, Any]] = []
        if lightcone_context is not None:
            unapplied_contextual_effects.append({"kind": "lightcone_effect", **lightcone_context, "status": "UNAPPLIED_CONTEXTUAL"})
        unapplied_contextual_effects.extend(
            {"kind": "relic_set_effect", "set_id": set_id, "piece_count": count, "status": "UNAPPLIED_CONTEXTUAL"}
            for set_id, count in sorted(relic_set_counts.items())
        )
        if eidolon_rank:
            unapplied_contextual_effects.append({"kind": "eidolon_mechanic", "rank": eidolon_rank, "status": "UNAPPLIED_CONTEXTUAL"})
        return {
            "schema": "hsr_battle_agent.static_loadout/1", "game_version": self.database.game_version,
            "avatar_id": avatar_id, "avatar_level": level, "avatar_promotion": promotion,
            "eidolon_rank": eidolon_rank, "lightcone_id": str(lightcone_id) if lightcone_id is not None else None,
            "base_stats_before_modifiers": base, "property_contributions": totals, "final_properties": final,
            "relics": relic_provenance,
            "unapplied_contextual_effects": unapplied_contextual_effects,
            "reconstruction_status": "PARTIAL", "evidence_level": "R3_CROSS_SOURCE_RECONSTRUCTED",
        }

    @staticmethod
    def evaluate_damage(request: Mapping[str, Any]) -> dict[str, Any]:
        """Evaluate Fribbels' 4.4v5 normal-damage model for explicit inputs only.

        The selected implementation fixes its attacker-level constant at 80.  This
        helper refuses other attacker levels rather than silently generalizing it.
        """
        if int(request.get("attacker_level", 80)) != 80:
            raise ValueError("external damage.def_multiplier.v1 is scoped to the selected level-80 implementation")
        atk, hp, defense = _number(request.get("atk")), _number(request.get("hp")), _number(request.get("def"))
        base_damage = _number(request.get("flat_damage")) + atk * _number(request.get("atk_scaling")) + hp * _number(request.get("hp_scaling")) + defense * _number(request.get("def_scaling"))
        def_pen = max(0.0, _number(request.get("def_pen")))
        def_multi = 100.0 / ((_number(request.get("enemy_level")) + 20.0) * max(0.0, 1.0 - def_pen) + 100.0)
        res_multi = 1.0 - (_number(request.get("enemy_res")) - _number(request.get("res_pen")))
        dmg_boost = 1.0 + _number(request.get("dmg_boost"))
        vulnerability = 1.0 + _number(request.get("vulnerability"))
        final_dmg = 1.0 + _number(request.get("final_dmg_boost"))
        crit_mode = str(request.get("crit_mode", "none"))
        crit_rate, crit_dmg = min(1.0, _number(request.get("crit_rate"))), _number(request.get("crit_dmg"))
        crit_multi = 1.0 if crit_mode == "none" else (1.0 + crit_dmg if crit_mode == "crit" else crit_rate * (1.0 + crit_dmg) + (1.0 - crit_rate))
        value = base_damage * dmg_boost * def_multi * res_multi * vulnerability * final_dmg * crit_multi * (1.0 + _number(request.get("true_damage_modifier")))
        return {"value": value, "components": {"base_damage": base_damage, "dmg_boost": dmg_boost, "def_multiplier": def_multi, "res_multiplier": res_multi, "vulnerability_multiplier": vulnerability, "final_damage_multiplier": final_dmg, "crit_multiplier": crit_multi}, "evidence_level": "R2_MATURE_IMPLEMENTATION", "reconstruction_status": "RECONSTRUCTION_READY", "scope": "amount_only; level_80_attacker; no runtime ordering"}

    @staticmethod
    def evaluate_break(request: Mapping[str, Any]) -> dict[str, Any]:
        base = 3767.5533 * _number(request.get("elemental_break_scaling"), 1.0)
        request_damage = {"flat_damage": base * (1.0 + _number(request.get("break_effect"))) * (1.0 + _number(request.get("break_boost"))), "enemy_level": request.get("enemy_level"), "enemy_res": request.get("enemy_res"), "res_pen": request.get("res_pen"), "def_pen": request.get("def_pen"), "vulnerability": request.get("vulnerability"), "final_dmg_boost": request.get("final_dmg_boost"), "true_damage_modifier": request.get("true_damage_modifier"), "crit_mode": "none", "attacker_level": 80}
        result = ReferenceEvaluator.evaluate_damage(request_damage)
        result.update({"evidence_level": "R2_MATURE_IMPLEMENTATION", "scope": "amount_only; selected external implementation; no weakness-break event timing"})
        return result

    @staticmethod
    def evaluate_super_break(request: Mapping[str, Any]) -> dict[str, Any]:
        effective_toughness = (1.0 + _number(request.get("break_efficiency"))) * _number(request.get("toughness_damage")) + _number(request.get("fixed_toughness_damage"))
        base = (3767.5533 / 10.0) * effective_toughness * _number(request.get("super_break_modifier")) * (1.0 + _number(request.get("break_effect"))) * (1.0 + _number(request.get("break_boost")))
        result = ReferenceEvaluator.evaluate_damage({"flat_damage": base, "enemy_level": request.get("enemy_level"), "enemy_res": request.get("enemy_res"), "res_pen": request.get("res_pen"), "def_pen": request.get("def_pen"), "vulnerability": request.get("vulnerability"), "final_dmg_boost": request.get("final_dmg_boost"), "true_damage_modifier": request.get("true_damage_modifier"), "crit_mode": "none", "attacker_level": 80})
        result.update({"evidence_level": "R2_MATURE_IMPLEMENTATION", "scope": "amount_only; selected external implementation; no runtime timing"})
        return result

    @staticmethod
    def evaluate_heal(request: Mapping[str, Any]) -> dict[str, Any]:
        base = _number(request.get("atk")) * _number(request.get("atk_scaling")) + _number(request.get("hp")) * _number(request.get("hp_scaling")) + _number(request.get("flat_heal"))
        value = base * (1.0 + _number(request.get("outgoing_heal_boost"))) * (1.0 + _number(request.get("heal_boost")))
        return {"value": value, "components": {"base_heal": base}, "evidence_level": "R2_MATURE_IMPLEMENTATION", "reconstruction_status": "RECONSTRUCTION_READY", "scope": "amount_only; no HealData consumer or HP-write timing"}

    @staticmethod
    def evaluate_shield(request: Mapping[str, Any]) -> dict[str, Any]:
        base = _number(request.get("def")) * _number(request.get("def_scaling")) + _number(request.get("hp")) * _number(request.get("hp_scaling")) + _number(request.get("atk")) * _number(request.get("atk_scaling")) + _number(request.get("flat_shield"))
        value = base * (1.0 + _number(request.get("shield_boost")))
        return {"value": value, "components": {"base_shield": base}, "evidence_level": "R2_MATURE_IMPLEMENTATION", "reconstruction_status": "RECONSTRUCTION_READY", "scope": "amount_only; no shield lifecycle or replacement timing"}


def _mapping_index() -> list[dict[str, Any]]:
    return [
        {"canonical_entity": "Avatar", "canonical_field": "identity_and_base_stats", "nanoka_field": "avatar.detail / avatar.collection", "turn_based_game_data": {"table": "ExcelOutput/AvatarConfig.json + AvatarPromotionConfig.json", "field": "AvatarID, HPBase, HPAdd, AttackBase, AttackAdd, DefenceBase, DefenceAdd"}, "mapping_data": {"path": "src/transformers/characters_transformer.py", "symbol": "transform_avatar_promotion"}, "starrailres": "index_new/cn/characters.json + character_promotions.json", "fribbels": "consumer only; not an exact-content source", "version_scope": "Nanoka EXACT; TBG/StarRailRes CLOSE", "source_confidence": "R1"},
        {"canonical_entity": "Skill", "canonical_field": "owner_and_static_parameters", "nanoka_field": "avatar.detail.skills", "turn_based_game_data": {"table": "ExcelOutput/AvatarSkillConfig.json", "field": "SkillID, Level, ParamList"}, "mapping_data": {"path": "src/transformers/characters_transformer.py", "symbol": "transform_avatar_skill"}, "starrailres": "index_new/cn/character_skills.json", "fribbels": None, "version_scope": "Nanoka EXACT; mapping sources CLOSE/SCHEMA_ONLY", "source_confidence": "R1"},
        {"canonical_entity": "Trace", "canonical_field": "static_status_add", "nanoka_field": "trace.status_add_list", "turn_based_game_data": {"table": "ExcelOutput/AvatarSkillTreeConfig.json", "field": "PointID, StatusAddList"}, "mapping_data": {"path": "src/transformers/characters_transformer.py", "symbol": "transform_avatar_skill_trees"}, "starrailres": "index_new/cn/character_skill_trees.json", "fribbels": "stat consumer only", "version_scope": "Nanoka EXACT; mapping sources CLOSE/SCHEMA_ONLY", "source_confidence": "R1"},
        {"canonical_entity": "Eidolon", "canonical_field": "rank_and_skill_levels", "nanoka_field": "avatar.detail.ranks", "turn_based_game_data": {"table": "ExcelOutput/AvatarRankConfig.json", "field": "RankID, Rank, SkillAddLevelList"}, "mapping_data": {"path": "src/transformers/characters_transformer.py", "symbol": "transform_avatar_rank"}, "starrailres": "index_new/cn/character_ranks.json", "fribbels": None, "version_scope": "Nanoka EXACT; mapping sources CLOSE/SCHEMA_ONLY", "source_confidence": "R1"},
        {"canonical_entity": "LightCone", "canonical_field": "promotion_stats", "nanoka_field": "lightcone.detail.stats", "turn_based_game_data": {"table": "ExcelOutput/EquipmentPromotionConfig.json", "field": "EquipmentID, HPBase/AttackBase/DefenceBase and Add fields"}, "mapping_data": {"path": "src/transformers/light_cone_transformer.py", "symbol": "transform_light_cone_promotion"}, "starrailres": "index_new/cn/light_cones.json + light_cone_promotions.json", "fribbels": "stat consumer only", "version_scope": "Nanoka EXACT; mapping sources CLOSE/SCHEMA_ONLY", "source_confidence": "R1"},
        {"canonical_entity": "RelicTemplate", "canonical_field": "slot_and_affix_groups", "nanoka_field": "relic items only; template added externally", "turn_based_game_data": {"table": "ExcelOutput/RelicConfig.json", "field": "ID, SetID, Type, MaxLevel, MainAffixGroup, SubAffixGroup"}, "mapping_data": {"path": "src/transformers/relic_transformer.py", "symbol": "transform_relics"}, "starrailres": "index_new/cn/relics.json", "fribbels": "relic stat consumer", "version_scope": "CLOSE/SCHEMA_ONLY", "source_confidence": "R3"},
        {"canonical_entity": "RelicAffix", "canonical_field": "main_level_curve_and_sub_roll_tiers", "nanoka_field": None, "turn_based_game_data": {"table": "ExcelOutput/RelicMainAffixConfig.json + RelicSubAffixConfig.json", "field": "GroupID, AffixID, Property, BaseValue, LevelAdd/StepValue, StepNum"}, "mapping_data": {"path": "src/transformers/relic_transformer.py", "symbol": "transform_relic_main_affixes / transform_relic_sub_affixes"}, "starrailres": "index_new/cn/relic_main_affixes.json + relic_sub_affixes.json", "fribbels": "src/lib/relics/statCalculator.ts", "version_scope": "CLOSE/SCHEMA_ONLY/ALGORITHM_ONLY", "source_confidence": "R3"},
        {"canonical_entity": "Monster", "canonical_field": "static_config_candidate", "nanoka_field": "monster.detail", "turn_based_game_data": {"table": "ExcelOutput/MonsterConfig.json + MonsterTemplateConfig.json", "field": "raw record preserved; no inferred variant join"}, "mapping_data": None, "starrailres": None, "fribbels": "enemy numeric input consumer", "version_scope": "Nanoka EXACT; TBG CLOSE", "source_confidence": "R1"},
        {"canonical_entity": "MonsterSkill", "canonical_field": "static_config", "nanoka_field": "monster skill relations", "turn_based_game_data": {"table": "ExcelOutput/MonsterSkillConfig.json", "field": "SkillID and raw parameters"}, "mapping_data": None, "starrailres": None, "fribbels": None, "version_scope": "Nanoka EXACT; TBG CLOSE", "source_confidence": "R1"},
        {"canonical_entity": "Stage", "canonical_field": "stage/wave binding", "nanoka_field": "stage, wave, wave_monster", "turn_based_game_data": {"table": "Stages/ plus ExcelOutput Maze tables", "field": "not imported in this narrow pass"}, "mapping_data": None, "starrailres": None, "fribbels": None, "version_scope": "Nanoka EXACT", "source_confidence": "C0"},
        {"canonical_entity": "StageBuff", "canonical_field": "raw_static_config", "nanoka_field": "stage_buff_relations binding", "turn_based_game_data": {"table": "ExcelOutput/MazeBuff.json", "field": "MazeBuffID and raw config"}, "mapping_data": None, "starrailres": None, "fribbels": None, "version_scope": "Nanoka binding EXACT; TBG detail CLOSE", "source_confidence": "R1"},
    ]


def _fribbels_inventory() -> list[dict[str, Any]]:
    source = _source_by_name("hsr-optimizer")
    damage_path = "src/lib/optimization/engine/damage/damageCalculator.ts"
    stat_path = "src/lib/relics/statCalculator.ts"
    return [
        {"rule_category": "normal_damage_amount", "source_path": damage_path, "symbol": "CritDamageFunction / calculateInitialDamage", "classification": "GENERAL_RULE", "inputs": ["ATK", "HP", "DEF", "scalings", "boost", "enemy level/res", "crit"], "output": "amount", "assumptions": ["amount only", "no runtime order"], "game_version_sensitivity": "ALGORITHM_ONLY", "source_commit": source.selected_commit},
        {"rule_category": "def_res_vulnerability_final_damage", "source_path": damage_path, "symbol": "computeCommonMultipliers / calculateDefMulti", "classification": "OPTIMIZER_ASSUMPTION", "inputs": ["enemy level", "def pen", "res", "vulnerability"], "output": "multipliers", "assumptions": ["selected code fixes attacker-level constant to 80"], "game_version_sensitivity": "ALGORITHM_ONLY", "source_commit": source.selected_commit},
        {"rule_category": "break_and_super_break_amount", "source_path": damage_path, "symbol": "BreakDamageFunction / SuperBreakDamageFunction", "classification": "GENERAL_RULE", "inputs": ["break effect", "toughness", "enemy multipliers"], "output": "amount", "assumptions": ["amount only; no break timeline"], "game_version_sensitivity": "ALGORITHM_ONLY", "source_commit": source.selected_commit},
        {"rule_category": "heal_amount", "source_path": damage_path, "symbol": "HealDamageFunction", "classification": "GENERAL_RULE", "inputs": ["ATK", "HP", "scalings", "flat heal", "outgoing heal boost"], "output": "amount", "assumptions": ["no HealData consumer/timing"], "game_version_sensitivity": "ALGORITHM_ONLY", "source_commit": source.selected_commit},
        {"rule_category": "shield_amount", "source_path": damage_path, "symbol": "ShieldDamageFunction", "classification": "GENERAL_RULE", "inputs": ["DEF", "HP", "ATK", "scalings", "flat shield"], "output": "amount", "assumptions": ["no shield lifecycle/timing"], "game_version_sensitivity": "ALGORITHM_ONLY", "source_commit": source.selected_commit},
        {"rule_category": "relic_display_stat_curve", "source_path": stat_path, "symbol": "StatCalculator", "classification": "OPTIMIZER_ASSUMPTION", "inputs": ["stat", "quality"], "output": "maxed display stat", "assumptions": ["optimizer quality model; not adopted as an exact client table"], "game_version_sensitivity": "ALGORITHM_ONLY", "source_commit": source.selected_commit},
    ]


def _rule_pack() -> list[dict[str, Any]]:
    source = _source_by_name("hsr-optimizer")
    ref = {"repository_url": source.repository_url, "commit": source.selected_commit, "path": "src/lib/optimization/engine/damage/damageCalculator.ts"}
    offline_test = "tests/game_data/test_external_reconstruction.py::ExternalReconstructionTest.test_external_records_stage_detail_and_static_loadout_round_trip"
    return [
        {"rule_id": "stat.avatar_promotion.v1", "rule_version": 1, "name": "Avatar promotion level stat", "domain": "stat", "inputs": ["promotion row", "level"], "outputs": ["HP", "ATK", "DEF", "SPD"], "operation": "base + per_level_add * (level - 1)", "source_refs": ["TurnBasedGameData AvatarPromotionConfig", "HSR-Mapping-DATA transform_avatar_promotion", "Nanoka avatar.detail.stats"], "source_commits": ["b11066beacc4de454b625fafc7ea3dd540c5bbf3", "245f286185f5274609be264b6ef6dbc15e8a27ad"], "game_version_scope": "Nanoka 4.4.54 exact input; external schema CLOSE", "assumptions": [], "unsupported_cases": [], "known_edge_cases": ["promotion must exist"], "evidence_level": "R3_CROSS_SOURCE_RECONSTRUCTED", "reconstruction_status": "RECONSTRUCTION_READY", "tests": [offline_test]},
        {"rule_id": "stat.lightcone_promotion.v1", "rule_version": 1, "name": "LightCone promotion level stat", "domain": "stat", "inputs": ["promotion row", "level"], "outputs": ["HP", "ATK", "DEF"], "operation": "base + per_level_add * (level - 1)", "source_refs": ["TurnBasedGameData EquipmentPromotionConfig", "Nanoka lightcone.detail.stats"], "source_commits": ["b11066beacc4de454b625fafc7ea3dd540c5bbf3"], "game_version_scope": "Nanoka 4.4.54 exact input; external schema CLOSE", "assumptions": [], "unsupported_cases": ["dynamic LightCone effects"], "known_edge_cases": ["promotion zero omits field in Nanoka"], "evidence_level": "R3_CROSS_SOURCE_RECONSTRUCTED", "reconstruction_status": "RECONSTRUCTION_READY", "tests": [offline_test]},
        {"rule_id": "stat.relic_main.v1", "rule_version": 1, "name": "Relic main affix level curve", "domain": "stat", "inputs": ["main affix", "relic level"], "outputs": ["property contribution"], "operation": "base_value + level_add * relic_level", "source_refs": ["TurnBasedGameData RelicMainAffixConfig", "StarRailRes relic_main_affixes", "HSR-Mapping-DATA transform_relic_main_affixes"], "source_commits": ["b11066beacc4de454b625fafc7ea3dd540c5bbf3", "02bdd75e1e3cf4272cea94165275c98a17ff1719", "245f286185f5274609be264b6ef6dbc15e8a27ad"], "game_version_scope": "CLOSE; explicit external provenance", "assumptions": [], "unsupported_cases": [], "known_edge_cases": [], "evidence_level": "R3_CROSS_SOURCE_RECONSTRUCTED", "reconstruction_status": "RECONSTRUCTION_READY", "tests": [offline_test]},
        {"rule_id": "stat.relic_sub.v1", "rule_version": 1, "name": "Relic sub affix roll tier", "domain": "stat", "inputs": ["sub affix", "roll tier"], "outputs": ["property contribution"], "operation": "base_value + step_value * tier", "source_refs": ["TurnBasedGameData RelicSubAffixConfig", "StarRailRes relic_sub_affixes", "HSR-Mapping-DATA transform_relic_sub_affixes"], "source_commits": ["b11066beacc4de454b625fafc7ea3dd540c5bbf3", "02bdd75e1e3cf4272cea94165275c98a17ff1719", "245f286185f5274609be264b6ef6dbc15e8a27ad"], "game_version_scope": "CLOSE; explicit external provenance", "assumptions": ["caller supplies actual number of rolls"], "unsupported_cases": ["drop/upgrade roll-distribution process"], "known_edge_cases": [], "evidence_level": "R3_CROSS_SOURCE_RECONSTRUCTED", "reconstruction_status": "RECONSTRUCTION_READY", "tests": [offline_test]},
        {"rule_id": "damage.amount.level80.v1", "rule_version": 1, "name": "Normal damage amount at selected optimizer attacker level", "domain": "damage", "inputs": ["ATK/HP/DEF scalings", "enemy level/res", "boosts", "crit"], "outputs": ["damage amount"], "operation": "base × dmg × def × res × vulnerability × final × crit × true", "source_refs": [ref], "source_commits": [source.selected_commit], "game_version_scope": "ALGORITHM_ONLY", "assumptions": ["attacker level fixed at 80", "amount only"], "unsupported_cases": ["request construction", "events", "HP mutation"], "known_edge_cases": ["resistance not clamped by this reference"], "evidence_level": "R2_MATURE_IMPLEMENTATION", "reconstruction_status": "RECONSTRUCTION_READY", "tests": [offline_test]},
        {"rule_id": "break.amount.v1", "rule_version": 1, "name": "Break and Super Break amount", "domain": "break", "inputs": ["break effect", "toughness", "enemy multipliers"], "outputs": ["amount"], "operation": "selected Fribbels amount model", "source_refs": [ref], "source_commits": [source.selected_commit], "game_version_scope": "ALGORITHM_ONLY", "assumptions": ["amount only", "level-80 implementation"], "unsupported_cases": ["break state timing"], "known_edge_cases": [], "evidence_level": "R2_MATURE_IMPLEMENTATION", "reconstruction_status": "RECONSTRUCTION_READY", "tests": [offline_test]},
        {"rule_id": "heal.amount.v1", "rule_version": 1, "name": "Heal amount", "domain": "heal", "inputs": ["ATK/HP scalings", "flat", "heal boosts"], "outputs": ["amount"], "operation": "(ATK×a + HP×h + flat) × (1+OHB) × (1+heal boost)", "source_refs": [ref], "source_commits": [source.selected_commit], "game_version_scope": "ALGORITHM_ONLY", "assumptions": ["amount only"], "unsupported_cases": ["HealData consumer", "HP write timing"], "known_edge_cases": [], "evidence_level": "R2_MATURE_IMPLEMENTATION", "reconstruction_status": "RECONSTRUCTION_READY", "tests": [offline_test]},
        {"rule_id": "shield.amount.v1", "rule_version": 1, "name": "Shield amount", "domain": "shield", "inputs": ["DEF/HP/ATK scalings", "flat", "shield boost"], "outputs": ["amount"], "operation": "(DEF×d + HP×h + ATK×a + flat) × (1+shield boost)", "source_refs": [ref], "source_commits": [source.selected_commit], "game_version_scope": "ALGORITHM_ONLY", "assumptions": ["amount only"], "unsupported_cases": ["shield replacement/lifecycle"], "known_edge_cases": [], "evidence_level": "R2_MATURE_IMPLEMENTATION", "reconstruction_status": "RECONSTRUCTION_READY", "tests": [offline_test]},
    ]


def _dynamic_matrix() -> list[dict[str, Any]]:
    numeric_ready = {"Static Stat Materialization": ("RECONSTRUCTION_READY", "R3_CROSS_SOURCE_RECONSTRUCTED"), "Damage Amount": ("RECONSTRUCTION_READY", "R2_MATURE_IMPLEMENTATION"), "Break Amount": ("RECONSTRUCTION_READY", "R2_MATURE_IMPLEMENTATION"), "Super Break": ("RECONSTRUCTION_READY", "R2_MATURE_IMPLEMENTATION"), "Heal Amount": ("RECONSTRUCTION_READY", "R2_MATURE_IMPLEMENTATION"), "Shield Amount": ("RECONSTRUCTION_READY", "R2_MATURE_IMPLEMENTATION"), "SP Numeric Facts": ("PARTIAL", "R1_CLIENT_DUMP_DERIVED"), "Energy Numeric Facts": ("PARTIAL", "R1_CLIENT_DUMP_DERIVED"), "Target Static Metadata": ("PARTIAL", "R1_CLIENT_DUMP_DERIVED")}
    timing = ["Event Ordering", "SP Mutation Timing", "Energy Mutation Timing", "Turn Recharge", "Death Timing", "Victory Timing", "Follow-up", "Summon", "Boss Phase"]
    rows = [{"domain": name, "external_status": status, "evidence_level": evidence, "runtime_status": "NOT_LOCAL_VERIFIED", "remaining_requirement": "External vs Local Validation, then local semantic proof for runtime use."} for name, (status, evidence) in numeric_ready.items()]
    rows.extend({"domain": name, "external_status": "NOT_AUTHORITATIVE", "evidence_level": "R0_HYPOTHESIS", "runtime_status": "NOT_READY", "remaining_requirement": "Future Local Reverse; external implementations cannot prove timing/order."} for name in timing)
    return rows


def _local_validation_queue() -> list[dict[str, Any]]:
    return [
        {"queue_id": "LVQ-DAMAGE-ORDER", "priority": "MVP_CRITICAL", "reason": "External amount model cannot prove native DamageRequest construction, event order, or HP-write timing."},
        {"queue_id": "LVQ-HEAL-CONSUMER", "priority": "MVP_CRITICAL", "reason": "External heal amount does not identify HealData consumer or mutation boundary."},
        {"queue_id": "LVQ-SP-ENERGY-BOUNDARY", "priority": "MVP_CRITICAL", "reason": "Static costs/gains do not prove state-write timing or Ult gate refresh."},
        {"queue_id": "LVQ-TURN-EVENT", "priority": "MVP_CRITICAL", "reason": "Turn recharge, action completion, and event dispatch are not authoritative externally."},
        {"queue_id": "LVQ-DEATH-VICTORY", "priority": "HIGH", "reason": "State transitions and wave progression need local runtime evidence."},
        {"queue_id": "LVQ-MONSTER-VARIANT-4034020", "priority": "MEDIUM", "reason": "External candidates lack an explicit complete variant join."},
        {"queue_id": "LVQ-SPECIAL-MECHANICS", "priority": "DEFERRED", "reason": "Follow-up, summon, extra action, boss phases, and character-specific state machines need local semantics."},
    ]


def emit_research_artifacts(build: ExternalReconstructionBuild, root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "external_reference_manifest.json": build.source_manifest,
        "authoritative_mapping_index.json": _mapping_index(),
        "fribbels_rule_inventory.json": _fribbels_inventory(),
        "reconstruction_rule_pack.json": _rule_pack(),
        "dynamic_reconstruction_matrix.json": _dynamic_matrix(),
        "local_validation_queue.json": _local_validation_queue(),
        "static_reconstruction_gaps.json": build.static_gaps,
        "cross_source_checks.json": build.cross_source_checks,
    }
    for name, payload in artifacts.items():
        write_json(root / name, payload)
    return {"artifact_root": str(root), "artifacts": sorted(artifacts), "artifact_sha256": stable_hash(artifacts)}


def build_external_reconstruction(
    version: str = CONTENT_VERSION,
    *, source_root: Path | None = None, canonical_root: Path | None = None,
    artifact_root: Path | None = None, database_path: Path,
) -> dict[str, Any]:
    build = ExternalReconstructionBuilder(source_root or default_external_root(), version, database_path=database_path).build()
    canonical = emit_external_canonical(build, canonical_root or default_external_canonical_root(version))
    sqlite = augment_content_database(build, database_path)
    artifacts = emit_research_artifacts(build, artifact_root or default_external_artifact_root(version))
    return {"game_version": version, "canonical": canonical, "sqlite": sqlite, "artifacts": artifacts, "static_gaps": build.static_gaps, "cross_source_checks": build.cross_source_checks}
