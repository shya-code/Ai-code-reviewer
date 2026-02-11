"""
Review Engine — Core backend for AI Code Reviewer.
Builds prompts, calls Gemini via the new google.genai SDK,
parses structured JSON responses, and caches results.
"""

import json
import re
from dataclasses import dataclass, field

import diskcache
from google import genai
from google.genai import types
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import (
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    GEMINI_MAX_OUTPUT_TOKENS,
    CACHE_DIR,
    CACHE_TTL,
)
from utils import code_hash, compress_code


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Issue:
    line: int | str
    severity: str
    category: str
    title: str
    description: str
    suggestion: str = ""


@dataclass
class ReviewResult:
    summary: str
    score: int
    issues: list[Issue] = field(default_factory=list)
    corrected_code: str = ""
    raw_response: str = ""
    from_cache: bool = False
    error: str | None = None


# ── Prompt builder ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert senior software engineer performing a thorough code review.
You are meticulous, fair, and constructive. You catch bugs, security issues,
performance problems, and style violations — but you also acknowledge good code.

RULES:
1. Return ONLY valid JSON — no markdown fences, no extra text.
2. Use the exact schema shown below.
3. "score" is an integer 1-10 (10 = perfect, 1 = critical problems).
4. "issues" is an array; may be empty if code is clean.
5. Each issue must have: line, severity, category, title, description, suggestion.
6. "severity" must be one of: critical, high, medium, low, info.
7. "category" must be one of: security, bug, performance, style, maintainability, best-practice.
8. "corrected_code" should be the improved version of the FULL code with all issues fixed.
   If the code is already perfect, set corrected_code to an empty string.
9. Be specific about line numbers. If you can't pinpoint a line, use 0.

JSON SCHEMA:
{
  "summary": "string — 2-4 sentence overall assessment",
  "score": integer,
  "issues": [
    {
      "line": integer,
      "severity": "string",
      "category": "string",
      "title": "string — short issue title",
      "description": "string — what's wrong and why it matters",
      "suggestion": "string — how to fix it"
    }
  ],
  "corrected_code": "string"
}\
"""


def build_review_prompt(code: str, language: str, focus_areas: list[str]) -> str:
    """Build the user prompt for code review."""
    focus_str = ", ".join(focus_areas) if focus_areas else "all categories"
    return (
        f"Review the following {language} code.\n"
        f"Focus especially on: {focus_str}.\n\n"
        f"```{language.lower()}\n{code}\n```"
    )


# ── Gemini API caller ────────────────────────────────────────────────────────

class GeminiAPIError(Exception):
    """Raised when the Gemini API returns an error."""
    pass


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    retry=retry_if_exception_type((GeminiAPIError, Exception)),
    reraise=True,
)
def call_gemini(api_key: str, user_prompt: str, model_name: str = GEMINI_MODEL) -> str:
    """
    Call Google Gemini with the review prompt using the new google.genai SDK.
    Retries on failure with exponential backoff (2s → 4s → 8s).
    """
    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=GEMINI_TEMPERATURE,
                max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
            ),
        )
        if not response or not response.text:
            raise GeminiAPIError("Empty response from Gemini API")
        return response.text
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "resource exhausted" in error_str:
            raise GeminiAPIError(f"Rate limited: {e}")
        if "500" in error_str or "internal" in error_str:
            raise GeminiAPIError(f"Server error: {e}")
        raise


# ── Response parser ───────────────────────────────────────────────────────────

def parse_review_response(raw_text: str) -> dict:
    """
    Parse Gemini's response into a structured dict.
    Handles raw JSON, markdown-fenced JSON, and graceful fallback.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(fence_pattern, text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find any JSON object in the text
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            try:
                data = json.loads(brace_match.group())
            except json.JSONDecodeError:
                return _fallback_result(raw_text)
        else:
            return _fallback_result(raw_text)

    # Validate required fields
    if "summary" not in data or "score" not in data:
        return _fallback_result(raw_text)

    # Normalise score
    try:
        data["score"] = max(1, min(10, int(data["score"])))
    except (ValueError, TypeError):
        data["score"] = 5

    # Normalise issues
    data.setdefault("issues", [])
    data.setdefault("corrected_code", "")

    return data


def _fallback_result(raw_text: str) -> dict:
    """Return a minimal result when JSON parsing fails."""
    return {
        "summary": "The AI returned a response that could not be parsed as structured JSON. "
                   "The raw response is shown below.",
        "score": 5,
        "issues": [],
        "corrected_code": "",
        "_raw_fallback": raw_text,
    }


# ── Cache ─────────────────────────────────────────────────────────────────────

_cache = diskcache.Cache(CACHE_DIR)


# ── Main review function ─────────────────────────────────────────────────────

def review_code(
    code: str,
    language: str,
    focus_areas: list[str],
    api_key: str,
    model_name: str = GEMINI_MODEL,
    use_cache: bool = True,
) -> ReviewResult:
    """
    Run a full AI code review. Returns a ReviewResult.
    """
    # Compress/truncate if needed to fit token budget
    code, _, _ = compress_code(code, language)

    # Check cache
    cache_key = code_hash(code, language, focus_areas)
    if use_cache:
        cached = _cache.get(cache_key)
        if cached is not None:
            result = _dict_to_result(cached)
            result.from_cache = True
            return result

    # Build prompt & call API
    user_prompt = build_review_prompt(code, language, focus_areas)

    try:
        raw_response = call_gemini(api_key, user_prompt, model_name)
    except Exception as e:
        return ReviewResult(
            summary="",
            score=0,
            error=f"API call failed: {e}",
            raw_response="",
        )

    # Parse
    data = parse_review_response(raw_response)

    # Cache the result
    if use_cache:
        _cache.set(cache_key, data, expire=CACHE_TTL)

    result = _dict_to_result(data)
    result.raw_response = raw_response
    return result


def _dict_to_result(data: dict) -> ReviewResult:
    """Convert a parsed dict into a ReviewResult dataclass."""
    issues = []
    for item in data.get("issues", []):
        issues.append(Issue(
            line=item.get("line", 0),
            severity=item.get("severity", "info"),
            category=item.get("category", "general"),
            title=item.get("title", "Untitled"),
            description=item.get("description", ""),
            suggestion=item.get("suggestion", ""),
        ))

    return ReviewResult(
        summary=data.get("summary", "No summary."),
        score=data.get("score", 5),
        issues=issues,
        corrected_code=data.get("corrected_code", ""),
    )
