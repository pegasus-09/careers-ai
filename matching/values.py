from core.career_components import Values


def match_values(
    user_values: Values,
    role_values: Values,
) -> float:
    """
    Reward alignment.

    Rules:
    - Role-side values define what matters
    - User alignment with rewarded values increases score
    - Values not rewarded by the role are ignored (not penalized)
    """

    score = 0.0

    for name, role_value in role_values.scores.items():
        if role_value <= 0:
            continue

        user_value = user_values.scores.get(name, 0.0)
        score += user_value * role_value

    return score
