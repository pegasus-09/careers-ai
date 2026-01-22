from models.profile import PsychometricProfile
from scripts.rank_all_careers import rank_profiles
from ingestion.read_occupation_data import load_soc_title_mapping
from scripts.test import build_components
from typing import Dict

def run_assessment(answers: Dict[str, int]):
    aptitudes, interests, traits, values, work_styles = build_components(answers)
    user_profile = PsychometricProfile(
        aptitudes,
        interests,
        traits,
        values,
        work_styles,
    )

    data, ranking = rank_profiles(user_profile)
    return ranking
