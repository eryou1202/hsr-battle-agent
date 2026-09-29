"""Transport metadata only; ScenarioCompiler and P4 own document semantics."""
from __future__ import annotations

from urllib.parse import urlsplit

CONTENT_VERSION = "4.4.54"
BRIDGE_VERSION = "1"
BIND_ADDRESS = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_REQUEST_BYTES = 2 * 1024 * 1024
INFO_SCHEMA = "hsr_battle_agent.frontend_bridge_info/1"
ERROR_SCHEMA = "hsr_battle_agent.frontend_bridge_error/1"
SCENARIO_SCHEMA = "hsr_battle_agent.scenario_package/2"
REPORT_SCHEMA = "hsr_battle_agent.scenario_support_report/1"
ROUTES = {"/api/v1/info": "GET", "/api/v1/scenario/compile": "POST", "/api/v1/scenario/support": "POST"}
REQUEST_KINDS = {"/api/v1/info": "INFO", "/api/v1/scenario/compile": "SCENARIO_COMPILE", "/api/v1/scenario/support": "SCENARIO_SUPPORT"}
DEFAULT_ORIGINS = (
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:4173", "http://127.0.0.1:4173",
)
# Messages never interpolate exception text, requests, file paths or stack frames.
ERRORS = {
    "INVALID_JSON": (400, "A complete valid JSON object is required."),
    "REQUEST_TOO_LARGE": (413, "The request exceeds the bridge body limit."),
    "UNSUPPORTED_CONTENT_VERSION": (400, "Explicit content version 4.4.54 is required."),
    "SCENARIO_COMPILE_REJECTED": (422, "ScenarioCompiler rejected the request; check selected content and required fields."),
    "SUPPORT_REPORT_REJECTED": (422, "ScenarioSupportReporter rejected the package; check its schema, shape, version and hash."),
    "METHOD_NOT_ALLOWED": (405, "This method is unavailable for this route."),
    "NOT_FOUND": (404, "This bridge route does not exist."),
    "UNSUPPORTED_MEDIA_TYPE": (415, "Content-Type application/json is required."),
    "ORIGIN_NOT_ALLOWED": (403, "Only explicitly allowed local development origins and loopback hosts are accepted."),
    "INTERNAL_ERROR": (500, "The local bridge could not complete the request."),
}


def validate_origins(origins: tuple[str, ...]) -> tuple[str, ...]:
    for origin in origins:
        url = urlsplit(origin)
        if (url.scheme not in ("http", "https") or url.hostname not in ("localhost", BIND_ADDRESS)
                or url.username is not None or url.password is not None or url.path or url.query
                or url.fragment or url.netloc != (url.hostname + (f":{url.port}" if url.port is not None else ""))):
            raise ValueError("INVALID_LOCAL_ORIGIN_ALLOWLIST")
    return tuple(dict.fromkeys(origins))


def bridge_info() -> dict:
    return {
        "schema": INFO_SCHEMA, "bridge_version": BRIDGE_VERSION,
        "content_version": CONTENT_VERSION, "host_scope": "LOOPBACK_ONLY",
        "capabilities": {"scenario_compile": True, "scenario_support_report": True,
                         "battle_execution": False, "planner": False, "native_execution": False},
        "accepted_input": {"scenario_compile": "ScenarioCompiler request", "scenario_support_report": SCENARIO_SCHEMA},
        "produced_documents": {"scenario_compile": SCENARIO_SCHEMA, "scenario_support_report": REPORT_SCHEMA},
    }


def bridge_error(code: str, request_kind: str) -> dict:
    return {"schema": ERROR_SCHEMA, "code": code, "message": ERRORS[code][1], "request_kind": request_kind}
