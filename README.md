# Care Session Service

FastAPI-based microservice for managing care sessions in the WailSalutem healthcare platform.

## Features

- **Care Session Management**: Create, update, complete, and track care sessions
- **NFC Integration**: Automatic patient identification via NFC tags
- **Multi-tenant Support**: Isolated data per tenant with schema-based separation
- **Feedback System**: Collect and analyze patient feedback
- **Report Generation**: Generate PDF reports for care sessions
- **OpenTelemetry Observability**: Comprehensive metrics, traces, and structured logging

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Message Queue**: RabbitMQ for event-driven architecture
- **Authentication**: Keycloak JWT-based authentication
- **Observability**: OpenTelemetry with OTLP exporter
- **Testing**: pytest with async support

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 14+
- RabbitMQ 3.x
- Keycloak (for authentication)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd care-session-service
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (see Configuration section)

4. Run database migrations:
```bash
# Apply migrations from migrations/ directory
psql -U $DB_USER -d $DB_NAME -f migrations/20260105_add_cache_tables.sql
```

5. Start the service:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Configuration

### Environment Variables

#### Database Configuration
- `DB_HOST`: PostgreSQL host (default: localhost)
- `DB_PORT`: PostgreSQL port (default: 5432)
- `DB_NAME`: Database name
- `DB_USER`: Database user
- `DB_PASSWORD`: Database password

#### RabbitMQ Configuration
- `RABBITMQ_HOST`: RabbitMQ host
- `RABBITMQ_PORT`: RabbitMQ port (default: 5672)
- `RABBITMQ_USER`: RabbitMQ username
- `RABBITMQ_PASSWORD`: RabbitMQ password

#### Keycloak Authentication
- `KEYCLOAK_BASE_URL`: Keycloak server URL
- `KEYCLOAK_REALM`: Keycloak realm name
- `KEYCLOAK_API_CLIENT_ID`: API client ID
- `JWT_ALGORITHM`: JWT algorithm (default: RS256)

#### OpenTelemetry Configuration
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP collector endpoint (default: http://otel-collector.observability.svc.cluster.local:4317)
- `OTEL_SERVICE_NAME`: Service name for telemetry (default: care-session-service)
- `OTEL_RESOURCE_ATTRIBUTES`: Additional resource attributes (e.g., service.namespace=wailsalutem)
- `SERVICE_VERSION`: Service version (default: 1.0.0)
- `SERVICE_NAMESPACE`: Service namespace (default: wailsalutem)
- `LOG_LEVEL`: Logging level (default: INFO)
- `OTEL_TRACES_SAMPLER`: Trace sampling strategy (default: parentbased_always_on)

#### Application Configuration
- `APP_ENV`: Environment (development/production)
- `ALLOWED_ORIGINS`: CORS allowed origins (comma-separated)

## Observability

The service includes comprehensive OpenTelemetry instrumentation for monitoring and debugging.

### Metrics

#### HTTP Metrics
- `http_server_requests_seconds_count`: Total HTTP requests
  - Labels: `service_name`, `http_method`, `http_route`, `http_status_code`
- `http_server_duration_milliseconds`: HTTP request duration
  - Labels: `service_name`, `http_method`, `http_route`, `http_status_code`

#### Business Metrics
- `care_session_operations_total`: Total care session operations
  - Labels: `operation_type` (create/update/complete/cancel/delete), `status` (success/failure), `tenant_id`
- `care_session_operation_duration_milliseconds`: Operation duration
  - Labels: `operation_type`, `status`, `tenant_id`
- `care_sessions_active`: Number of active care sessions
  - Labels: `tenant_id`

### Traces

Distributed tracing is automatically enabled for:
- HTTP requests (FastAPI instrumentation)
- Database queries (SQLAlchemy instrumentation)
- External HTTP calls (requests instrumentation)
- Custom business operations (manual instrumentation)

Trace context is propagated using W3C Trace Context standard.

### Logs

Structured JSON logging with trace correlation:
- All logs include `trace_id` and `span_id` when available
- Logs are exported via OTLP to the observability stack
- Log levels: DEBUG, INFO, WARN, ERROR

### Viewing Telemetry

Telemetry data is sent to the centralized observability stack:
- **Traces**: View in Tempo/Jaeger
- **Metrics**: Query in Prometheus, visualize in Grafana
- **Logs**: Search in Loki, view in Grafana

### Health Check Exclusion

The `/health` endpoint is excluded from telemetry to reduce noise and avoid impacting monitoring systems.

## API Documentation

Once the service is running, access the interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for detailed API specifications.

## Testing

Run tests with coverage:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=app --cov-report=html

# Run specific test types
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m e2e           # End-to-end tests only

# Run tests in parallel
pytest -n auto
```

Test structure:
- `tests/unit/`: Unit tests for individual components
- `tests/integration/`: Integration tests with database
- `tests/e2e/`: End-to-end workflow tests

## Deployment

### Docker

Build and run with Docker:

```bash
# Build image
docker build -t care-session-service:latest .

# Run container
docker run -p 8000:8000 \
  -e DB_HOST=postgres \
  -e DB_USER=user \
  -e DB_PASSWORD=pass \
  care-session-service:latest
```

### Kubernetes

Deploy to Kubernetes/OpenShift:

```bash
# Apply configurations
kubectl apply -f k8s/config/
kubectl apply -f k8s/base/

# Check deployment status
kubectl get pods -n wailsalutem-suite
kubectl logs -f deployment/care-session-service -n wailsalutem-suite
```

The service includes:
- High availability with 3 replicas
- Horizontal Pod Autoscaler (HPA)
- Pod Disruption Budget (PDB)
- Rolling updates with zero downtime
- Health checks (liveness and readiness probes)

## Architecture

### Multi-tenant Design

The service uses PostgreSQL schemas for tenant isolation:
- Each tenant has a dedicated schema
- Tenant context is extracted from JWT tokens
- All database operations are scoped to the tenant schema

### Event-Driven Architecture

Integration with other services via RabbitMQ:
- **NFC Events**: Listens for NFC tag scan events
- **Care Session Events**: Publishes session lifecycle events
- **Report Requests**: Consumes report generation requests

### Security

- JWT-based authentication via Keycloak
- Role-based access control (RBAC)
- Permission validation using `permissions.yml`
- Tenant isolation at database level
- CORS configuration for web clients

## Development

### Code Quality

The project uses several tools for code quality:
- **Black**: Code formatting
- **isort**: Import sorting
- **Ruff**: Fast Python linter
- **mypy**: Static type checking
- **pytest**: Testing framework

Run code quality checks:

```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Lint code
ruff check app/ tests/

# Type check
mypy app/
```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

## Troubleshooting

### Database Connection Issues

If you encounter database connection errors:
1. Verify PostgreSQL is running
2. Check database credentials in environment variables
3. Ensure database exists and migrations are applied
4. Check network connectivity to database host

### RabbitMQ Connection Issues

If NFC events are not being processed:
1. Verify RabbitMQ is running
2. Check RabbitMQ credentials
3. Verify queue exists: `nfc.events`
4. Check consumer logs for errors

### Telemetry Not Appearing

If telemetry data is not visible:
1. Verify OTLP collector is running
2. Check `OTEL_EXPORTER_OTLP_ENDPOINT` configuration
3. Verify network connectivity to collector
4. Check service logs for telemetry initialization errors
5. Note: Service will continue running even if telemetry fails

## License

[Add your license information here]

## Support

For issues and questions, please contact the WailSalutem development team.
