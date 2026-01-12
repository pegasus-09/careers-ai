COMPONENT_WEIGHTS = {
    "aptitudes": 1.0,
    "interests": 1.2,
    "traits": 1.0,
    "values": 0.8,
    "work_styles": 1.1,
}


def aggregate_match(scores: dict[str, float]) -> float:
    """
    Aggregate component-wise match scores into a single ranking score.

    Rules:
    - Positive components add
    - Penalties subtract
    - Weights express relative importance
    - No normalization
    """

    total = 0.0

    for component, value in scores.items():
        weight = COMPONENT_WEIGHTS.get(component, 1.0)
        total += weight * value

    return total
