# Care Session & Feedback API Documentation

**Base URL:** `http://localhost:8002`  
**Authentication:** JWT Bearer Token (OAuth2/OIDC via Keycloak)  
**Timezone:** All timestamps in responses are converted to CET (Central European Time)

---

## Table of Contents

1. [Authentication & Authorization](#authentication--authorization)
2. [Care Sessions API](#care-sessions-api)
3. [Feedback API](#feedback-api)
4. [Response Formats](#response-formats)
5. [Error Handling](#error-handling)

---

## Authentication & Authorization

### How It Works

1. **Authentication**: All endpoints require a valid JWT bearer token
   - Token obtained from Keycloak OAuth2/OIDC server
   - Token includes user ID, tenant schema, and role information

2. **Authorization**: Endpoints validate user permissions based on role
   - Roles determine what endpoints user can access
   - Permissions are checked at router level via `check_permission()`

### Roles & Permissions Matrix

| Role | Permissions | Endpoints Access |
|------|-------------|------------------|
| **SUPER_ADMIN** | `organization:*`, `care-session:read`, `care-session:admin`, `feedback:read`, `feedback:delete` | All care sessions (read/admin), All feedback (read/delete) |
| **ORG_ADMIN** | `organization:view`, `user:manage`, `nfc:assign`, `care-session:read`, `care-session:admin`, `care-session:report`, `feedback:read`, `feedback:delete` | All care sessions (read/admin/report), All feedback (read/delete) |
| **CAREGIVER** | `nfc:check-in`, `nfc:check-out`, `care-session:create`, `care-session:update`, `care-session:read` | Create/read sessions, Complete sessions |
| **PATIENT** | `care-session:read`, `feedback:create`, `feedback:read` | Read own sessions, Create/read feedback |
| **MUNICIPALITY** | `care-session:report` | Care session reports only |
| **INSURER** | `care-session:report` | Care session reports only |

### Authorization Header

```
Authorization: Bearer <JWT_TOKEN>
```

---

# Care Sessions API

## Endpoint Overview

| Method | Endpoint | Purpose | Required Permission | Status |
|--------|----------|---------|-------------------|--------|
| **POST** | `/care-sessions/create` | Create new session (check-in) | `care-session:create` | 201 Created |
| **GET** | `/care-sessions/{session_id}` | Get session details | `care-session:read` | 200 OK |
| **PUT** | `/care-sessions/{session_id}/complete` | Complete session (check-out) | `care-session:update` | 200 OK |
| **GET** | `/care-sessions/` | List sessions with filters | `care-session:read` | 200 OK |
| **PATCH** | `/care-sessions/{session_id}` | Update session (admin only) | `care-session:admin` | 200 OK |
| **DELETE** | `/care-sessions/{session_id}` | Delete session (dev/test only) | `care-session:admin` | 204 No Content |

---

## 1. Create Care Session (Check-In)

**POST** `/care-sessions/create`

### Access Control
- **Allowed Roles**: CAREGIVER
- **Required Permission**: `care-session:create`

### Business Rules
1. Only one active session per patient at a time
2. NFC tag must exist and be active in the system
3. Session automatically starts with `check_in_time = now()`
4. Session `status` always starts as `"in_progress"`

### Request Body

```json
{
  "tag_id": "NFC-TAG-001",
  "session_id": "CS-0001"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tag_id` | string | ✅ Yes | NFC tag identifier (e.g., "NFC-TAG-001") |
| `session_id` | string | ❌ No | Custom session ID (e.g., "CS-0001"). If not provided, system generates next sequential ID from `care_session_id_seq` |

### Response (201 Created)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "CS-0001",
  "patient_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
  "check_in_time": "2025-01-16T14:30:45.123456",
  "check_out_time": null,
  "status": "in_progress",
  "caregiver_notes": null,
  "created_at": "2025-01-16T14:30:45.123456",
  "updated_at": null
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique session identifier (primary key) |
| `session_id` | string | Readable session identifier (CS-0001, CS-0002, etc.) |
| `patient_id` | UUID | ID of patient receiving care |
| `caregiver_id` | UUID | ID of caregiver providing care |
| `check_in_time` | datetime | Session start time (UTC converted to CET) |
| `check_out_time` | datetime \| null | Session end time (null while in_progress) |
| `status` | string | `"in_progress"` or `"completed"` |
| `caregiver_notes` | string \| null | Notes added by caregiver at checkout |
| `created_at` | datetime | Record creation timestamp |
| `updated_at` | datetime \| null | Record last modification timestamp |

### Example Request

```bash
curl -X POST http://localhost:8000/care-sessions/create \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tag_id": "NFC-TAG-001"
  }'
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `care-session:create` permission |
| **404** | `NFCTagNotFoundException` | Tag not found or inactive |
| **409** | `DuplicateActiveSessionException` | Patient already has active session |
| **500** | `InternalServerError` | Database or sequence generation error |

---

## 2. Get Care Session Details

**GET** `/care-sessions/{session_id}`

### Access Control
- **Allowed Roles**: CAREGIVER, PATIENT, ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `care-session:read`

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | UUID | ✅ Yes | Unique session identifier |

### Response (200 OK)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "CS-0001",
  "patient_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
  "check_in_time": "2025-01-16T14:30:45.123456",
  "check_out_time": "2025-01-16T16:45:30.654321",
  "status": "completed",
  "caregiver_notes": "Patient was in good spirits. Assisted with medication",
  "created_at": "2025-01-16T14:30:45.123456",
  "updated_at": "2025-01-16T16:45:30.654321"
}
```

### Example Request

```bash
curl -X GET http://localhost:8000/care-sessions/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `care-session:read` permission |
| **404** | `SessionNotFoundException` | Session ID not found |

---

## 3. Complete Care Session (Check-Out)

**PUT** `/care-sessions/{session_id}/complete`

### Access Control
- **Allowed Roles**: CAREGIVER
- **Required Permission**: `care-session:update`

### Business Rules
1. Session must be in `"in_progress"` status
2. Only the caregiver who started the session can complete it
3. Automatically sets `check_out_time = now()`
4. Changes session status to `"completed"`

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | UUID | ✅ Yes | Session to complete |

### Request Body

```json
{
  "caregiver_notes": "Patient was cooperative. Vitals stable. Provided medication as prescribed."
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `caregiver_notes` | string | ✅ Yes | Notes about the care session (e.g., observations, care provided) |

### Response (200 OK)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "CS-0001",
  "patient_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
  "check_in_time": "2025-01-16T14:30:45.123456",
  "check_out_time": "2025-01-16T16:45:30.654321",
  "status": "completed",
  "caregiver_notes": "Patient was cooperative. Vitals stable. Provided medication as prescribed.",
  "created_at": "2025-01-16T14:30:45.123456",
  "updated_at": "2025-01-16T16:45:30.654321"
}
```

### Example Request

```bash
curl -X PUT http://localhost:8000/care-sessions/550e8400-e29b-41d4-a716-446655440000/complete \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "caregiver_notes": "Patient was cooperative. Vitals stable."
  }'
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `care-session:update` permission |
| **404** | `SessionNotFoundException` | Session not found |
| **409** | `SessionNotInProgressException` | Session not in "in_progress" status |
| **403** | `UnauthorizedCaregiverException` | User is not the caregiver who started this session |

---

## 4. List Care Sessions with Filters

**GET** `/care-sessions/`

### Access Control
- **Allowed Roles**: CAREGIVER, PATIENT, ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `care-session:read`

### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `caregiver_id` | UUID | ❌ No | Filter by caregiver | `?caregiver_id=6ba7b811-9dad-11d1-80b4-00c04fd430c8` |
| `patient_id` | UUID | ❌ No | Filter by patient | `?patient_id=6ba7b810-9dad-11d1-80b4-00c04fd430c8` |
| `status` | string | ❌ No | Filter by status (in_progress, completed) | `?status=completed` |
| `start_date` | datetime | ❌ No | Filter sessions from this date (inclusive) | `?start_date=2025-01-01T00:00:00` |
| `end_date` | datetime | ❌ No | Filter sessions until this date (inclusive) | `?end_date=2025-01-31T23:59:59` |
| `page` | integer | ❌ No | Page number (default: 1, min: 1) | `?page=1` |
| `page_size` | integer | ❌ No | Items per page (default: 20, min: 1, max: 100) | `?page_size=50` |

### Response (200 OK)

```json
{
  "sessions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "session_id": "CS-0001",
      "patient_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
      "check_in_time": "2025-01-16T14:30:45.123456",
      "check_out_time": "2025-01-16T16:45:30.654321",
      "status": "completed",
      "caregiver_notes": "Patient was cooperative",
      "created_at": "2025-01-16T14:30:45.123456",
      "updated_at": "2025-01-16T16:45:30.654321"
    },
    {
      "id": "650e8400-e29b-41d4-a716-446655440001",
      "session_id": "CS-0002",
      "patient_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
      "check_in_time": "2025-01-15T10:15:20.123456",
      "check_out_time": "2025-01-15T12:30:15.654321",
      "status": "completed",
      "caregiver_notes": "Regular check-up completed",
      "created_at": "2025-01-15T10:15:20.123456",
      "updated_at": "2025-01-15T12:30:15.654321"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### Filter Examples

#### Example 1: Get all completed sessions for a patient

```bash
curl -X GET "http://localhost:8000/care-sessions/?patient_id=6ba7b810-9dad-11d1-80b4-00c04fd430c8&status=completed" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

#### Example 2: Get sessions for a caregiver in a date range

```bash
curl -X GET "http://localhost:8000/care-sessions/?caregiver_id=6ba7b811-9dad-11d1-80b4-00c04fd430c8&start_date=2025-01-01T00:00:00&end_date=2025-01-31T23:59:59&page_size=50" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

#### Example 3: Get all in-progress sessions (active check-ins)

```bash
curl -X GET "http://localhost:8000/care-sessions/?status=in_progress" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

#### Example 4: Pagination - Get page 2 with 25 items per page

```bash
curl -X GET "http://localhost:8000/care-sessions/?page=2&page_size=25" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `care-session:read` permission |
| **400** | `ValidationError` | Invalid date format or invalid status value |

---

## 5. Update Care Session (Admin Only)

**PATCH** `/care-sessions/{session_id}`

### Access Control
- **Allowed Roles**: ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `care-session:admin`

### Business Rules
1. Admin-only endpoint for correcting or adjusting session data
2. All fields are optional - only provided fields are updated
3. Can correct check-in/check-out times or status

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | UUID | ✅ Yes | Session to update |

### Request Body

```json
{
  "check_in_time": "2025-01-16T14:30:45.123456",
  "check_out_time": "2025-01-16T16:45:30.654321",
  "caregiver_notes": "Updated notes from admin review",
  "status": "completed"
}
```

**Parameters (all optional):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `check_in_time` | datetime | ❌ No | Override session check-in time |
| `check_out_time` | datetime | ❌ No | Override session check-out time |
| `caregiver_notes` | string | ❌ No | Update/add caregiver notes |
| `status` | string | ❌ No | Change status (in_progress, completed) |

### Response (200 OK)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "CS-0001",
  "patient_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
  "check_in_time": "2025-01-16T14:30:45.123456",
  "check_out_time": "2025-01-16T16:45:30.654321",
  "status": "completed",
  "caregiver_notes": "Updated notes from admin review",
  "created_at": "2025-01-16T14:30:45.123456",
  "updated_at": "2025-01-16T17:00:00.000000"
}
```

### Example Request

```bash
curl -X PATCH http://localhost:8000/care-sessions/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "check_in_time": "2025-01-16T14:00:00.000000",
    "caregiver_notes": "Corrected timing based on patient records"
  }'
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `care-session:admin` permission |
| **404** | `SessionNotFoundException` | Session not found |
| **409** | `InvalidSessionTimesException` | check_out_time <= check_in_time |
| **400** | `InvalidStatusException` | Invalid status value |

---

## 6. Delete Care Session (Developers Only)

**DELETE** `/care-sessions/{session_id}`

### Access Control
- **Allowed Roles**: ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `care-session:admin`

### ⚠️ Warning
This endpoint is intended **ONLY for development and testing environments**. In production, care session deletions should be handled through proper administrative processes with audit trails.

### Business Rules
1. Soft delete only (preserves data integrity with `deleted_at` timestamp)
2. Admin-only endpoint
3. Cannot be used for permanent data destruction in production

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | UUID | ✅ Yes | Session to delete |

### Response (204 No Content)

Empty response body with HTTP 204 status.

### Example Request

```bash
curl -X DELETE http://localhost:8000/care-sessions/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `care-session:admin` permission |
| **404** | `SessionNotFoundException` | Care session not found |
| **500** | `InternalServerError` | Database error |

---

# Feedback API

## Endpoint Overview

| Method | Endpoint | Purpose | Required Permission | Status |
|--------|----------|---------|-------------------|--------|
| **POST** | `/feedback/` | Create feedback | `feedback:create` | 201 Created |
| **GET** | `/feedback/{feedback_id}` | Get feedback details | `feedback:read` | 200 OK |
| **GET** | `/feedback/` | List feedbacks | `feedback:read` | 200 OK |
| **GET** | `/feedback/metrics/daily` | Daily average metrics | `feedback:read` | 200 OK |
| **GET** | `/feedback/metrics/caregivers/{caregiver_id}/weekly` | Caregiver weekly metrics | `feedback:read` | 200 OK |
| **GET** | `/feedback/metrics/patients/{patient_id}` | Patient average rating | `feedback:read` | 200 OK |
| **GET** | `/feedback/metrics/caregivers/top-performers/weekly` | Top 3 caregivers | `feedback:read` | 200 OK |
| **GET** | `/feedback/metrics/caregivers/{caregiver_id}/period` | Caregiver period metrics | `feedback:read` | 200 OK |
| **DELETE** | `/feedback/{feedback_id}` | Delete feedback | `feedback:delete` | 204 No Content |

---

## 1. Create Feedback

**POST** `/feedback/`

### Access Control
- **Allowed Roles**: PATIENT
- **Required Permission**: `feedback:create`

### Business Rules
1. Only patients can create feedback
2. Must be for a completed care session
3. One feedback per care session
4. Rating scale: 1 = Dissatisfied, 2 = Neutral, 3 = Satisfied

### Request Body

```json
{
  "care_session_id": "550e8400-e29b-41d4-a716-446655440000",
  "rating": 3,
  "patient_feedback": "The caregiver was very attentive and professional."
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `care_session_id` | UUID | ✅ Yes | ID of the care session |
| `rating` | integer | ✅ Yes | Rating: 1 (Dissatisfied), 2 (Neutral), 3 (Satisfied) |
| `patient_feedback` | string | ❌ No | Optional text feedback from patient |

### Response (201 Created)

```json
{
  "id": "750e8400-e29b-41d4-a716-446655440002",
  "care_session_id": "550e8400-e29b-41d4-a716-446655440000",
  "patient_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
  "rating": 3,
  "patient_feedback": "The caregiver was very attentive and professional.",
  "satisfaction_level": "SATISFIED",
  "created_at": "2025-01-16T17:30:00.123456"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique feedback identifier |
| `care_session_id` | UUID | Associated care session |
| `patient_id` | UUID | Patient who gave feedback |
| `caregiver_id` | UUID | Caregiver who received feedback |
| `rating` | integer | 1, 2, or 3 |
| `patient_feedback` | string | Patient's text feedback |
| `satisfaction_level` | string | `"DISSATISFIED"`, `"NEUTRAL"`, or `"SATISFIED"` |
| `created_at` | datetime | Feedback creation timestamp |

### Example Request

```bash
curl -X POST http://localhost:8000/feedback/ \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "care_session_id": "550e8400-e29b-41d4-a716-446655440000",
    "rating": 3,
    "patient_feedback": "Excellent care provided"
  }'
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `feedback:create` permission |
| **404** | `SessionNotFoundException` | Care session not found |
| **400** | `ValidationError` | Rating outside 1-3 range |

---

## 2. Get Feedback Details

**GET** `/feedback/{feedback_id}`

### Access Control
- **Allowed Roles**: PATIENT, ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `feedback:read`

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `feedback_id` | UUID | ✅ Yes | Unique feedback identifier |

### Response (200 OK)

```json
{
  "id": "750e8400-e29b-41d4-a716-446655440002",
  "care_session_id": "550e8400-e29b-41d4-a716-446655440000",
  "patient_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
  "rating": 3,
  "patient_feedback": "The caregiver was very attentive and professional.",
  "satisfaction_level": "SATISFIED",
  "created_at": "2025-01-16T17:30:00.123456"
}
```

### Example Request

```bash
curl -X GET http://localhost:8000/feedback/750e8400-e29b-41d4-a716-446655440002 \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `feedback:read` permission |
| **404** | `FeedbackNotFoundException` | Feedback not found |

---

## 3. List Feedbacks with Metrics

**GET** `/feedback/`

### Access Control
- **Allowed Roles**: PATIENT, ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `feedback:read`

### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `patient_id` | UUID | ❌ No | Filter by patient | `?patient_id=6ba7b810-9dad-11d1-80b4-00c04fd430c8` |
| `page` | integer | ❌ No | Page number (default: 1, min: 1) | `?page=1` |
| `page_size` | integer | ❌ No | Items per page (default: 20, min: 1, max: 100) | `?page_size=25` |

### Response (200 OK)

```json
{
  "feedbacks": [
    {
      "id": "750e8400-e29b-41d4-a716-446655440002",
      "care_session_id": "550e8400-e29b-41d4-a716-446655440000",
      "patient_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
      "rating": 3,
      "patient_feedback": "The caregiver was very attentive and professional.",
      "satisfaction_level": "SATISFIED",
      "created_at": "2025-01-16T17:30:00.123456"
    }
  ],
  "count": 1,
  "total": 42,
  "page": 1,
  "page_size": 20,
  "total_pages": 3,
  "metrics": {
    "average_rating": 2.73,
    "satisfaction_index": 91.0,
    "total_feedbacks": 42,
    "distribution": {
      "1": 5.0,
      "2": 21.0,
      "3": 74.0
    },
    "satisfaction_levels": {
      "DISSATISFIED": 2,
      "NEUTRAL": 9,
      "SATISFIED": 31
    }
  }
}
```

**Metrics Explanation:**

| Field | Description |
|-------|-------------|
| `average_rating` | Mean of all ratings (1-3 scale) |
| `satisfaction_index` | Average rating converted to 0-100 scale (formula: (avg_rating / 3) * 100) |
| `total_feedbacks` | Total number of feedbacks |
| `distribution` | Percentage breakdown of each rating (1, 2, 3) |
| `satisfaction_levels` | Count of feedbacks in each satisfaction level |

### Filter Examples

#### Example 1: Get feedbacks for a specific patient

```bash
curl -X GET "http://localhost:8000/feedback/?patient_id=6ba7b810-9dad-11d1-80b4-00c04fd430c8" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

#### Example 2: Pagination - Get page 2 with 25 items per page

```bash
curl -X GET "http://localhost:8000/feedback/?page=2&page_size=25" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `feedback:read` permission |
| **400** | `ValidationError` | Invalid pagination parameters |

---

## 4. Get Daily Average Metrics

**GET** `/feedback/metrics/daily`

### Access Control
- **Allowed Roles**: ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `feedback:read`

### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `start_date` | date | ✅ Yes | Start date (YYYY-MM-DD format) | `?start_date=2025-01-01` |
| `end_date` | date | ✅ Yes | End date (YYYY-MM-DD format) | `?end_date=2025-01-31` |

### Response (200 OK)

```json
{
  "daily_averages": [
    {
      "date": "2025-01-16",
      "average_rating": 2.85,
      "total_feedbacks": 13,
      "satisfaction_index": 95.0
    },
    {
      "date": "2025-01-15",
      "average_rating": 2.67,
      "total_feedbacks": 9,
      "satisfaction_index": 89.0
    },
    {
      "date": "2025-01-14",
      "average_rating": 2.5,
      "total_feedbacks": 6,
      "satisfaction_index": 83.33
    }
  ],
  "count": 3,
  "overall_metrics": {
    "average_rating": 2.73,
    "satisfaction_index": 91.0,
    "total_feedbacks": 28,
    "distribution": {
      "1": 3.57,
      "2": 32.14,
      "3": 64.29
    },
    "satisfaction_levels": {
      "DISSATISFIED": 1,
      "NEUTRAL": 9,
      "SATISFIED": 18
    }
  }
}
```

### Example Request

```bash
curl -X GET "http://localhost:8000/feedback/metrics/daily?start_date=2025-01-01&end_date=2025-01-31" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `feedback:read` permission |
| **400** | `ValidationError` | Invalid date format |

---

## 5. Get Caregiver Weekly Metrics

**GET** `/feedback/metrics/caregivers/{caregiver_id}/weekly`

### Access Control
- **Allowed Roles**: ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `feedback:read`

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `caregiver_id` | UUID | ✅ Yes | Caregiver identifier |

### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `week_start` | date | ✅ Yes | Monday of the week (YYYY-MM-DD) | `?week_start=2025-01-13` |

### Response (200 OK)

```json
{
  "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
  "week_start": "2025-01-13",
  "week_end": "2025-01-19",
  "average_rating": 2.88,
  "total_feedbacks": 16,
  "satisfaction_index": 96.0,
  "distribution": {
    "1": 0.0,
    "2": 12.5,
    "3": 87.5
  },
  "satisfaction_levels": {
    "DISSATISFIED": 0,
    "NEUTRAL": 2,
    "SATISFIED": 14
  }
}
```

### Example Request

```bash
curl -X GET "http://localhost:8000/feedback/metrics/caregivers/6ba7b811-9dad-11d1-80b4-00c04fd430c8/weekly?week_start=2025-01-13" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `feedback:read` permission |
| **400** | `ValidationError` | Invalid date format or caregiver not found |

---

## 6. Get Patient Average Rating

**GET** `/feedback/metrics/patients/{patient_id}`

### Access Control
- **Allowed Roles**: PATIENT, ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `feedback:read`

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `patient_id` | UUID | ✅ Yes | Patient identifier |

### Response (200 OK)

```json
{
  "patient_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "average_rating": 2.8,
  "satisfaction_index": 93.33,
  "total_feedbacks": 10
}
```

### Example Request

```bash
curl -X GET "http://localhost:8000/feedback/metrics/patients/6ba7b810-9dad-11d1-80b4-00c04fd430c8" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `feedback:read` permission |
| **404** | `PatientNotFoundException` | Patient not found |

---

## 7. Get Top Caregivers of the Week

**GET** `/feedback/metrics/caregivers/top-performers/weekly`

### Access Control
- **Allowed Roles**: ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `feedback:read`

### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `week_start` | date | ✅ Yes | Monday of the week (YYYY-MM-DD) | `?week_start=2025-01-13` |

### Response (200 OK)

```json
{
  "week_start": "2025-01-13",
  "week_end": "2025-01-19",
  "top_caregivers": [
    {
      "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
      "average_rating": 2.95,
      "satisfaction_index": 98.33,
      "total_feedbacks": 20,
      "rank": 1
    },
    {
      "caregiver_id": "6ba7b812-9dad-11d1-80b4-00c04fd430c9",
      "average_rating": 2.88,
      "satisfaction_index": 96.0,
      "total_feedbacks": 16,
      "rank": 2
    },
    {
      "caregiver_id": "6ba7b813-9dad-11d1-80b4-00c04fd430ca",
      "average_rating": 2.75,
      "satisfaction_index": 91.67,
      "total_feedbacks": 12,
      "rank": 3
    }
  ]
}
```

### Example Request

```bash
curl -X GET "http://localhost:8000/feedback/metrics/caregivers/top-performers/weekly?week_start=2025-01-13" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `feedback:read` permission |
| **400** | `ValidationError` | Invalid date format |

---

## 8. Get Caregiver Metrics for a Period

**GET** `/feedback/metrics/caregivers/{caregiver_id}/period`

### Access Control
- **Allowed Roles**: ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `feedback:read`

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `caregiver_id` | UUID | ✅ Yes | Caregiver identifier |

### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `period` | string | ❌ No | Period type: `daily`, `weekly`, `monthly` | `?period=weekly` |
| `start_date` | date | ❌ No | Custom start date (YYYY-MM-DD) | `?start_date=2025-01-01` |
| `end_date` | date | ❌ No | Custom end date (YYYY-MM-DD) | `?end_date=2025-01-31` |

### Auto-Calculation Rules

If period is specified but start_date/end_date are not provided, they're auto-calculated:

- **daily**: start_date = today, end_date = today
- **weekly**: start_date = Monday of current week, end_date = Sunday of current week
- **monthly**: start_date = 1st of current month, end_date = last day of current month

### Response (200 OK)

```json
{
  "caregiver_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
  "period": "weekly",
  "start_date": "2025-01-13",
  "end_date": "2025-01-19",
  "average_rating": 2.88,
  "total_feedbacks": 16
}
```

### Example Requests

#### Example 1: Get current week metrics (auto-calculated)

```bash
curl -X GET "http://localhost:8000/feedback/metrics/caregivers/6ba7b811-9dad-11d1-80b4-00c04fd430c8/period?period=weekly" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

#### Example 2: Get current month metrics (auto-calculated)

```bash
curl -X GET "http://localhost:8000/feedback/metrics/caregivers/6ba7b811-9dad-11d1-80b4-00c04fd430c8/period?period=monthly" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

#### Example 3: Get custom date range

```bash
curl -X GET "http://localhost:8000/feedback/metrics/caregivers/6ba7b811-9dad-11d1-80b4-00c04fd430c8/period?start_date=2025-01-01&end_date=2025-01-31" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `feedback:read` permission |
| **400** | `ValidationError` | Invalid period or date format |

---

## 9. Delete Feedback

**DELETE** `/feedback/{feedback_id}`

### Access Control
- **Allowed Roles**: ORG_ADMIN, SUPER_ADMIN
- **Required Permission**: `feedback:delete`

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `feedback_id` | UUID | ✅ Yes | Feedback to delete |

### Response (204 No Content)

Empty response body with HTTP 204 status.

### Example Request

```bash
curl -X DELETE http://localhost:8000/feedback/750e8400-e29b-41d4-a716-446655440002 \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Error Scenarios

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| **401** | `UnauthorizedException` | Invalid/missing JWT token |
| **403** | `PermissionDenied` | User lacks `feedback:delete` permission |
| **404** | `FeedbackNotFoundException` | Feedback not found |

---

# Response Formats

## Standard Response Fields

All responses include these standard fields (when applicable):

### DateTime Format

- **Format**: ISO 8601 with timezone
- **Example**: `"2025-01-16T14:30:45.123456"` (UTC converted to CET)
- **Timezone**: All timestamps converted to Central European Time (CET)

### UUID Format

- **Format**: Standard UUID v4 (32 hex digits with hyphens)
- **Example**: `"550e8400-e29b-41d4-a716-446655440000"`

### Pagination

All list endpoints follow this pagination format:

```json
{
  "items": [...],
  "count": 10,
  "total": 42,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

**Pagination Fields:**

| Field | Description |
|-------|-------------|
| `count` | Number of items in current response |
| `total` | Total number of items across all pages |
| `page` | Current page number (1-indexed) |
| `page_size` | Items per page |
| `total_pages` | Total number of pages |

---

# Error Handling

## Error Response Format

All errors follow this standard format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Or for validation errors:

```json
{
  "detail": [
    {
      "loc": ["query", "page"],
      "msg": "ensure this value is greater than or equal to 1",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

## HTTP Status Codes

| Status | Meaning | When Returned |
|--------|---------|---------------|
| **200** | OK | Successful GET/PUT/PATCH request |
| **201** | Created | Successful POST request (resource created) |
| **204** | No Content | Successful DELETE request |
| **400** | Bad Request | Invalid request parameters or validation error |
| **401** | Unauthorized | Missing or invalid JWT token |
| **403** | Forbidden | Valid token but lacks required permission |
| **404** | Not Found | Resource (session, feedback) not found |
| **409** | Conflict | Business logic violation (e.g., duplicate session) |
| **500** | Internal Server Error | Unexpected server error |

## Common Error Scenarios

### Missing Authentication Header

```
Status: 401 Unauthorized
{
  "detail": "Not authenticated"
}
```

**Fix**: Add `Authorization: Bearer <JWT_TOKEN>` header

### Insufficient Permissions

```
Status: 403 Forbidden
{
  "detail": "Permission denied: care-session:create"
}
```

**Fix**: Ensure user role has required permission

### Resource Not Found

```
Status: 404 Not Found
{
  "detail": "Session not found"
}
```

**Fix**: Verify resource ID is correct

### Duplicate Active Session

```
Status: 409 Conflict
{
  "detail": "Patient already has active session"
}
```

**Fix**: Complete existing session before creating new one

---

## Quick Reference Cheatsheet

### Create Care Session (Check-In)
```bash
POST /care-sessions/create
Permission: care-session:create
Body: {"tag_id": "NFC-TAG-001"}
```

### Complete Care Session (Check-Out)
```bash
PUT /care-sessions/{id}/complete
Permission: care-session:update
Body: {"caregiver_notes": "Notes here"}
```

### Update Care Session (Admin)
```bash
PATCH /care-sessions/{id}
Permission: care-session:admin
Body: {"check_in_time": "...", "status": "completed"}
```

### Delete Care Session (Dev/Test Only)
```bash
DELETE /care-sessions/{id}
Permission: care-session:admin
```

### List Sessions with Filters
```bash
GET /care-sessions/?status=completed&caregiver_id=<UUID>&page=1&page_size=20
Permission: care-session:read
```

### Create Feedback
```bash
POST /feedback/
Permission: feedback:create
Body: {"care_session_id": "<UUID>", "rating": 3, "patient_feedback": "Text"}
```

### Get Daily Metrics
```bash
GET /feedback/metrics/daily?start_date=2025-01-01&end_date=2025-01-31
Permission: feedback:read
```

### Get Top Caregivers
```bash
GET /feedback/metrics/caregivers/top-performers/weekly?week_start=2025-01-13
Permission: feedback:read
```

### Get Caregiver Weekly Metrics
```bash
GET /feedback/metrics/caregivers/{id}/weekly?week_start=2025-01-13
Permission: feedback:read
```

---

**Last Updated**: January 16, 2026  
**API Version**: 1.0  
**Environment**: Production-ready

