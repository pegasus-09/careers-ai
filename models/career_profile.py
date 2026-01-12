from dataclasses import dataclass
from models.career_components import (
    Aptitudes,
    Interests,
    Traits,
    Values,
    WorkStyles,
)

@dataclass(frozen=True)
class CareerProfile:
    """
    Container for all career-side components for a single SOC.
    No logic. No scoring.
    """

    soc_code: str

    aptitudes: Aptitudes
    interests: Interests
    traits: Traits
    values: Values
    work_styles: WorkStyles
