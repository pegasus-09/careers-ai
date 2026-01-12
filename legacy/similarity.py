from math import sqrt
from fixtures.archetype_profiles import CAREER_PROFILES
from scripts.sample import build_test_profile

"""
LEGACY PROTOTYPE

Early cosine-similarity matcher for hand-authored career archetypes.
Not used in the O*NET-based matching system.
Preserved for reference only.
"""

BASE_WEIGHTS = {
    "traits": 1.0,
    "interests": 1.0,
    "aptitudes": 1.0,
    "values": 1.0,
    "work_styles": 1.0
}

FEATURE_ORDER = {
    "traits": [
        "analytical",
        "creative",
        "social",
        "leadership",
        "detail_oriented",
        "adaptability"
    ],
    "interests": [
        "technology",
        "science",
        "business",
        "arts",
        "social_impact",
        "hands_on"
    ],
    "aptitudes": [
        "logical_reasoning",
        "numerical_reasoning",
        "verbal_reasoning",
        "spatial_reasoning",
        "memory"
    ],
    "values": [
        "autonomy",
        "stability",
        "financial_security",
        "prestige",
        "helping_others",
        "work_life_balance"
    ],
    "work_styles": [
        "team_based",
        "structure",
        "pace",
        "ambiguity_tolerance"
    ]
}


def cosine_similarity(vec_a, vec_b):
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sqrt(sum(a * a for a in vec_a))
    norm_b = sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def profile_to_vector(profile_dict, career_weights=None):
    vector = []

    for section, keys in FEATURE_ORDER.items():
        section_data = profile_dict[section]

        if hasattr(section_data, "scores"):
            scores = section_data.scores
        else:
            scores = section_data

        for key in keys:
            value = scores.get(key, 0.0)
            weight = 1.0

            if career_weights:
                weight = career_weights.get(f"{section}.{key}", 1.0)

            vector.append(value * weight)

    return vector


def select_cluster(user_profile):
    interests = user_profile.interests.scores

    if interests["arts"] >= interests["technology"]:
        return "creative_design"
    else:
        return "technology_engineering"


def filter_by_cluster(careers, cluster):
    return {
        name: career
        for name, career in careers.items()
        if career.get("cluster") == cluster
    }



def rank_careers(user_profile, careers=CAREER_PROFILES):
    scored = []

    for name, career in careers.items():
        career_weights = career.get("weights", {})

        user_vect = profile_to_vector(
            user_profile.to_dict(),
            career_weights
        )

        career_vect = profile_to_vector(
            career,
            career_weights
        )

        sim = cosine_similarity(user_vect, career_vect)
        scored.append((name, sim))

    return sorted(scored, key=lambda x: x[1], reverse=True)


sample_profile = build_test_profile()
selected_cluster = select_cluster(sample_profile)

filtered_careers = filter_by_cluster(
    CAREER_PROFILES,
    selected_cluster
)

results = rank_careers(sample_profile, filtered_careers)
print("Cluster:", selected_cluster)
print(results)
