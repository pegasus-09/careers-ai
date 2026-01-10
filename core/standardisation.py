import math
from collections import defaultdict


def compute_stats(career_profiles: dict):
    """
    career_profiles: dict[soc -> PsychometricProfile]
    Returns: dict[dimension -> (mean, std)]
    """
    values = defaultdict(list)

    for profile in career_profiles.values():
        for group in [
            profile.traits,
            profile.interests,
            profile.aptitudes,
            profile.values,
            profile.work_styles,
        ]:
            for k, v in group.scores.items():
                values[k].append(v)

    stats = {}
    for k, vs in values.items():
        mean = sum(vs) / len(vs)
        variance = sum((v - mean) ** 2 for v in vs) / len(vs)
        std = math.sqrt(variance) or 1.0
        stats[k] = (mean, std)

    return stats


def standardize_profile(profile, stats):
    for group in [
        profile.traits,
        profile.interests,
        profile.aptitudes,
        profile.values,
        profile.work_styles,
    ]:
        for k, v in group.scores.items():
            mean, std = stats[k]
            group.scores[k] = (v - mean) / std

    return profile

