"""Real loopback HTTP requests over the public Scenario/P4 authority stack."""
from __future__ import annotations

import ast
from hashlib import sha256
import http.client
import json
from pathlib import Path
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

from hsr_battle_agent.frontend_bridge import server as module
from hsr_battle_agent.frontend_bridge.contract import (
    CONTENT_VERSION, DEFAULT_ORIGINS, ERROR_SCHEMA, MAX_REQUEST_BYTES, bridge_info, validate_origins,
)
from hsr_battle_agent.frontend_bridge.server import AuthorityStack, BridgeStartupError, build_authorities, create_server
from hsr_battle_agent.game_data.nanoka_content import default_db_path, stable_bytes
from tests.product_support.test_scenario_support_report import _request

ROOT = Path(__file__).resolve().parents[2]


class StartupContractTests(unittest.TestCase):
    def test_version_is_required_and_never_latest(self):
        for version in (None, "", "latest", "4.5.54"):
            with self.subTest(version=version), self.assertRaises(BridgeStartupError):
                build_authorities(version)
        with self.assertRaises(TypeError):
            create_server()

    def test_coherent_identity_and_version_are_mandatory(self):
        database = SimpleNamespace(game_version=CONTENT_VERSION)
        registry = SimpleNamespace(content_version="4.5.54")
        stack = AuthorityStack(database, registry, SimpleNamespace(database=database), SimpleNamespace(database=database, registry=registry))
        with self.assertRaises(BridgeStartupError):
            stack.validate()
        registry.content_version = CONTENT_VERSION
        stack.validate()
        stack.reporter.registry = SimpleNamespace(content_version=CONTENT_VERSION)
        with self.assertRaises(BridgeStartupError):
            stack.validate()

    def test_startup_rejects_missing_db_without_creating_it(self):
        absent = ROOT / "data/db/p5b-must-never-create.sqlite"
        self.assertFalse(absent.exists())
        with patch.object(module, "default_db_path", return_value=absent), patch.object(module, "ContentDatabase") as facade:
            with self.assertRaises(BridgeStartupError):
                build_authorities(CONTENT_VERSION)
            facade.assert_not_called()
        self.assertFalse(absent.exists())

    def test_registry_version_mismatch_refuses_start_before_compiler(self):
        with patch.object(module, "load_registry", return_value=SimpleNamespace(content_version="4.5.54")), \
             patch.object(module, "ScenarioCompiler") as compiler:
            with self.assertRaises(BridgeStartupError):
                build_authorities(CONTENT_VERSION)
            compiler.assert_not_called()

    def test_only_explicit_local_origins_and_no_execution_imports(self):
        self.assertEqual(validate_origins(DEFAULT_ORIGINS), DEFAULT_ORIGINS)
        for origin in ("*", "null", "https://evil.example", "http://0.0.0.0:5173", "http://localhost:5173/path", "http://user@localhost:5173"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                validate_origins((origin,))
        source = Path(module.__file__).read_text(encoding="utf-8")
        imports = [node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]
        self.assertFalse(any(any(term in name for term in ("reference_sandbox", "battle_sandbox", "reference_battle_planner", "content_planner")) for name in imports if name))
        self.assertNotIn("ThreadingHTTPServer", source)
        self.assertNotIn("eval(", source)
        self.assertNotIn("exec(", source)
        self.assertNotIn("read_text(", source)


@unittest.skipUnless(default_db_path(CONTENT_VERSION).is_file(), "real 4.4.54 DB required")
class LocalHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(CONTENT_VERSION, port=0)
        cls.stack = cls.server.authorities
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(5)

    def http(self, method="GET", path="/api/v1/info", value=None, *, body=None, headers=None):
        if value is not None:
            body = stable_bytes(value)
        request_headers = {"Content-Type": "application/json"} if body is not None else {}
        request_headers.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            payload = response.read()
            return response.status, dict(response.getheaders()), payload
        finally:
            connection.close()

    def error(self, result, code):
        status, headers, payload = result
        document = json.loads(payload)
        self.assertEqual(document["schema"], ERROR_SCHEMA)
        self.assertEqual(document["code"], code)
        self.assertGreaterEqual(status, 400)
        self.assertEqual(set(document), {"schema", "code", "message", "request_kind"})
        self.assertNotIn("*", headers.get("Access-Control-Allow-Origin", ""))
        for forbidden in (str(ROOT), "sqlite", "Traceback", "File ", "C:\\", "D:\\", "registry_path", "PYTHONPATH"):
            self.assertNotIn(forbidden, payload.decode())
        return document

    def test_info_is_deterministic_loopback_only_and_denies_execution(self):
        first = self.http()
        self.assertEqual(first[0], 200)
        self.assertEqual(first[2], stable_bytes(bridge_info()))
        self.assertEqual(first[2], self.http()[2])
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        info = json.loads(first[2])
        self.assertEqual(info["content_version"], CONTENT_VERSION)
        self.assertEqual(info["host_scope"], "LOOPBACK_ONLY")
        self.assertEqual(info["capabilities"], {"scenario_compile": True, "scenario_support_report": True,
                                               "battle_execution": False, "planner": False, "native_execution": False})
        self.assertNotIn("path", info)

    def test_free_compile_is_byte_equivalent_to_authority_and_does_not_report(self):
        request = _request("p5b-free")
        expected = self.stack.compiler.compile(request)
        with patch.object(self.stack.reporter, "build", side_effect=AssertionError("support must be separate")):
            status, _, payload = self.http("POST", "/api/v1/scenario/compile", request)
        self.assertEqual(status, 200)
        self.assertEqual(payload, stable_bytes(expected))
        package = json.loads(payload)
        self.assertEqual(package["schema"], "hsr_battle_agent.scenario_package/2")
        self.assertIsNone(package["source_stage"])
        self.assertFalse(package["golden_eligible"])

    def test_stage_compile_preserves_variant_identity_and_template_provenance(self):
        request = _request("p5b-stage", source_stage_id=420101, enemy_waves=None)
        expected = self.stack.compiler.compile(request)
        status, _, payload = self.http("POST", "/api/v1/scenario/compile", request)
        self.assertEqual(status, 200)
        self.assertEqual(payload, stable_bytes(expected))
        package = json.loads(payload)
        wave = package["waves"][0]
        self.assertEqual(wave["origin"], "TEMPLATE")
        self.assertEqual(wave["wave_id"], "420101:1")
        self.assertEqual(wave["provenance"]["source_stage_id"], "420101")
        enemy = wave["enemies"][0]
        self.assertEqual(enemy["monster_id"], "100401401")
        self.assertEqual(enemy["resolution"], {"requested_id": "100401401", "resolved_kind": "MONSTER_VARIANT",
                                               "canonical_monster_id": "1004014", "variant_id": "100401401"})

    def test_overlay_rules_and_requested_variant_are_preserved(self):
        request = _request("p5b-overlay", source_stage_id=420101)
        request["enemy_waves"][0]["enemies"][0]["monster_id"] = "100401401"
        request["rules"]["victory_rule_id"] = "caller-reference"
        expected = self.stack.compiler.compile(request)
        status, _, payload = self.http("POST", "/api/v1/scenario/compile", request)
        self.assertEqual(status, 200)
        self.assertEqual(payload, stable_bytes(expected))
        self.assertEqual(expected["waves"][0]["origin"], "TEMPLATE_WITH_CALLER_OVERRIDE")
        self.assertEqual(expected["rules"]["victory_rule"]["resolution_status"], "UNKNOWN")
        self.assertEqual(expected["rules"]["victory_rule"]["execution_semantics"], "NONE")

    def test_support_accepts_raw_compile_response_and_is_byte_equivalent_to_p4(self):
        for request in (_request("p5b-free-support"), _request("p5b-stage-support", source_stage_id=420101, enemy_waves=None)):
            with self.subTest(scenario=request["scenario_id"]):
                status, _, compiled_bytes = self.http("POST", "/api/v1/scenario/compile", request)
                self.assertEqual(status, 200)
                package = json.loads(compiled_bytes)
                expected = self.stack.reporter.build(package)
                with patch.object(self.stack.compiler, "compile", side_effect=AssertionError("no implicit compile")):
                    status, _, payload = self.http("POST", "/api/v1/scenario/support", body=compiled_bytes)
                self.assertEqual(status, 200)
                self.assertEqual(payload, stable_bytes(expected))
                report = json.loads(payload)
                self.assertFalse(report["non_claims"]["planner_invoked"])
                self.assertFalse(report["non_claims"]["real_content_execution_performed"])
                self.assertTrue(all(result["outcome"] == "REJECTED" for result in report["real_content_execution_admission"]["results"]))
                self.assertTrue(all(value == 0 for value in report["real_content_execution_admission"]["non_effects"].values()))
                self.assertEqual(report["monster_runtime_support"]["scope"], "FAMILY_LEVEL_ONLY")

    def test_invalid_json_duplicate_keys_and_nonstandard_numbers_fail(self):
        for body in (b"{", b"[]", b'{"a":1,"a":2}', b'{"seed":NaN}', b'{"seed":Infinity}', b'\xff'):
            with self.subTest(body=body):
                self.error(self.http("POST", "/api/v1/scenario/compile", body=body), "INVALID_JSON")

    def test_non_json_media_types_are_rejected(self):
        for media in ("text/plain", "application/x-www-form-urlencoded", "application/jsonp"):
            with self.subTest(media=media):
                self.error(self.http("POST", "/api/v1/scenario/compile", body=b"{}", headers={"Content-Type": media}), "UNSUPPORTED_MEDIA_TYPE")

    def test_oversized_body_rejected_before_reading_or_parsing(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            with patch.object(self.stack.compiler, "compile") as compiler:
                connection.putrequest("POST", "/api/v1/scenario/compile")
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Content-Length", str(MAX_REQUEST_BYTES + 1))
                connection.endheaders()  # No body is transmitted.
                response = connection.getresponse()
                self.error((response.status, dict(response.getheaders()), response.read()), "REQUEST_TOO_LARGE")
                compiler.assert_not_called()
        finally:
            connection.close()

    def test_unknown_routes_and_wrong_methods_are_typed(self):
        for path in ("/api/v1/characters", "/api/v1/battle/step", "/api/v1/planner", "/api/v1/scenario/analyze", "/api/v1/info?path=secret", "/../../secret"):
            with self.subTest(path=path):
                self.error(self.http(path=path), "NOT_FOUND")
        for method, path in (("GET", "/api/v1/scenario/compile"), ("POST", "/api/v1/info"), ("DELETE", "/api/v1/info"), ("BOGUS", "/api/v1/info")):
            with self.subTest(method=method):
                self.error(self.http(method, path, body=b"{}"), "METHOD_NOT_ALLOWED")

    def test_invalid_scenarios_and_versions_are_sanitized(self):
        for request in ({"game_version": CONTENT_VERSION}, _request("invalid", source_stage_id="D:\\private\\content.sqlite")):
            self.error(self.http("POST", "/api/v1/scenario/compile", request), "SCENARIO_COMPILE_REJECTED")
        for version in (None, "latest", "4.5.54"):
            request = _request("wrong-version")
            request["game_version"] = version
            self.error(self.http("POST", "/api/v1/scenario/compile", request), "UNSUPPORTED_CONTENT_VERSION")

    def test_p4_rejects_legacy_hash_tamper_shape_and_version(self):
        valid = self.stack.compiler.compile(_request("p5b-reject"))
        for change in ({"schema": "hsr_battle_agent.scenario_package/1"}, {"package_sha256": "0" * 64},
                       {"players": "invalid"}, {"game_version": "4.5.54"}):
            with self.subTest(change=change):
                self.error(self.http("POST", "/api/v1/scenario/support", {**valid, **change}), "SUPPORT_REPORT_REJECTED")

    def test_untrusted_origins_and_rebinding_hosts_are_rejected_before_authority(self):
        with patch.object(self.stack.compiler, "compile") as compiler:
            for origin in ("https://evil.example", "null", "http://localhost:9999"):
                result = self.http("POST", "/api/v1/scenario/compile", _request("drive-by"), headers={"Origin": origin})
                self.error(result, "ORIGIN_NOT_ALLOWED")
                self.assertNotIn("Access-Control-Allow-Origin", result[1])
            self.error(self.http(headers={"Host": "attacker.example"}), "ORIGIN_NOT_ALLOWED")
            compiler.assert_not_called()

    def test_allowed_origin_and_cli_without_origin_work(self):
        for origin in DEFAULT_ORIGINS:
            result = self.http(headers={"Origin": origin})
            self.assertEqual(result[0], 200)
            self.assertEqual(result[1]["Access-Control-Allow-Origin"], origin)
            self.assertNotIn("Access-Control-Allow-Credentials", result[1])
        self.assertEqual(self.http()[0], 200)

    def test_options_only_allows_known_route_origin_method_and_header(self):
        headers = {"Origin": DEFAULT_ORIGINS[0], "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
        result = self.http("OPTIONS", "/api/v1/scenario/compile", headers=headers)
        self.assertEqual(result[0], 204)
        self.assertEqual(result[1]["Access-Control-Allow-Methods"], "POST")
        self.assertEqual(result[2], b"")
        self.error(self.http("OPTIONS", "/api/v1/unknown", headers=headers), "NOT_FOUND")
        self.error(self.http("OPTIONS", "/api/v1/scenario/compile", headers={**headers, "Origin": "https://evil.example"}), "ORIGIN_NOT_ALLOWED")
        self.error(self.http("OPTIONS", "/api/v1/scenario/compile", headers={**headers, "Access-Control-Request-Method": "DELETE"}), "METHOD_NOT_ALLOWED")
        self.error(self.http("OPTIONS", "/api/v1/scenario/compile", headers={**headers, "Access-Control-Request-Headers": "x-python-method"}), "UNSUPPORTED_MEDIA_TYPE")

    def test_internal_exceptions_do_not_leak_paths_or_tracebacks(self):
        with patch.object(self.stack.compiler, "compile", side_effect=RuntimeError("D:\\private\\registry.sqlite\nTraceback secret")):
            self.error(self.http("POST", "/api/v1/scenario/compile", _request("error")), "INTERNAL_ERROR")

    def test_requests_do_not_write_db_registry_or_files_or_read_raw_registry(self):
        path = default_db_path(CONTENT_VERSION)
        before = sha256(path.read_bytes()).hexdigest()
        observed = []
        original = Path.open
        def open_read_only(p, mode="r", *args, **kwargs):
            self.assertFalse(any(letter in mode for letter in ("w", "a", "x", "+")))
            observed.append(p.as_posix())
            return original(p, mode, *args, **kwargs)
        with patch.object(Path, "open", open_read_only):
            status, _, payload = self.http("POST", "/api/v1/scenario/compile", _request("p5b-pure"))
            self.assertEqual(status, 200)
            self.assertEqual(self.http("POST", "/api/v1/scenario/support", body=payload)[0], 200)
        self.assertFalse(any("registry" in p.lower() for p in observed))
        self.assertEqual(before, sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
