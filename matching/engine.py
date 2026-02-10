from statistics import stdev

from models.user_profile import UserProfile
from models.career_profile import CareerProfile
from matching.aptitudes import match_aptitudes
from matching.intersts import match_interests
from matching.traits import match_traits
from matching.values import match_values
from matching.work_styles import match_work_styles
from matching.aggregate import aggregate_match

"""
Matching orchestration layer.

This module coordinates component-wise matchers.
It does not contain scoring logic itself.
"""


def _compute_peakiness(values: list[float]) -> float:
    """
    Normalised peakiness score: 0.0 = perfectly flat, 1.0 = maximally peaked.
    Based on standard deviation normalised to the theoretical max for 0-1 range.
    """
    if len(values) < 2:
        return 0.0
    sd = stdev(values)
    # Max possible stdev for values in [0,1] is 0.5 (half at 0, half at 1)
    return min(sd / 0.5, 1.0)


def _get_all_scores(profile) -> dict[str, float]:
    """Extract all dimension scores from a profile/career into a flat dict."""
    all_scores = {}
    for component_name in ("aptitudes", "interests", "traits", "values", "work_styles"):
        component = getattr(profile, component_name, None)
        if component is not None:
            for dim, val in component.scores.items():
                all_scores[f"{component_name}.{dim}"] = val
    return all_scores


def _top_n_dimensions(scores: dict[str, float], n: int = 3) -> set[str]:
    """Return the top N dimension keys by score."""
    sorted_dims = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return {dim for dim, _ in sorted_dims[:n]}


def match_user_to_role(
    user: UserProfile,
    role: CareerProfile,
) -> dict[str, float]:
    """
    Entry point for matching.
    Returns component-wise scores plus peakiness metadata.
    """

    psych = user.psychometrics

    component_scores = {
        "aptitudes": match_aptitudes(psych.aptitudes, role.aptitudes),
        "interests": match_interests(psych.interests, role.interests),
        "traits": match_traits(psych.traits, role.traits),
        "values": match_values(psych.values, role.values),
        "work_styles": match_work_styles(psych.work_styles, role.work_styles),
    }

    # Peakiness metrics across ALL dimensions
    profile_scores = _get_all_scores(psych)
    career_scores = _get_all_scores(role)

    profile_peakiness = _compute_peakiness(list(profile_scores.values()))
    career_specificity = _compute_peakiness(list(career_scores.values()))

    component_scores["profile_peakiness"] = profile_peakiness
    component_scores["career_specificity"] = career_specificity

    # Peak alignment: how many of the student's top 3 match the career's top 3
    profile_top3 = _top_n_dimensions(profile_scores)
    career_top3 = _top_n_dimensions(career_scores)
    component_scores["peak_alignment"] = len(profile_top3 & career_top3)

    component_scores["total"] = aggregate_match(component_scores)
    return component_scores
