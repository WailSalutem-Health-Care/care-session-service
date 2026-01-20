"""OpenTelemetry Telemetry Provider Initialization."""

import os
import logging
from typing import Optional
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, SERVICE_NAMESPACE
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

logger = logging.getLogger(__name__)

_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None


def init_telemetry() -> bool:
    """
    Initialize OpenTelemetry telemetry providers.

    Returns:
        bool: True if initialization succeeded, False otherwise.
    """
    global _tracer_provider, _meter_provider

    try:
        # Get configuration from environment
        otlp_endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector.observability.svc.cluster.local:4317"
        )
        service_name = os.getenv("OTEL_SERVICE_NAME", "care-session-service")
        service_version = os.getenv("SERVICE_VERSION", "1.0.0")
        service_namespace = os.getenv("SERVICE_NAMESPACE", "wailsalutem")

        # Parse additional resource attributes
        resource_attrs = {
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
            SERVICE_NAMESPACE: service_namespace,
        }

        # Add custom resource attributes from env
        otel_resource_attrs = os.getenv("OTEL_RESOURCE_ATTRIBUTES", "")
        if otel_resource_attrs:
            for attr in otel_resource_attrs.split(","):
                if "=" in attr:
                    key, value = attr.split("=", 1)
                    resource_attrs[key.strip()] = value.strip()

        resource = Resource.create(resource_attrs)

        # Initialize Trace Provider
        _tracer_provider = TracerProvider(resource=resource)

        # Configure OTLP Span Exporter
        span_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True,  # Internal cluster communication
        )

        # Add BatchSpanProcessor for efficient batching
        span_processor = BatchSpanProcessor(
            span_exporter,
            max_queue_size=2048,
            max_export_batch_size=512,
            export_timeout_millis=30000,
        )
        _tracer_provider.add_span_processor(span_processor)

        # Set global tracer provider
        trace.set_tracer_provider(_tracer_provider)

        # Initialize Metrics Provider
        metric_exporter = OTLPMetricExporter(
            endpoint=otlp_endpoint,
            insecure=True,
        )

        # Configure PeriodicExportingMetricReader with 30-second interval
        metric_reader = PeriodicExportingMetricReader(
            exporter=metric_exporter,
            export_interval_millis=30000,
        )

        _meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader],
        )

        # Set global meter provider
        metrics.set_meter_provider(_meter_provider)

        # Instrument libraries
        LoggingInstrumentor().instrument(set_logging_format=True)
        RequestsInstrumentor().instrument()

        logger.info(f"OpenTelemetry initialized successfully: " f"service={service_name}, endpoint={otlp_endpoint}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}", exc_info=True)
        return False


def shutdown_telemetry():
    """Gracefully shutdown telemetry providers and flush pending data."""

    try:
        if _tracer_provider:
            _tracer_provider.shutdown()
            logger.info("Tracer provider shutdown successfully")

        if _meter_provider:
            _meter_provider.shutdown()
            logger.info("Meter provider shutdown successfully")

    except Exception as e:
        logger.error(f"Error during telemetry shutdown: {e}", exc_info=True)


def instrument_fastapi(app):
    """
    Instrument FastAPI application.

    Args:
        app: FastAPI application instance
    """
    try:
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health",  # Exclude health check from telemetry
        )
        logger.info("FastAPI instrumented successfully")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}", exc_info=True)


def instrument_sqlalchemy(engine):
    """
    Instrument SQLAlchemy engine.

    Args:
        engine: SQLAlchemy engine instance
    """
    try:
        SQLAlchemyInstrumentor().instrument(
            engine=engine.sync_engine,
            enable_commenter=True,
        )
        logger.info("SQLAlchemy instrumented successfully")
    except Exception as e:
        logger.error(f"Failed to instrument SQLAlchemy: {e}", exc_info=True)
