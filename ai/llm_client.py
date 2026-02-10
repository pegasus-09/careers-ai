"""
Groq LLM client for LaunchPad AI analysis.
Uses Llama 3.3 70B Versatile via Groq for fast, free-tier inference.
Free tier: 30 RPM, 1,000 requests/day, no credit card, no expiry.
"""
import os
import json
import re
import groq
from groq import AsyncGroq

_client = None


def _get_client(use_backup: bool = False) -> AsyncGroq:
    global _client
    if use_backup:
        api_key = os.environ.get("GROQ_BACKUP_API_KEY")
        _client = AsyncGroq(api_key=api_key)
    elif _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        _client = AsyncGroq(api_key=api_key)
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
        except groq.RateLimitError:
            print(f"[LLM] Rate limit exceeded, retrying with backup key.")
            client = _get_client(use_backup=True)
        except Exception as e:
            print(f"[LLM] analyse error: {e}")
            return {"error": str(e)}


async def generate_text(system_prompt: str, user_prompt: str) -> str:
    """
    Generate free-form text (narratives, explanations).
    Falls back to placeholder on error — never crashes.
    """
    client = _get_client()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
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
        except groq.RateLimitError:
            print(f"[LLM] Rate limit exceeded, retrying with backup key.")
            client = _get_client(use_backup=True)
        except Exception as e:
            print(f"[LLM] generate_text error: {e}")
            return f"[Analysis unavailable: {str(e)}]"
    return "[Analysis unavailable: Max retries exceeded]"
