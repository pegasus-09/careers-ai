from core.user_profile import UserProfile
from core.career_profile import CareerProfile
from matching.aptitudes import match_aptitudes
from matching.intersts import match_interests
from matching.traits import match_traits
from matching.values import match_values
from matching.work_styles import match_work_styles

"""
Matching orchestration layer.

This module coordinates component-wise matchers.
It does not contain scoring logic itself.
"""

def match_user_to_role(
    user: UserProfile,
    role: CareerProfile,
) -> dict[str, float]:
    """
    Entry point for matching.
    Returns component-wise scores.
    """

    psych = user.psychometrics

    return {
        "aptitudes": match_aptitudes(psych.aptitudes, role.aptitudes),
        "interests": match_interests(psych.interests, role.interests),
        "traits": match_traits(psych.traits, role.traits),
        "values": match_values(psych.values, role.values),
        "work_styles": match_work_styles(psych.work_styles, role.work_styles),
    }