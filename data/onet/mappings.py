"""
O*NET → Internal Schema Mappings (LITERAL)

Rules:
- Ingest literally, derive later
- No cross-component mapping
- No abstractions (pace, autonomy, ambiguity, etc.)
- No aggregation logic here

This file ONLY declares:
- which O*NET elements map
- to which INTERNAL component
"""


# ======================================================
# ABILITIES → APTITUDES
# Source: Abilities.txt
# Scales: LV (Level), IM (Importance)
# Raw scale: 0–7
# ======================================================

ABILITY_MAP = {
    # Logical reasoning
    "Deductive Reasoning": ("logical_reasoning", 1.0),
    "Inductive Reasoning": ("logical_reasoning", 1.0),

    # Numerical reasoning
    "Number Facility": ("numerical_reasoning", 1.0),
    "Mathematical Reasoning": ("numerical_reasoning", 0.9),

    # Verbal reasoning
    "Verbal Reasoning": ("verbal_reasoning", 1.0),
    "Written Comprehension": ("verbal_reasoning", 0.8),
    "Oral Comprehension": ("verbal_reasoning", 0.8),

    # Spatial reasoning
    "Spatial Orientation": ("spatial_reasoning", 1.0),
    "Visualization": ("spatial_reasoning", 0.9),

    # Memory
    "Memorization": ("memory", 1.0),
}


# ======================================================
# INTERESTS (RIASEC) → INTERESTS
# Source: Interests.txt
# Scale: OI (Occupational Interest) ONLY
# Raw scale: 0–7
# ======================================================

INTEREST_MAP = {
    "Realistic": ("hands_on", 1.0),
    "Investigative": ("science", 1.0),
    "Artistic": ("arts", 1.0),
    "Social": ("social_impact", 1.0),
    "Enterprising": ("business", 1.0),
    # Conventional intentionally omitted (handled later via derived styles)
}


# ======================================================
# WORK STYLES → TRAITS (LITERAL)
# Source: Work Styles.txt
# Scale: IM (Importance)
# Raw scale: 0–100
# ======================================================

# ======================================================
# WORK STYLES → TRAITS (REAL O*NET NAMES)
# Source: Work Styles.txt
# Scale: WI (Impact)  [-3 → +3], normalize /3
# ======================================================

WORK_STYLE_MAP = {
    # Analytical / thinking orientation
    "Intellectual Curiosity": ("analytical", 1.0),

    # Creativity / novelty
    "Innovation": ("creative", 1.0),
    "Optimism": ("creative", 0.5),

    # Precision / reliability
    "Attention to Detail": ("detail_oriented", 1.0),
    "Cautiousness": ("detail_oriented", 0.7),
    "Dependability": ("detail_oriented", 0.6),

    # Social orientation
    "Cooperation": ("social", 1.0),
    "Empathy": ("social", 0.9),
    "Social Orientation": ("social", 1.0),
    "Sincerity": ("social", 0.6),
    "Humility": ("social", 0.5),

    # Leadership / drive
    "Leadership Orientation": ("leadership", 1.0),
    "Initiative": ("leadership", 0.8),
    "Achievement Orientation": ("leadership", 0.7),
    "Self-Confidence": ("leadership", 0.6),

    # Flexibility / adaptability
    "Adaptability": ("adaptability", 1.0),
    "Tolerance for Ambiguity": ("adaptability", 1.0),
    "Stress Tolerance": ("adaptability", 0.8),
}


# ======================================================
# WORK ACTIVITIES → TRAITS (LITERAL)
# Source: Work Activities.txt
# Scale: IM (Importance)
# Raw scale: 0–100
# ======================================================

WORK_ACTIVITY_MAP = {
    "Analyzing Data or Information": ("analytical", 1.0),
    "Thinking Creatively": ("creative", 1.0),
    "Interacting With Computers": ("technical_interaction", 1.0),
    "Communicating with Supervisors, Peers, or Subordinates": ("communication", 1.0),
    "Guiding, Directing, and Motivating Subordinates": ("leadership", 1.0),
}
