"""
Tests for POST /api/logs (browser log ingestion).

A public, unauthenticated endpoint that writes to CloudWatch, so most of
these cover the defences rather than the happy path.

A minimal FastAPI app with just this router is mounted instead of importing
the full application, to avoid pulling in langgraph and the RAG engine.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers import logs as logs_router
from backend.observability import configure_logging


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.delenv("LOG_CLOUDWATCH_ENABLED", raising=False)

    # Module-level state: without clearing, one test exhausting the bucket
    # would fail the next.
    logs_router._buckets.clear()

    app = FastAPI()
    app.include_router(logs_router.router)
    return TestClient(app)


@pytest.fixture
def emitted_events(capsys):
    def _read():
        out = capsys.readouterr().out.strip().splitlines()
        return [
            json.loads(line)
            for line in out
            if line.startswith("{") and '"geoyield-frontend"' in line
        ]

    return _read


def _configure():
    """See the note on pytest phases in test_logging.py."""
    configure_logging(force=True)


def test_a_browser_event_is_re_emitted_with_its_context(client, emitted_events):
    _configure()
    response = client.post(
        "/api/logs",
        json=[
            {
                "timestamp": "2026-09-20T10:00:00.123Z",
                "level": "error",
                "logger": "api.informes",
                "message": "Report generation failed",
                "trace_id": "abc123",
                "session_id": "session1",
                "duration_ms": 1234.5678,
                "error": {"type": "TypeError", "message": "x is null", "stack": "at f()"},
                "context": {"codi_districte": "01"},
            }
        ],
    )

    assert response.status_code == 204

    event = emitted_events()[0]
    assert event["level"] == "ERROR"
    assert event["service"] == "geoyield-frontend"
    # The client's timestamp is kept, not the receive time.
    assert event["timestamp"] == "2026-09-20T10:00:00.123Z"
    assert event["trace_id"] == "abc123"
    assert event["session_id"] == "session1"
    assert event["duration_ms"] == 1234.57
    assert event["error"]["type"] == "TypeError"
    assert event["context"] == {"codi_districte": "01"}
    assert event["logger"] == "geoyield.frontend.api.informes"


def test_javascript_warn_maps_to_python_warning(client, emitted_events):
    _configure()
    client.post("/api/logs", json=[{"level": "warn", "message": "careful"}])
    assert emitted_events()[0]["level"] == "WARNING"


def test_an_empty_batch_is_accepted(client):
    _configure()
    assert client.post("/api/logs", json=[]).status_code == 204


def test_log_lines_cannot_be_forged_with_newlines(client, emitted_events):
    """Unsanitised, this message would become TWO events, the second one fake."""
    _configure()
    client.post(
        "/api/logs",
        json=[{"level": "INFO", "message": 'innocent\n{"level":"ERROR","message":"FORGED"}'}],
    )

    events = emitted_events()
    assert len(events) == 1
    assert "FORGED" in events[0]["message"]
    assert "\n" not in events[0]["message"]


def test_a_client_cannot_impersonate_the_api(client, emitted_events):
    _configure()
    client.post(
        "/api/logs",
        json=[{"level": "INFO", "message": "i am the api", "service": "geoyield-api", "env": "production"}],
    )

    event = emitted_events()[0]
    assert event["service"] == "geoyield-frontend"
    assert event["env"] == "test"


def test_an_unknown_level_degrades_to_info(client, emitted_events):
    _configure()
    client.post("/api/logs", json=[{"level": "BANANA", "message": "odd"}])
    assert emitted_events()[0]["level"] == "INFO"


def test_the_client_logger_name_is_sanitised(client, emitted_events):
    _configure()
    client.post("/api/logs", json=[{"level": "INFO", "logger": "../../etc/passwd; rm -rf /", "message": "x"}])

    name = emitted_events()[0]["logger"]
    assert name.startswith("geoyield.frontend.")
    assert "/" not in name and ";" not in name and " " not in name


def test_the_user_address_is_redacted_even_when_the_browser_sends_it(client, emitted_events):
    """Defence in depth: if the frontend slips, the backend still redacts."""
    _configure()
    client.post(
        "/api/logs",
        json=[{"level": "INFO", "message": "geo", "context": {"direccion": "Carrer Mallorca 401"}}],
    )
    assert emitted_events()[0]["context"]["direccion"] == "[REDACTED]"


def test_an_oversized_batch_is_rejected(client):
    _configure()
    assert client.post("/api/logs", json=[{"level": "INFO", "message": "x"}] * 500).status_code == 413


def test_the_rate_limit_stops_a_burst(client):
    _configure()
    codes = [
        client.post("/api/logs", json=[{"level": "INFO", "message": "spam"}]).status_code
        for _ in range(logs_router.BUCKET_CAPACITY + 15)
    ]

    assert 429 in codes
    assert codes[0] == 204, "the first requests must go through"


def test_the_rate_limit_is_per_ip(client):
    """One abusive client must not starve everyone else of logs."""
    _configure()
    for _ in range(logs_router.BUCKET_CAPACITY + 5):
        client.post(
            "/api/logs",
            json=[{"level": "INFO", "message": "spam"}],
            headers={"X-Forwarded-For": "10.0.0.1"},
        )

    other_ip = client.post(
        "/api/logs",
        json=[{"level": "INFO", "message": "legitimate"}],
        headers={"X-Forwarded-For": "10.0.0.2"},
    )
    assert other_ip.status_code == 204


def test_unknown_keys_do_not_reject_the_batch(client):
    """After a deploy some browsers still run the previous frontend."""
    _configure()
    response = client.post(
        "/api/logs",
        json=[{"level": "INFO", "message": "x", "field_from_an_old_version": 42}],
    )
    assert response.status_code == 204


def test_an_oversized_message_is_rejected_by_the_schema(client):
    _configure()
    assert client.post("/api/logs", json=[{"level": "INFO", "message": "x" * 100_000}]).status_code == 422
