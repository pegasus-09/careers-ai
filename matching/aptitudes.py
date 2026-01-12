from core.career_components import Aptitudes


def match_aptitudes(
    user_aptitudes: Aptitudes,
    role_aptitudes: Aptitudes,
) -> float:
    """
    Capacity fit.

    Rule:
    - Underqualification hurts
    - Overqualification does not help
    - Missing user aptitude counts as 0
    """

    score = 0.0

    for name, role_value in role_aptitudes.scores.items():
        user_value = user_aptitudes.scores.get(name, 0.0)
        score += min(user_value, role_value)

    return score
