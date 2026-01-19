"""Structured Logging Configuration with Trace Correlation."""

import os
import sys
import logging
import json
from datetime import datetime
from typing import Any, Dict
from opentelemetry import trace


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging with trace correlation."""
    
    def __init__(self, service_name: str = "care-session-service"):
        """
        Initialize JSON formatter.
        
        Args:
            service_name: Name of the service
        """
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON with trace context.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON formatted log string
        """
        # Base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": {
                "name": self.service_name,
            },
        }
        
        # Add trace context if available
        span = trace.get_current_span()
        if span:
            span_context = span.get_span_context()
            if span_context.is_valid:
                log_entry["trace_id"] = format(span_context.trace_id, "032x")
                log_entry["span_id"] = format(span_context.span_id, "016x")
                log_entry["trace_flags"] = span_context.trace_flags
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stacktrace": self.formatException(record.exc_info),
            }
        
        # Add extra fields
        if hasattr(record, "extra"):
            log_entry["extra"] = record.extra
        
        # Add source location
        log_entry["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }
        
        return json.dumps(log_entry)


def configure_logging(
    log_level: str = None,
    service_name: str = "care-session-service",
    json_format: bool = True,
):
    """
    Configure structured logging with trace correlation.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARN, ERROR)
        service_name: Name of the service
        json_format: Whether to use JSON formatting (default: True for production)
    """
    # Get log level from environment or parameter
    level_str = log_level or os.getenv("LOG_LEVEL", "INFO")
    level = getattr(logging, level_str.upper(), logging.INFO)
    
    # Determine if we should use JSON format
    # Use JSON in production, plain text in development
    use_json = json_format and os.getenv("APP_ENV", "production") != "development"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Set formatter
    if use_json:
        formatter = JSONFormatter(service_name=service_name)
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set log levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    logging.info(
        f"Logging configured: level={level_str}, json_format={use_json}, service={service_name}"
    )
