"""OpenTelemetry Observability Module for Care Session Service."""

from app.observability.telemetry import init_telemetry, shutdown_telemetry
from app.observability.middleware import TelemetryMiddleware
from app.observability.metrics import (
    record_care_session_operation,
    record_operation_duration,
    set_active_sessions,
    CareSessionMetrics,
)

__all__ = [
    "init_telemetry",
    "shutdown_telemetry",
    "TelemetryMiddleware",
    "record_care_session_operation",
    "record_operation_duration",
    "set_active_sessions",
    "CareSessionMetrics",
]
