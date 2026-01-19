"""Custom Business Metrics for Care Session Service."""

import time
import logging
from contextlib import contextmanager
from typing import Literal
from opentelemetry import metrics

logger = logging.getLogger(__name__)

# Get meter for business metrics
meter = metrics.get_meter(__name__)

# Care Session Operation Metrics
care_session_operations_counter = meter.create_counter(
    name="care_session_operations_total",
    description="Total number of care session operations",
    unit="1",
)

care_session_operation_duration = meter.create_histogram(
    name="care_session_operation_duration_milliseconds",
    description="Duration of care session operations in milliseconds",
    unit="ms",
)

care_sessions_active_gauge = meter.create_up_down_counter(
    name="care_sessions_active",
    description="Number of currently active care sessions",
    unit="1",
)


OperationType = Literal["create", "update", "complete", "cancel", "delete"]
OperationStatus = Literal["success", "failure"]


def record_care_session_operation(
    operation_type: OperationType,
    status: OperationStatus,
    tenant_id: str = None,
):
    """
    Record a care session operation.
    
    Args:
        operation_type: Type of operation (create/update/complete/cancel/delete)
        status: Operation status (success/failure)
        tenant_id: Optional tenant identifier
    """
    try:
        labels = {
            "operation_type": operation_type,
            "status": status,
        }
        if tenant_id:
            labels["tenant_id"] = tenant_id
        
        care_session_operations_counter.add(1, labels)
    except Exception as e:
        logger.warning(f"Failed to record care session operation metric: {e}")


def record_operation_duration(
    operation_type: OperationType,
    duration_ms: float,
    status: OperationStatus,
    tenant_id: str = None,
):
    """
    Record the duration of a care session operation.
    
    Args:
        operation_type: Type of operation
        duration_ms: Duration in milliseconds
        status: Operation status
        tenant_id: Optional tenant identifier
    """
    try:
        labels = {
            "operation_type": operation_type,
            "status": status,
        }
        if tenant_id:
            labels["tenant_id"] = tenant_id
        
        care_session_operation_duration.record(duration_ms, labels)
    except Exception as e:
        logger.warning(f"Failed to record operation duration metric: {e}")


def set_active_sessions(count: int, tenant_id: str = None):
    """
    Set the number of active care sessions.
    
    Args:
        count: Number of active sessions
        tenant_id: Optional tenant identifier
    """
    try:
        labels = {}
        if tenant_id:
            labels["tenant_id"] = tenant_id
        
        # Note: This is an up-down counter, so we need to track the delta
        # In practice, you'd want to maintain state and calculate the difference
        # For now, we'll just record the value
        care_sessions_active_gauge.add(count, labels)
    except Exception as e:
        logger.warning(f"Failed to set active sessions metric: {e}")


class CareSessionMetrics:
    """Context manager for automatic care session operation timing and metrics."""
    
    def __init__(
        self,
        operation_type: OperationType,
        tenant_id: str = None,
    ):
        """
        Initialize metrics context manager.
        
        Args:
            operation_type: Type of operation
            tenant_id: Optional tenant identifier
        """
        self.operation_type = operation_type
        self.tenant_id = tenant_id
        self.start_time = None
        self.status: OperationStatus = "success"
    
    def __enter__(self):
        """Start timing the operation."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Record metrics when operation completes."""
        if exc_type is not None:
            self.status = "failure"
        
        # Calculate duration
        duration_ms = (time.time() - self.start_time) * 1000
        
        # Record metrics
        record_care_session_operation(
            self.operation_type,
            self.status,
            self.tenant_id,
        )
        record_operation_duration(
            self.operation_type,
            duration_ms,
            self.status,
            self.tenant_id,
        )
        
        # Don't suppress exceptions
        return False
    
    def set_status(self, status: OperationStatus):
        """
        Manually set operation status.
        
        Args:
            status: Operation status
        """
        self.status = status


@contextmanager
def track_care_session_operation(
    operation_type: OperationType,
    tenant_id: str = None,
):
    """
    Context manager for tracking care session operations.
    
    Args:
        operation_type: Type of operation
        tenant_id: Optional tenant identifier
        
    Yields:
        CareSessionMetrics: Metrics context manager
        
    Example:
        with track_care_session_operation("create", tenant_id="tenant-123"):
            # Perform operation
            create_care_session(...)
    """
    with CareSessionMetrics(operation_type, tenant_id) as metrics:
        yield metrics
