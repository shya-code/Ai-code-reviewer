"""
AI Code Reviewer — Streamlit Frontend
A polished web UI for AI-powered code review using Google Gemini.
"""

import streamlit as st
from review_engine import review_code, ReviewResult
from utils import detect_language, format_severity, generate_markdown_report
from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    CATEGORIES,
    SEVERITY_COLOR,
    SEVERITY_EMOJI,
    EXTENSION_MAP,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Code Reviewer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
# (Removed per user request for plain Streamlit UI)



# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ Settings")

    api_key = st.text_input(
        "Gemini API Key",
        value=GEMINI_API_KEY,
        type="password",
        help="Your Google Gemini API key. Get one at https://aistudio.google.com/apikey",
    )

    model_name = st.selectbox(
        "Model",
        ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro"],
        index=0,
        help="Choose the Gemini model for code review",
    )

    st.markdown("---")
    st.markdown("### 🎯 Focus Areas")

    focus_all = st.checkbox("All categories", value=True)
    if focus_all:
        selected_focus = CATEGORIES.copy()
    else:
        selected_focus = []
        for cat in CATEGORIES:
            if st.checkbox(cat.replace("-", " ").title(), value=False, key=f"focus_{cat}"):
                selected_focus.append(cat)

    st.markdown("---")
    st.markdown("### 📋 Options")
    use_cache = st.checkbox("Use cached results", value=True, help="Skip API call if the same code was reviewed recently")

    lang_options = ["Auto-detect"] + sorted(set(EXTENSION_MAP.values()))
    selected_lang = st.selectbox("Language", lang_options, index=0)

    st.markdown("---")
    st.markdown("---")
    st.caption("Built with Streamlit + Gemini API")


# ── Header ────────────────────────────────────────────────────────────────────

st.title("🔍 AI Code Reviewer")
st.write("Paste or upload your code — get an instant, AI-powered review with bug detection, security analysis, and style suggestions.")
st.markdown("---")


# ── Input section ─────────────────────────────────────────────────────────────

col_input, col_upload = st.columns([3, 1])

with col_upload:
    uploaded_file = st.file_uploader(
        "📂 Upload a file",
        type=list(ext.lstrip(".") for ext in EXTENSION_MAP.keys()),
        help="Upload a source code file to review",
    )

with col_input:
    default_code = ""
    detected_filename = None

    if uploaded_file is not None:
        default_code = uploaded_file.read().decode("utf-8", errors="replace")
        detected_filename = uploaded_file.name
        st.success(f"📄 Loaded **{uploaded_file.name}** ({len(default_code):,} characters)")

    code_input = st.text_area(
        "💻 Paste your code here",
        value=default_code,
        height=350,
        placeholder="# Paste your code here...\ndef hello():\n    print('Hello, world!')",
    )


# ── Review button ─────────────────────────────────────────────────────────────

review_clicked = st.button("🚀 Review Code", use_container_width=True, type="primary")


# ── Review logic ──────────────────────────────────────────────────────────────

if review_clicked:
    if not api_key:
        st.error("⚠️ Please enter your Gemini API key in the sidebar.")
        st.stop()

    if not code_input.strip():
        st.warning("📝 Please paste or upload some code to review.")
        st.stop()

    # Detect language
    if selected_lang == "Auto-detect":
        language = detect_language(detected_filename, code_input)
    else:
        language = selected_lang

    st.info(f"🔄 Reviewing your {language} code... This usually takes 5–15 seconds.")

    with st.spinner(""):
        result: ReviewResult = review_code(
            code=code_input,
            language=language,
            focus_areas=selected_focus or CATEGORIES,
            api_key=api_key,
            model_name=model_name,
            use_cache=use_cache,
        )

    if result.error:
        st.error(f"❌ Review failed: {result.error}")
        st.stop()

    # ── Display results ───────────────────────────────────────────

    if result.from_cache:
        st.info("⚡ Results loaded from cache (same code was reviewed recently)")

    # Score + stats in columns
    score = result.score
    total_issues = len(result.issues)
    critical_count = sum(1 for i in result.issues if i.severity in ("critical", "high"))
    
    col_score, col_issues, col_crit, col_lang = st.columns(4)
    
    col_score.metric("Overall Score", f"{score}/10")
    col_issues.metric("Total Issues", total_issues)
    col_crit.metric("Critical/High", critical_count, delta_color="inverse")
    col_lang.metric("Language", language)
    
    st.markdown("---")
    
    # Summary
    st.subheader("📋 Summary")
    st.write(result.summary)
    
    st.markdown("---")

    st.markdown("")

    # Issues
    if result.issues:
        st.markdown(f"### 🐛 Issues ({total_issues})")

        # Severity filter
        sev_filter = st.multiselect(
            "Filter by severity",
            options=["critical", "high", "medium", "low", "info"],
            default=["critical", "high", "medium", "low", "info"],
            format_func=lambda x: f"{SEVERITY_EMOJI.get(x, '')} {x.capitalize()}",
        )

        filtered_issues = [i for i in result.issues if i.severity in sev_filter]

        for issue in filtered_issues:
            emoji = SEVERITY_EMOJI.get(issue.severity, "❓")
            with st.expander(f"{emoji} {issue.severity.upper()} - {issue.title}"):
                st.markdown(f"**Category:** {issue.category} | **Line:** {issue.line}")
                st.write(issue.description)
                if issue.suggestion:
                    st.info(f"💡 **Suggestion:** {issue.suggestion}")
                    
    else:
        st.success("✅ No issues found! Your code looks clean.")

    st.markdown("")

    # Corrected code
    if result.corrected_code:
        with st.expander("✨ View Corrected Code", expanded=False):
            lang_lower = language.lower().split(" ")[0] if language != "Unknown" else ""
            st.code(result.corrected_code, language=lang_lower or None, line_numbers=True)

    # Download report
    report_md = generate_markdown_report({
        "summary": result.summary,
        "score": result.score,
        "issues": [
            {
                "line": i.line,
                "severity": i.severity,
                "category": i.category,
                "title": i.title,
                "description": i.description,
                "suggestion": i.suggestion,
            }
            for i in result.issues
        ],
        "corrected_code": result.corrected_code,
    })

    st.download_button(
        label="📥 Download Review Report (.md)",
        data=report_md,
        file_name="code_review_report.md",
        mime="text/markdown",
        use_container_width=True,
    )

elif not st.session_state.get("_review_done"):
    # Empty state

    st.info("👋 Ready to review! Paste your code above or upload a file, then click **Review Code**.")
