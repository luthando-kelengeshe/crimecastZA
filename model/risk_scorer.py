"""
model/risk_scorer.py

Derives Risk_Score (integer 1-5) from predicted crime counts by ranking
against the historical distribution using 20th-percentile boundaries.

Score 1 = bottom 20% (lowest risk)
Score 5 = top 20% (highest risk)
"""

from __future__ import annotations

import numpy as np


def compute_risk_score(
    predicted_count: float,
    historical_counts: list[float],
) -> int:
    """
    Compute a Risk_Score (1-5) for a predicted crime count.

    Ranks the predicted_count against the historical_counts distribution
    using 20th-percentile boundaries:
      - Score 1: predicted_count <= 20th percentile
      - Score 2: 20th < predicted_count <= 40th percentile
      - Score 3: 40th < predicted_count <= 60th percentile
      - Score 4: 60th < predicted_count <= 80th percentile
      - Score 5: predicted_count > 80th percentile

    Args:
        predicted_count: The forecasted crime count.
        historical_counts: List of historical crime counts for the same
                          crime category and province.

    Returns:
        Integer risk score between 1 and 5 inclusive.
    """
    if not historical_counts:
        return 3  # Default to middle if no history

    arr = np.array(historical_counts, dtype=float)
    percentiles = np.percentile(arr, [20, 40, 60, 80])

    if predicted_count <= percentiles[0]:
        return 1
    elif predicted_count <= percentiles[1]:
        return 2
    elif predicted_count <= percentiles[2]:
        return 3
    elif predicted_count <= percentiles[3]:
        return 4
    else:
        return 5
