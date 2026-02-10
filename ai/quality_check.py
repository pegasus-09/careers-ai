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

    # 1. All identical → invalid
    if distinct_values == 1:
        flags.append("all_identical")

    # 2. Straight-lining: 80%+ same answer → low confidence
    elif straight_line_ratio >= 0.8:
        flags.append("straight_lining")

    # 3. Only 2 distinct values → medium confidence
    elif distinct_values <= 2:
        flags.append("limited_differentiation")

    # 4. Section straight-lining: entire section has same value
    sections = {"A": [], "I": [], "T": [], "V": [], "W": []}
    for qid, val in answers.items():
        prefix = qid[0]
        if prefix in sections:
            sections[prefix].append(val)

    for section, vals in sections.items():
        if vals and len(set(vals)) == 1 and len(vals) > 1:
            flags.append(f"section_straight_line_{section}")

    # Determine confidence level
    if "all_identical" in flags:
        confidence = "low"
        valid = False
    elif "straight_lining" in flags:
        confidence = "low"
        valid = True
    elif "limited_differentiation" in flags:
        confidence = "medium"
        valid = True
    elif any(f.startswith("section_straight_line") for f in flags):
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
