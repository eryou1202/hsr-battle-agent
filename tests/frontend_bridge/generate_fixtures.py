"""Explicit test-fixture export only; never imported by the HTTP server.

Run from the repository with its package on sys.path. No content ingestion,
reverse/compiler regeneration, production assets or registry writes occur.
"""
from pathlib import Path

from hsr_battle_agent.frontend_bridge.contract import CONTENT_VERSION, bridge_info
from hsr_battle_agent.frontend_bridge.server import build_authorities
from hsr_battle_agent.game_data.nanoka_content import stable_bytes
from tests.product_support.test_scenario_support_report import _request


def main() -> None:
    stack = build_authorities(CONTENT_VERSION)
    destination = Path(__file__).resolve().parents[2] / "frontend/src/fe3/scenarioBridgeFixtures"
    destination.mkdir(exist_ok=True)
    free = _request("p5b-free")
    overlay = _request("p5b-overlay", source_stage_id=420101)
    overlay["enemy_waves"][0]["enemies"][0]["monster_id"] = "100401401"
    overlay["rules"]["victory_rule_id"] = "caller-reference"
    requests = {
        "free": free,
        "stage": _request("p5b-stage", source_stage_id=420101, enemy_waves=None),
        "overlay": overlay,
    }
    documents = {"info.json": bridge_info(), "free.request.json": free}
    for name, request in requests.items():
        documents[f"{name}.package.json"] = stack.compiler.compile(request)
    documents["free.report.json"] = stack.reporter.build(documents["free.package.json"])
    for name, document in documents.items():
        payload = stable_bytes(document)
        (destination / name).write_bytes(payload)
        print(f"{name}: {len(payload)} bytes")


if __name__ == "__main__":
    main()
