from models.user_profile import UserProfile
from ingestion.build_career_profiles import build_all_career_profiles
from matching.engine import match_user_to_role


def rank_profiles(user_profile):
    user = UserProfile(psychometrics=user_profile)

    # Build all career profiles
    career_profiles = build_all_career_profiles()

    results = {}
    rank_list = {}

    for soc_code, career in career_profiles.items():
        scores = match_user_to_role(user, career)
        results[soc_code] = scores
        rank_list[soc_code] = scores['total']

    # Sort by aggregate score (descending)
    # results.sort(key=lambda x: x[1], reverse=True)
    rank_list = (sorted(rank_list.items(), key=lambda item: item[1], reverse=True))
    return results, rank_list


def main():
    # Build user profile
    results, ranks = rank_profiles()
    print(ranks)

    # Print ranked results
    print("\n===== CAREER RANKINGS =====\n")

    for rank, (soc, total, scores) in enumerate(results, start=1):
        print(f"{rank:3d}. SOC {soc}  |  TOTAL: {total:.3f}")
        print(
            f"     aptitudes:   {scores['aptitudes']:.3f}\n"
            f"     interests:   {scores['interests']:.3f}\n"
            f"     traits:      {scores['traits']:.3f}\n"
            f"     values:      {scores['values']:.3f}\n"
            f"     work_styles: {scores['work_styles']:.3f}\n"
        )
