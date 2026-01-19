# Observability Guide

This document provides detailed information about the OpenTelemetry observability implementation in the Care Session Service.

## Overview

The service uses OpenTelemetry to provide comprehensive observability through:
- **Distributed Tracing**: Track requests across service boundaries
- **Metrics**: Monitor service health and business operations
- **Structured Logging**: Correlated logs with trace context

All telemetry data is exported to the centralized observability stack via OTLP (OpenTelemetry Protocol).

## Architecture

```
┌─────────────────────────────────────┐
│   Care Session Service              │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  OpenTelemetry SDK           │  │
│  │  - TracerProvider            │  │
│  │  - MeterProvider             │  │
│  │  - LoggingInstrumentor       │  │
│  └──────────────────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌──────────────────────────────┐  │
│  │  OTLP Exporter (gRPC)        │  │
│  └──────────────────────────────┘  │
└──────────────┬──────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  OpenTelemetry Collector             │
│  (observability namespace)           │
└──────────────┬───────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
┌─────────────┐  ┌─────────────┐
│   Tempo     │  │ Prometheus  │
│  (Traces)   │  │  (Metrics)  │
└─────────────┘  └─────────────┘
       │               │
       └───────┬───────┘
               ▼
       ┌─────────────┐
       │   Grafana   │
       │ (Dashboards)│
       └─────────────┘
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector.observability.svc.cluster.local:4317` | OTLP collector endpoint |
| `OTEL_SERVICE_NAME` | `care-session-service` | Service name in telemetry |
| `OTEL_RESOURCE_ATTRIBUTES` | - | Additional resource attributes (comma-separated) |
| `SERVICE_VERSION` | `1.0.0` | Service version |
| `SERVICE_NAMESPACE` | `wailsalutem` | Service namespace |
| `LOG_LEVEL` | `INFO` | Logging level |
| `OTEL_TRACES_SAMPLER` | `parentbased_always_on` | Trace sampling strategy |

### Example Configuration

```yaml
env:
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://otel-collector.observability.svc.cluster.local:4317"
  - name: OTEL_SERVICE_NAME
    value: "care-session-service"
  - name: OTEL_RESOURCE_ATTRIBUTES
    value: "service.namespace=wailsalutem,deployment.environment=production"
  - name: LOG_LEVEL
    value: "INFO"
```

## Metrics

### HTTP Metrics

#### `http_server_requests_seconds_count`
Counter for total HTTP requests.

**Labels:**
- `service_name`: Service identifier
- `http_method`: HTTP method (GET, POST, etc.)
- `http_route`: Route pattern (e.g., `/care-sessions/{id}`)
- `http_status_code`: HTTP status code

**Example Query (PromQL):**
```promql
# Request rate per endpoint
rate(http_server_requests_seconds_count{service_name="care-session-service"}[5m])

# Error rate
rate(http_server_requests_seconds_count{service_name="care-session-service",http_status_code=~"5.."}[5m])
```

#### `http_server_duration_milliseconds`
Histogram for HTTP request duration.

**Labels:** Same as `http_server_requests_seconds_count`

**Example Query (PromQL):**
```promql
# P95 latency per endpoint
histogram_quantile(0.95, 
  rate(http_server_duration_milliseconds_bucket{service_name="care-session-service"}[5m])
)

# Average latency
rate(http_server_duration_milliseconds_sum[5m]) / 
rate(http_server_duration_milliseconds_count[5m])
```

### Business Metrics

#### `care_session_operations_total`
Counter for care session operations.

**Labels:**
- `operation_type`: Operation type (create, update, complete, cancel, delete)
- `status`: Operation status (success, failure)
- `tenant_id`: Tenant identifier (optional)

**Example Query (PromQL):**
```promql
# Operation rate by type
rate(care_session_operations_total{service_name="care-session-service"}[5m])

# Success rate
sum(rate(care_session_operations_total{status="success"}[5m])) /
sum(rate(care_session_operations_total[5m]))

# Failed operations
rate(care_session_operations_total{status="failure"}[5m])
```

