"""
AI Analysis Engine — the core of LaunchPad's career guidance system.

Single comprehensive prompt approach: sends ALL evidence to Llama 3.3 70B
(via Groq) in one call and gets back the complete analysis as structured JSON.

This replaces the old multi-step pipeline (comment_analyser → signal_aggregator
→ strength_gap → explainer). The AI reads everything holistically, like a real
career counsellor would.
"""
from typing import Dict, List

from ai.llm_client import analyse
from ai.quality_check import check_assessment_quality
from ai.conflict_detector import detect_conflicts
from ai.career_suggestor import suggest_careers_from_comments

# ── Dimension labels for human-readable formatting ──────────────────

DIMENSION_LABELS = {
    "A1": "Verbal Reasoning", "A2": "Numerical Reasoning", "A3": "Spatial Awareness",
    "A4": "Mechanical Reasoning", "A5": "Abstract Thinking",
    "I1": "Realistic", "I2": "Investigative", "I3": "Artistic",
    "I4": "Social", "I5": "Enterprising", "I6": "Conventional",
    "T1": "Conscientiousness", "T2": "Emotional Stability", "T3": "Agreeableness",
    "T4": "Openness", "T5": "Extraversion", "T6": "Resilience",
    "V1": "Achievement", "V2": "Independence", "V3": "Recognition",
    "V4": "Relationships", "V5": "Support", "V6": "Working Conditions",
    "W1": "Attention to Detail", "W2": "Leadership", "W3": "Cooperation", "W4": "Innovation",
}

CATEGORIES = {
    "Aptitudes": ["A1", "A2", "A3", "A4", "A5"],
    "Interests": ["I1", "I2", "I3", "I4", "I5", "I6"],
    "Traits": ["T1", "T2", "T3", "T4", "T5", "T6"],
    "Values": ["V1", "V2", "V3", "V4", "V5", "V6"],
    "Work Styles": ["W1", "W2", "W3", "W4"],
}

# ── System prompt ───────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert career guidance counsellor for Australian high school students (Years 9-12). You are analysing a student's psychometric assessment results alongside their teachers' observations to produce a comprehensive, personalised career analysis.

Your job is to act as a co-ranker: you receive a shortlist of 20 career candidates from a deterministic matching algorithm, plus teacher comments and subject data. You must produce a FINAL ranking of exactly 5 careers, along with detailed analysis.

CRITICAL RULES:
1. You CAN reorder the 20 candidates based on teacher evidence.
2. You CAN inject a career NOT in the top 20 if teacher comments provide strong evidence for it. If you do this, you MUST explain why.
3. You MUST dynamically weight data sources based on quality:
   - If assessment quality is low but teacher comments are rich → weight teachers heavily
   - If no teacher comments → rely on assessment, note lower confidence
   - If they conflict → flag the conflict explicitly and explain your reasoning
4. Every claim in your analysis MUST reference specific evidence. Not "You show strong analytical skills" but "Your Maths teacher Mrs Patterson noted you 'pick up new concepts quickly, particularly in statistics', and your own answers show you're really confident with numbers too." Always ground claims in teacher quotes, subject grades, or specific observations — but express them naturally, never with scores or dimension names.
5. Use Australian English exclusively: analyse not analyze, behaviour not behavior, organisation not organization, colour not color, maths not math, uni not university, Year 10 not 10th grade, programme not program. Address the student as "you". Be warm, encouraging, and specific. Frame gaps as growth opportunities.
6. NEVER use technical jargon, psychometric terminology, or academic language in summaries, explanations, or narratives. Write as if you're a friendly, approachable careers adviser talking to a teenager face-to-face. Say "you're great with numbers" not "you demonstrate strong numerical reasoning aptitude." Say "you like figuring out how things work" not "you score highly on the Investigative dimension." Say "your teachers noticed you take charge in group work" not "teacher observations corroborate high Enterprising/Leadership scores." The student should NEVER see dimension codes (A1, I2, T5 etc.), scale references (4/5, 0.8 normalised), or statistical terms. Keep it natural, conversational, and human.
7. Be honest. If the data is ambiguous or contradictory, say so.
8. CONFLICTS: When the "PRE-DETECTED CONFLICTS" section lists conflicts, you MUST include ALL of them in your "conflicts" array. For each, provide your interpretation — don't just say "they disagree", explain WHY this might be (e.g., the student behaves differently in different subjects, or their self-perception doesn't match reality). If you detect additional conflicts beyond those listed, include them too.
9. CAREER INJECTION: When the "CAREER CANDIDATES FROM TEACHER EVIDENCE" section lists careers, seriously consider including at least one in your final_ranking if the teacher evidence is compelling. Set "from_deterministic_top20" to false for injected careers. You don't HAVE to inject — but you must explain why you chose not to if you skip a suggestion with strong evidence.

