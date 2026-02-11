# 🔍 AI Code Reviewer

An AI-powered code review tool that uses **Google Gemini** to analyze your code for bugs, security vulnerabilities, performance issues, and style violations.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red) ![Gemini](https://img.shields.io/badge/Google%20Gemini-API-orange)

## ✨ Features

- **Multi-language support** — Python, JavaScript, TypeScript, Java, Go, Rust, C/C++, and 20+ more
- **Smart analysis** — Detects security flaws, bugs, performance bottlenecks, style violations, and maintainability concerns
- **Structured output** — Issues with severity levels, categories, line numbers, and fix suggestions
- **Corrected code** — AI generates a fixed version of your code
- **Score badge** — 1–10 quality score with visual indicators
- **Download reports** — Export review as a Markdown file
- **Caching** — Avoid duplicate API calls with disk-based caching
- **Retry logic** — Exponential backoff handles rate limits gracefully

## 🚀 Quick Start

### 1. Clone & install

```bash
cd "c:\Projects\Ai code reviewer"
pip install -r requirements.txt
```

### 2. Set up your API key

Copy the `.env.example` file and add your Gemini API key:

```bash
cp .env.example .env
# Edit .env and add your key
```

Or just enter it directly in the app sidebar.

### 3. Run the app

```bash
py -m streamlit run app.py
```

Open your browser at **http://localhost:8501** and start reviewing code!

## 📂 Project Structure

```
Ai code reviewer/
├── app.py              # Streamlit frontend
├── review_engine.py    # Core backend (Gemini API, prompt builder, parser)
├── config.py           # Configuration & constants
├── utils.py            # Utility functions
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## 🔧 Configuration

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Your Google Gemini API key (required) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model to use |
| `CACHE_TTL` | `3600` | Cache expiry in seconds |

## 🙏 Credits

Inspired by open-source projects:
- [Nayjest/Gito](https://github.com/Nayjest/Gito) — LLM-agnostic code reviewer
- [CodeRabbit](https://github.com/coderabbitai/coderabbit) — AI PR reviewer
- [AnyMaint AI Code Reviewer](https://github.com/anymaint/ai-code-reviewer) — Gemini-based analyzer
