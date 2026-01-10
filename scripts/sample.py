from inference.ai_interpreter import interpret_profile
from core.career_components import Traits, Interests, Aptitudes, Values, WorkStyles
from core.profile import PsychometricProfile


sample_profile = PsychometricProfile(
    traits=Traits({
        "analytical": 0.85,
        "creative": 0.40,
        "social": 0.30,
        "leadership": 0.35,
        "detail_oriented": 0.80,
        "adaptability": 0.45
    }),
    interests=Interests({
        "technology": 0.85,
        "science": 0.70,
        "business": 0.40,
        "arts": 0.20,
        "social_impact": 0.30,
        "hands_on": 0.50
    }),
    aptitudes=Aptitudes({
        "numerical_reasoning": 0.80,
        "verbal_reasoning": 0.55,
        "spatial_reasoning": 0.45,
        "logical_reasoning": 0.85,
        "memory": 0.65
    }),
    values=Values({
        "stability": 0.55,
        "financial_security": 0.60,
        "prestige": 0.40,
        "autonomy": 0.50,
        "helping_others": 0.30,
        "work_life_balance": 0.45
    }),
    work_styles=WorkStyles({
        "team_based": 0.40,
        "structure": 0.70,
        "pace": 0.60,
        "ambiguity_tolerance": 0.35
    })
)
sample_profile.confidence = 0.65



if __name__ == '__main__':
    # Optional sanity check
    results = interpret_profile(sample_profile)
    print(f"Strengths: \n{'\n'.join(results['strengths'])}\n")
    print(f"Challenges: \n{'\n'.join(results['challenges'])}\n")
    print(f"Summary: \n{results['summary']}\n")
