
"""
M3 observation freshness model.

Measures time since the last successful observation of a
platform-category pair. This does not measure actual listing age.
"""

from datetime import datetime, timezone
from math import exp


def calculate_freshness(
    last_observed_at: datetime,
    half_life_hours: float = 24.0,
    now: datetime | None = None,
) -> dict:
    """
    Calculate freshness using exponential decay.

    A score of 1.0 means the observation is current.
    A score of 0.5 means one half-life has elapsed.
    """

    if half_life_hours <= 0:
        raise ValueError("half_life_hours must be greater than zero")

    now = now or datetime.now(timezone.utc)

    if last_observed_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("Timestamps must include timezone information")

    age_seconds = max(
        0.0,
        (now - last_observed_at).total_seconds(),
    )

    age_hours = age_seconds / 3600

    decay_rate = 0.6931471805599453 / half_life_hours
    freshness_score = exp(-decay_rate * age_hours)

    return {
        "age_hours": round(age_hours, 2),
        "freshness_score": round(freshness_score, 4),
        "half_life_hours": half_life_hours,
    }


if __name__ == "__main__":
    from datetime import timedelta

    now = datetime.now(timezone.utc)

    test_observations = [
        ("Just observed", now),
        ("12 hours ago", now - timedelta(hours=12)),
        ("24 hours ago", now - timedelta(hours=24)),
        ("48 hours ago", now - timedelta(hours=48)),
    ]

    print("M3 Observation Freshness Test")
    print("-" * 40)

    for label, timestamp in test_observations:
        result = calculate_freshness(
            last_observed_at=timestamp,
            half_life_hours=24,
            now=now,
        )

        print(
            f"{label:18} "
            f"Age: {result['age_hours']:6.2f} h | "
            f"Freshness: {result['freshness_score']:.4f}"
        )
if __name__ == "__main__":
    from datetime import timedelta

    now = datetime.now(timezone.utc)

    test_cases = {
        "Just observed": now,
        "12 hours ago": now - timedelta(hours=12),
        "24 hours ago": now - timedelta(hours=24),
        "48 hours ago": now - timedelta(hours=48),
    }

    for label, observed_at in test_cases.items():
        result = calculate_freshness(
            last_observed_at=observed_at,
            half_life_hours=24,
            now=now,
        )

        print(
            f"{label}: "
            f"score={result['freshness_score']:.4f}, "
            f"age={result['age_hours']:.2f} hours"
        )