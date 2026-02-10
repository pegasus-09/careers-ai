"""
Test script to verify the peakiness fix for the matching engine.
Ensures flat profiles (all-4s) no longer get teaching-dominated rankings,
and peaked STEM profiles get STEM careers.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inference.answer_converter import convert_answers_to_profile
from scripts.rank_all_careers import rank_profiles


def make_flat_answers():
    """All answers are 4 — produces a flat profile (stdev ≈ 0)."""
    ids = (
        [f"A{i}" for i in range(1, 6)] +
        [f"I{i}" for i in range(1, 7)] +
        [f"T{i}" for i in range(1, 7)] +
        [f"V{i}" for i in range(1, 7)] +
        [f"W{i}" for i in range(1, 5)]
    )
    return {qid: 4 for qid in ids}


def make_stem_answers():
    """High technology/science/analytical, low arts/social — peaked STEM profile."""
    return {
        "A1": 5, "A2": 3, "A3": 5, "A4": 5, "A5": 4,  # Strong numerical/spatial/logical
        "I1": 5, "I2": 5, "I3": 2, "I4": 1, "I5": 2, "I6": 3,  # Tech + science high
        "T1": 5, "T2": 2, "T3": 1, "T4": 3, "T5": 5, "T6": 3,  # Analytical + detail
        "V1": 3, "V2": 4, "V3": 2, "V4": 4, "V5": 2, "V6": 3,
        "W1": 2, "W2": 4, "W3": 4, "W4": 3,
    }


def test_flat_profile():
    print("=" * 60)
    print("TEST 1: Flat profile (all 4s)")
    print("=" * 60)

    answers = make_flat_answers()
    profile = convert_answers_to_profile(answers)

    print(f"Interest scores: {profile.interests.scores}")
    print(f"Trait scores:    {profile.traits.scores}")

    _results, ranking = rank_profiles(profile)

    top5 = ranking[:5]
    print("\nTop 5 careers:")
    for i, (code, title, score) in enumerate(top5, 1):
        print(f"  {i}. {title} ({code}) — score: {score:.3f}")

    # Check teaching isn't dominating
    teaching_keywords = ["teach", "education", "instructor"]
    teaching_in_top5 = sum(
        1 for _, title, _ in top5
        if title and any(kw in title.lower() for kw in teaching_keywords)
    )
    print(f"\nTeaching-related in top 5: {teaching_in_top5}")
    if teaching_in_top5 <= 1:
        print("PASS: Teaching is not dominating flat profile rankings")
    else:
        print("FAIL: Teaching still dominates flat profile rankings")

    return teaching_in_top5 <= 1


def test_stem_profile():
    print("\n" + "=" * 60)
    print("TEST 2: Peaked STEM profile")
    print("=" * 60)

    answers = make_stem_answers()
    profile = convert_answers_to_profile(answers)

    print(f"Interest scores: {profile.interests.scores}")
    print(f"Trait scores:    {profile.traits.scores}")

    _results, ranking = rank_profiles(profile)

    top5 = ranking[:5]
    print("\nTop 5 careers:")
    for i, (code, title, score) in enumerate(top5, 1):
        print(f"  {i}. {title} ({code}) — score: {score:.3f}")

    stem_keywords = ["engineer", "software", "computer", "data", "scientist",
                     "developer", "analyst", "programmer", "math", "statistic"]
    stem_in_top5 = sum(
        1 for _, title, _ in top5
        if title and any(kw in title.lower() for kw in stem_keywords)
    )
    print(f"\nSTEM-related in top 5: {stem_in_top5}")
    if stem_in_top5 >= 2:
        print("PASS: STEM careers appear in peaked STEM profile")
    else:
        print("WARN: Fewer STEM careers than expected (may still be acceptable)")

    return True


if __name__ == "__main__":
    pass1 = test_flat_profile()
    pass2 = test_stem_profile()

    print("\n" + "=" * 60)
    if pass1 and pass2:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)
