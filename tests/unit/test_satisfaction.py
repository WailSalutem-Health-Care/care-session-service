"""
Tests for satisfaction level calculations
"""
import pytest
from unittest.mock import Mock
from app.feedback.satisfaction import (
    SatisfactionLevel,
    get_satisfaction_level,
    compute_metrics,
)


def test_satisfaction_level_mapping():
    """Test that ratings map to correct satisfaction levels."""
    assert get_satisfaction_level(1) == SatisfactionLevel.DISSATISFIED
    assert get_satisfaction_level(2) == SatisfactionLevel.NEUTRAL
    assert get_satisfaction_level(3) == SatisfactionLevel.SATISFIED


def test_satisfaction_level_invalid():
    """Test handling of invalid ratings."""
    # Should default to NEUTRAL for invalid ratings
    assert get_satisfaction_level(0) == SatisfactionLevel.NEUTRAL
    assert get_satisfaction_level(5) == SatisfactionLevel.NEUTRAL


def test_compute_metrics_all_satisfied():
    """Test metrics when all ratings are satisfied."""
    # Create mock Feedback objects
    feedbacks = [Mock(rating=3) for _ in range(4)]
    metrics = compute_metrics(feedbacks)
    
    assert metrics["average_rating"] == 3.0
    assert metrics["satisfaction_index"] == 100.0  # (3/3) * 100
    assert metrics["distribution"]["3_satisfied"] == 100.0
    assert metrics["distribution"]["2_neutral"] == 0.0
    assert metrics["distribution"]["1_dissatisfied"] == 0.0


def test_compute_metrics_mixed():
    """Test metrics with mixed ratings."""
    # Create mock Feedback objects with mixed ratings
    feedbacks = [Mock(rating=1), Mock(rating=2), Mock(rating=3), Mock(rating=3)]
    metrics = compute_metrics(feedbacks)
    
    assert metrics["average_rating"] == 2.25
    assert round(metrics["satisfaction_index"], 2) == 75.0  # (2.25/3) * 100
    assert metrics["distribution"]["3_satisfied"] == 50.0
    assert metrics["distribution"]["2_neutral"] == 25.0
    assert metrics["distribution"]["1_dissatisfied"] == 25.0


def test_compute_metrics_all_dissatisfied():
    """Test metrics when all ratings are dissatisfied."""
    feedbacks = [Mock(rating=1) for _ in range(3)]
    metrics = compute_metrics(feedbacks)
    
    assert metrics["average_rating"] == 1.0
    assert round(metrics["satisfaction_index"], 2) == 33.33  # (1/3) * 100
    assert metrics["distribution"]["3_satisfied"] == 0.0
    assert metrics["distribution"]["2_neutral"] == 0.0
    assert metrics["distribution"]["1_dissatisfied"] == 100.0


def test_compute_metrics_empty():
    """Test metrics with no ratings."""
    feedbacks = []
    metrics = compute_metrics(feedbacks)
    
    assert metrics["average_rating"] == 0.0
    assert metrics["satisfaction_index"] == 0.0
    assert metrics["distribution"]["3_satisfied"] == 0.0
    assert metrics["distribution"]["2_neutral"] == 0.0
    assert metrics["distribution"]["1_dissatisfied"] == 0.0
