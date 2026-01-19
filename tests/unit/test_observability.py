"""Unit tests for observability module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.observability.metrics import (
    record_care_session_operation,
    record_operation_duration,
    set_active_sessions,
    CareSessionMetrics,
    track_care_session_operation,
)


class TestCareSessionMetrics:
    """Tests for CareSessionMetrics context manager."""

    def test_context_manager_success(self):
        """Test context manager records success metrics."""
        with patch("app.observability.metrics.record_care_session_operation") as mock_record_op:
            with patch("app.observability.metrics.record_operation_duration") as mock_record_duration:
                with CareSessionMetrics("create", tenant_id="test-tenant") as metrics:
                    # Simulate successful operation
                    pass

                # Verify metrics were recorded
                mock_record_op.assert_called_once_with("create", "success", "test-tenant")
                mock_record_duration.assert_called_once()
                args = mock_record_duration.call_args[0]
                assert args[0] == "create"
                assert args[1] > 0  # Duration should be positive
                assert args[2] == "success"

    def test_context_manager_failure(self):
        """Test context manager records failure metrics on exception."""
        with patch("app.observability.metrics.record_care_session_operation") as mock_record_op:
            with patch("app.observability.metrics.record_operation_duration") as mock_record_duration:
                with pytest.raises(ValueError):
                    with CareSessionMetrics("update", tenant_id="test-tenant") as metrics:
                        raise ValueError("Test error")

                # Verify failure metrics were recorded
                mock_record_op.assert_called_once_with("update", "failure", "test-tenant")
                mock_record_duration.assert_called_once()
                args = mock_record_duration.call_args[0]
                assert args[2] == "failure"

    def test_context_manager_without_tenant(self):
        """Test context manager works without tenant_id."""
        with patch("app.observability.metrics.record_care_session_operation") as mock_record_op:
            with patch("app.observability.metrics.record_operation_duration") as mock_record_duration:
                with CareSessionMetrics("complete") as metrics:
                    pass

                # Verify metrics were recorded without tenant_id
                mock_record_op.assert_called_once_with("complete", "success", None)

    def test_set_status_manually(self):
        """Test manually setting operation status."""
        with patch("app.observability.metrics.record_care_session_operation") as mock_record_op:
            with patch("app.observability.metrics.record_operation_duration") as mock_record_duration:
                with CareSessionMetrics("delete") as metrics:
                    metrics.set_status("failure")

                # Verify failure status was recorded
                args = mock_record_op.call_args[0]
                assert args[1] == "failure"


class TestTrackCareSessionOperation:
    """Tests for track_care_session_operation helper."""

    def test_track_operation_success(self):
        """Test tracking successful operation."""
        with patch("app.observability.metrics.record_care_session_operation") as mock_record_op:
            with patch("app.observability.metrics.record_operation_duration") as mock_record_duration:
                with track_care_session_operation("create", tenant_id="test") as metrics:
                    result = "success"

                assert result == "success"
                mock_record_op.assert_called_once()

    def test_track_operation_failure(self):
        """Test tracking failed operation."""
        with patch("app.observability.metrics.record_care_session_operation") as mock_record_op:
            with patch("app.observability.metrics.record_operation_duration") as mock_record_duration:
                with pytest.raises(RuntimeError):
                    with track_care_session_operation("cancel") as metrics:
                        raise RuntimeError("Operation failed")

                # Verify failure was recorded
                args = mock_record_op.call_args[0]
                assert args[1] == "failure"


class TestMetricFunctions:
    """Tests for individual metric recording functions."""

    @patch("app.observability.metrics.care_session_operations_counter")
    def test_record_care_session_operation(self, mock_counter):
        """Test recording care session operation."""
        record_care_session_operation("create", "success", tenant_id="test")

        mock_counter.add.assert_called_once_with(
            1,
            {"operation_type": "create", "status": "success", "tenant_id": "test"}
        )

    @patch("app.observability.metrics.care_session_operations_counter")
    def test_record_operation_without_tenant(self, mock_counter):
        """Test recording operation without tenant_id."""
        record_care_session_operation("update", "success")

        mock_counter.add.assert_called_once_with(
            1,
            {"operation_type": "update", "status": "success"}
        )

    @patch("app.observability.metrics.care_session_operation_duration")
    def test_record_operation_duration(self, mock_histogram):
        """Test recording operation duration."""
        record_operation_duration("complete", 123.45, "success", tenant_id="test")

        mock_histogram.record.assert_called_once_with(
            123.45,
            {"operation_type": "complete", "status": "success", "tenant_id": "test"}
        )

    @patch("app.observability.metrics.care_sessions_active_gauge")
    def test_set_active_sessions(self, mock_gauge):
        """Test setting active sessions count."""
        set_active_sessions(5, tenant_id="test")

        mock_gauge.add.assert_called_once_with(5, {"tenant_id": "test"})

    @patch("app.observability.metrics.care_sessions_active_gauge")
    def test_set_active_sessions_without_tenant(self, mock_gauge):
        """Test setting active sessions without tenant_id."""
        set_active_sessions(10)

        mock_gauge.add.assert_called_once_with(10, {})


class TestMetricErrorHandling:
    """Tests for metric error handling."""

    @patch("app.observability.metrics.care_session_operations_counter")
    def test_metric_recording_handles_exceptions(self, mock_counter):
        """Test that metric recording failures don't crash the application."""
        mock_counter.add.side_effect = Exception("Metric export failed")

        # Should not raise exception
        record_care_session_operation("create", "success")

    @patch("app.observability.metrics.care_session_operation_duration")
    def test_duration_recording_handles_exceptions(self, mock_histogram):
        """Test that duration recording failures don't crash the application."""
        mock_histogram.record.side_effect = Exception("Metric export failed")

        # Should not raise exception
        record_operation_duration("update", 100.0, "success")
