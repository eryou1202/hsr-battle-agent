# -*- coding: utf-8 -*-
"""HSR unpack/reverse pipeline v1 - single command entry point.

Run from the repository root:

    scripts/unpack_version.ps1 -GameRoot "D:\\StarRail_4.4.53"

or directly:

    <resolved-python> tools/unpack_pipeline/run_pipeline.py --game-root <root>
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

from .common import (
    Anomaly,
    REPO_ROOT,
    RUNTIME_OPTIONAL_COMPONENT,
    STAGE_NAMES,
    StageResult,
    load_pe,
    stage_key,
    utc_now,
    write_json,
)
from . import PIPELINE_SCHEMA_VERSION, PIPELINE_VERSION
from .asset_discovery import discover as asset_discover
from .bridge import build_bridge_registry
from .design_structural import discover as design_discover
from .diff import run_diff
from .method_code import build_registry as build_code_registry
from .mhy_core import MhyModel
from .normalize import normalize
from .report import write_anomalies, write_pipeline_report
from .version_discovery import build_manifest, read_binary_version


class PipelineRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.game_root = Path(args.game_root).resolve()
        self.stages: list[StageResult] = []
        self.anomalies: list[Anomaly] = []
        self.ctx: dict[str, Any] = {}
        self.counts: dict[str, Any] = {}
        self.version_dir: Path | None = None
        self.normalized_dir: Path | None = None
        self.diff_dir: Path | None = None
        self.manifest: dict[str, Any] = {}

    # ------------------------------------------------------------------
    def _record(self, stage: str, status: str, artifacts: list[str] | None = None,
                counts: dict[str, int] | None = None, warnings: list[str] | None = None,
                error: str | None = None, runtime: bool = False) -> StageResult:
        result = StageResult(stage, status, artifacts or [], counts or {},
                             warnings or [], error, runtime)
        self.stages.append(result)
        if self.version_dir is not None:
            write_json(self.version_dir / "stage_status.json", {
                "schema": "unpack_pipeline_stage_status/1",
                "updated_at": utc_now(),
                "stages": [s.as_dict() for s in self.stages],
            })
        return result

    def _run(self, name: str, func: Callable[[], StageResult]) -> StageResult:
        print(f"\n=== STAGE {STAGE_NAMES.index(name) + 1} {name} ===", flush=True)
        try:
            result = func()
        except Exception as exc:  # keep prior artifacts, record anomaly, continue
            message = f"{type(exc).__name__}: {exc}"
            print(f"[FAIL] {name}: {message}", flush=True)
            traceback.print_exc()
            self.anomalies.append(Anomaly(
                stage=name,
                expected_invariant=f"{name} completes without exception",
                observed_result=message,
                severity="ERROR",
                suggested_follow_up="Inspect the stage log and upstream artifacts; prior stage outputs are preserved.",
            ))
            result = self._record(name, "FAIL", error=message)
        if result.status == "FAIL":
            self.anomalies.append(Anomaly(
                stage=name,
                expected_invariant=f"{name} = PASS",
                observed_result=result.error or "stage failed",
                severity="ERROR",
                suggested_follow_up=result.error or "See pipeline_report.json.",
            ))
        print(f"[{result.status}] {name}", flush=True)
        return result

    # ------------------------------------------------------------------
    def stage_version(self) -> StageResult:
        info = read_binary_version(self.game_root)
        self.version_dir = Path(self.args.output_root) / info["game_version"]
        self.version_dir.mkdir(parents=True, exist_ok=True)
        manifest = build_manifest(self.game_root, self.version_dir)
        self.manifest = manifest
        warnings = []
        if manifest.get("version_source") != "StarRail_Data\\StreamingAssets\\BinaryVersion.bytes":
            warnings.append("version came from an alternate confirmed source layout")
        return self._record(
            "VERSION_DISCOVERY", "PASS",
            artifacts=[str(self.version_dir / "manifest.json")],
            counts={"game_version": info["game_version"]},
            warnings=warnings)

    def stage_assets(self) -> StageResult:
        assert self.version_dir is not None
        inventory = asset_discover(self.game_root, self.version_dir)
        warnings = []
        for label in inventory["missing_required"]:
            warnings.append(f"missing required asset: {label}")
        if warnings:
            raise RuntimeError("; ".join(warnings))
        return self._record(
            "ASSET_DISCOVERY", "PASS",
            artifacts=[str(self.version_dir / "asset_inventory.json")],
            counts={"design_data_files": inventory["design_data_file_count"]})

    def stage_design(self) -> StageResult:
        assert self.version_dir is not None
        inventory_path = self.version_dir / "asset_inventory.json"
        inventory = __import__("json").load(open(inventory_path, encoding="utf-8"))
        try:
            design = design_discover(self.game_root, inventory, self.manifest,
                                     self.version_dir / "design")
        except (FileNotFoundError, ValueError) as exc:
            # Non-fatal for the metadata core: a new version may have changed
            # DesignData chunk layout.  Record an anomaly and continue.
            self.anomalies.append(Anomaly(
                stage="DESIGNDATA_STRUCTURAL_PARSE",
                expected_invariant="known ability-directory structural names are present in one DesignData chunk",
                observed_result=str(exc),
                severity="WARN",
                suggested_follow_up="Run the historical adaptive probes manually against the new chunk set.",
            ))
            design = None
            warning = str(exc)
        else:
            warning = ""
        status = "PASS" if design is not None else "WARN"
        self.ctx["design_structural"] = design
        artifacts = [str(self.version_dir / "design" / "design_structural.json")] if design else []
        return self._record(
            "DESIGNDATA_STRUCTURAL_PARSE", status, artifacts=artifacts,
            counts={"ability_directory_rows": len(design["directory_rows"]) if design else 0},
            warnings=[warning] if warning else [])

    def stage_metadata(self) -> StageResult:
        assert self.version_dir is not None
        manifest = self.manifest
        game = Path(manifest["GameAssembly"]["path"])
        metadata = Path(manifest["global_metadata"]["path"])
        sys.path.insert(0, str(REPO_ROOT / "tools" / "reverse" / "scripts"))
        from recover_mhy_table_registry import build_registry as build_table_registry
        from recover_mhy_table_registry import locate_template_rva as locate_mhy_template
        pe = load_pe(game)
        result = build_table_registry(pe, metadata, locate_mhy_template(pe))
        output = self.version_dir / "mhy_table_registry.json"
        write_json(output, result)
        out_of_file = [row for row in result["tables"]
                       if row.get("in_metadata") is False]
        for row in out_of_file:
            self.anomalies.append(Anomaly(
                stage="MHY_METADATA_PARSE",
                expected_invariant="every payload-rule file offset falls inside global-metadata.dat",
                observed_result=f"template_field {row['template_field']} -> "
                                f"{row.get('file_offset')} outside metadata",
                severity="WARN",
                suggested_follow_up="Verify the table rule on the new build before consuming the field.",
            ))
        return self._record(
            "MHY_METADATA_PARSE", "PASS",
            artifacts=[str(output)],
            counts={"tables": len(result["tables"]),
                    "payload_out_of_file": len(out_of_file)},
            warnings=[f"{len(out_of_file)} payload rules decode outside metadata"]
            if out_of_file else [])

    def stage_types(self) -> StageResult:
        assert self.version_dir is not None
        model = self._load_model()
        self.ctx["model"] = model
        samples = list(model.iter_types())[:32]
        checks = {
            "method_partition_exact_once": model.validations["method_partition"]["covered_exactly_once"],
            "type_descriptor_coverage_exact_once": model.validations.get("type_descriptor_coverage_exact_once"),
            "type_relation_indices_in_bounds": model.validations["type_relation_indices_in_bounds"],
        }
        output = self.version_dir / "type_registry_evidence.json"
        write_json(output, {
            "schema": "unpack_pipeline_type_registry_evidence/1",
            "generated_at": utc_now(),
            "template_rva": f"0x{model.template_rva:X}",
            "type_table": {"field": "0x84", "entry_size": 70, "count": model.ntypes},
            "checks": checks,
            "samples": samples,
            "status": "MHY_METADATA = TYPE_REGISTRY_PROOF" if all(checks.values()) else "PARTIAL",
        })
        return self._record(
            "TYPE_REGISTRY", "PASS" if all(checks.values()) else "WARN",
            artifacts=[str(output)], counts={"types": model.ntypes})

    def stage_members(self) -> StageResult:
        model = self.ctx.get("model")
        assert isinstance(model, MhyModel)
        assert self.version_dir is not None
        validation = model.validations
        samples = {
            "methods": list(model.iter_methods())[:24],
            "fields": list(model.iter_fields())[:24],
            "parameters": list(model.iter_parameters())[:24],
        }
        checks = {
            "method_partition_exact_once": validation["method_partition"]["covered_exactly_once"],
            "field_partition_exact_once": validation["field_partition"]["covered_exactly_once"],
            "parameter_partition_exact_once": validation["parameter_partition"]["covered_exactly_once"],
            "declaring_type_all_match": validation["declaring_type_all_match"],
        }
        output = self.version_dir / "member_registry_evidence.json"
        write_json(output, {
            "schema": "unpack_pipeline_member_registry_evidence/1",
            "generated_at": utc_now(),
            "counts": {"types": model.ntypes, "methods": model.nmethods,
                       "fields": model.nfields, "parameters": model.nparams},
            "checks": checks,
            "samples": samples,
            "status": "MHY_METADATA = MEMBER_REGISTRY_PROOF" if all(checks.values()) else "PARTIAL",
        })
        return self._record(
            "MEMBER_REGISTRY", "PASS" if all(checks.values()) else "WARN",
            artifacts=[str(output)],
            counts={"methods": model.nmethods, "fields": model.nfields,
                    "parameters": model.nparams})

    def stage_method_code(self) -> StageResult:
        model = self.ctx.get("model")
        assert isinstance(model, MhyModel)
        assert self.version_dir is not None
        result = build_code_registry(model, self.version_dir)
        if not result["checks"]["consumer_found"]:
            self.anomalies.append(Anomaly(
                stage="METHOD_CODE_REGISTRY",
                expected_invariant="consumer `mov r12, [registry.field + method_index*8]` byte shape exists",
                observed_result="consumer needle not found; code table still anchored structurally/semantically",
                severity="WARN",
                suggested_follow_up="Re-run the historical Capstone consumer locator and review registry layout.",
            ))
        if not result["checks"]["registry_struct_reference_found"]:
            self.anomalies.append(Anomaly(
                stage="METHOD_CODE_REGISTRY",
                expected_invariant="registry struct absolute reference to the code table exists",
                observed_result="no registry struct reference found for the selected code table",
                severity="WARN",
                suggested_follow_up="Verify the new build's registry struct field offset.",
            ))
        self.ctx["code_table_path"] = result["_raw_table_path"]
        stats = result["statistics"]
        self.counts["method_code"] = stats
        return self._record(
            "METHOD_CODE_REGISTRY", "PASS" if result["status"].endswith("PROOF") else "WARN",
            artifacts=[str(self.version_dir / "method_code_registry.json")],
            counts={"non_null": stats["direct_native_slots"], "null": stats["null_slots"]},
            warnings=[] if result["status"].endswith("PROOF") else [result["status"]])

    def stage_bridge(self) -> StageResult:
        model = self.ctx.get("model")
        assert isinstance(model, MhyModel)
        assert self.version_dir is not None
        table_path = Path(self.ctx["code_table_path"])
        runtime_snapshot = self.args.runtime_snapshot
        if runtime_snapshot:
            runtime_snapshot = Path(runtime_snapshot)
            if not runtime_snapshot.is_file():
                raise FileNotFoundError(runtime_snapshot)
        result = build_bridge_registry(
            model, table_path, self.version_dir, self.manifest["game_version"],
            design_structural=self.ctx.get("design_structural"),
            runtime_snapshot=runtime_snapshot)
        normalized_dir = Path(self.args.normalized_root) / self.manifest["game_version"]
        normalized_dir.mkdir(parents=True, exist_ok=True)
        write_json(normalized_dir / "design_runtime_registry.json", result)
        static_ok = all(d.get("status") == "PASS" for d in result["domains"] if not d.get("runtime"))
        runtime_status = next((d.get("status") for d in result["domains"]
                               if d.get("runtime")), "NOT_RUN")
        self.ctx["runtime_status"] = "PASS" if runtime_status == "PASS" else "NOT_RUN"
        warnings = [] if static_ok else ["one or more static bridge domains failed"]
        return self._record(
            "DESIGN_RUNTIME_BRIDGE",
            "PASS" if static_ok else "FAIL",
            artifacts=[str(self.version_dir / "design_runtime_registry.json")],
            counts={"static_domains": len(result["domains"]) - 1,
                    "runtime_status": runtime_status},
            warnings=warnings)

    def stage_normalization(self) -> StageResult:
        model = self.ctx.get("model")
        assert isinstance(model, MhyModel)
        assert self.version_dir is not None
        self.normalized_dir = Path(self.args.normalized_root) / self.manifest["game_version"]
        summary = normalize(model, Path(self.ctx["code_table_path"]), self.normalized_dir)
        self.counts.update(summary["counts"])
        return self._record(
            "NORMALIZATION", "PASS",
            artifacts=list(summary["files"].values()),
            counts=summary["counts"])

    def stage_diff(self) -> StageResult:
        assert self.normalized_dir is not None
        current = self.manifest["game_version"]
        baseline = None
        label = current
        diff_dir = Path(self.args.diff_root) / current
        legacy_raw = None
        current_raw_bridge = None
        old_raw_bridge = None
        old_normalized = None

        if self.args.reference_normalized:
            old_normalized = Path(self.args.reference_normalized)
            label = f"{old_normalized.name}_vs_{current}"
        elif self.args.legacy_reference:
            legacy_raw = Path(self.args.legacy_reference)
        elif (REPO_ROOT / "data" / "raw" / "4.4.0").is_dir():
            legacy_raw = REPO_ROOT / "data" / "raw" / "4.4.0"
        if legacy_raw is not None:
            label = f"{legacy_raw.name}_vs_{current}"
            current_raw_bridge = (REPO_ROOT / "data" / "raw" / current / "bridge"
                                  / f"ability_mixin_type_bridge_{current}.json")
            old_raw_bridge = (legacy_raw / "bridge" / "ability_mixin_type_bridge_4.4.0.json")
            if not current_raw_bridge.is_file():
                current_raw_bridge = None
            if not old_raw_bridge.is_file():
                old_raw_bridge = None
        self.diff_dir = Path(self.args.diff_root) / label
        diff = run_diff(self.normalized_dir, self.diff_dir,
                        old_normalized=old_normalized, legacy_raw_old=legacy_raw,
                        current_raw_bridge=current_raw_bridge, old_raw_bridge=old_raw_bridge,
                        new_code_stats=self.counts.get("method_code"))
        return self._record(
            "VERSION_DIFF", "PASS",
            artifacts=[str(self.diff_dir / "version_diff.json"),
                       str(self.diff_dir / "version_diff.md")],
            counts={"diff_status": diff.get("status")})

    def _load_model(self) -> MhyModel:
        game = Path(self.manifest["GameAssembly"]["path"])
        metadata = Path(self.manifest["global_metadata"]["path"])
        model = MhyModel(game, metadata)
        return model

    # ------------------------------------------------------------------
    def run(self) -> int:
        self._run("VERSION_DISCOVERY", self.stage_version)
        self._run("ASSET_DISCOVERY", self.stage_assets)
        self._run("DESIGNDATA_STRUCTURAL_PARSE", self.stage_design)
        self._run("MHY_METADATA_PARSE", self.stage_metadata)
        self._run("TYPE_REGISTRY", self.stage_types)
        self._run("MEMBER_REGISTRY", self.stage_members)
        self._run("METHOD_CODE_REGISTRY", self.stage_method_code)
        self._run("DESIGN_RUNTIME_BRIDGE", self.stage_bridge)
        self._run("NORMALIZATION", self.stage_normalization)
        self._run("VERSION_DIFF", self.stage_diff)

        model = self.ctx.get("model")
        if model is not None:
            self.counts.update({
                "types": model.ntypes,
                "methods": model.nmethods,
                "fields": model.nfields,
                "parameters": model.nparams,
            })
            model.close()
            self.ctx["model"] = None

        assert self.version_dir is not None
        runtime_status = self.ctx.get("runtime_status", "NOT_RUN")
        evidence_summary = {
            "metadata": {
                "TYPE_REGISTRY": self._stage_status("TYPE_REGISTRY"),
                "MEMBER_REGISTRY": self._stage_status("MEMBER_REGISTRY"),
                "evidence_level": "E3 structural + E4 consumer code (historical proofs in docs/reverse/)",
            },
            "method_code": {
                "RVA_REGISTRY": self._stage_status("METHOD_CODE_REGISTRY"),
                "evidence_level": "E3 structural + E4 code table consumer",
            },
            "design_runtime": {
                "STATIC_FACTORY": self._stage_status("DESIGN_RUNTIME_BRIDGE"),
                "POLYMORPHIC_RUNTIME": runtime_status,
                "correction": "SkillAbilityConfig.AbilityList = List<string>; "
                              "generated registry, not Black Swan semantic proof",
            },
        }
        write_anomalies(self.version_dir / "anomalies.json", self.anomalies)
        write_pipeline_report(
            self.version_dir / "pipeline_report.json",
            game_version=self.manifest["game_version"],
            build_string=self.manifest.get("build_string"),
            stages=self.stages,
            anomalies=self.anomalies,
            counts=self.counts,
            runtime_status=runtime_status,
            evidence_summary=evidence_summary,
        )
        # Also expose the canonical reports next to normalized output.
        assert self.normalized_dir is not None
        for name in ("manifest.json", "pipeline_report.json", "anomalies.json",
                     "design_runtime_registry.json"):
            src = self.version_dir / name
            if src.is_file():
                write_json(self.normalized_dir / name, __import__("json").load(open(src, encoding="utf-8")))
        write_json(self.normalized_dir / "pipeline_report.json",
                   __import__("json").load(open(self.version_dir / "pipeline_report.json", encoding="utf-8")))

        failed = [s.stage for s in self.stages
                  if s.stage != "DESIGNDATA_STRUCTURAL_PARSE" and s.status == "FAIL"]
        print("\n=== PIPELINE SUMMARY ===")
        for s in self.stages:
            print(f"  {s.stage:28s} {s.status}")
        print(f"  runtime_enrichment = {runtime_status}")
        print(f"  static_failed = {failed or 'none'}")
        print(f"  report = {self.version_dir / 'pipeline_report.json'}")
        return 1 if failed else 0

    def _stage_status(self, name: str) -> str:
        for s in self.stages:
            if s.stage == name:
                return s.status
        return "NOT_RUN"


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="HSR unpack/reverse pipeline v1")
    ap.add_argument("--game-root", required=True, type=Path,
                    help="client install root (directory name is never used as version)")
    ap.add_argument("--output-root", type=Path,
                    default=REPO_ROOT / "data" / "parsed",
                    help="parsed stage artifacts root (default data/parsed)")
    ap.add_argument("--normalized-root", type=Path,
                    default=REPO_ROOT / "data" / "normalized",
                    help="normalized registry root (default data/normalized)")
    ap.add_argument("--diff-root", type=Path,
                    default=REPO_ROOT / "data" / "diff",
                    help="version diff root (default data/diff)")
    ap.add_argument("--runtime-snapshot", type=Path, default=None,
                    help="optional read-only MKIOEPLIEIH registry snapshot JSON")
    ap.add_argument("--reference-normalized", type=Path, default=None,
                    help="optional baseline normalized version dir for full diff")
    ap.add_argument("--legacy-reference", type=Path, default=None,
                    help="optional archived raw evidence dir (e.g. data/raw/4.4.0)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    runner = PipelineRunner(args)
    return runner.run()


if __name__ == "__main__":
    raise SystemExit(main())
