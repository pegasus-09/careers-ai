import os
from typing import Dict, Any, List
import json

from openai import OpenAI

client = OpenAI(api_key="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")


class ExplanationEngine:
    """
    End-to-end explanation engine.

    Responsibilities:
    - Build a grounded explanation input from engine outputs
    - Explain what the system measures and why a result occurred
    - Use GPT-4o-mini strictly for language generation
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def explain_career(
        self,
        user_profile: Dict[str, Dict[str, float]],
        career_meta: Dict[str, str],
        scores
    ) -> str:
        """
        Generate a human-readable explanation for a single career result.

        All inputs are assumed to be deterministic outputs
        from the core engine.
        """

        explanation_input = self._build_explanation_input(
            user_profile=user_profile,
            career_meta=career_meta,
            scores=scores,
        )

        prompt = self._build_prompt(explanation_input)
        return self._call_llm(prompt)

    # --------------------------------------------------
    # Explanation input construction
    # --------------------------------------------------

    def _build_explanation_input( # noqa
        self,
        user_profile: Dict[str, Dict[str, float]],
        career_meta: Dict[str, str],
        scores,
    ) -> Dict[str, Any]:
        """
        Canonical explanation input.

        This is the ONLY place where engine outputs
        are translated into explanatory facts.
        """

        return {
            "career": {
                "soc": career_meta["soc"],
                "title": career_meta["title"],
            },
            "system_meaning": {
                "aptitudes": "What the user is capable of doing",
                "interests": "What the user is motivated to engage with",
                "traits": "How the user tends to behave while working",
                "values": "What the user wants to be rewarded with",
                "work_styles": "What kind of work environment the user prefers",
            },
            "scores": scores,
            "user_snapshot": user_profile,
        }

    # --------------------------------------------------
    # Prompt construction
    # --------------------------------------------------

    def _build_prompt(self, explanation_input: Dict[str, Any]) -> str: # noqa
        return f"""
You are an explanation engine for a career-matching system.

Your role is to explain what the result means and why it occurred.

Rules you must follow:
- Do NOT rescore or reinterpret the data.
- Do NOT give advice or recommendations.
- Do NOT compare this career to others.
- Do NOT judge the user.
- Do NOT use markdown or text-formatting such as bolding
- Do NOT mention raw numerical data
- Base every statement strictly on the provided data.

Explain clearly:
1. What this career tends to emphasize or demand.
2. How the user's aptitudes, interests, traits, values, and work styles interacted with it.
3. Where alignment contributed positively.
4. Where friction reduced the score.
5. Why the final score ended up where it did.

Assume the reader is intelligent but unfamiliar with the system.
Be neutral, explanatory, and precise.

Here is the factual data you must rely on:

{json.dumps(explanation_input, indent=2)}
""".strip()

    # --------------------------------------------------
    # OpenAI GPT-4o-mini call
    # --------------------------------------------------

    def _call_llm(self, prompt: str) -> str:
        response = client.chat.completions.create(
            model=self.model,
            messages=[ # noqa
                {
                    "role": "system",
                    "content": "You explain system outputs. You do not make decisions.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.3,
        )

        return response.choices[0].message.content


# if __name__ == "__main__":
#
#     # -----------------------------
#     # Sample user profile snapshot
#     # -----------------------------
#
#     user_profile_snapshot = {
#         "aptitudes": {
#             "numerical_reasoning": 0.78,
#             "verbal_reasoning": 0.64,
#             "spatial_reasoning": 0.41,
#             "logical_reasoning": 0.82,
#             "memory": 0.69,
#         },
#         "interests": {
#             "technology": 0.86,
#             "science": 0.72,
#             "business": 0.33,
#             "arts": 0.28,
#             "social_impact": 0.44,
#             "hands_on": 0.31,
#         },
#         "traits": {
#             "analytical": 0.81,
#             "creative": 0.47,
#             "social": 0.29,
#             "leadership": 0.22,
#             "detail_oriented": 0.74,
#             "adaptability": 0.38,
#         },
#         "values": {
#             "stability": 0.62,
#             "financial_security": 0.71,
#             "prestige": 0.26,
#             "autonomy": 0.68,
#             "helping_others": 0.41,
#             "work_life_balance": 0.77,
#         },
#         "work_styles": {
#             "team_based": 0.34,
#             "structure": 0.73,
#             "pace": 0.52,
#             "ambiguity_tolerance": 0.29,
#         },
#     }
#
#     # -----------------------------
#     # Career metadata
#     # -----------------------------
#
#     career_meta = {
#         "soc": "15-1251.00",
#         "title": "Software Developer",
#     }
#
#     # -----------------------------
#     # Deterministic engine outputs
#     # -----------------------------
#
#     component_scores = {
#         "aptitudes": 0.64,
#         "interests": 0.71,
#         "traits": -0.12,
#         "values": 0.19,
#         "work_styles": 0.06,
#     }
#
#     top_alignments = [
#         {
#             "component": "interests",
#             "dimension": "technology",
#             "value": 0.86,
#             "reason": "Strong interest in technology-heavy work",
#         },
#         {
#             "component": "aptitudes",
#             "dimension": "logical_reasoning",
#             "value": 0.82,
#             "reason": "High logical reasoning capacity aligns with problem-solving demands",
#         },
#     ]
#
#     top_frictions = [
#         {
#             "component": "traits",
#             "dimension": "leadership",
#             "value": 0.22,
#             "reason": "Role places some emphasis on leadership and initiative",
#         },
#         {
#             "component": "work_styles",
#             "dimension": "team_based",
#             "value": 0.34,
#             "reason": "Preference for independent work over collaborative environments",
#         },
#     ]
#
#     total_score = 1.48
#
#     # -----------------------------
#     # Run explanation engine
#     # -----------------------------
#
#     engine = ExplanationEngine()
#
#     explanation_text = engine.explain_career(
#         user_profile=user_profile_snapshot,
#         career_meta=career_meta,
#         component_scores=component_scores,
#         alignments=top_alignments,
#         frictions=top_frictions,
#         total_score=total_score,
#     )
#
#     print("\n--- Career Explanation ---\n")
#     print(explanation_text)