You MUST respond with EXACTLY this JSON structure — no extra keys, no missing keys:
{
  "career_explanations": {
    "<soc_code>": {
      "title": "Career Title",
      "score": 2.15,
      "rank": 1,
      "explanation": "2-3 sentence explanation referencing specific evidence for why this career suits the student."
    }
  },
  "final_ranking": [
    {
      "rank": 1,
      "career_name": "Career Title",
      "soc_code": "XX-XXXX.XX",
      "from_deterministic_top20": true,
      "original_position": 3,
      "reasoning": "Why this career was ranked here.",
      "key_evidence": ["Quote or data point 1", "Quote or data point 2"]
    }
  ],
  "strengths": [
    {
      "dimension": "A2",
      "label": "Numerical Reasoning",
      "score": 1.0,
      "teacher_confirmed": true
    }
  ],
  "gaps": [
    {
      "dimension": "T5",
      "label": "Extraversion",
      "score": 0.4,
      "severity": "mild"
    }
  ],
  "strength_narrative": "A warm 2-3 paragraph summary of the student's overall profile, strengths, and growth areas.",
  "confidence_score": 0.85,
  "data_weighting": {
    "assessment_weight": 0.6,
    "teacher_weight": 0.4,
    "reasoning": "Why you weighted sources this way."
  },
  "conflicts": []
}

