"""All Gemma 4 calls: report extraction, Nepali summary, chat."""
import json
import re

from google import genai
from google.genai import types

from .config import GEMINI_API_KEY, GEMMA_MODEL
from .prompts import CHAT_SYSTEM_PROMPT, EXTRACTION_PROMPT, SUMMARY_PROMPT

_client = None


def client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _parse_json(text: str) -> dict | list:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def _generate_json(contents, retries: int = 1) -> dict:
    last_err = None
    for _ in range(retries + 1):
        resp = client().models.generate_content(
            model=GEMMA_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(temperature=0.1),
        )
        try:
            parsed = _parse_json(resp.text or "")
            if isinstance(parsed, list):
                return {"tests": parsed}
            if isinstance(parsed, dict):
                return parsed
            raise ValueError("Model JSON must be an object or list")
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
    raise ValueError(f"Model did not return valid JSON: {last_err}")


def extract_report(images: list[tuple[bytes, str]]) -> dict:
    """Vision step: report images -> structured JSON of tests."""
    parts = [types.Part.from_bytes(data=b, mime_type=m) for b, m in images]
    data = _generate_json(parts + [EXTRACTION_PROMPT])
    tests = data.get("tests") or []
    if not isinstance(tests, list):
        tests = []
    clean = []
    tests_skipped = 0
    for t in tests:
        if not isinstance(t, dict) or not t.get("name") or t.get("value") in (None, ""):
            tests_skipped += 1
            continue
        clean.append(
            {
                "name": str(t["name"]).strip(),
                "value": str(t["value"]).strip(),
                "unit": str(t.get("unit") or "").strip(),
                "reference_range": str(t.get("reference_range") or "").strip(),
            }
        )
    data["tests"] = clean
    data["tests_skipped"] = tests_skipped
    return data


def summarize_nepali(flagged_tests: list[dict]) -> dict:
    """Text step: verified, flagged results -> Nepali summary + tips."""
    prompt = SUMMARY_PROMPT.format(results_json=json.dumps(flagged_tests, ensure_ascii=False, indent=2))
    data = _generate_json([prompt])
    tips = data.get("tips_ne") or {}
    return {
        "summary_ne": str(data.get("summary_ne", "")).strip(),
        "tips_ne": {
            "diet": list(tips.get("diet") or []),
            "lifestyle": list(tips.get("lifestyle") or []),
            "behaviour": list(tips.get("behaviour") or []),
        },
        "see_doctor_soon": bool(data.get("see_doctor_soon", False)),
    }


def chat_answer(flagged_tests: list[dict], history: list[dict], question: str) -> str:
    system = CHAT_SYSTEM_PROMPT.format(results_json=json.dumps(flagged_tests, ensure_ascii=False))
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
    # Gemma models may not accept a separate system instruction, so prepend it to the first turn.
    if contents:
        contents[0] = types.Content(
            role=contents[0].role,
            parts=[types.Part.from_text(text=system + "\n\n")] + list(contents[0].parts),
        )
    else:
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=system)]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=question)]))
    resp = client().models.generate_content(
        model=GEMMA_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(temperature=0.3),
    )
    return (resp.text or "").strip()
