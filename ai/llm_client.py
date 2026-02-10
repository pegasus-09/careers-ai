"""
Groq LLM client for LaunchPad AI analysis.
Uses Llama 3.3 70B Versatile via Groq for fast, free-tier inference.
Free tier: 30 RPM, 1,000 requests/day, no credit card, no expiry.
"""
import os
import json
import re
from groq import AsyncGroq

_client = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client


MODEL = "llama-3.3-70b-versatile"

MAX_RETRIES = 3


def _strip_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) that Llama sometimes wraps around JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


async def analyse(
    system_prompt: str,
    user_prompt: str,
    response_format: dict | None = None,
) -> dict:
    """
    Send a prompt to Llama 3.3 70B and get structured JSON back.

    Groq does NOT guarantee valid JSON output, so we validate and
    retry up to 3 times on parse failure. At 800+ tokens/sec,
    3 retries complete in <2 seconds.
    """
    client = _get_client()
    kwargs = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
    }
    if response_format:
        kwargs["response_format"] = response_format
    else:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.chat.completions.create(**kwargs)
            text = response.choices[0].message.content.strip()
            text = _strip_fences(text)
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"[LLM] JSON parse failed (attempt {attempt}/{MAX_RETRIES})")
            if attempt == MAX_RETRIES:
                print(f"[LLM] analyse error: failed to parse JSON after {MAX_RETRIES} attempts")
                return {"error": f"JSON parse failed after {MAX_RETRIES} attempts"}
        except Exception as e:
            print(f"[LLM] analyse error: {e}")
            return {"error": str(e)}


async def generate_text(system_prompt: str, user_prompt: str) -> str:
    """
    Generate free-form text (narratives, explanations).
    Falls back to placeholder on error — never crashes.
    """
    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        print(f"[LLM] generate_text error: {e}")
        return f"[Analysis unavailable: {str(e)}]"
