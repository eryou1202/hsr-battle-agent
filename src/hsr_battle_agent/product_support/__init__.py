# -*- coding: utf-8 -*-
"""Product aggregation layer above game_data / content_support / content_planner.

This namespace exists so that cross-layer *descriptive* aggregation has a home
that is not inside any frozen layer.  It imports the public M14 (``content_support``)
and M15 (``content_planner``) APIs and the game_data product projections, and it
edits none of them.

Contents
--------

* :mod:`hsr_battle_agent.product_support.scenario_report` -- the Scenario Support
  Report (``hsr_battle_agent.scenario_support_report/1``).

This layer is DESCRIPTIVE ONLY: it executes no battle, creates no legal action,
invokes no planner and promotes no evidence.
"""
from __future__ import annotations

from .scenario_report import (
    ACCEPTED_M15_OUTCOME,
    FUTURE_OUTCOME_AUTO_EXTENSION,
    SCENARIO_SUPPORT_REPORT_SCHEMA,
    ContentVersionMismatchError,
    MalformedScenarioPackageError,
    MissingM14RegistryError,
    ScenarioSupportReportError,
    ScenarioSupportReporter,
    UnsupportedFutureAdmissionOutcomeError,
    UnsupportedScenarioSchemaError,
    build_scenario_support_report,
)

__all__ = [
    "SCENARIO_SUPPORT_REPORT_SCHEMA",
    "ACCEPTED_M15_OUTCOME",
    "FUTURE_OUTCOME_AUTO_EXTENSION",
    "ScenarioSupportReporter",
    "build_scenario_support_report",
    "ScenarioSupportReportError",
    "MissingM14RegistryError",
    "UnsupportedScenarioSchemaError",
    "ContentVersionMismatchError",
    "MalformedScenarioPackageError",
    "UnsupportedFutureAdmissionOutcomeError",
]
