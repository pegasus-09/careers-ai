import json
from openai import OpenAI
from pathlib import Path

client = OpenAI(api_key="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")
BASE_DIR = Path(__file__).resolve().parents[1]
PROMPT_PATH = BASE_DIR / "questionnaires" / "prompt.txt"

def build_profile_prompt(profile_dict):
    json_string = json.dumps(profile_dict)

    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        prompt = f"{f.read()}{json_string}"

    return prompt


def call_ai(prompt: str) -> dict:
    print("Calling AI...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # fast, cheap, good enough for MVP
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )

    raw_text = response.choices[0].message.content

    try:
        parsed = json.loads(raw_text)
        if parsed["summary"] in parsed["challenges"]:
            raise ValueError("AI response reused challenge text in summary")
        return parsed
    except json.JSONDecodeError:
        raise ValueError("AI did not return valid JSON")



def interpret_profile(profile):
    prompt = build_profile_prompt(profile.to_dict())

    response = call_ai(prompt)  # OpenAI, Anthropic, whatever

    return response

