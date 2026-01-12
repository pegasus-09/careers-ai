from core.career_components import Interests


def match_interests(
    user_interests: Interests,
    role_interests: Interests,
) -> float:
    """
    Motivation fit.

    Rule:
    - Higher overlap is better
    - Role-side interests define what matters
    - Missing dimensions default to 0
    """

    score = 0.0

    for name, role_value in role_interests.scores.items():
        user_value = user_interests.scores.get(name, 0.0)
        score += user_value * role_value

    return score
