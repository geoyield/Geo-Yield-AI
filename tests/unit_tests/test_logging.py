"""
Tests for structured logging (backend/observability/).

These cover the schema contract shared with the frontend logger: if it
changes on one side only, the CloudWatch Logs Insights queries stop working
across both services, which is the whole point of a common schema.
"""

import json
import logging

import pytest

from backend.observability import configure_logging, log_event, set_trace_id
from backend.observability.context import reset_trace_id
from backend.observability.logging_config import (
    JsonFormatter,
    _parse_level,
    is_production,
    redact,
)


@pytest.fixture
def emit(capsys, monkeypatch):
    """Emits a log record and returns the parsed JSON lines."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("SERVICE_NAME", "geoyield-api")
    monkeypatch.setenv("SERVICE_VERSION", "9.9.9")
    monkeypatch.delenv("LOG_CLOUDWATCH_ENABLED", raising=False)
    monkeypatch.delenv("LOG_FILE", raising=False)

    def _emit(fn):
        # Configured here rather than in the fixture body: pytest swaps
        # sys.stdout per test phase, and StreamHandler captures the stream at
        # construction time, so configuring during setup would write to a
        # buffer readouterr() no longer reads.
        configure_logging(force=True)
        fn(logging.getLogger("geoyield.api"))
        out = capsys.readouterr().out.strip().splitlines()
        return [json.loads(line) for line in out if line.startswith("{")]

    return _emit


def test_every_event_is_one_json_line_with_the_contract_keys(emit):
    events = emit(lambda log: log.info("hello"))

    assert len(events) == 1
    event = events[0]
    for key in ("timestamp", "level", "service", "env", "version", "logger", "message"):
        assert key in event, f"missing contract key: {key}"

    assert event["level"] == "INFO"
    assert event["service"] == "geoyield-api"
    assert event["env"] == "test"
    assert event["version"] == "9.9.9"
    assert event["message"] == "hello"


def test_a_multiline_message_stays_a_single_line(emit):
    """CloudWatch splits on newlines, so one event must occupy one line."""
    events = emit(lambda log: log.info("line1\nline2\nline3"))

    assert len(events) == 1
    assert events[0]["message"] == "line1\nline2\nline3"


def test_level_is_uppercase_like_the_frontend(emit):
    assert emit(lambda log: log.warning("careful"))[0]["level"] == "WARNING"


def test_trace_id_propagates_to_every_logger(emit):
    """
    The property that justifies the whole setup: a trace id pinned by the
    middleware must also appear on RAG and agent lines, which know nothing
    about HTTP.
    """
    token = set_trace_id("abc123def456")
    try:
        events = emit(
            lambda _: (
                logging.getLogger("geoyield.api.informes").info("from the api"),
                logging.getLogger("geoyield.rag.gemini_adapter").info("from rag"),
                logging.getLogger("geoyield.ia.agent").info("from the agent"),
            )
        )
    finally:
        reset_trace_id(token)

    assert len(events) == 3
    assert all(event["trace_id"] == "abc123def456" for event in events)


def test_no_trace_id_outside_a_request(emit):
    assert "trace_id" not in emit(lambda log: log.info("outside a request"))[0]


def test_log_event_puts_kwargs_under_context(emit):
    event = emit(
        lambda log: log_event(
            log, "INFO", "Report generated",
            event="informe.generado", duration_ms=1234.5678, codi_districte="01",
        )
    )[0]

    assert event["event"] == "informe.generado"
    assert event["duration_ms"] == 1234.57
    assert event["context"] == {"codi_districte": "01"}


def test_an_exception_becomes_the_error_object(emit):
    def _raise(log):
        try:
            raise ValueError("something broke")
        except ValueError:
            log.exception("could not process")

    event = emit(_raise)[0]

    assert event["level"] == "ERROR"
    assert event["error"]["type"] == "ValueError"
    assert event["error"]["message"] == "something broke"
    assert "Traceback" in event["error"]["stack"]


def test_a_non_serialisable_value_does_not_break_the_log(emit):
    class Odd:
        def __repr__(self):
            return "<Odd>"

    events = emit(lambda log: log_event(log, "INFO", "x", obj=Odd()))
    assert events[0]["context"]["obj"] == "<Odd>"


def test_the_user_address_never_reaches_the_log(emit):
    """The geocoder's free-text address is personal data."""
    event = emit(
        lambda log: log_event(
            log, "INFO", "geocoded",
            direccion="Carrer de Mallorca 401", codi_districte="02",
        )
    )[0]

    assert event["context"]["direccion"] == "[REDACTED]"
    assert event["context"]["codi_districte"] == "02"


