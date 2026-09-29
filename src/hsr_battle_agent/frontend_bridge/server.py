"""Single-threaded HTTP transport over exactly one version-coherent authority stack."""
from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from typing import Any

from hsr_battle_agent.content_support import ContentSupportRegistry, load_registry
from hsr_battle_agent.game_data.nanoka_content import ContentDatabase, default_db_path, stable_bytes
from hsr_battle_agent.game_data.scenario_compiler import ScenarioCompiler, ScenarioCompileError
from hsr_battle_agent.product_support import ScenarioSupportReporter, ScenarioSupportReportError
from .contract import (
    BIND_ADDRESS, CONTENT_VERSION, DEFAULT_ORIGINS, DEFAULT_PORT, ERRORS,
    MAX_REQUEST_BYTES, REQUEST_KINDS, ROUTES, bridge_error, bridge_info, validate_origins,
)


class BridgeStartupError(ValueError):
    """Public startup failure with no local path/exception disclosure."""


@dataclass(frozen=True)
class AuthorityStack:
    database: ContentDatabase
    registry: ContentSupportRegistry
    compiler: ScenarioCompiler
    reporter: ScenarioSupportReporter

    def validate(self) -> None:
        if (self.database.game_version != CONTENT_VERSION or self.registry.content_version != CONTENT_VERSION
                or self.compiler.database is not self.database or self.reporter.database is not self.database
                or self.reporter.registry is not self.registry):
            raise BridgeStartupError("AUTHORITY_VERSION_OR_IDENTITY_MISMATCH")


def build_authorities(content_version: str) -> AuthorityStack:
    if content_version != CONTENT_VERSION:
        raise BridgeStartupError("UNSUPPORTED_CONTENT_VERSION")
    path = default_db_path(content_version)
    # The facade opens short-lived SQLite connections. Refuse a missing DB
    # before those connections can create a file; no provisioning is exposed.
    if not path.is_file():
        raise BridgeStartupError("CONTENT_DATABASE_UNAVAILABLE")
    try:
        database = ContentDatabase(path, content_version)
        registry = load_registry(content_version)
        if database.game_version != registry.content_version:
            raise BridgeStartupError("AUTHORITY_VERSION_OR_IDENTITY_MISMATCH")
        if not database.list_avatar_ids():
            raise BridgeStartupError("CONTENT_DATABASE_VERSION_UNAVAILABLE")
        stack = AuthorityStack(database, registry, ScenarioCompiler(database),
                               ScenarioSupportReporter(database, registry=registry))
        stack.validate()
        return stack
    except BridgeStartupError:
        raise
    except Exception:
        raise BridgeStartupError("AUTHORITY_UNAVAILABLE") from None


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("NON_JSON_NUMBER")


class ScenarioBridgeServer(HTTPServer):
    """No ThreadingMixIn: one request at a time uses the same authority stack."""
    def __init__(self, authorities: AuthorityStack, *, port: int = DEFAULT_PORT,
                 allowed_origins: tuple[str, ...] = DEFAULT_ORIGINS):
        authorities.validate()
        self.authorities = authorities
        self.allowed_origins = validate_origins(allowed_origins)
        super().__init__((BIND_ADDRESS, port), ScenarioBridgeHandler)

    def handle_error(self, request, client_address) -> None:
        # The stdlib default prints tracebacks. Unexpected socket failures are
        # contained here; handler failures get a sanitized JSON error instead.
        pass


class ScenarioBridgeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "HSRScenarioBridge/1"
    sys_version = ""
    server: ScenarioBridgeServer

    def setup(self) -> None:
        self.request.settimeout(10)
        super().setup()

    def log_message(self, format: str, *args) -> None:
        # Do not log request bodies, exception details or caller-controlled URLs.
        pass

    def _kind(self) -> str:
        return REQUEST_KINDS.get(getattr(self, "path", ""), "UNKNOWN")

    def _respond(self, status: int, document: dict | None, *, preflight: bool = False) -> None:
        payload = b"" if document is None else stable_bytes(document)
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Vary", "Origin")
        origin = getattr(self, "headers", {}).get("Origin")
        if origin in self.server.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            if preflight:
                self.send_header("Access-Control-Allow-Methods", ROUTES[self.path])
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if status == 405 and getattr(self, "path", "") in ROUTES:
            self.send_header("Allow", f"{ROUTES[self.path]}, OPTIONS")
        self.end_headers()
        if getattr(self, "command", "") != "HEAD" and payload:
            self.wfile.write(payload)

    def _error(self, code: str) -> None:
        self._respond(ERRORS[code][0], bridge_error(code, self._kind()))

    def send_error(self, code: int, message=None, explain=None) -> None:
        # Also replace stdlib protocol-error HTML and unsupported-method errors.
        transport = "REQUEST_TOO_LARGE" if code in (413, 414, 431) else (
            "METHOD_NOT_ALLOWED" if code == 501 else "INVALID_JSON")
        self._error(transport)

    def handle_expect_100(self) -> bool:
        # Buffered JSON only; do not acknowledge a body before transport gates.
        self._error("INVALID_JSON")
        return False

    def _gate(self) -> bool:
        host = self.headers.get_all("Host", [])
        port = self.server.server_address[1]
        if len(host) != 1 or host[0] not in (f"{BIND_ADDRESS}:{port}", f"localhost:{port}"):
            self._error("ORIGIN_NOT_ALLOWED")
            return False
        origins = self.headers.get_all("Origin", [])
        if len(origins) > 1 or (origins and origins[0] not in self.server.allowed_origins):
            self._error("ORIGIN_NOT_ALLOWED")
            return False
        if self.path not in ROUTES:
            self._error("NOT_FOUND")
            return False
        return True

    def do_OPTIONS(self) -> None:
        if not self._gate():
            return
        origin = self.headers.get("Origin")
        method = self.headers.get("Access-Control-Request-Method")
        headers = [name.strip().lower() for name in self.headers.get("Access-Control-Request-Headers", "").split(",") if name.strip()]
        if not origin or origin not in self.server.allowed_origins:
            self._error("ORIGIN_NOT_ALLOWED")
        elif method != ROUTES[self.path]:
            self._error("METHOD_NOT_ALLOWED")
        elif any(name != "content-type" for name in headers):
            self._error("UNSUPPORTED_MEDIA_TYPE")
        else:
            self._respond(204, None, preflight=True)

    def do_GET(self) -> None:
        if not self._gate():
            return
        if ROUTES[self.path] != "GET":
            self._error("METHOD_NOT_ALLOWED")
        else:
            self._respond(200, bridge_info())

    def _body(self) -> dict[str, Any] | None:
        media = self.headers.get_all("Content-Type", [])
        if len(media) != 1 or media[0].split(";", 1)[0].strip().lower() != "application/json":
            self._error("UNSUPPORTED_MEDIA_TYPE")
            return None
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") is not None or len(lengths) != 1 or not lengths[0].isdigit():
            self._error("INVALID_JSON")
            return None
        if len(lengths[0]) > len(str(MAX_REQUEST_BYTES)):
            self._error("REQUEST_TOO_LARGE")
            return None
        length = int(lengths[0])
        if length > MAX_REQUEST_BYTES:
            self._error("REQUEST_TOO_LARGE")
            return None
        try:
            payload = self.rfile.read(length)
            if len(payload) != length:
                raise ValueError("INCOMPLETE_BODY")
            value = json.loads(payload.decode("utf-8"), parse_constant=_invalid_constant, object_pairs_hook=_object_pairs)
            if not isinstance(value, dict):
                raise ValueError("OBJECT_REQUIRED")
        except (UnicodeError, ValueError, RecursionError, TimeoutError, OSError):
            self._error("INVALID_JSON")
            return None
        return value

    def do_POST(self) -> None:
        if not self._gate():
            return
        if ROUTES[self.path] != "POST":
            self._error("METHOD_NOT_ALLOWED")
            return
        try:
            value = self._body()
            if value is None:
                return
            stack = self.server.authorities
            # No request-provided paths or registries. Re-check existence so a
            # removed DB is not silently recreated by a facade connection.
            if not stack.database.database_path.is_file():
                self._error("INTERNAL_ERROR")
                return
            if self.path == "/api/v1/scenario/compile":
                if value.get("game_version") != CONTENT_VERSION:
                    self._error("UNSUPPORTED_CONTENT_VERSION")
                    return
                try:
                    document = stack.compiler.compile(value)
                except (ScenarioCompileError, ValueError, TypeError, KeyError, OverflowError):
                    self._error("SCENARIO_COMPILE_REJECTED")
                    return
            else:
                try:
                    document = stack.reporter.build(value)
                except (ScenarioSupportReportError, ValueError, TypeError, KeyError, OverflowError):
                    self._error("SUPPORT_REPORT_REJECTED")
                    return
            self._respond(200, document)
        except Exception:
            self._error("INTERNAL_ERROR")

    def _wrong_method(self) -> None:
        if self._gate():
            self._error("METHOD_NOT_ALLOWED")

    do_HEAD = _wrong_method
    do_PUT = _wrong_method
    do_PATCH = _wrong_method
    do_DELETE = _wrong_method
    do_TRACE = _wrong_method
    do_CONNECT = _wrong_method


def create_server(content_version: str, *, port: int = DEFAULT_PORT,
                  allowed_origins: tuple[str, ...] = DEFAULT_ORIGINS) -> ScenarioBridgeServer:
    return ScenarioBridgeServer(build_authorities(content_version), port=port, allowed_origins=allowed_origins)
