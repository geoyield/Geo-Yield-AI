"""
Smoke-checks the logging setup without needing a database, AWS or any
third-party package.

    PYTHONPATH=. python3 scripts/check_logging.py

Prints the same events twice -- once as they appear locally (readable text)
and once as they appear in production (one JSON line per event) -- then
verifies the schema, the trace id and the CloudWatch gating.
"""

import io
import json
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.observability import (  # noqa: E402
    configure_logging,
    get_logger,
    log_event,
    reset_trace_id,
    set_trace_id,
)
from backend.observability.cloudwatch import _shipping_enabled  # noqa: E402


def emit_sample_events():
    log = get_logger("api.informes")
    token = set_trace_id("demo-trace-1")
    try:
        log.debug("DEBUG line (hidden in production)")
        log.info("GET /api/distritos 200")
        log_event(
            log, "INFO", "Report generated",
            event="informe.generado", codi_districte="01", duration_ms=1234.5,
        )
        log_event(
            get_logger("api.geocodificacion"), "WARNING",
            "Address could not be geocoded", event="direccion.no_encontrada",
            direccion="Carrer de Mallorca 401",  # must come out redacted
        )
        try:
            raise ValueError("the model is unreachable")
        except ValueError:
            log.exception("Report generation failed")
    finally:
        reset_trace_id(token)


def run(env: dict) -> str:
    for key in ("ENV", "LOG_FORMAT", "LOG_LEVEL", "LOG_CLOUDWATCH_ENABLED",
                "LOG_CLOUDWATCH_GROUP", "NO_COLOR"):
        os.environ.pop(key, None)
    os.environ.update(env)

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        configure_logging(force=True)
        emit_sample_events()
    return buffer.getvalue()


def check(label: str, passed: bool) -> bool:
    print(f"  {'PASS' if passed else 'FAIL'}  {label}")
    return passed


def main() -> int:
    print("\n=== LOCAL (ENV=development) -- what you see in the terminal ===\n")
    local = run({"ENV": "development"})
    print(local.rstrip())

    print("\n=== PRODUCTION (ENV=production) -- what reaches CloudWatch ===\n")
    production = run({"ENV": "production"})
    print(production.rstrip())

    events = [json.loads(line) for line in production.splitlines() if line.startswith("{")]
    redacted = run({"ENV": "production"})

    print("\n=== Checks ===\n")
    ok = [
        check("local output is readable text, not JSON", "{" not in local.splitlines()[0]),
        check("local shows DEBUG", "DEBUG line" in local),
        check("production emits one JSON object per line", len(events) >= 3),
        check("production hides DEBUG", "DEBUG line" not in production),
        check("every event carries the shared schema keys", all(
            {"timestamp", "level", "service", "env", "version", "logger", "message"} <= set(e)
            for e in events
        )),
        check("trace id is on every event", all(e.get("trace_id") == "demo-trace-1" for e in events)),
        check("exceptions become a structured error object", any(
            e.get("error", {}).get("type") == "ValueError" for e in events
        )),
        check("the user's address is redacted (GDPR)", "Mallorca" not in redacted),
        check("CloudWatch stays off locally", not _shipping_enabled_in("development", "/geoyield/api")),
        check("CloudWatch stays off in production without a log group",
              not _shipping_enabled_in("production", "")),
        check("CloudWatch turns on in production with a log group",
              _shipping_enabled_in("production", "/geoyield/api")),
    ]

    print()
    if all(ok):
        print(f"All {len(ok)} checks passed.\n")
        return 0
    print(f"{ok.count(False)} of {len(ok)} checks FAILED.\n")
    return 1


def _shipping_enabled_in(env: str, group: str) -> bool:
    os.environ["ENV"] = env
    os.environ["LOG_CLOUDWATCH_GROUP"] = group
    os.environ.pop("LOG_CLOUDWATCH_ENABLED", None)
    return _shipping_enabled(group)


if __name__ == "__main__":
    raise SystemExit(main())
