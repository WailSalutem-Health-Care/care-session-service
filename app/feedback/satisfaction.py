"""Satisfaction semantics and metrics computation"""
from enum import Enum
from typing import List, Dict
from app.feedback.models import Feedback


class SatisfactionLevel(str, Enum):
    """Satisfaction levels based on star ratings"""
    VERY_DISSATISFIED = "VERY_DISSATISFIED"
    DISSATISFIED = "DISSATISFIED"
    NEUTRAL = "NEUTRAL"
    SATISFIED = "SATISFIED"
    VERY_SATISFIED = "VERY_SATISFIED"


# Rating to satisfaction level mapping
RATING_TO_SATISFACTION = {
    1: SatisfactionLevel.VERY_DISSATISFIED,
    2: SatisfactionLevel.DISSATISFIED,
    3: SatisfactionLevel.NEUTRAL,
    4: SatisfactionLevel.SATISFIED,
    5: SatisfactionLevel.VERY_SATISFIED,
}


def get_satisfaction_level(rating: int) -> SatisfactionLevel:
    """
    Convert star rating to satisfaction level.
    
    Args:
        rating: Star rating (1-5)
        
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
    - distribution: Percentage distribution of each star rating
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
        "distribution": {"5_star": 0.0, "4_star": 0.0, "3_star": 0.0, "2_star": 0.0, "1_star": 0.0},
        "satisfaction_levels": {
            "VERY_SATISFIED": 0, "SATISFIED": 0, "NEUTRAL": 0, "DISSATISFIED": 0, "VERY_DISSATISFIED": 0
        }
    }
    
    if not feedbacks:
        return empty_metrics
    
    total = len(feedbacks)
    ratings = [f.rating for f in feedbacks]
    avg_rating = sum(ratings) / total
    
    # Count ratings
    rating_counts = {i: ratings.count(i) for i in range(1, 6)}
    
    # Distribution (percentage)
    distribution = {f"{i}_star": round((rating_counts[i] / total) * 100, 2) for i in range(5, 0, -1)}
    
    # Satisfaction levels (matching rating to level)
    satisfaction_counts = {
        "VERY_SATISFIED": rating_counts[5],
        "SATISFIED": rating_counts[4],
        "NEUTRAL": rating_counts[3],
        "DISSATISFIED": rating_counts[2],
        "VERY_DISSATISFIED": rating_counts[1],
    }
    
    return {
        "average_rating": round(avg_rating, 2),
        "satisfaction_index": round((avg_rating / 5) * 100, 2),
        "total_feedbacks": total,
        "distribution": distribution,
        "satisfaction_levels": satisfaction_counts,
    }
