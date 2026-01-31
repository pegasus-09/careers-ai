from models.profile import PsychometricProfile
from scripts.rank_all_careers import rank_profiles
from ingestion.read_occupation_data import load_soc_title_mapping
from scripts.test import build_profile_from_ans
from typing import Dict

def run_assessment(answers: Dict[str, int]):
    user_profile = build_profile_from_ans(answers)
    data, ranking = rank_profiles(user_profile)
    return ranking
