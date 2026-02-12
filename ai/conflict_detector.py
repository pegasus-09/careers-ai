"""
Programmatic conflict detection between self-assessment scores and teacher observations.
No LLM calls — rule-based comparison so conflicts are reliably surfaced.
"""
from typing import Dict, List
import re


# Keywords that signal contradicting teacher observations
ENGAGEMENT_KEYWORDS = [
    "animated", "outgoing", "talkative", "leads discussions",
    "confident speaker", "speaks up", "vocal",
]

SOCIAL_KEYWORDS = [
    "collaborative", "helps others", "team player",
    "works well with peers", "supportive of classmates",
]

LEADERSHIP_KEYWORDS = [
    "takes charge", "leads", "delegates", "captain", "organises",
    "organizes", "initiative", "natural leader",
]

CONSCIENTIOUSNESS_KEYWORDS = [
    "meticulous", "organised", "organized", "thorough",
    "consistent", "diligent", "detail-oriented", "reliable",
]

# Which aptitude dimensions relate to which subjects
SUBJECT_APTITUDE_MAP = {
    "mathematics": ["A2"],
    "maths": ["A2"],
    "english": ["A1"],
    "science": ["A5", "A2"],
    "digital technologies": ["A5"],
    "industrial technology": ["A4", "A3"],
}


def _comment_text_lower(tc: dict) -> str:
    return (tc.get("comment_text") or "").lower()


def _has_keyword(text: str, keywords: list) -> str | None:
    """Return the first matching keyword found in text, or None."""
    for kw in keywords:
        if kw in text:
            return kw
    return None


def detect_conflicts(
    answers: Dict[str, int],
    teacher_comments: List[dict],
) -> List[dict]:
    """
    Detect contradictions between low self-assessment scores and
    high teacher observations (or vice versa).

    Returns list of conflict dicts with type, description, and evidence.
    """
    conflicts: List[dict] = []
    if not teacher_comments:
        return conflicts

    extraversion = answers.get("T5", 3)
    social = answers.get("I4", 3)
    leadership = answers.get("W2", 3)
    conscientiousness = answers.get("T1", 3)

    for tc in teacher_comments:
        text = _comment_text_lower(tc)
        teacher = tc.get("teacher_name", "A teacher")
        subject = tc.get("subject_name", "Unknown")
        engagement = tc.get("engagement_rating") or 0
        performance = tc.get("performance_rating") or 0

        # Extraversion vs engagement
        if extraversion <= 2:
            kw = _has_keyword(text, ENGAGEMENT_KEYWORDS)
            if engagement >= 4 or kw:
                evidence = {"self_score": extraversion, "teacher": teacher, "subject": subject}
                if kw:
                    evidence["keyword"] = kw
                if engagement >= 4:
                    evidence["engagement_rating"] = engagement
                conflicts.append({
                    "type": "extraversion_engagement",
                    "description": (
                        f"Student self-assessed Extraversion at {extraversion}/5, "
                        f"but {teacher} rated engagement {engagement}/5"
                        + (f" and noted behaviour suggesting extroversion (\"{kw}\")" if kw else "")
                        + ". Is the student more outgoing than they think, or is this context-dependent?"
                    ),
                    "evidence": evidence,
                })

        # Social interest vs observed social behaviour
        if social <= 2:
            kw = _has_keyword(text, SOCIAL_KEYWORDS)
            if engagement >= 4 or kw:
                evidence = {"self_score": social, "teacher": teacher, "subject": subject}
                if kw:
                    evidence["keyword"] = kw
                if engagement >= 4:
                    evidence["engagement_rating"] = engagement
                conflicts.append({
                    "type": "social_behaviour",
                    "description": (
                        f"Student self-assessed Social interest at {social}/5, "
                        f"but {teacher} observed social behaviour"
                        + (f" (\"{kw}\")" if kw else "")
                        + ". Low self-rated social interest vs. observed social engagement."
                    ),
                    "evidence": evidence,
                })

        # Leadership gap
        if leadership <= 2:
            kw = _has_keyword(text, LEADERSHIP_KEYWORDS)
            if kw:
                conflicts.append({
                    "type": "leadership_gap",
                    "description": (
                        f"Student self-assessed Leadership at {leadership}/5, "
                        f"but {teacher} noted \"{kw}\". "
                        "The student may underestimate their leadership ability."
                    ),
                    "evidence": {"self_score": leadership, "teacher": teacher, "keyword": kw},
                })

        # Conscientiousness vs performance
        if conscientiousness <= 2:
            kw = _has_keyword(text, CONSCIENTIOUSNESS_KEYWORDS)
            if performance >= 4 or kw:
                evidence = {"self_score": conscientiousness, "teacher": teacher, "subject": subject}
                if kw:
                    evidence["keyword"] = kw
                if performance >= 4:
                    evidence["performance_rating"] = performance
                conflicts.append({
                    "type": "conscientiousness_performance",
                    "description": (
                        f"Student self-assessed Conscientiousness at {conscientiousness}/5, "
                        f"but {teacher} rated performance {performance}/5"
                        + (f" and described them as \"{kw}\"" if kw else "")
                        + ". Low self-reported discipline vs. observed diligence."
                    ),
                    "evidence": evidence,
                })

        # Aptitude conflicts (hidden talent or overrating)
        subj_lower = (tc.get("subject_name") or "").lower()
        for subj_key, aptitude_codes in SUBJECT_APTITUDE_MAP.items():
            if subj_key in subj_lower:
                for code in aptitude_codes:
                    score = answers.get(code, 3)
                    # Hidden talent: low self-assessment, high teacher rating
                    if score <= 2 and performance >= 4:
                        conflicts.append({
                            "type": "hidden_talent",
                            "description": (
                                f"Student self-assessed {code} at {score}/5, "
                                f"but {teacher} rated performance {performance}/5 in {subject}. "
                                "Possible hidden talent — the student may be underestimating themselves."
                            ),
                            "evidence": {
                                "dimension": code, "self_score": score,
                                "performance_rating": performance,
                                "teacher": teacher, "subject": subject,
                            },
                        })
                    # Overrating: high self-assessment, low teacher rating
                    elif score >= 4 and performance <= 2:
                        conflicts.append({
                            "type": "overrating",
                            "description": (
                                f"Student self-assessed {code} at {score}/5, "
                                f"but {teacher} rated performance only {performance}/5 in {subject}. "
                                "The student's confidence may exceed current ability in this area."
                            ),
                            "evidence": {
                                "dimension": code, "self_score": score,
                                "performance_rating": performance,
                                "teacher": teacher, "subject": subject,
                            },
                        })

    # Deduplicate by type (keep first instance of each type)
    seen_types: set = set()
    unique: List[dict] = []
    for c in conflicts:
        if c["type"] not in seen_types:
            seen_types.add(c["type"])
            unique.append(c)

    return unique