FIELD RULES:
- "career_explanations": one entry per career in final_ranking, keyed by SOC code. "score" is the deterministic engine score. "rank" is your final rank (1-5). The "explanation" field must use plain, natural language — no jargon.
- "final_ranking": exactly 5 entries. Set "from_deterministic_top20" to false if you injected a career. The "reasoning" field must use plain, natural language — no jargon or dimension codes.
- "strengths": dimensions where score >= 4/5. "score" is normalised 0-1 (e.g. 5/5 = 1.0, 4/5 = 0.8). "teacher_confirmed" is true only if a teacher comment corroborates this strength.
- "gaps": dimensions where score <= 2/5. "score" is normalised 0-1. "severity" is "mild", "moderate", or "significant".
- "strength_narrative": address the student as "you". Reference specific teacher quotes and observations. Write in plain, natural language — no jargon, no dimension codes, no psychometric terms. This should read like a friendly conversation, not a clinical report.
- "confidence_score": 0-1 float. Higher when data is rich and consistent.
- "conflicts": list of strings describing any conflicts between data sources. Empty list if none."""


# ── Prompt building ─────────────────────────────────────────────────

def format_scores(answers: Dict[str, int]) -> str:
    """Format assessment scores with dimension labels, grouped by category."""
    lines = []
    for category, qids in CATEGORIES.items():
        scores = [f"{DIMENSION_LABELS[qid]}: {answers.get(qid, '?')}/5" for qid in qids]
        lines.append(f"  {category}: {', '.join(scores)}")
    return "\n".join(lines)


def build_analysis_prompt(
    answers: Dict[str, int],
    quality: dict,
    top_20: list,
    teacher_comments: List[dict],
    subject_enrolments: List[dict],
    conflicts: List[dict] | None = None,
    career_suggestions: List[dict] | None = None,
    follow_up_answers: list[dict] | None = None,
) -> str:
    """Build the user prompt with all evidence."""

    scores_text = format_scores(answers)

    ranking_text = "\n".join(
        f"{i+1}. {name} ({soc}) — score: {score:.2f}"
        for i, (soc, name, score) in enumerate(top_20)
    )

    # Include teacher comments VERBATIM
    if teacher_comments:
        comments_text = "\n\n".join(
            f"**{tc.get('teacher_name', 'Unknown')}** | {tc.get('subject_name', 'Unknown')} | "
            f"Performance: {tc.get('performance_rating', '?')}/5 | "
            f"Engagement: {tc.get('engagement_rating', '?')}/5\n"
            f"\"{tc.get('comment_text', '')}\""
            for tc in teacher_comments
        )
    else:
        comments_text = "No teacher comments available for this student."

    # Format subjects
    if subject_enrolments:
        subjects_text = "\n".join(
            f"- {se.get('subject_name', 'Unknown')} (Year {se.get('year_level', '?')})"
            + (f" — Grade: {se['grade']}" if se.get('grade') else "")
            for se in subject_enrolments
        )
    else:
        subjects_text = "No subject enrolment data available."

    quality_flags = ", ".join(quality.get("flags", [])) or "No quality issues detected"

    # Pre-detected conflicts section
    if conflicts:
        conflict_lines = "\n".join(
            f"{i+1}. {c['description']}" for i, c in enumerate(conflicts)
        )
        conflicts_section = (
            f"## PRE-DETECTED CONFLICTS\n"
            f"(The following contradictions were detected between the student's self-assessment "
            f"and teacher observations. You MUST address each one in your \"conflicts\" array "
            f"and explain your interpretation.)\n\n{conflict_lines}"
        )
    else:
        conflicts_section = (
            "## PRE-DETECTED CONFLICTS\n"
            "No conflicts detected between assessment and teacher data."
        )

    # Career suggestions section
    if career_suggestions:
        suggestion_lines = "\n".join(
            f"{i+1}. {s['title']} ({s['soc_code']}) — {s['teacher']} mentioned \"{s['quote']}\""
            for i, s in enumerate(career_suggestions)
        )
        careers_section = (
            f"\n\n## CAREER CANDIDATES FROM TEACHER EVIDENCE\n"
            f"(The following careers were identified from teacher comments but are NOT in the "
            f"deterministic top 20. Consider injecting them into your final ranking if the "
            f"evidence is strong enough.)\n\n{suggestion_lines}"
        )
    else:
        careers_section = ""

    # Follow-up answers section
    if follow_up_answers:
        fu_lines = "\n".join(
            f"Q{i+1}: \"{fu.get('question', '')}\"\nA{i+1}: \"{fu.get('answer', '')}\""
            for i, fu in enumerate(follow_up_answers)
        )
        follow_up_section = (
            f"\n\n## FOLLOW-UP RESPONSES\n"
            f"The student's profile was initially ambiguous, so they were asked targeted follow-up questions.\n"
            f"Their responses provide additional signal about their true preferences:\n\n"
            f"{fu_lines}\n\n"
            f"Weight these responses heavily — the student gave these answers knowing their profile was unclear, "
            f"so these represent their most deliberate self-assessment."
        )
    else:
        follow_up_section = ""

    return f"""## STUDENT ASSESSMENT
Quality: {quality['confidence']} confidence
{quality_flags}

Scores:
{scores_text}

## DETERMINISTIC ENGINE TOP 20
{ranking_text}

## TEACHER COMMENTS
{comments_text}

## SUBJECT ENROLMENTS
{subjects_text}

{conflicts_section}{careers_section}{follow_up_section}

