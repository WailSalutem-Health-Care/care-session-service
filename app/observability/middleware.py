"""HTTP Request Instrumentation Middleware."""

import time
import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from opentelemetry import trace, metrics
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)

# Get meter for HTTP metrics
meter = metrics.get_meter(__name__)

# HTTP Metrics
http_requests_counter = meter.create_counter(
    name="http_server_requests_seconds_count",
    description="Total number of HTTP requests",
    unit="1",
)

http_duration_histogram = meter.create_histogram(
    name="http_server_duration_milliseconds",
    description="HTTP request duration in milliseconds",
    unit="ms",
)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Middleware for HTTP request telemetry with metrics and traces."""
    
    def __init__(self, app, excluded_paths: list[str] = None):
        """
        Initialize telemetry middleware.
        
        Args:
            app: ASGI application
            excluded_paths: List of paths to exclude from telemetry (default: ["/health"])
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or ["/health"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process HTTP request with telemetry.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response: HTTP response
        """
        # Skip telemetry for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Start timing
        start_time = time.time()
        
        # Get tracer
        tracer = trace.get_tracer(__name__)
        
        # Extract route pattern (if available)
        route = request.url.path
        if hasattr(request, "scope") and "route" in request.scope:
            route_obj = request.scope.get("route")
            if route_obj and hasattr(route_obj, "path"):
                route = route_obj.path
        
        # Create span for this request
        with tracer.start_as_current_span(
            f"{request.method} {route}",
            kind=trace.SpanKind.SERVER,
        ) as span:
            # Set span attributes
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.route", route)
            span.set_attribute("http.target", str(request.url))
            span.set_attribute("http.scheme", request.url.scheme)
            span.set_attribute("http.host", request.url.hostname or "")
            
            # Add client info if available
            if request.client:
                span.set_attribute("http.client_ip", request.client.host)
            
            response = None
            status_code = 500  # Default to error
            
            try:
                # Process request
                response = await call_next(request)
                status_code = response.status_code
                
                # Set span status
                if status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR))
                else:
                    span.set_status(Status(StatusCode.OK))
                
                span.set_attribute("http.status_code", status_code)
                
                return response
                
            except Exception as e:
                # Record exception in span
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("http.status_code", 500)
                status_code = 500
                raise
                
            finally:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Record metrics
                labels = {
                    "service_name": "care-session-service",
                    "http_method": request.method,
                    "http_route": route,
                    "http_status_code": str(status_code),
                }
                
                try:
                    http_requests_counter.add(1, labels)
                    http_duration_histogram.record(duration_ms, labels)
                except Exception as e:
                    logger.warning(f"Failed to record HTTP metrics: {e}")
