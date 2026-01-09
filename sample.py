from ai_interpreter import interpret_profile
from career_components import Traits, Interests, Aptitudes, Values, WorkStyles
from profile import PsychometricProfile

if __name__ == '__main__':
    # -------------------------
    # Sample Traits
    # -------------------------
    traits = Traits()
    traits.scores = {
        "analytical": 0.78,
        "creative": 0.52,
        "social": 0.41,
        "leadership": 0.47,
        "detail_oriented": 0.83,
        "adaptability": 0.66
    }

    # -------------------------
    # Sample Interests
    # -------------------------
    interests = Interests()
    interests.scores = {
        "technology": 0.81,
        "science": 0.74,
        "business": 0.38,
        "arts": 0.29,
        "social_impact": 0.45,
        "hands_on": 0.34
    }

    # -------------------------
    # Sample Aptitudes
    # -------------------------
    aptitudes = Aptitudes()
    aptitudes.scores = {
        "numerical_reasoning": 0.86,
        "verbal_reasoning": 0.62,
        "spatial_reasoning": 0.55,
        "logical_reasoning": 0.88,
        "memory": 0.71
    }

    # -------------------------
    # Sample Values
    # -------------------------
    values = Values()
    values.scores = {
        "stability": 0.42,
        "financial_security": 0.58,
        "prestige": 0.31,
        "autonomy": 0.79,
        "helping_others": 0.46,
        "work_life_balance": 0.67
    }

    # -------------------------
    # Sample Work Styles
    # -------------------------
    work_styles = WorkStyles()
    work_styles.scores = {
        "team_based": 0.44,
        "structure": 0.33,
        "pace": 0.71,
        "ambiguity_tolerance": 0.76
    }

    # -------------------------
    # Final Psychometric Profile
    # -------------------------
    profile = PsychometricProfile(
        traits=traits,
        interests=interests,
        aptitudes=aptitudes,
        values=values,
        work_styles=work_styles
    )

    profile.confidence = 0.65

    # Optional sanity check
    results = interpret_profile(profile)
    print(f"Strengths: \n{'\n'.join(results['strengths'])}\n")
    print(f"Challenges: \n{'\n'.join(results['challenges'])}\n")
    print(f"Summary: \n{results['summary']}\n")
