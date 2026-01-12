from core.career_components import Traits, Interests, Aptitudes, Values, WorkStyles


class PsychometricProfile:
    def __init__(self, aptitudes=Aptitudes(), interests=Interests(), traits=Traits(), values=Values(), work_styles=WorkStyles()):
        self.traits = traits
        self.interests = interests
        self.aptitudes = aptitudes
        self.values = values
        self.work_styles = work_styles

        self._trait_totals = {}
        self._trait_counts = {}

        self._interest_totals = {}
        self._interest_counts = {}

        self._aptitude_totals = {}
        self._aptitude_counts = {}

        self._value_totals = {}
        self._value_counts = {}

        self._work_style_totals = {}
        self._work_style_counts = {}

        self._total_answers = 0
        self.confidence = 0.0

    def _validate(self, answer):
        required_keys = {"question_type", "target", "answer"}

        if not required_keys.issubset(answer):
            raise ValueError(f"Invalid answer shape: {answer}")

        q_type = answer["question_type"]
        target = answer["target"]
        value = answer["answer"]

        if q_type not in ["trait", "interest", "aptitude", "value", "work_style"]:
            raise ValueError(f"Invalid question_type: {q_type}")

        if type(value) not in [int, float]:
            raise ValueError(f"Value must be numeric: {value}")

        # Checking targets
        if q_type == "trait" and target not in self.traits.scores:
            raise ValueError(f"Invalid trait target: {target}")

        if q_type == "interest" and target not in self.interests.scores:
            raise ValueError(f"Invalid interest target: {target}")

        if q_type == "aptitude" and target not in self.aptitudes.scores:
            raise ValueError(f"Invalid aptitude target: {target}")

        if q_type == "value" and target not in self.values.scores:
            raise ValueError(f"Invalid value target: {target}")

        if q_type == "work_style" and target not in self.work_styles.scores:
            raise ValueError(f"Invalid work_style target: {target}")


    def add_answer(self, answer):
        self._validate(answer)

        q_type = answer["question_type"]
        target = answer["target"]
        value = answer["answer"]

        if q_type == "trait": # Updates for each trait
            self._trait_totals[target] = self._trait_totals.get(target, 0) + value
            self._trait_counts[target] = self._trait_counts.get(target, 0) + 1

        elif q_type == "interest":
            self._interest_totals[target] = self._interest_totals.get(target, 0) + value
            self._interest_counts[target] = self._interest_counts.get(target, 0) + 1

        elif q_type == "aptitude":
            self._aptitude_totals[target] = self._aptitude_totals.get(target, 0) + value
            self._aptitude_counts[target] = self._aptitude_counts.get(target, 0) + 1

        elif q_type == "value":
            self._value_totals[target] = self._value_totals.get(target, 0) + value
            self._value_counts[target] = self._value_counts.get(target, 0) + 1

        elif q_type == "work_style":
            self._work_style_totals[target] = self._work_style_totals.get(target, 0) + value
            self._work_style_counts[target] = self._work_style_counts.get(target, 0) + 1

        self._total_answers += 1

    def finalise(self):
        for trait, total in self._trait_totals.items():
            avg = total / self._trait_counts[trait]
            self.traits.set(trait, avg)

        for interest, total in self._interest_totals.items():
            avg = total / self._interest_counts[interest]
            self.interests.set(interest, avg)

        for aptitude, total in self._aptitude_totals.items():
            avg = total / self._aptitude_counts[aptitude]
            self.aptitudes.set(aptitude, avg)

        for value, total in self._value_totals.items():
            avg = total / self._value_counts[value]
            self.values.set(value, avg)

        for work_style, total in self._work_style_totals.items():
            avg = total / self._work_style_counts[work_style]
            self.work_styles.set(work_style, avg)

        self.confidence = min(self._total_answers / 20, 1.0)

    def to_dict(self):
        return {"traits": self.traits.scores, "interests": self.interests.scores, "aptitudes": self.aptitudes.scores, "values": self.values.scores, "work_styles": self.work_styles.scores, "confidence": self.confidence}
