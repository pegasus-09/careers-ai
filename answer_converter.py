from questions import Question

LIKERT_5_MAP = {
    1: 0.0,
    2: 0.25,
    3: 0.5,
    4: 0.75,
    5: 1.0
}

def convert_answer(question: dict, raw_answer: int) -> Question:
    if question["scale"] == "likert_5":
        return Question({
            "question_id": question["id"],
            "question_type": question["question_type"],
            "target": question["target"],
            "answer": LIKERT_5_MAP[raw_answer]
        })

    raise ValueError(f"Unknown scale: {question['scale']}")
