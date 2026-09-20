"""
Optional direct shipping to CloudWatch Logs.

Enabled when ENV=production and LOG_CLOUDWATCH_GROUP is set. On
ECS/Fargate/App Runner leave the group unset: the host driver already ships
stdout, so pushing as well pays twice for the same ingestion.
"""

import logging
import os
import socket

from backend.observability.logging_config import is_production

_fallback = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _shipping_enabled(group: str) -> bool:
    """The log group is the opt-in; LOG_CLOUDWATCH_ENABLED overrides."""
    explicit = os.getenv("LOG_CLOUDWATCH_ENABLED")
    if explicit is not None:
        return _env_bool("LOG_CLOUDWATCH_ENABLED", False)
    return is_production() and bool(group)


def build_cloudwatch_handler() -> logging.Handler | None:
    """
    Returns None rather than raising when disabled, when boto3/watchtower are
    missing or when AWS rejects the credentials: losing log shipping is an
    observability problem, taking down the API is an outage.
    """
    group = os.getenv("LOG_CLOUDWATCH_GROUP", "").strip()

    if not _shipping_enabled(group):
        return None

    if not group:
        _fallback.warning(
            "LOG_CLOUDWATCH_ENABLED=true but LOG_CLOUDWATCH_GROUP is empty; "
            "falling back to stdout only."
        )
        return None

    # boto3 and watchtower are optional dependencies.
    try:
        import boto3
        import watchtower
    except ImportError:
        _fallback.warning(
            "LOG_CLOUDWATCH_ENABLED=true but boto3/watchtower are not installed "
            "(pip install boto3 watchtower); falling back to stdout only."
        )
        return None

    stream = os.getenv("LOG_CLOUDWATCH_STREAM", "").strip() or socket.gethostname()
    region = os.getenv("AWS_REGION", "").strip() or None

    # A new log group retains events forever and bills storage indefinitely.
    retention_raw = os.getenv("LOG_CLOUDWATCH_RETENTION_DAYS", "30").strip()
    try:
        retention = int(retention_raw) if retention_raw else None
    except ValueError:
        retention = 30

    try:
        client = boto3.client("logs", region_name=region)
        handler = watchtower.CloudWatchLogHandler(
            log_group_name=group,
            log_stream_name=stream,
            boto3_client=client,
            # Already batches off-thread, so no extra QueueHandler layer.
            use_queues=True,
            send_interval=int(os.getenv("LOG_CLOUDWATCH_SEND_INTERVAL", "10")),
            create_log_group=True,
            create_log_stream=True,
            log_group_retention_days=retention,
        )
        _fallback.info(
            "CloudWatch shipping enabled (group=%s, stream=%s, region=%s).",
            group, stream, region or "environment default",
        )
        return handler

    except Exception:
        _fallback.exception(
            "Could not initialise the CloudWatch handler; falling back to stdout only."
        )
        return None
