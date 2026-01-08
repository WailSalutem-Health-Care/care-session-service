"""Satisfaction semantics and metrics computation"""
from enum import Enum
from typing import List, Dict
from app.feedback.models import Feedback


class SatisfactionLevel(str, Enum):
    """Satisfaction levels based on ratings (1-3 scale)"""
    DISSATISFIED = "DISSATISFIED"
    NEUTRAL = "NEUTRAL"
    SATISFIED = "SATISFIED"


# Rating to satisfaction level mapping
RATING_TO_SATISFACTION = {
    1: SatisfactionLevel.DISSATISFIED,
    2: SatisfactionLevel.NEUTRAL,
    3: SatisfactionLevel.SATISFIED,
}


def get_satisfaction_level(rating: int) -> SatisfactionLevel:
    """
    Convert rating to satisfaction level.
    
    Args:
        rating: Rating (1-3: 1=Dissatisfied, 2=Neutral, 3=Satisfied)
        
    Returns:
        SatisfactionLevel enum
    """
    return RATING_TO_SATISFACTION.get(rating, SatisfactionLevel.NEUTRAL)


def compute_metrics(feedbacks: List[Feedback]) -> Dict:
    """
    Compute satisfaction metrics from feedback list.
    
    Metrics computed:
    - average_rating: Mean of all ratings
    - satisfaction_index: Normalized score (0-100)
    - total_feedbacks: Count of feedbacks
    - distribution: Percentage distribution of each rating (1-3)
    - satisfaction_levels: Count by satisfaction level
    
    Args:
        feedbacks: List of Feedback objects
        
    Returns:
        Dictionary with computed metrics
    """
    # Default empty metrics
    empty_metrics = {
        "average_rating": 0.0,
        "satisfaction_index": 0.0,
        "total_feedbacks": 0,
        "distribution": {"3_satisfied": 0.0, "2_neutral": 0.0, "1_dissatisfied": 0.0},
        "satisfaction_levels": {
            "SATISFIED": 0, "NEUTRAL": 0, "DISSATISFIED": 0
        }
    }
    
    if not feedbacks:
        return empty_metrics
    
    total = len(feedbacks)
    ratings = [f.rating for f in feedbacks]
    avg_rating = sum(ratings) / total
    
    # Count ratings (1-3)
    rating_counts = {i: ratings.count(i) for i in range(1, 4)}
    
    # Distribution (percentage)
    distribution = {
        "3_satisfied": round((rating_counts[3] / total) * 100, 2),
        "2_neutral": round((rating_counts[2] / total) * 100, 2),
        "1_dissatisfied": round((rating_counts[1] / total) * 100, 2),
    }
    
    # Satisfaction levels
    satisfaction_counts = {
        "SATISFIED": rating_counts[3],
        "NEUTRAL": rating_counts[2],
        "DISSATISFIED": rating_counts[1],
    }
    
    return {
        "average_rating": round(avg_rating, 2),
        "satisfaction_index": round((avg_rating / 3) * 100, 2),  # Normalized to 0-100 scale
        "total_feedbacks": total,
        "distribution": distribution,
        "satisfaction_levels": satisfaction_counts,
    }
