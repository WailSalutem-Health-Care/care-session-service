"""Database Instrumentation for SQLAlchemy."""

import logging
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)


def instrument_database_operation(operation: str, table: str = None):
    """
    Decorator for instrumenting database operations with tracing.
    
    Args:
        operation: Database operation type (e.g., "SELECT", "INSERT", "UPDATE", "DELETE")
        table: Optional table name
        
    Example:
        @instrument_database_operation("SELECT", "care_sessions")
        async def get_care_session(session_id: str):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            
            span_name = f"db.{operation}"
            if table:
                span_name = f"db.{operation}.{table}"
            
            with tracer.start_as_current_span(
                span_name,
                kind=trace.SpanKind.CLIENT,
            ) as span:
                # Set span attributes
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("db.operation", operation)
                if table:
                    span.set_attribute("db.table", table)
                
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        return wrapper
    return decorator


class DatabaseInstrumentation:
    """Helper class for manual database instrumentation."""
    
    @staticmethod
    def create_span(operation: str, table: str = None, statement: str = None):
        """
        Create a span for a database operation.
        
        Args:
            operation: Database operation type
            table: Optional table name
            statement: Optional SQL statement (be careful with sensitive data)
            
        Returns:
            Span context manager
        """
        tracer = trace.get_tracer(__name__)
        
        span_name = f"db.{operation}"
        if table:
            span_name = f"db.{operation}.{table}"
        
        span = tracer.start_span(
            span_name,
            kind=trace.SpanKind.CLIENT,
        )
        
        # Set span attributes
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.operation", operation)
        if table:
            span.set_attribute("db.table", table)
        if statement:
            # Only include statement if it's safe (no sensitive data)
            span.set_attribute("db.statement", statement)
        
        return span
