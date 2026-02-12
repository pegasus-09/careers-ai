"""
Follow-up question generator for ambiguous assessment profiles.

When a student's assessment has low differentiation (flat/identical scores),
this module generates targeted follow-up questions via Groq to tease out
genuine preferences before the full analysis runs.
"""
from typing import Dict

from ai.llm_client import analyse
from ai.analysis_engine import format_scores


SYSTEM_PROMPT = """You are an expert career guidance counsellor for Australian high school students.

A student has just completed a psychometric assessment, but their answers lack differentiation — the scores are too flat or uniform to produce meaningful career guidance. Your job is to generate targeted follow-up questions that will reveal their genuine preferences, strengths, and interests.

RULES:
1. Generate EXACTLY {question_count} follow-up questions.
2. Each question must target the specific ambiguity in the student's profile.
3. Use scenario-based or forced-choice formats — NOT generic "what do you like?" questions.
4. Questions should feel natural and engaging for a teenager, not clinical or academic.
5. Use Australian English (organisation, behaviour, colour, maths, uni).
6. Each question must have a clear "targets" field listing which assessment dimensions it helps disambiguate.
7. Mix question types: "choice" (pick one of 2-4 options), "scale" (1-5 rating), or "scenario" (pick one of 2-3 scenarios).

Respond with EXACTLY this JSON structure:
{{
  "questions": [
    {{
      "id": "FU1",
      "text": "The question text",
      "type": "choice",
      "options": ["Option A", "Option B", "Option C"],
      "targets": ["I1", "I3", "T4"]
    }}
  ]
}}

QUESTION TYPE RULES:
- "choice": 2-4 mutually exclusive options. Best for forced-choice preference detection.
- "scale": No options needed (frontend renders 1-5). Best for intensity/confidence questions.
- "scenario": 2-3 scenario descriptions. Best for revealing behavioural preferences.

Make questions progressively more specific. Start broad ("hands-on vs. analytical") then narrow in on the specific gaps in differentiation."""


async def generate_follow_up_questions(
    answers: Dict[str, int],
    quality: dict,
) -> list[dict]:
    """
    Generate follow-up questions for an ambiguous assessment profile.

    Args:
        answers: The student's 27 assessment answers {question_id: 1-5}
        quality: Quality check result from check_assessment_quality()

    Returns:
        List of question dicts with keys: id, text, type, options, targets.
        Returns empty list on failure (graceful degradation).
    """
    confidence = quality.get("confidence", "high")

    # Determine question count based on confidence level
    if confidence == "low":
        question_count = 5
    elif confidence == "medium":
        question_count = 3
    else:
        return []  # High confidence → no follow-up needed

    scores_text = format_scores(answers)
    flags_text = ", ".join(quality.get("flags", []))

    system = SYSTEM_PROMPT.format(question_count=question_count)

    user_prompt = f"""## STUDENT ASSESSMENT PROFILE

Quality: {confidence} confidence
Flags: {flags_text}
Straight-line ratio: {quality.get('straight_line_ratio', 0)}
Variance: {quality.get('variance', 0)}

Scores:
{scores_text}

Generate {question_count} targeted follow-up questions to disambiguate this student's profile. Focus on the dimensions where scores are most uniform or uninformative."""

    try:
        result = await analyse(
            system_prompt=system,
            user_prompt=user_prompt,
        )

        if "error" in result:
            print(f"[FollowUp] Groq error: {result['error']}")
            return []

        questions = result.get("questions", [])

        # Validate shape
        validated = []
        for i, q in enumerate(questions):
            if not isinstance(q, dict):
                continue
            if not q.get("text"):
                continue
            validated.append({
                "id": q.get("id", f"FU{i+1}"),
                "text": q["text"],
                "type": q.get("type", "choice"),
                "options": q.get("options", []),
                "targets": q.get("targets", []),
            })

        return validated[:question_count]

    except Exception as e:
        print(f"[FollowUp] Exception generating follow-up questions: {e}")
        return []