#### `care_session_operation_duration_milliseconds`
Histogram for care session operation duration.

**Labels:** Same as `care_session_operations_total`

**Example Query (PromQL):**
```promql
# P99 operation duration
histogram_quantile(0.99,
  rate(care_session_operation_duration_milliseconds_bucket[5m])
)
```

#### `care_sessions_active`
Up-down counter for active care sessions.

**Labels:**
- `tenant_id`: Tenant identifier (optional)

**Example Query (PromQL):**
```promql
# Current active sessions
care_sessions_active

# Active sessions by tenant
sum by (tenant_id) (care_sessions_active)
```

## Traces

### Automatic Instrumentation

The following components are automatically instrumented:

1. **FastAPI**: All HTTP endpoints
   - Span name: `{METHOD} {route}`
   - Attributes: `http.method`, `http.route`, `http.status_code`, etc.

2. **SQLAlchemy**: All database queries
   - Span name: `db.{operation}`
   - Attributes: `db.system`, `db.operation`, `db.table`

3. **Requests**: All outbound HTTP calls
   - Span name: `HTTP {METHOD}`
   - Attributes: `http.url`, `http.method`, `http.status_code`

### Manual Instrumentation

#### Using the Decorator

```python
from app.observability.database import instrument_database_operation

@instrument_database_operation("SELECT", "care_sessions")
async def get_care_session(session_id: str):
    # Your code here
    pass
```

#### Using Context Manager

```python
from app.observability.metrics import track_care_session_operation

async def create_care_session(data):
    with track_care_session_operation("create", tenant_id="tenant-123"):
        # Your operation code here
        session = await repository.create(data)
        return session
```

#### Creating Custom Spans

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def complex_operation():
    with tracer.start_as_current_span("complex_operation") as span:
        span.set_attribute("custom.attribute", "value")
        
        # Your code here
        result = await do_work()
        
        span.set_attribute("result.count", len(result))
        return result
```

### Trace Context Propagation

Trace context is automatically propagated:
- **Incoming**: Extracted from HTTP headers (W3C Trace Context)
- **Outgoing**: Injected into HTTP headers for downstream services
- **Logs**: Trace ID and Span ID included in all log entries

## Structured Logging

### Log Format

Logs are output in JSON format with the following structure:

```json
{
  "timestamp": "2026-01-19T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.care_sessions.service",
  "message": "Care session created successfully",
  "service": {
    "name": "care-session-service"
  },
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "trace_flags": 1,
  "source": {
    "file": "/app/app/care_sessions/service.py",
    "line": 67,
    "function": "create_session"
  }
}
```

### Using Structured Logging

```python
import logging

logger = logging.getLogger(__name__)

# Simple logging
logger.info("Care session created")
logger.error("Failed to create session", exc_info=True)

# With extra fields
logger.info("Operation completed", extra={
    "session_id": session_id,
    "duration_ms": duration,
    "tenant_id": tenant_id
})
```

### Querying Logs in Loki

```logql
# All logs from care-session-service
{service_name="care-session-service"}

# Error logs only
{service_name="care-session-service"} |= "ERROR"

# Logs for specific trace
{service_name="care-session-service"} | json | trace_id="4bf92f3577b34da6a3ce929d0e0e4736"

# Logs with specific operation
{service_name="care-session-service"} | json | message=~".*create.*"
```

## Dashboards

### Recommended Grafana Dashboards

1. **Service Overview**
   - Request rate and error rate
   - Latency percentiles (P50, P95, P99)
   - Active sessions gauge
   - Resource utilization

2. **Business Metrics**
   - Care session operations by type
   - Success/failure rates
   - Operation duration trends
   - Active sessions by tenant

3. **Database Performance**
   - Query duration
   - Connection pool metrics
   - Slow queries
   - Error rates

### Example Dashboard Panels

#### Request Rate
```promql
sum(rate(http_server_requests_seconds_count{service_name="care-session-service"}[5m])) by (http_route)
```

#### Error Rate
```promql
sum(rate(http_server_requests_seconds_count{service_name="care-session-service",http_status_code=~"5.."}[5m])) /
sum(rate(http_server_requests_seconds_count{service_name="care-session-service"}[5m]))
```

#### P95 Latency
```promql
histogram_quantile(0.95,
  sum(rate(http_server_duration_milliseconds_bucket{service_name="care-session-service"}[5m])) by (le, http_route)
)
```

## Alerting

### Recommended Alerts

#### High Error Rate
```yaml
alert: HighErrorRate
expr: |
  sum(rate(http_server_requests_seconds_count{service_name="care-session-service",http_status_code=~"5.."}[5m])) /
  sum(rate(http_server_requests_seconds_count{service_name="care-session-service"}[5m])) > 0.05
