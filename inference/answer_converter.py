from typing import Dict, List
from statistics import mean

from models.profile import PsychometricProfile
from models.career_components import Traits, Interests, Aptitudes, Values, WorkStyles
from ingestion.utils import clamp

LIKERT_5_MAP = {
    1: 0.0,
    2: 0.25,
    3: 0.5,
    4: 0.75,
    5: 1.0
}

# Question ID to (component, dimension) mapping
QUESTION_MAPPING = {
    "A1": ("aptitudes", "numerical_reasoning"),
    "A2": ("aptitudes", "verbal_reasoning"),
    "A3": ("aptitudes", "spatial_reasoning"),
    "A4": ("aptitudes", "logical_reasoning"),
    "A5": ("aptitudes", "memory"),
    "I1": ("interests", "technology"),
    "I2": ("interests", "science"),
    "I3": ("interests", "business"),
    "I4": ("interests", "arts"),
    "I5": ("interests", "social_impact"),
    "I6": ("interests", "hands_on"),
    "T1": ("traits", "analytical"),
    "T2": ("traits", "creative"),
    "T3": ("traits", "social"),
    "T4": ("traits", "leadership"),
    "T5": ("traits", "detail_oriented"),
    "T6": ("traits", "adaptability"),
    "V1": ("values", "stability"),
    "V2": ("values", "financial_security"),
    "V3": ("values", "prestige"),
    "V4": ("values", "autonomy"),
    "V5": ("values", "helping_others"),
    "V6": ("values", "work_life_balance"),
    "W1": ("work_styles", "team_based"),
    "W2": ("work_styles", "structure"),
    "W3": ("work_styles", "pace"),
    "W4": ("work_styles", "ambiguity_tolerance"),
}


def convert_answers_to_profile(answers: Dict[str, int]) -> PsychometricProfile:
    """
    Convert raw quiz answers (1-5 scale) to a PsychometricProfile.
    """
    buckets: Dict[str, Dict[str, List[int]]] = {
        "aptitudes": {},
        "interests": {},
        "traits": {},
        "values": {},
        "work_styles": {},
    }

    for qid, raw_value in answers.items():
        if qid not in QUESTION_MAPPING:
            continue
        component, dimension = QUESTION_MAPPING[qid]
        buckets[component].setdefault(dimension, []).append(raw_value)

    def avg_normalized(d: Dict[str, List[int]]) -> Dict[str, float]:
        return {
            k: clamp(mean(v) / 5)
            for k, v in d.items()
        }

    return PsychometricProfile(
        Aptitudes(avg_normalized(buckets["aptitudes"])),
        Interests(avg_normalized(buckets["interests"])),
        Traits(avg_normalized(buckets["traits"])),
        Values(avg_normalized(buckets["values"])),
        WorkStyles(avg_normalized(buckets["work_styles"])),
    )