def test_redaction_reaches_nested_keys():
    data = {"level1": {"level2": {"api_key": "secret", "ok": "visible"}}}
    assert redact(data)["level1"]["level2"] == {"api_key": "[REDACTED]", "ok": "visible"}


def test_redaction_does_not_loop_on_circular_structures():
    data = {}
    data["self"] = data
    redact(data)  # must not raise RecursionError


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("20", logging.INFO),
        ("10", logging.DEBUG),
        ("INFO", logging.INFO),
        ("debug", logging.DEBUG),
        ("ERROR", logging.ERROR),
        # The previous int() cast crashed startup on LOG_LEVEL=INFO.
        ("banana", logging.INFO),
        ("", logging.INFO),
        (None, logging.INFO),
    ],
)
def test_parse_level_accepts_numbers_and_names(raw, expected):
    assert _parse_level(raw) == expected


def test_configuring_twice_does_not_duplicate_handlers(monkeypatch, capsys):
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.delenv("LOG_CLOUDWATCH_ENABLED", raising=False)
    configure_logging(force=True)
    configure_logging()
    configure_logging()

    logging.getLogger("geoyield.api").warning("only once")
    lines = [l for l in capsys.readouterr().out.strip().splitlines() if l.startswith("{")]
    assert len(lines) == 1


def test_the_formatter_takes_service_from_the_record_not_the_client():
    """The /api/logs router sets it; a browser-supplied value is ignored."""
    formatter = JsonFormatter(service="geoyield-api", env="test", version="1.0")
    record = logging.LogRecord("x", logging.INFO, "f", 1, "m", None, None)
    record.service = "geoyield-frontend"

    assert json.loads(formatter.format(record))["service"] == "geoyield-frontend"


# --- Behaviour derived from ENV ---------------------------------------------


@pytest.mark.parametrize("value,expected", [
    ("production", True),
    ("PRODUCTION", True),
    ("prod", True),
    ("development", False),
    ("staging", False),
    ("", False),
])
def test_is_production_recognises_the_usual_spellings(value, expected):
    assert is_production(value) is expected


def _log_one(monkeypatch, capsys, **env):
    for key in ("ENV", "LOG_FORMAT", "LOG_LEVEL", "LOG_CLOUDWATCH_ENABLED",
                "LOG_CLOUDWATCH_GROUP", "LOG_FILE", "NO_COLOR"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    # NO_COLOR keeps the assertions free of ANSI escapes.
    monkeypatch.setenv("NO_COLOR", "1")

    configure_logging(force=True)
    log = logging.getLogger("geoyield.api")
    log.debug("a debug line")
    log.info("an info line")
    return capsys.readouterr().out


def test_locally_logs_are_readable_text_with_debug_visible(monkeypatch, capsys):
    out = _log_one(monkeypatch, capsys, ENV="development")

    assert "{" not in out, "local logs must not be JSON"
    assert "a debug line" in out, "DEBUG must be visible locally"
    assert "INFO" in out


def test_in_production_logs_are_json_without_debug(monkeypatch, capsys):
    out = _log_one(monkeypatch, capsys, ENV="production")

    lines = [l for l in out.strip().splitlines() if l.startswith("{")]
    assert len(lines) == 1, "only the INFO line should be emitted"
    assert json.loads(lines[0])["message"] == "an info line"
    assert "a debug line" not in out


def test_log_format_overrides_the_environment_default(monkeypatch, capsys):
    out = _log_one(monkeypatch, capsys, ENV="development", LOG_FORMAT="json")
    assert any(l.startswith("{") for l in out.splitlines())


def test_log_level_overrides_the_environment_default(monkeypatch, capsys):
    out = _log_one(monkeypatch, capsys, ENV="production", LOG_LEVEL="DEBUG")
    assert "a debug line" in out
