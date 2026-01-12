from core.career_components import WorkStyles

def match_work_styles(
    user_ws: WorkStyles,
    role_ws: WorkStyles,
) -> float:
    """
    Environment fit.

    Rule:
    - Penalize mismatch
    - Signed values allowed
    - Exact match is best (penalty = 0)
    """

    penalty = 0.0

    for name, role_value in role_ws.scores.items():
        user_value = user_ws.scores.get(name, 0.0)
        penalty += abs(user_value - role_value)

    return -penalty
