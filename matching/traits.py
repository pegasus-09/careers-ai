from core.career_components import Traits


def match_traits(
    user_traits: Traits,
    role_traits: Traits,
) -> float:
    """
    Performance fit.

    Rule:
    - Penalize mismatch
    - Exact match is best (penalty = 0)
    - Larger differences hurt more
    """

    penalty = 0.0

    for name, role_value in role_traits.scores.items():
        user_value = user_traits.scores.get(name, 0.0)
        penalty += abs(user_value - role_value)

    # Negative so higher is better (consistent with other matchers)
    return -penalty
