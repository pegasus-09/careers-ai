from models.user_profile import UserProfile
from ingestion.build_career_profiles import build_all_career_profiles
from ingestion.read_occupation_data import load_soc_title_mapping
from matching.engine import match_user_to_role

def rank_profiles(user_profile):
    user = UserProfile(psychometrics=user_profile)

    # Build all career profiles
    career_profiles = build_all_career_profiles()

    socs = load_soc_title_mapping()

    results = {}
    rank_list = []

    for soc_code, career in career_profiles.items():
        scores = match_user_to_role(user, career)
        results[soc_code] = scores
        rank_list.append((soc_code, socs.get(soc_code), scores['total']))

    # Sort by aggregate score (descending)
    # results.sort(key=lambda x: x[1], reverse=True)
    rank_list.sort(key=lambda x: x[2], reverse=True)
    return results, rank_list