Produce your analysis as JSON."""


# ── Fallback analysis ───────────────────────────────────────────────

def build_fallback_analysis(
    answers: Dict[str, int],
    quality: dict,
    top_20: list,
) -> dict:
    """
    Produce a basic analysis using only the deterministic engine.
    Used when Groq/Llama is unavailable.
    """
    top_5 = []
    career_explanations = {}
    for i, (soc, name, score) in enumerate(top_20[:5]):
        top_5.append({
            "rank": i + 1,
            "career_name": name or soc,
            "soc_code": soc,
            "from_deterministic_top20": True,
            "original_position": i + 1,
            "reasoning": f"Ranked #{i+1} by the deterministic matching engine based on your assessment scores.",
            "key_evidence": [],
        })
        career_explanations[soc] = {
            "title": name or soc,
            "score": round(score, 4),
            "rank": i + 1,
            "explanation": f"Ranked #{i+1} by the deterministic matching engine based on your assessment scores.",
        }

    # Strengths = dimensions with score >= 4
    strengths = []
    for qid, val in answers.items():
        if val >= 4 and qid in DIMENSION_LABELS:
            strengths.append({
                "dimension": qid,
                "label": DIMENSION_LABELS[qid],
                "score": val / 5,
                "teacher_confirmed": False,
            })

    # Gaps = dimensions with score <= 2
    gaps = []
    for qid, val in answers.items():
        if val <= 2 and qid in DIMENSION_LABELS:
            gaps.append({
                "dimension": qid,
                "label": DIMENSION_LABELS[qid],
                "score": val / 5,
                "severity": "moderate",
            })

    return {
        "career_explanations": career_explanations,
        "final_ranking": top_5,
        "strengths": strengths[:5],
        "gaps": gaps[:5],
        "strength_narrative": "AI analysis was unavailable. These results are based solely on your assessment scores without teacher input or AI interpretation. Please try again later for a more comprehensive analysis.",
        "confidence_score": 0.3,
        "data_weighting": {
            "assessment_weight": 1.0,
            "teacher_weight": 0.0,
            "reasoning": "AI analysis unavailable — using assessment data only.",
        },
        "conflicts": [],
    }


# ── Main entry point ────────────────────────────────────────────────

async def run_analysis(
    answers: Dict[str, int],
    top_20: list,
    teacher_comments: List[dict],
    subject_enrolments: List[dict],
    follow_up_answers: list[dict] | None = None,
) -> dict:
    """
    Run the full AI analysis pipeline.

    Args:
        answers: Raw assessment answers {question_id: 1-5}
        top_20: Top 20 careers from deterministic engine [(soc, name, score), ...]
        teacher_comments: List of dicts with keys:
            teacher_name, subject_name, comment_text, performance_rating, engagement_rating
        subject_enrolments: List of dicts with keys:
            subject_name, year_level, grade (optional)

    Returns:
        Complete analysis dict ready for storage/display.
    """

    # Step 1: Check assessment quality (pure Python, no LLM)
    quality = check_assessment_quality(answers)

    # Step 1.5: Pre-compute conflicts and career suggestions
    conflicts = detect_conflicts(answers, teacher_comments)
    top_20_socs = {soc for soc, _, _ in top_20}
    career_suggestions = suggest_careers_from_comments(teacher_comments, top_20_socs)

    # Step 2: Build the comprehensive prompt
    user_prompt = build_analysis_prompt(
        answers, quality, top_20, teacher_comments, subject_enrolments,
        conflicts=conflicts,
        career_suggestions=career_suggestions,
        follow_up_answers=follow_up_answers,
    )

    # Step 3: Single LLM call with structured output
    result = await analyse(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    if "error" in result:
        # Graceful degradation: return basic analysis without AI
        result = build_fallback_analysis(answers, quality, top_20)

    # Map frontend field names → DB column names for _store_analysis
    result["strength_profile"] = result.get("strengths")
    result["gap_analysis"] = result.get("gaps")
    result["overall_narrative"] = result.get("strength_narrative")

    # Step 4: Attach metadata
    result["assessment_quality"] = quality
    result["deterministic_top20"] = [
        {"soc_code": soc, "title": name, "score": round(score, 4)}
        for soc, name, score in top_20
    ]
    fu = follow_up_answers or []
    result["data_sources_used"] = {
        "assessment": True,
        "teacher_comments": len(teacher_comments) > 0,
        "subject_enrolments": len(subject_enrolments) > 0,
        "comment_count": len(teacher_comments),
        "follow_up_answers": len(fu) > 0,
        "follow_up_count": len(fu),
    }

    return result
