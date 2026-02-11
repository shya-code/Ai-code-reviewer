"""
Utility functions for the AI Code Reviewer.
Includes token counting and context compression to minimize API costs.
"""

import hashlib
import os
import re

from config import EXTENSION_MAP, MAX_CODE_CHARS, MAX_TOKEN_BUDGET, SEVERITY_EMOJI

# ── Token counting ────────────────────────────────────────────────────────────

def count_tokens(text: str) -> int:
    """
    Estimate tokens using a simple heuristic (1 token ≈ 4 chars).
    This avoids network calls required by tiktoken to download encodings.
    """
    if not text:
        return 0
    return len(text) // 4


# ── Code compression ─────────────────────────────────────────────────────────

def compress_code(code: str, language: str, token_budget: int = MAX_TOKEN_BUDGET) -> tuple[str, int, int]:
    """
    Compress code to fit within a token budget while preserving meaning.
    
    Strategy (applied in order):
      1. Collapse consecutive blank lines → single blank line
      2. Strip trailing whitespace on every line
      3. Remove inline comments (language-aware) — keeps doc strings
      4. If still over budget: keep first 60% + last 40% of lines, cut middle
    
    Returns: (compressed_code, original_tokens, final_tokens)
    """
    original_tokens = count_tokens(code)

    if original_tokens <= token_budget:
        return code, original_tokens, original_tokens

    # Step 1: collapse blank lines
    code = re.sub(r"\n{3,}", "\n\n", code)

    # Step 2: strip trailing whitespace
    code = "\n".join(line.rstrip() for line in code.splitlines())

    # Step 3: remove inline comments (language-aware)
    code = _strip_inline_comments(code, language)

    current_tokens = count_tokens(code)
    if current_tokens <= token_budget:
        return code, original_tokens, current_tokens

    # Step 4: smart truncation — keep head + tail, cut middle
    lines = code.splitlines()
    total_lines = len(lines)

    if total_lines <= 10:
        # Too few lines to split meaningfully, just hard-truncate
        while count_tokens(code) > token_budget and len(code) > 100:
            code = code[:int(len(code) * 0.8)]
        return code + "\n// [compressed]", original_tokens, count_tokens(code)

    head_ratio = 0.6  # Keep 60% from top (imports, class defs, key logic)
    head_count = max(5, int(total_lines * head_ratio))
    tail_count = max(5, total_lines - head_count)

    # Binary search: shrink until we fit
    while head_count + tail_count > 10:
        candidate = (
            "\n".join(lines[:head_count])
            + f"\n\n// ... [{total_lines - head_count - tail_count} lines omitted for brevity] ...\n\n"
            + "\n".join(lines[-tail_count:])
        )
        if count_tokens(candidate) <= token_budget:
            return candidate, original_tokens, count_tokens(candidate)
        # Shrink both proportionally
        head_count = max(5, head_count - max(1, head_count // 10))
        tail_count = max(5, tail_count - max(1, tail_count // 10))

    # Last resort: hard truncate to budget
    candidate = "\n".join(lines[:head_count]) + "\n// [compressed — code truncated to fit token budget]"
    return candidate, original_tokens, count_tokens(candidate)


def _strip_inline_comments(code: str, language: str) -> str:
    """
    Remove single-line inline comments while preserving strings and doc comments.
    Supports // and # style comments based on language.
    """
    lang_lower = language.lower()

    # Languages that use // for comments
    slash_langs = {"javascript", "typescript", "java", "go", "rust", "c", "c++",
                   "c#", "swift", "kotlin", "scala", "dart", "zig"}
    # Languages that use # for comments
    hash_langs = {"python", "ruby", "shell", "bash", "powershell", "r", "yaml"}

    result_lines = []
    for line in code.splitlines():
        stripped = line.lstrip()

        # Skip full-line comments but keep doc comments (///, /** , """, ''')
        if lang_lower in slash_langs:
            if stripped.startswith("///") or stripped.startswith("/**"):
                result_lines.append(line)  # doc comment — keep
            elif stripped.startswith("//"):
                continue  # remove full-line comment
            else:
                result_lines.append(line)
        elif lang_lower in hash_langs:
            if stripped.startswith("#!") or stripped.startswith("# type:"):
                result_lines.append(line)  # shebang or type hint — keep
            elif stripped.startswith("#"):
                continue  # remove full-line comment
            else:
                result_lines.append(line)
        else:
            result_lines.append(line)

    return "\n".join(result_lines)



def detect_language(filename: str | None, code: str) -> str:
    """
    Detect the programming language from a filename extension.
    Falls back to 'Unknown' if no match is found.
    """
    if filename:
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        if ext in EXTENSION_MAP:
            return EXTENSION_MAP[ext]

    # Simple heuristic fallbacks based on content
    first_lines = code[:500].lower()
    if "#!/usr/bin/env python" in first_lines or "import " in first_lines and "def " in first_lines:
        return "Python"
    if "function " in first_lines or "const " in first_lines or "=>" in first_lines:
        return "JavaScript"
    if "public class " in first_lines or "public static void main" in first_lines:
        return "Java"
    if "package main" in first_lines:
        return "Go"
    if "#include" in first_lines:
        return "C/C++"

    return "Unknown"


def truncate_code(code: str, max_chars: int = MAX_CODE_CHARS) -> tuple[str, bool]:
    """
    Truncate code to max_chars. Returns (truncated_code, was_truncated).
    """
    if len(code) <= max_chars:
        return code, False
    return code[:max_chars] + "\n\n// ... [truncated — code too long for review] ...", True


def code_hash(code: str, language: str, focus_areas: list[str]) -> str:
    """
    Generate a deterministic cache key from code + language + focus areas.
    """
    payload = f"{language}::{','.join(sorted(focus_areas))}::{code}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def format_severity(level: str) -> str:
    """
    Return an emoji + label string for a severity level.
    """
    emoji = SEVERITY_EMOJI.get(level.lower(), "❓")
    return f"{emoji} {level.capitalize()}"


def generate_markdown_report(result: dict) -> str:
    """
    Turn a structured review result dict into a downloadable Markdown report.
    """
    lines: list[str] = []
    lines.append("# 🔍 AI Code Review Report\n")

    score = result.get("score", "N/A")
    lines.append(f"**Overall Score:** {score} / 10\n")
    lines.append(f"## Summary\n\n{result.get('summary', 'No summary available.')}\n")

    issues = result.get("issues", [])
    if issues:
        lines.append(f"## Issues Found ({len(issues)})\n")
        for i, issue in enumerate(issues, 1):
            sev = format_severity(issue.get("severity", "info"))
            cat = issue.get("category", "general").capitalize()
            title = issue.get("title", "Untitled Issue")
            desc = issue.get("description", "")
            suggestion = issue.get("suggestion", "")
            line_num = issue.get("line", "?")

            lines.append(f"### {i}. {sev} — {title}")
            lines.append(f"- **Category:** {cat}")
            lines.append(f"- **Line:** {line_num}")
            lines.append(f"- **Description:** {desc}")
            if suggestion:
                lines.append(f"- **Suggestion:** {suggestion}")
            lines.append("")
    else:
        lines.append("## Issues Found\n\n✅ No issues found — great job!\n")

    corrected = result.get("corrected_code", "")
    if corrected:
        lines.append("## Corrected Code\n")
        lines.append(f"```\n{corrected}\n```\n")

    return "\n".join(lines)
