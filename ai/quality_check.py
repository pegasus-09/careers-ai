"""
Deterministic assessment quality checks.
No LLM calls — pure statistical analysis of answer patterns.
"""
from statistics import stdev, variance
from typing import Dict, List
from collections import Counter


def check_assessment_quality(answers: Dict[str, int]) -> dict:
    """
    Analyse assessment answers for suspicious patterns.

    Returns:
        valid: bool — whether the assessment can be used
        confidence: str — "high", "medium", or "low"
        flags: list[str] — detected issues
        straight_line_ratio: float — fraction of most common answer
        variance: float — variance of answers
    """
    flags: List[str] = []
    values = list(answers.values())

    if not values:
        return {
            "valid": False,
            "confidence": "low",
            "flags": ["no_answers"],
            "straight_line_ratio": 0.0,
            "variance": 0.0,
        }

    # Compute stats
    counts = Counter(values)
    most_common_count = counts.most_common(1)[0][1]
    straight_line_ratio = most_common_count / len(values)
    distinct_values = len(set(values))
    answer_variance = variance(values) if len(values) >= 2 else 0.0
    answer_stdev = stdev(values) if len(values) >= 2 else 0.0

    # ── Flag detection (stdev-based) ──────────────────────────────

    # 1. All identical → LOW
    if distinct_values == 1:
        flags.append("all_identical")

    # 2. stdev < 0.6 → LOW (very flat profile, catches extreme straight-lining)
    elif answer_stdev < 0.6:
        flags.append("low_differentiation")

    # 3. 45%+ same value → MEDIUM
    elif straight_line_ratio >= 0.45:
        flags.append("moderate_straight_lining")

    # 4. ≤3 distinct values → MEDIUM
    elif distinct_values <= 3:
        flags.append("limited_differentiation")

    # 5. stdev < 0.9 → MEDIUM
    elif answer_stdev < 0.9:
        flags.append("moderate_low_differentiation")

    # ── Section straight-lining (additional flag) ─────────────────
    sections = {"A": [], "I": [], "T": [], "V": [], "W": []}
    for qid, val in answers.items():
        prefix = qid[0]
        if prefix in sections:
            sections[prefix].append(val)

    for section, vals in sections.items():
        if vals and len(set(vals)) == 1 and len(vals) > 1:
            flags.append(f"section_straight_line_{section}")

    # ── Determine confidence level ────────────────────────────────
    # LOW: all_identical, low_differentiation (stdev<0.6)
    low_flags = {"all_identical", "low_differentiation"}
    # MEDIUM: moderate_straight_lining (45%+), limited_differentiation (≤3 distinct), moderate_low_differentiation (stdev<0.9)
    medium_flags = {"moderate_straight_lining", "limited_differentiation", "moderate_low_differentiation"}

    if any(f in low_flags for f in flags):
        confidence = "low"
        valid = "all_identical" not in flags  # all_identical → invalid
    elif any(f in medium_flags for f in flags):
        confidence = "medium"
        valid = True
    elif any(f.startswith("section_straight_line") for f in flags):
        # Section straight-lining bumps HIGH → MEDIUM
        confidence = "medium"
        valid = True
    else:
        confidence = "high"
        valid = True

    return {
        "valid": valid,
        "confidence": confidence,
        "flags": flags,
        "straight_line_ratio": round(straight_line_ratio, 3),
        "variance": round(answer_variance, 3),
    }
