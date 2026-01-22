from typing import Dict, List
from statistics import mean
import json

from models.profile import PsychometricProfile
from ingestion.utils import clamp
from models.career_components import Traits, Interests, Aptitudes, Values, WorkStyles
from scripts.rank_all_careers import rank_profiles
from ingestion.read_occupation_data import load_soc_title_mapping


# -----------------------------
# Question definition
# -----------------------------

class Question:
    def __init__(self, qid: str, text: str, component: str, dimension: str):
        self.id = qid
        self.text = text
        self.component = component
        self.dimension = dimension


# -----------------------------
# Quiz questions
# -----------------------------

QUESTIONS: List[Question] = [

    # -------- Aptitudes --------
    Question("A1", "I am good with numbers and quantitative problems.", "aptitudes", "numerical_reasoning"),
    Question("A2", "I understand written material quickly.", "aptitudes", "verbal_reasoning"),
    Question("A3", "I can visualize objects or spaces in my mind.", "aptitudes", "spatial_reasoning"),
    Question("A4", "I can reason through problems step by step.", "aptitudes", "logical_reasoning"),
    Question("A5", "I can remember information accurately over time.", "aptitudes", "memory"),

    # -------- Interests --------
    Question("I1", "I enjoy working with computers and technology.", "interests", "technology"),
    Question("I2", "I am curious about science and how things work.", "interests", "science"),
    Question("I3", "I am interested in business, strategy, or entrepreneurship.", "interests", "business"),
    Question("I4", "I enjoy creative expression like design, writing, or art.", "interests", "arts"),
    Question("I5", "I care deeply about helping others or society.", "interests", "social_impact"),
    Question("I6", "I enjoy hands-on or practical work.", "interests", "hands_on"),

    # -------- Traits --------
    Question("T1", "I enjoy analyzing problems deeply.", "traits", "analytical"),
    Question("T2", "I enjoy generating new ideas or approaches.", "traits", "creative"),
    Question("T3", "I enjoy interacting with people.", "traits", "social"),
    Question("T4", "I am comfortable taking the lead.", "traits", "leadership"),
    Question("T5", "I care about details and accuracy.", "traits", "detail_oriented"),
    Question("T6", "I adapt easily when circumstances change.", "traits", "adaptability"),

    # -------- Values --------
    Question("V1", "Job stability is important to me.", "values", "stability"),
    Question("V2", "Long-term financial security matters to me.", "values", "financial_security"),
    Question("V3", "Status or prestige matters to me.", "values", "prestige"),
    Question("V4", "I value having autonomy in my work.", "values", "autonomy"),
    Question("V5", "Helping others through my work is important to me.", "values", "helping_others"),
    Question("V6", "Work-life balance is a top priority for me.", "values", "work_life_balance"),

    # -------- Work Styles --------
    Question("W1", "I prefer working in teams rather than alone.", "work_styles", "team_based"),
    Question("W2", "I prefer clear structure and expectations.", "work_styles", "structure"),
    Question("W3", "I enjoy fast-paced environments.", "work_styles", "pace"),
    Question("W4", "I am comfortable with ambiguity.", "work_styles", "ambiguity_tolerance"),
]


# -----------------------------
# Interactive quiz
# -----------------------------

def run_quiz() -> Dict[str, int]:
    print("\nCareerAI Psychometric Quiz")
    print("Rate each statement from 1 to 5")
    print("1 = Strongly disagree | 5 = Strongly agree")
    print("Press Enter to skip\n")

    ans: Dict[str, int] = {}

    for q in QUESTIONS:
        while True:
            raw = input(f"[{q.id}] {q.text} (1–5): ").strip()

            if raw == "":
                break

            if raw.isdigit() and 1 <= int(raw) <= 5:
                ans[q.id] = int(raw)
                break

            print("Invalid input. Enter 1–5 or press Enter to skip.")

    return ans


# -----------------------------
# Build component instances
# -----------------------------

def build_components(ans: Dict[str, int]):
    buckets = {
        "aptitudes": {},
        "interests": {},
        "traits": {},
        "values": {},
        "work_styles": {},
    }

    for q in QUESTIONS:
        if q.id not in ans:
            continue

        buckets[q.component].setdefault(q.dimension, []).append(ans[q.id])

    def avg_normalized(d: Dict[str, List[int]]) -> Dict[str, float]:
        return {
            k: clamp(mean(v) / 5)
            for k, v in d.items()
        }

    return (
        Aptitudes(avg_normalized(buckets["aptitudes"])),
        Interests(avg_normalized(buckets["interests"])),
        Traits(avg_normalized(buckets["traits"])),
        Values(avg_normalized(buckets["values"])),
        WorkStyles(avg_normalized(buckets["work_styles"])),
    )


# -----------------------------
# Entry point
# -----------------------------

if __name__ == "__main__":
    answers = run_quiz()
    # answers = json.load(open("answers.json"))
    #
    aptitudes, interests, traits, values, work_styles = build_components(answers)
    user_profile = PsychometricProfile(aptitudes, interests, traits, values, work_styles)
    socs = load_soc_title_mapping()
    data, ranking = rank_profiles(user_profile)
    #
    TOP_RANKS = 20

    # correct = input("Answer SOC? ").title()
    # if correct:
    #     if '.' not in correct:
    #         correct += '.00'
    #     career = socs.get(correct)
    #     soc_to_index = {soc: i for i, (soc, _) in enumerate(ranking)}
    #     index = next(
    #         (i for i, (soc, _) in enumerate(ranking) if soc == correct),
    #         None
    #     )
    #     print(f"{correct} ({career}) is ranked {index + 1}")
    # print(f"\nTop {TOP_RANKS} Careers:\n")
    print(ranking[:TOP_RANKS])
    #
    # for i in range(0, TOP_RANKS):
    #     print(f"{i+1}. {socs.get(ranking[i][0])}")

    # print(f"\nExplanation for {socs.get(ranking[1][0])}\n")
    # explain = ExplanationEngine()
    # explain.explain_career(user_profile.to_dict(),
    #                        {"soc": ranking[1][0], "title": socs.get(ranking[1][0])},
    #                        data[ranking[1][0]])
