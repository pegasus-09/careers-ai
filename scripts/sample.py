from core.profile import PsychometricProfile
from core.career_components import Traits, Interests, Aptitudes, Values, WorkStyles
from inference.ai_interpreter import interpret_profile


def build_test_profile():
    traits = Traits({
        "analytical": 0.80,
        "creative": 0.35,
        "social": 0.40,
        "leadership": 0.30,
        "detail_oriented": 0.75,
        "adaptability": 0.50
    })

    interests = Interests({
        "technology": 0.85,
        "science": 0.70,
        "business": 0.40,
        "arts": 0.20,
        "social_impact": 0.30,
        "hands_on": 0.55
    })

    aptitudes = Aptitudes({
        "numerical_reasoning": 0.80,
        "verbal_reasoning": 0.55,
        "spatial_reasoning": 0.45,
        "logical_reasoning": 0.85,
        "memory": 0.65
    })

    values = Values({
        "stability": 0.55,
        "financial_security": 0.60,
        "prestige": 0.35,
        "autonomy": 0.45,
        "helping_others": 0.30,
        "work_life_balance": 0.40
    })

    work_styles = WorkStyles({
        "team_based": 0.40,
        "structure": 0.70,
        "pace": 0.60,
        "ambiguity_tolerance": 0.35
    })

    profile = PsychometricProfile(
        traits=traits,
        interests=interests,
        aptitudes=aptitudes,
        values=values,
        work_styles=work_styles
    )

    profile.confidence = 0.65
    return profile


if __name__ == "__main__":
    profile = build_test_profile()
    results = interpret_profile(profile)

    print("\n=== SANITY CHECK RESULTS ===\n")

    print("Top Strengths:")
    for s in results.get("strengths", []):
        print(f"- {s}")

    print("\nKey Challenges:")
    for c in results.get("challenges", []):
        print(f"- {c}")

    print("\nSummary:")
    print(results.get("summary", "No summary returned"))
