from models.user_profile import UserProfile
from matching.engine import match_user_to_role
from ingestion.build_career_profiles import build_all_career_profiles
from scripts.sample import build_test_profile


def main():
    # Build careers from O*NET
    career_profiles = build_all_career_profiles()

    # Build a fake user
    user_psych = build_test_profile()
    user = UserProfile(psychometrics=user_psych)

    for soc in ["15-1251.00", "11-1011.00", "53-3033.00"]:
        role = career_profiles[soc]
        result = match_user_to_role(user, role)

        print(f"\nSOC {soc}")

        print(f"  aptitudes: {result['aptitudes']:.3f}")
        print(f"  interests: {result['interests']:.3f}")
        print(f"  traits: {result['traits']:.3f}")
        print(f"  values: {result['values']:.3f}")
        print(f"  work styles: {result['work_styles']:.3f}")

        print(f"AGGREGATE: {result['total']}")


if __name__ == "__main__":
    main()
