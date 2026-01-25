# Care Session Service - Architecture & API Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Database Models](#database-models)
5. [Authentication & Authorization](#authentication--authorization)
6. [Event-Driven Architecture](#event-driven-architecture)
7. [API Endpoints](#api-endpoints)
8. [Deployment](#deployment)

---

## Overview

The **Care Session Service** is a microservice responsible for managing care sessions, feedback, and reporting in the WailSalutem healthcare platform. It handles:
- **Care Sessions**: Creation, management, and completion of caregiver-patient sessions
- **Feedback**: Collection and analysis of feedback from caregivers
- **Reports**: Aggregation and reporting on care session metrics, caregiver performance, and patient data
- **Multi-tenancy**: Supports multiple healthcare organizations with isolated data per tenant

### Key Features
- ✅ Multi-tenant architecture (schema-based isolation)
- ✅ Event-driven sync with RabbitMQ for caregiver/patient data
- ✅ Role-based access control (SUPER_ADMIN, ORG_ADMIN, CAREGIVER, PATIENT, etc.)
- ✅ JWT authentication via Keycloak
- ✅ Real-time feedback and analytics
- ✅ PDF and CSV report generation

---

## Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Web/Mobile)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        v                         v
┌──────────────────┐    ┌──────────────────┐
│  Keycloak Auth   │    │  Care Session    │
│  (JWT Tokens)    │    │  Service APIs    │
└──────────────────┘    └────────┬─────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        v                        v                        v
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   PostgreSQL     │    │   RabbitMQ       │    │  Organization    │
│   (Tenant Data)  │    │   (Events)       │    │  Service APIs    │
└──────────────────┘    └────────┬─────────┘    └──────────────────┘
                                 │
                                 v
                        ┌──────────────────┐
                        │  Event Consumer  │
                        │  (Sync Patient/  │
                        │   Caregiver Data)│
                        └──────────────────┘
```

### Layered Architecture

```
┌─────────────────────────────────────────┐
│  API Layer (FastAPI Routers)            │
│  - /care-sessions, /feedback, /reports  │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Service Layer (Business Logic)         │
│  - CareSessionService                   │
│  - FeedbackService                      │
│  - ReportsService                       │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Repository Layer (Data Access)         │
│  - CareSessionRepository                │
│  - FeedbackRepository                   │
│  - ReportsRepository                    │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Database Layer (PostgreSQL)            │
│  - Multi-tenant schema-based isolation  │
└─────────────────────────────────────────┘
```

---

## Core Components

### 1. **Care Sessions Module** (`app/care_sessions/`)
Manages the lifecycle of care sessions (caregiver-patient interactions).

**Key Files:**
- `router.py`: API endpoints for care session operations
- `service.py`: Business logic for session management
- `repository.py`: Database queries
- `schemas.py`: Pydantic models for request/response
- `validators.py`: NFC tag and business rule validation
- `event_publisher.py`: Publishes session events to RabbitMQ

**Key Models:**
```python
class CareSession:
    id: UUID                    # Primary key
    session_id: str            # Public code (e.g., "CS-0001")
    patient_id: UUID           # Patient reference
    caregiver_id: UUID         # Caregiver reference
    check_in_time: datetime    # Session start time
    check_out_time: datetime   # Session end time (nullable)
    status: str                # "in_progress" or "completed"
    caregiver_notes: str       # Notes from caregiver
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime       # Soft delete
```

### 2. **Feedback Module** (`app/feedback/`)
Collects and manages feedback from caregivers about patients.

**Key Files:**
- `router.py`: API endpoints for feedback operations
- `service.py`: Business logic for feedback
- `repository.py`: Database queries
- `schemas.py`: Pydantic models
- `satisfaction.py`: Satisfaction rating logic

**Key Models:**
```python
class Feedback:
    id: UUID
    care_session_id: UUID      # Reference to care session
    patient_id: UUID
    caregiver_id: UUID
    rating: int                # 1-3 (Dissatisfied, Neutral, Satisfied)
    patient_feedback: str      # Text feedback
    created_at: datetime
    deleted_at: datetime       # Soft delete
```

### 3. **Reports Module** (`app/reports/`)
Generates analytical reports on care sessions, caregivers, and patients.

**Key Files:**
- `router.py`: API endpoints for reports
- `service.py`: Report generation logic
- `repository.py`: Complex queries for analytics
- `schemas.py`: Report data models

**Reports Include:**
- Care session reports (by period, all-time)
- Caregiver performance metrics
- Patient summaries and care session history
- Feedback analytics and summaries

### 4. **Authentication & Authorization** (`app/auth/`)
Handles JWT verification and permission management.

**Key Files:**
- `middleware.py`: Token verification and tenant context
- `jwt_verifier.py`: Keycloak token validation
- `permissions_manager.py`: Role-to-permission mapping
- `models.py`: JWTPayload, user permission models

### 5. **Messaging** (`app/messaging/`)
Asynchronous event handling via RabbitMQ.

**Key Files:**
- `consumer.py`: Listens for patient/caregiver events (in `app/reports/consumer.py` as well)
- `rabbitmq.py`: RabbitMQ connection management

**Events Consumed:**
- `patient.created`, `patient.deleted`, `patient.status_changed`
- `user.created`, `user.deleted`, `user.status_changed`, `user.role_changed`

### 6. **Database** (`app/db/`)
Multi-tenant PostgreSQL setup with schema isolation.

**Key Files:**
- `models.py`: SQLAlchemy ORM models
- `postgres.py`: Database connection and session management
- `repository.py`: Base repository with tenant context

---

## Database Models

### Tenant Isolation
Each organization has its own schema (e.g., `org_lifecare_healthcare_315298bf`). All queries automatically set the search path to the tenant schema.

### Core Tables

#### `care_sessions`
```sql
CREATE TABLE care_sessions (
    id UUID PRIMARY KEY,
    session_id VARCHAR(50) UNIQUE NOT NULL,    -- Public code (CS-0001)
    patient_id UUID NOT NULL,
    caregiver_id UUID NOT NULL,
    check_in_time TIMESTAMP NOT NULL,
    check_out_time TIMESTAMP,
    status VARCHAR(20),                        -- "in_progress", "completed"
    caregiver_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP
);
```

#### `feedback`
```sql
CREATE TABLE feedback (
    id UUID PRIMARY KEY,
    care_session_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    caregiver_id UUID NOT NULL,
    rating INTEGER (1-3),                      -- Satisfaction rating
    patient_feedback TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);
```

#### `patients` (synced from events)
```sql
CREATE TABLE patients (
    id UUID PRIMARY KEY,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    email VARCHAR(255),
    phone_number VARCHAR(20),
    date_of_birth DATE,
    address TEXT,
    medical_notes TEXT,
    careplan_type VARCHAR(100),
    careplan_frequency VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP
);
```

#### `users` (synced from events)
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    keycloak_user_id UUID,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    email VARCHAR(255),
    role VARCHAR(50),                          -- "CAREGIVER", "PATIENT", etc.
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP
);
```

---

## Authentication & Authorization

### JWT Token Flow
1. **Frontend/Mobile** sends credentials to **Keycloak**
2. **Keycloak** issues a JWT token with:
   - `sub`: User ID
   - `organizationID`: Organization ID
   - `orgSchemaName`: Tenant schema name
   - `realm_access.roles`: List of roles (SUPER_ADMIN, ORG_ADMIN, CAREGIVER, PATIENT)
3. **Frontend** includes token in `Authorization: Bearer <token>` header
4. **Care Session Service** middleware verifies token and extracts permissions

### Roles & Permissions

| Role        | Permissions                              | Description                          |
|-------------|------------------------------------------|--------------------------------------|
| SUPER_ADMIN | All operations, cross-organization      | Platform administrator               |
| ORG_ADMIN   | Full access within organization         | Organization administrator          |
| CAREGIVER   | Create sessions, submit feedback        | Care provider                        |
| PATIENT     | View own sessions and feedback          | Patient receiving care              |
| MUNICIPALITY| View reports for assigned patients      | Municipal care coordinator          |
| INSURER     | View aggregate reports                  | Insurance provider                  |

### Permission Mapping
```python
PERMISSIONS_MAP = {
    "SUPER_ADMIN": [
        "care-session:create", "care-session:read", "care-session:update", "care-session:delete",
        "feedback:create", "feedback:read", "feedback:update", "feedback:delete",
        "care-session:report", "care-session:admin"
    ],
    "ORG_ADMIN": [
        "care-session:create", "care-session:read", "care-session:update", "care-session:delete",
        "feedback:create", "feedback:read", "feedback:update",
        "care-session:report"
    ],
    "CAREGIVER": [
        "care-session:create", "care-session:read",
        "feedback:create", "feedback:read"
    ],
    "PATIENT": [
        "care-session:read",
        "feedback:read"
    ],
    # ... others
}
```

---

## Event-Driven Architecture

### RabbitMQ Consumer (Organization Events)

**Queue:** `care_session_org_events`  
**Exchange:** `wailsalutem.events` (topic)

**Events Consumed:**
- `patient.created` → Insert/update patient in local cache
- `patient.deleted` → Mark patient as deleted
- `patient.status_changed` → Update patient active status
- `user.created` → Insert/update caregiver in local cache
- `user.deleted` → Mark caregiver as deleted
- `user.status_changed` → Update caregiver active status
- `user.role_changed` → Handle role transitions

**Flow:**
```
Organization Service
    ↓ (publishes event)
RabbitMQ
    ↓ (consumed by)
Care Session Service Consumer
    ↓ (updates)
Local PostgreSQL Cache (patients, users tables)
    ↓ (used by)
Reporting APIs
```

### Care Session Events (Published)

When a care session is created or completed, events are published to RabbitMQ:
- `care_session.created`
- `care_session.completed`

These can be consumed by other services for analytics, notifications, etc.

---

## API Endpoints

### 1. Health Check
```
GET /health

Response:
{
  "status": "ok",
  "service": "care-session-service"
}
```

---

### 2. Care Sessions APIs

#### 2.1 Create Care Session
```
POST /care-sessions/create
Authorization: Bearer <caregiver_token>

Request Body:
{
  "tag_id": "NFC882348918"
}

Response: 201 Created
{
  "id": "99999999-0005-0005-0005-000000000005",
  "session_id": "CS-0005",
  "patient_id": "eeeeeeee-cccc-cccc-cccc-cccccccccccc",
  "caregiver_id": "55555555-5555-5555-5555-555555555555",
  "check_in_time": "2025-12-29T11:08:00",
  "check_out_time": null,
  "status": "in_progress",
  "caregiver_notes": null,
  "created_at": "2026-01-08T10:23:43.038635",
  "updated_at": null
}
```

#### 2.2 Get Care Session by ID
```
GET /care-sessions/{session_id}
Authorization: Bearer <token>

Response: 200 OK
{
  "id": "99999999-0005-0005-0005-000000000005",
  "session_id": "CS-0005",
  "patient_id": "eeeeeeee-cccc-cccc-cccc-cccccccccccc",
  "caregiver_id": "55555555-5555-5555-5555-555555555555",
  "check_in_time": "2025-12-29T11:08:00",
  "check_out_time": null,
  "status": "in_progress",
  "caregiver_notes": null,
  "created_at": "2026-01-08T10:23:43.038635",
  "updated_at": null
}
```

#### 2.3 Complete Care Session
```
POST /care-sessions/{session_id}/complete
Authorization: Bearer <caregiver_token>

Request Body:
{
  "caregiver_notes": "Patient responded well to exercises"
}

Response: 200 OK
{
  "id": "99999999-0005-0005-0005-000000000005",
  "session_id": "CS-0005",
  "status": "completed",
  "check_out_time": "2025-12-29T11:30:00",
  ...
}
```

#### 2.4 List Care Sessions
```
GET /care-sessions/?page=1&page_size=10
Authorization: Bearer <token>

Query Parameters:
- page: int (default 1)
- page_size: int (default 10, max 100)

Response: 200 OK
{
  "sessions": [
    { ...session_object },
    ...
  ],
  "total": 25,
  "page": 1,
  "page_size": 10,
  "total_pages": 3
}
```

#### 2.5 Update Care Session (Admin Only)
```
PUT /care-sessions/{session_id}
Authorization: Bearer <org_admin_token>
Headers: X-Organization-ID: <org_id>

Request Body:
{
  "check_in_time": "2025-12-29T10:00:00",
  "check_out_time": "2025-12-29T11:00:00",
  "caregiver_notes": "Updated notes",
  "status": "completed"
}

Response: 200 OK
{ ...updated_session }
```

---

### 3. Feedback APIs

#### 3.1 Submit Feedback
```
POST /feedback/
Authorization: Bearer <caregiver_token>

Request Body:
{
  "care_session_id": "99999999-0005-0005-0005-000000000005",
  "patient_id": "eeeeeeee-cccc-cccc-cccc-cccccccccccc",
  "rating": 3,
  "patient_feedback": "Patient was cooperative and responsive"
}

Response: 201 Created
{
  "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
  "care_session_id": "99999999-0005-0005-0005-000000000005",
  "patient_id": "eeeeeeee-cccc-cccc-cccc-cccccccccccc",
  "caregiver_id": "55555555-5555-5555-5555-555555555555",
  "rating": 3,
  "patient_feedback": "Patient was cooperative and responsive",
  "created_at": "2026-01-08T11:30:00"
}
```

#### 3.2 Get Feedback by Session
```
GET /feedback/{session_id}
Authorization: Bearer <token>

Response: 200 OK
{
  "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
  "care_session_id": "99999999-0005-0005-0005-000000000005",
  ...
}
```

#### 3.3 List All Feedback
```
GET /feedback/?page=1&page_size=10
Authorization: Bearer <token>

Response: 200 OK
{
  "feedback": [
    { ...feedback_object },
    ...
  ],
  "total": 42,
  "page": 1,
  "page_size": 10
}
```

#### 3.4 Get Daily Average Ratings
```
GET /feedback/analytics/daily?start_date=2026-01-01&end_date=2026-01-31
Authorization: Bearer <token>

Response: 200 OK
[
  {
    "date": "2026-01-01",
    "avg_rating": 2.8,
    "total_feedbacks": 5,
    "positive_count": 4,
    "neutral_count": 1,
    "negative_count": 0
  },
  ...
]
```

#### 3.5 Get Top Caregivers of Week
```
GET /feedback/analytics/top-caregivers/weekly?week_start=2026-01-06
Authorization: Bearer <token>

Response: 200 OK
[
  {
    "caregiver_id": "55555555-5555-5555-5555-555555555555",
    "caregiver_name": "Deepika Bhandari",
    "avg_rating": 2.9,
    "feedback_count": 12,
    "rank": 1
  },
  ...
]
```

---

### 4. Reports APIs

#### 4.1 Get Session Report by Period
```
GET /reports/sessions/period?period=week&limit=10
Authorization: Bearer <org_admin_token>

Query Parameters:
- period: "day" | "week" | "month"
- limit: int (default 10)

Response: 200 OK
{
  "sessions": [
    {
      "id": "99999999-0005-0005-0005-000000000005",
      "session_id": "CS-0005",
      "patient_full_name": "John Doe",
      "caregiver_full_name": "Deepika Bhandari",
      "check_in_time": "2025-12-29T11:08:00",
      "check_out_time": "2025-12-29T11:30:00",
      "duration_minutes": 22,
      "status": "completed"
    },
    ...
  ],
  "total": 15
}
```

#### 4.2 Get All-Time Session Report
```
GET /reports/sessions/all?limit=10
Authorization: Bearer <org_admin_token>

Response: 200 OK
{ ...same as above }
```

#### 4.3 Download Sessions Report as CSV
```
GET /reports/sessions/download?format=csv
Authorization: Bearer <org_admin_token>

Response: 200 OK (CSV file)
```

#### 4.4 List Caregivers
```
GET /reports/caregivers?limit=100&offset=0
Authorization: Bearer <token>

Response: 200 OK
[
  {
    "id": "55555555-5555-5555-5555-555555555555",
    "full_name": "Deepika Bhandari",
    "email": "deepika@gmail.com",
    "is_active": true
  },
  ...
]
```

#### 4.5 Get Caregiver Performance
```
GET /reports/caregivers/performance
Authorization: Bearer <org_admin_token>

Query Parameters:
- start_date: datetime (optional)
- end_date: datetime (optional)

Response: 200 OK
[
  {
    "caregiver_id": "55555555-5555-5555-5555-555555555555",
    "caregiver_full_name": "Deepika Bhandari",
    "caregiver_email": "deepika@gmail.com",
    "total_sessions": 42,
    "completed_sessions": 40,
    "avg_rating": 2.85,
    "avg_duration_minutes": 28.5,
    "status": "Active"
  },
  ...
]
```

#### 4.6 List Patients
```
GET /reports/patients?limit=100&offset=0
Authorization: Bearer <token>

Response: 200 OK
[
  {
    "id": "eeeeeeee-cccc-cccc-cccc-cccccccccccc",
    "full_name": "Roozbach Kouchaki",
    "email": "roozbach@test.com",
    "careplan_type": "Daily",
    "is_active": true
  },
  ...
]
```

#### 4.7 Get Feedback Reports
```
GET /reports/feedback?limit=10
Authorization: Bearer <org_admin_token>

Response: 200 OK
[
  {
    "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
    "care_session_id": "99999999-0005-0005-0005-000000000005",
    "patient_full_name": "Roozbach Kouchaki",
    "caregiver_full_name": "Deepika Bhandari",
    "rating": 3,
    "patient_feedback": "Patient was cooperative",
    "created_at": "2026-01-08T11:30:00"
  },
  ...
]
```

#### 4.8 Get Feedback Summary
```
GET /reports/feedback/summary
Authorization: Bearer <org_admin_token>

Query Parameters:
- start_date: datetime (optional)
- end_date: datetime (optional)

Response: 200 OK
{
  "total_feedback": 127,
  "avg_rating": 2.73,
  "positive_feedback": 102,
  "neutral_feedback": 20,
  "negative_feedback": 5
}
```

#### 4.9 Download Caregiver Report as CSV
```
GET /reports/caregivers/download?format=csv
Authorization: Bearer <org_admin_token>

Response: 200 OK (CSV file)
```

#### 4.10 Download Caregiver Report as PDF
```
GET /reports/caregivers/download?format=pdf
Authorization: Bearer <org_admin_token>

Response: 200 OK (PDF file)
```

---

## Deployment

### Environment Variables

```bash
# Service
SERVICE_NAME=care-session-service

# Database (Multi-tenant PostgreSQL)
DB_HOST=postgresql
DB_PORT=5432
DB_NAME=WailSalutem_Suite_DB
DB_USER=admin
DB_PASSWORD=secure_password

# RabbitMQ
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=wailsalutem
RABBITMQ_PASSWORD=wailsalutem

# Keycloak (JWT/OAuth2)
KEYCLOAK_BASE_URL=https://keycloak-wailsalutem-suite.apps.inholland-minor.openshift.eu
KEYCLOAK_REALM=wailsalutem
KEYCLOAK_API_CLIENT_ID=wailsalutem-api
JWT_ALGORITHM=RS256

# CORS
ALLOWED_ORIGINS=http://localhost:3000,https://wailsalutem-web-ui.netlify.app
```

### Docker & Kubernetes

**Dockerfile:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app app
COPY permissions.yml .
COPY start_consumer.py .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Kubernetes Deployment:**
- Uses ConfigMaps for environment variables
- Uses Secrets for sensitive data (DB credentials, API keys)
- Deployment with 2+ replicas for high availability
- Service exposes port 8000
- Route (OpenShift) provides external access

---

## Request/Response Flow Example

### Creating a Care Session

```
1. Frontend (Mobile App)
   └─> POST /care-sessions/create
       Headers: Authorization: Bearer <caregiver_jwt>
       Body: { "tag_id": "NFC882348918" }

2. Care Session Service
   ├─> Middleware: Verify JWT, extract roles/permissions
   ├─> Router: validate_session_creation permission
   ├─> Service: Validate NFC tag, check for duplicate sessions
   ├─> Repository: Create session in DB
   └─> Event Publisher: Publish "care_session.created" to RabbitMQ

3. Response (201 Created)
   └─> { "id": "...", "session_id": "CS-0001", ... }

4. Frontend
   └─> Display session created, show session ID to caregiver
```

---

## Error Handling

Common HTTP Status Codes:
- **200 OK**: Request successful
- **201 Created**: Resource created
- **400 Bad Request**: Invalid request body
- **401 Unauthorized**: Missing or invalid JWT token
- **403 Forbidden**: Missing required permission
- **404 Not Found**: Resource not found
- **409 Conflict**: Business rule violation (e.g., duplicate session)
- **500 Internal Server Error**: Server error

Example Error Response:
```json
{
  "detail": "Missing required permission: care-session:create"
}
```

---

## Summary

The Care Session Service is a comprehensive microservice that:
1. ✅ Manages care sessions with proper validation
2. ✅ Collects feedback with satisfaction ratings
3. ✅ Generates detailed reports and analytics
4. ✅ Syncs data from Organization Service via RabbitMQ
5. ✅ Enforces role-based access control with Keycloak JWT
6. ✅ Supports multi-tenant deployments with schema isolation
7. ✅ Provides CSV and PDF exports for reports

For more details on specific endpoints, see the individual module documentation or the inline code comments.
