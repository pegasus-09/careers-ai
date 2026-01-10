from ingestion import utils


# Traits are characteristics that the user possesses
class Traits:
    TRAIT_TYPES = [
        "analytical",
        "creative",
        "social",
        "leadership",
        "detail_oriented",
        "adaptability"
    ]

    def __init__(self, scores=None):
        self.scores = {trait: 0.0 for trait in self.TRAIT_TYPES}

        if scores:
            for trait, value in scores.items():
                if trait not in self.scores:
                    raise ValueError(f"Invalid trait: {trait}")
                self.scores[trait] = utils.clamp(value)

    def set(self, trait, value):
        if trait not in self.scores:
            raise ValueError(f"Invalid trait: {trait}")

        self.scores[trait] = utils.clamp(value)


# Interests are what the user is drawn to
'''
technology: Enjoyment of computing, systems, tools, digital problem-solving
science: Curiosity about how things work, experimentation, theory, research
business: Interest in strategy, money, management, entrepreneurship
arts: Creative expression, design, storytelling, aesthetics
social_impact: Helping others, community work, social good, education, healthcare
hands_on: Preference for building, fixing, physical or practical work
'''

class Interests:
    INTEREST_TYPES = [
        "technology",
        "science",
        "business",
        "arts",
        "social_impact",
        "hands_on"
    ]

    def __init__(self, scores=None):
        self.scores = {interest: 0.0 for interest in self.INTEREST_TYPES}

        if scores:
            for interest, value in scores.items():
                if interest not in self.scores:
                    raise ValueError(f"Invalid interest: {interest}")
                self.scores[interest] = utils.clamp(value)

    def set(self, interest, value):
        if interest not in self.scores:
            raise ValueError(f"Invalid interest: {interest}")

        self.scores[interest] = utils.clamp(value)


# Aptitudes are what the user is actually good at
class Aptitudes:
    APTITUDE_TYPES = [
        "numerical_reasoning",
        "verbal_reasoning",
        "spatial_reasoning",
        "logical_reasoning",
        "memory"
    ]

    def __init__(self, scores=None):
        self.scores = {aptitude: 0.0 for aptitude in self.APTITUDE_TYPES}

        if scores:
            for aptitude, value in scores.items():
                if aptitude not in self.scores:
                    raise ValueError(f"Invalid aptitude: {aptitude}")
                self.scores[aptitude] = utils.clamp(value)

    def set(self, aptitude, value):
        if aptitude not in self.scores:
            raise ValueError(f"Invalid aptitude: {aptitude}")

        self.scores[aptitude] = utils.clamp(value)


# Values are what the user cares about in the long-term
class Values:
    VALUE_TYPES = [
        "stability",
        "financial_security",
        "prestige",
        "autonomy",
        "helping_others",
        "work_life_balance"
    ]

    def __init__(self, scores=None):
        self.scores = {val: 0.0 for val in self.VALUE_TYPES}

        if scores:
            for val, value in scores.items():
                if val not in self.scores:
                    raise ValueError(f"Invalid value: {val}")
                self.scores[val] = utils.clamp(value)

    def set(self, type_value, value):
        if type_value not in self.scores:
            raise ValueError(f"Invalid value: {value}")

        self.scores[type_value] = utils.clamp(value)


# The work style is the type of environment the user ENJOYS working in
class WorkStyles:
    WORK_STYLE_TYPES = [
        "team_based",
        "structure",
        "pace",
        "ambiguity_tolerance"
    ]

    def __init__(self, scores=None):
        self.scores = {work_style: 0.0 for work_style in self.WORK_STYLE_TYPES}

        if scores:
            for work_style, value in scores.items():
                if work_style not in self.scores:
                    raise ValueError(f"Invalid work_style: {work_style}")
                self.scores[work_style] = utils.clamp(value)

    def set(self, work_style, value):
        if work_style not in self.scores:
            raise ValueError(f"Invalid value: {value}")

        self.scores[work_style] = utils.clamp(value)
