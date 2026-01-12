from models.career_components import Traits, Interests, Aptitudes, Values, WorkStyles

"""
Hand-authored archetype profiles for testing and UI prototyping.
Not part of the O*NET-derived career pipeline.
"""


CAREER_PROFILES = {
    "software_developer": {
        "cluster": "technology_engineering",
        "weights": {
            "interests.technology": 2.5,
            "aptitudes.logical_reasoning": 2.0,
            "aptitudes.numerical_reasoning": 1.5,
            "traits.creative": 0.8
        },
        "traits": Traits({
            "analytical": 0.85,
            "creative": 0.45,
            "social": 0.35,
            "leadership": 0.40,
            "detail_oriented": 0.80,
            "adaptability": 0.65
        }),
        "interests": Interests({
            "technology": 0.90,
            "science": 0.70,
            "business": 0.35,
            "arts": 0.20,
            "social_impact": 0.40,
            "hands_on": 0.45
        }),
        "aptitudes": Aptitudes({
            "logical_reasoning": 0.88,
            "numerical_reasoning": 0.75,
            "verbal_reasoning": 0.55,
            "spatial_reasoning": 0.40,
            "memory": 0.65
        }),
        "values": Values({
            "autonomy": 0.65,
            "stability": 0.55,
            "financial_security": 0.60,
            "prestige": 0.40,
            "helping_others": 0.35,
            "work_life_balance": 0.60
        }),
        "work_styles": WorkStyles({
            "team_based": 0.55,
            "structure": 0.40,
            "pace": 0.65,
            "ambiguity_tolerance": 0.75
        })
    },

    "graphic_designer": {
        "cluster": "creative_design",
        "weights": {
            "traits.creative": 2.5,
            "interests.arts": 2.5,
            "aptitudes.spatial_reasoning": 2.0,
            "interests.technology": 0.6
        },
        "traits": Traits({
            "analytical": 0.45,
            "creative": 0.90,
            "social": 0.50,
            "leadership": 0.35,
            "detail_oriented": 0.65,
            "adaptability": 0.70
        }),
        "interests": Interests({
            "technology": 0.50,
            "science": 0.30,
            "business": 0.40,
            "arts": 0.90,
            "social_impact": 0.45,
            "hands_on": 0.60
        }),
        "aptitudes": Aptitudes({
            "logical_reasoning": 0.50,
            "numerical_reasoning": 0.40,
            "verbal_reasoning": 0.65,
            "spatial_reasoning": 0.85,
            "memory": 0.60
        }),
        "values": Values({
            "autonomy": 0.75,
            "stability": 0.45,
            "financial_security": 0.45,
            "prestige": 0.35,
            "helping_others": 0.40,
            "work_life_balance": 0.65
        }),
        "work_styles": WorkStyles({
            "team_based": 0.50,
            "structure": 0.35,
            "pace": 0.60,
            "ambiguity_tolerance": 0.80
        })
    }
}
