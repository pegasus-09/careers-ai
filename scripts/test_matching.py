"""
Test script to verify matching engine fixes.
Run from CareersAI directory: python scripts/test_matching.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inference.answer_converter import convert_answers_to_profile
from scripts.rank_all_careers import rank_profiles


def make_answers(overrides: dict[str, int]) -> dict[str, int]:
    """Build a full answer dict with defaults of 3, then apply overrides."""
    keys = (
        [f"A{i}" for i in range(1, 6)] +
        [f"I{i}" for i in range(1, 7)] +
        [f"T{i}" for i in range(1, 7)] +
        [f"V{i}" for i in range(1, 7)] +
        [f"W{i}" for i in range(1, 5)]
    )
    base = {k: 3 for k in keys}
    base.update(overrides)
    return base


# Test profiles
ALL_5S = make_answers({k: 5 for k in make_answers({})})
STEM_PEAKED = make_answers({
    "A1": 3, "A2": 5, "A3": 4, "A4": 5, "A5": 5,
    "I1": 4, "I2": 5, "I3": 1, "I4": 2, "I5": 3, "I6": 3,
    "T1": 4, "T2": 4, "T3": 2, "T4": 5, "T5": 2, "T6": 4,
    "V1": 5, "V2": 4, "V3": 2, "V4": 2, "V5": 2, "V6": 3,
    "W1": 5, "W2": 3, "W3": 2, "W4": 5,
})
SOCIAL_ARTISTIC = make_answers({
    "A1": 4, "A2": 2, "A3": 4, "A4": 1, "A5": 3,
    "I1": 2, "I2": 3, "I3": 5, "I4": 4, "I5": 3, "I6": 1,
    "T1": 2, "T2": 3, "T3": 4, "T4": 5, "T5": 4, "T6": 3,
    "V1": 3, "V2": 5, "V3": 4, "V4": 3, "V5": 2, "V6": 2,
    "W1": 2, "W2": 2, "W3": 3, "W4": 5,
})


def test_profile(name: str, answers: dict):
    profile = convert_answers_to_profile(answers)
    _results, ranking = rank_profiles(profile)
    top10 = ranking[:10]
    print(f"\n{'='*60}")
    print(f"Profile: {name}")
    print(f"{'='*60}")
    for i, (soc, title, score) in enumerate(top10, 1):
        marker = " *** TEACHING ***" if title and "teach" in title.lower() else ""
        print(f"  {i:2d}. {title or soc} — {score:.4f}{marker}")

    # Check teaching position
    teaching_positions = [
        i + 1 for i, (_, title, _) in enumerate(ranking[:20])
        if title and "teach" in title.lower()
    ]
    if teaching_positions:
        print(f"\n  Teaching roles in top 20: positions {teaching_positions}")
    else:
        print(f"\n  No teaching roles in top 20")


if __name__ == "__main__":
    print("Matching Engine Verification Tests")
    print("===================================")

    test_profile("All 5s (flat)", ALL_5S)
    test_profile("STEM-peaked", STEM_PEAKED)
    test_profile("Social/Artistic", SOCIAL_ARTISTIC)

    # Explicit check: all-5s should not have teaching as #1
    profile = convert_answers_to_profile(ALL_5S)
    _, ranking = rank_profiles(profile)
    top1_title = ranking[0][1] or ""
    if "teach" in top1_title.lower():
        print("\n[FAIL] All-5s profile has teaching as #1!")
    else:
        print(f"\n[PASS] All-5s profile #1 is: {top1_title}")

    # STEM profile should have STEM careers in top 5
    profile = convert_answers_to_profile(STEM_PEAKED)
    _, ranking = rank_profiles(profile)
    stem_keywords = {"engineer", "software", "developer", "scientist", "analyst", "computer", "data", "math", "statistic"}
    top5_titles = [ranking[i][1].lower() for i in range(5) if ranking[i][1]]
    stem_count = sum(1 for t in top5_titles if any(kw in t for kw in stem_keywords))
    if stem_count >= 2:
        print(f"[PASS] STEM profile has {stem_count}/5 STEM careers in top 5")
    else:
        print(f"[WARN] STEM profile has only {stem_count}/5 STEM careers in top 5")
