# -*- coding: utf-8 -*-
"""Generate data/sandbox/kernel_01_report.json from real inputs.

This script does not hardcode the test result: it discovers and runs the
Kernel 01 battle test suites, then writes the machine report only when all of
them pass.  The semantic artifact JSON is loaded and validated as the source
of the implemented primitive list.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.semantic_artifact import load_vertical_slice_01  # noqa: E402
from hsr_battle_agent.battle_sandbox.rng import (  # noqa: E402
    CLIENT_RNG_ALGORITHM,
    SANDBOX_RNG,
    SANDBOX_RNG_ALGORITHM,
)
from hsr_battle_agent.battle_sandbox.snapshot import SNAPSHOT_SCHEMA_VERSION  # noqa: E402
from hsr_battle_agent.battle_sandbox.state import BATTLE_STATE_SCHEMA_VERSION  # noqa: E402
from hsr_battle_agent.battle_sandbox.trace import TRACE_SCHEMA  # noqa: E402

TEST_DIRS = (
    REPO / "tests" / "battle_ir",
    REPO / "tests" / "battle_runtime",
    REPO / "tests" / "battle_sandbox",
)
OUTPUT_PATH = REPO / "data" / "sandbox" / "kernel_01_report.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    suite = unittest.TestSuite()
    for directory in TEST_DIRS:
        suite.addTests(unittest.defaultTestLoader.discover(
            start_dir=str(directory),
            top_level_dir=str(REPO),
            pattern="test_*.py",
        ))

    result = unittest.TestResult()
    suite.run(result)
    test_count = result.testsRun
    test_pass = test_count - len(result.failures) - len(result.errors)

    if result.failures or result.errors:
        print(f"kernel_01_report: {len(result.failures)} failure(s), "
              f"{len(result.errors)} error(s); refusing to write PASS report")
        return 1

    recovered = load_vertical_slice_01()
    artifact_path = REPO / "data" / "semantics" / "4.4.54" / "vertical_slice_01.json"

    report = {
        "schema": "battle_sandbox_kernel_report/1",
        "sandbox_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "battle_state_schema_version": BATTLE_STATE_SCHEMA_VERSION,
        "trace_schema": TRACE_SCHEMA,
        "game_semantic_version": recovered.provenance.game_version,
        "final_status": "BATTLE_SANDBOX = KERNEL_01_PROOF",
        "implemented_primitives": [
            {
                "primitive_id": recovered.spec.primitive_id,
                "semantic_name": recovered.spec.semantic_name,
                "result": recovered.spec.result,
                "determinism": recovered.spec.determinism,
                "context_reads": list(recovered.spec.context_reads),
                "context_writes": list(recovered.spec.context_writes),
                "source_runtime_type": recovered.provenance.runtime_type,
                "source_method": recovered.provenance.method,
                "source_method_index": recovered.provenance.method_index,
                "source_native_rva": recovered.provenance.native_rva,
                "evidence_level": recovered.provenance.evidence_level,
                "provenance_note": recovered.provenance.note,
            }
        ],
        "test_count": test_count,
        "test_pass": test_pass,
        "semantic_sources": [
            {
                "path": artifact_path.relative_to(REPO).as_posix(),
                "schema": "battle_semantics_vertical_slice/1",
                "evidence_level": recovered.provenance.evidence_level,
                "sha256": _sha256(artifact_path),
            }
        ],
        "rng": {
            "client_rng_algorithm": CLIENT_RNG_ALGORITHM,
            "sandbox_rng": SANDBOX_RNG,
            "sandbox_rng_algorithm": SANDBOX_RNG_ALGORITHM,
        },
        "not_implemented_surfaces": [
            "legal_actions",
            "step",
            "is_terminal",
        ],
        "known_unknowns": [
            "FieldDefinition provenance for the +0x30 ValueType tag byte",
            "Generic IL2CPP null-check helper internals (error path only)",
            "No E5 client-side runtime observation yet (out of scope for this slice)",
            "Real client PRNG algorithm (sandbox RNG is a deterministic abstraction)",
            "ARRAY/MAP heap contents are only carried as optional ObjectRef metadata; "
            "a real heap model is deferred until a recovered semantic slice reads them",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT_PATH.relative_to(REPO)} (tests={test_count}, pass={test_pass})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
