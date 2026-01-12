from dataclasses import dataclass, field
from core.profile import PsychometricProfile


@dataclass
class UserProfile:
    """
    Wraps a PsychometricProfile with user-specific intent,
    preferences, and matching configuration.
    """

    psychometrics: PsychometricProfile

    # Optional, used during matching
    component_weights: dict[str, float] = field(default_factory=dict)
    preferences: dict[str, float] = field(default_factory=dict)
    constraints: dict[str, object] = field(default_factory=dict)
