"""
Tests for when CloudWatch shipping switches on.

Local development must never ship, and an AWS host that already collects
stdout must not ship either, or the same events are ingested (and billed)
twice.
"""

import pytest

from backend.observability.cloudwatch import _shipping_enabled

GROUP = "/geoyield/api"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("ENV", "LOG_CLOUDWATCH_ENABLED", "LOG_CLOUDWATCH_GROUP"):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize("env,group,expected", [
    # Local development never ships, even if a group is left configured.
    ("development", "", False),
    ("development", GROUP, False),
    # Production without a group: the ECS/Fargate case, where the host
    # driver already ships stdout.
    ("production", "", False),
    # Production with a group: the Render case.
    ("production", GROUP, True),
])
def test_shipping_is_derived_from_env_and_group(monkeypatch, env, group, expected):
    monkeypatch.setenv("ENV", env)
    monkeypatch.setenv("LOG_CLOUDWATCH_GROUP", group)
    assert _shipping_enabled(group) is expected


def test_explicit_flag_overrides_in_both_directions(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("LOG_CLOUDWATCH_ENABLED", "false")
    assert _shipping_enabled(GROUP) is False

    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("LOG_CLOUDWATCH_ENABLED", "true")
    assert _shipping_enabled(GROUP) is True
