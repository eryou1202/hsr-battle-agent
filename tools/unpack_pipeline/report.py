# -*- coding: utf-8 -*-
"""Pipeline capability report and anomaly report writers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import Anomaly, StageResult, STATIC_STAGES, utc_now, write_json
from . import PIPELINE_SCHEMA_VERSION, PIPELINE_VERSION


def write_anomalies(path: Path, anomalies: list[Anomaly]) -> None:
    write_json(path, {
        "schema": "unpack_pipeline_anomalies/1",
        "generated_at": utc_now(),
        "count": len(anomalies),
        "items": [a.as_dict() for a in anomalies],
    })


def write_pipeline_report(path: Path, *, game_version: str, build_string: str | None,
                          stages: list[StageResult], anomalies: list[Anomaly],
                          counts: dict[str, Any], runtime_status: str,
                          evidence_summary: dict[str, Any]) -> None:
    static_failed = [s for s in stages if s.stage in STATIC_STAGES and s.status == "FAIL"]
    static_passed = all(s.status == "PASS" for s in stages
                        if s.stage in STATIC_STAGES)
    report = {
        "schema": "unpack_pipeline_report/1",
        "pipeline_schema_version": PIPELINE_SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": utc_now(),
        "version": game_version,
        "build_string": build_string,
        "stage_statuses": [s.as_dict() for s in stages],
        "counts": counts,
        "warnings": sorted({w for s in stages for w in s.warnings}),
        "anomaly_count": len(anomalies),
        "static_pipeline": "PASS" if static_passed else "FAIL",
        "static_failed_stages": [s.stage for s in static_failed],
        "runtime_enrichment": runtime_status,
        "evidence_summary": evidence_summary,
        "final_status": (
            "UNPACK_PIPELINE = V1_COMPLETE"
            if static_passed and runtime_status == "PASS"
            else "UNPACK_PIPELINE = V1_STATIC_COMPLETE"
            if static_passed and runtime_status == "NOT_RUN"
            else "UNPACK_PIPELINE = V1_PARTIAL"
        ),
    }
    write_json(path, report)
