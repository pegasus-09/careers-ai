from statistics import stdev as _stdev

COMPONENT_WEIGHTS = {
    "aptitudes": 1.0,
    "interests": 1.2,
    "traits": 1.0,
    "values": 0.8,
    "work_styles": 1.1,
}

# Metadata keys that should NOT be included in the weighted sum
_METADATA_KEYS = {"profile_peakiness", "career_specificity", "peak_alignment"}

# Peakiness thresholds (normalised 0-1 scale)
FLAT_PROFILE_THRESHOLD = 0.3
PEAK_ALIGNMENT_BONUS = 0.15     # up to 15% boost for peak alignment


def aggregate_match(scores: dict[str, float]) -> float:
    """
    Aggregate component-wise match scores into a single ranking score.

    Adjustments for flat profiles (peakiness < 0.3):
    1. Weight normalisation: blend component weights towards uniform (1.0).
    2. Component capping: cap each component's absolute contribution to the
       mean absolute value. This prevents careers that score extremely well
       on one component from dominating when the student profile provides
       no differentiation signal.

    For peaked profiles:
    3. Peak alignment bonus: up to 15% boost when the student's top 3
       dimensions match the career's top 3 requirements.
    """

    profile_peakiness = scores.get("profile_peakiness", 0.0)
    career_specificity = scores.get("career_specificity", 0.0)
    peak_alignment = scores.get("peak_alignment", 0)

    # For flat profiles, blend weights towards uniform (1.0)
    if profile_peakiness < FLAT_PROFILE_THRESHOLD:
        blend = profile_peakiness / FLAT_PROFILE_THRESHOLD
    else:
        blend = 1.0

    weighted_components = {}
    for component, value in scores.items():
        if component in _METADATA_KEYS:
            continue
        normal_weight = COMPONENT_WEIGHTS.get(component, 1.0)
        weight = 1.0 + blend * (normal_weight - 1.0)
        weighted_components[component] = weight * value

    # For flat profiles: cap outlier components towards the mean
    if profile_peakiness < FLAT_PROFILE_THRESHOLD and weighted_components:
        flatness = 1.0 - (profile_peakiness / FLAT_PROFILE_THRESHOLD)
        abs_values = [abs(v) for v in weighted_components.values()]
        mean_abs = sum(abs_values) / len(abs_values)

        capped = {}
        for comp, val in weighted_components.items():
            if abs(val) > mean_abs:
                # Blend towards mean_abs, proportional to flatness
                sign = 1.0 if val >= 0 else -1.0
                capped_val = mean_abs * sign
                val = val + flatness * (capped_val - val)
            capped[comp] = val
        weighted_components = capped

    total = sum(weighted_components.values())

    # Peak alignment bonus: peaked profile matched to specific career
    if profile_peakiness >= FLAT_PROFILE_THRESHOLD and career_specificity >= FLAT_PROFILE_THRESHOLD:
        alignment_bonus = (peak_alignment / 3.0) * PEAK_ALIGNMENT_BONUS
        total *= (1.0 + alignment_bonus)

    return total
