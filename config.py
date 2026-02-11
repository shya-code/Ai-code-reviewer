"""
Configuration module for AI Code Reviewer.
Loads environment variables and defines constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini API ────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
GEMINI_TEMPERATURE = 0.3          # Low temperature for consistent reviews
GEMINI_MAX_OUTPUT_TOKENS = 8192   # Enough for detailed reviews

# ── Cache ─────────────────────────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
CACHE_TTL = int(os.getenv("CACHE_TTL", "86400"))  # 24 hours — aggressive caching

# ── Code limits ───────────────────────────────────────────────────────────────
MAX_CODE_CHARS = 100_000  # ~2500 lines, safe for Gemini context window
MAX_TOKEN_BUDGET = 6000   # Max tokens for the code portion of prompt (leaves room for system prompt + response)

# ── Language mapping (extension → display name) ──────────────────────────────
EXTENSION_MAP: dict[str, str] = {
    ".py":    "Python",
    ".js":    "JavaScript",
    ".jsx":   "JavaScript (React)",
    ".ts":    "TypeScript",
    ".tsx":   "TypeScript (React)",
    ".java":  "Java",
    ".go":    "Go",
    ".rs":    "Rust",
    ".cpp":   "C++",
    ".c":     "C",
    ".cs":    "C#",
    ".rb":    "Ruby",
    ".php":   "PHP",
    ".swift": "Swift",
    ".kt":    "Kotlin",
    ".scala": "Scala",
    ".r":     "R",
    ".sql":   "SQL",
    ".html":  "HTML",
    ".css":   "CSS",
    ".sh":    "Shell",
    ".bash":  "Bash",
    ".ps1":   "PowerShell",
    ".yaml":  "YAML",
    ".yml":   "YAML",
    ".json":  "JSON",
    ".xml":   "XML",
    ".dart":  "Dart",
    ".lua":   "Lua",
    ".zig":   "Zig",
}

# ── Review categories & severities ───────────────────────────────────────────
CATEGORIES = [
    "security",
    "bug",
    "performance",
    "style",
    "maintainability",
    "best-practice",
]

SEVERITIES = ["critical", "high", "medium", "low", "info"]

SEVERITY_EMOJI: dict[str, str] = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🔵",
    "info":     "⚪",
}

SEVERITY_COLOR: dict[str, str] = {
    "critical": "#ff4444",
    "high":     "#ff8800",
    "medium":   "#ffcc00",
    "low":      "#4488ff",
    "info":     "#aaaaaa",
}