for: 5m
labels:
  severity: warning
annotations:
  summary: "High error rate in care-session-service"
  description: "Error rate is {{ $value | humanizePercentage }}"
```

#### High Latency
```yaml
alert: HighLatency
expr: |
  histogram_quantile(0.95,
    sum(rate(http_server_duration_milliseconds_bucket{service_name="care-session-service"}[5m])) by (le)
  ) > 1000
for: 5m
labels:
  severity: warning
annotations:
  summary: "High latency in care-session-service"
  description: "P95 latency is {{ $value }}ms"
```

#### Failed Operations
```yaml
alert: HighOperationFailureRate
expr: |
  sum(rate(care_session_operations_total{status="failure"}[5m])) /
  sum(rate(care_session_operations_total[5m])) > 0.1
for: 5m
labels:
  severity: critical
annotations:
  summary: "High operation failure rate"
  description: "{{ $value | humanizePercentage }} of operations are failing"
```

## Troubleshooting

### Telemetry Not Appearing

1. **Check service logs:**
   ```bash
   kubectl logs -f deployment/care-session-service -n wailsalutem-suite | grep -i "telemetry\|otel"
   ```

2. **Verify collector endpoint:**
   ```bash
   # Test connectivity to collector
   kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
     curl -v http://otel-collector.observability.svc.cluster.local:4317
   ```

3. **Check collector logs:**
   ```bash
   kubectl logs -f deployment/otel-collector -n observability
   ```

4. **Verify configuration:**
   ```bash
   kubectl get configmap wailsalutem-backend-config -n wailsalutem-suite -o yaml | grep OTEL
   ```

### Service Continues Despite Telemetry Failure

This is by design. The service will:
1. Log a warning if telemetry initialization fails
2. Continue running normally
3. Skip telemetry collection for requests

To enable telemetry:
1. Fix the configuration issue
2. Restart the service: `kubectl rollout restart deployment/care-session-service`

### High Cardinality Issues

If you experience performance issues due to high cardinality:

1. **Limit tenant_id labels** (if you have many tenants)
2. **Adjust sampling rate**: Set `OTEL_TRACES_SAMPLER=parentbased_traceidratio` and `OTEL_TRACES_SAMPLER_ARG=0.1` (10% sampling)
3. **Increase collector resources**

## Best Practices

1. **Always use structured logging** instead of print statements
2. **Add business context** to spans and metrics (tenant_id, operation_type, etc.)
3. **Use consistent naming** for operations and metrics
4. **Avoid high cardinality labels** (e.g., user IDs, session IDs)
5. **Set appropriate sampling rates** for high-traffic services
6. **Monitor collector health** to ensure telemetry is being received
7. **Use trace context** to correlate logs, traces, and metrics
8. **Exclude health checks** from telemetry to reduce noise

## Performance Impact

OpenTelemetry instrumentation has minimal performance impact:

- **Traces**: ~1-2ms overhead per request (with sampling)
- **Metrics**: Negligible overhead (in-memory aggregation)
- **Logs**: ~0.5ms overhead per log entry

The service uses:
- **Batch processing** for traces (reduces network calls)
- **Periodic export** for metrics (30-second intervals)
- **Async I/O** for all telemetry operations

## References

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [OpenTelemetry Python SDK](https://opentelemetry-python.readthedocs.io/)
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
