# streamlit_good_morning.py
from dotenv import load_dotenv
load_dotenv()

import os
from datetime import datetime
from typing import Optional
import streamlit as st

# Autogen
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

# --------------------------------------------------------------------------------------
# Config / env
# --------------------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

st.set_page_config(page_title="Good Morning Quotes — Autogen", page_icon="🌅", layout="centered")

if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY not found. Add it to your .env or Streamlit secrets, then rerun.")
    st.stop()

LLM_CONFIG = {
    "timeout": 60,
    "cache_seed": 42,
    "config_list": [
        {"model": OPENAI_MODEL, "api_key": OPENAI_API_KEY}
    ],
}

# --------------------------------------------------------------------------------------
# Agent system prompts
# --------------------------------------------------------------------------------------
DIRECTOR_SYS = """You are the Orchestrator/Director of a small creative team.
Goal: Produce simple, original, upbeat *Good morning* motivation quotes every day.
Process:
1) Ask Theme Curator for today's theme and a 1-line rationale.
2) Ask Quote Writer for N short original quotes (<= 18 words each), tied to the theme.
3) Ask Editor to polish, deduplicate, enforce positivity & brevity (no religion/politics/medical/finance advice).
4) Ask Translator to create Tamil versions and present EN ↔ TA pairs.
5) Ask Publisher to assemble final Markdown.
If anything is missing or weak, request a revision from that specific agent.
Publisher must output the final Markdown as the last message.
"""

CURATOR_SYS = """Role: Theme Curator.
Pick today's micro-theme for a 'Good morning' motivational set.
Output exactly in this JSON:
{"theme": "<2-3 words>", "rationale": "<one crisp sentence>"}"""

# IMPORTANT: use <<N>> token (avoid .format on JSON braces)
WRITER_SYS = """Role: Quote Writer.
Write <<N>> short, original 'Good morning' motivational quotes tied to the given theme.
Constraints:
- 10–18 words each, imperative or declarative.
- No clichés, no emojis, no hashtags, no religion/politics.
- Avoid rhymes and superlatives; sound fresh, grounded, and kind.
Output JSON:
{"quotes_en": ["..."]}"""

EDITOR_SYS = """Role: Editor & Tone Stylist.
Input: JSON with English quotes.
Tasks:
- Remove duplicates/near-duplicates.
- Tighten wording for clarity, warmth, and brevity (<=18 words).
- Keep motivating but calm and credible.
Output JSON:
{"quotes_en_final": ["..."]}"""

TRANSLATOR_SYS = """Role: Tamil Translator.
Translate each English quote to natural, simple Tamil that preserves tone and brevity.
Avoid transliteration unless necessary.
Output JSON:
{"pairs": [{"en": "...", "ta": "..."}]}"""

PUBLISHER_SYS = """Role: Publisher.
Assemble a clean Markdown document for today's set.
Sections:
- Title with today's date
- Theme + one-line rationale
- A numbered list: English quote, then Tamil below it in *italics*
- Footer: "Have a great day!"
Only output Markdown (no code fences)."""

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def build_team(llm_config, n_quotes: int):
    """Create agents, group chat, and return a manager + team dict for direct access.
       The QuoteWriter receives the desired quote count at construction time (read-only property)."""
    director   = AssistantAgent(name="Director",        system_message=DIRECTOR_SYS,   llm_config=llm_config)
    curator    = AssistantAgent(name="ThemeCurator",    system_message=CURATOR_SYS,    llm_config=llm_config)

    writer_msg = WRITER_SYS.replace("<<N>>", str(n_quotes))  # inject N safely
    writer     = AssistantAgent(name="QuoteWriter",     system_message=writer_msg,     llm_config=llm_config)

    editor     = AssistantAgent(name="Editor",          system_message=EDITOR_SYS,     llm_config=llm_config)
    translator = AssistantAgent(name="TamilTranslator", system_message=TRANSLATOR_SYS, llm_config=llm_config)
    publisher  = AssistantAgent(name="Publisher",       system_message=PUBLISHER_SYS,  llm_config=llm_config)

    user = UserProxyAgent(name="User", human_input_mode="NEVER", code_execution_config=False)

    agents = [director, curator, writer, editor, translator, publisher, user]
    groupchat = GroupChat(
        agents=agents,
        messages=[],
        max_round=18,                 # higher to avoid early stop
        speaker_selection_method="auto",
    )
    manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)

    team = {
        "Director":        director,
        "ThemeCurator":    curator,
        "QuoteWriter":     writer,
        "Editor":          editor,
        "TamilTranslator": translator,
        "Publisher":       publisher,
        "User":            user,
    }
    return manager, groupchat, team

def kickoff_message(n_quotes: int, custom_theme: Optional[str]):
    today = datetime.now().strftime("%Y-%m-%d")
    theme_line = f"- Use theme: '{custom_theme}' (if provided); otherwise let Curator choose.\n" if custom_theme else ""
    return (
        f"It's morning ({today}). Produce the daily set:\n"
        f"{theme_line}"
        f"- {n_quotes} quotes (Writer)\n"
        "- Polish (Editor)\n"
        "- Tamil translations (Translator)\n"
        "- Final Markdown (Publisher). Publisher must output the final Markdown as the last message."
    )

def extract_last_content(messages):
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("content"):
            return m["content"]
    return ""

def save_markdown(md_text: str) -> str:
    d = datetime.now().strftime("%Y-%m-%d")
    path = f"good_morning_quotes_{d}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(md_text)
    return path

# --------------------------------------------------------------------------------------
# Streamlit UI
# --------------------------------------------------------------------------------------
st.title("🌅 Good Morning Motivation — Multi-Agent Autogen")

with st.sidebar:
    st.success("OPENAI_API_KEY detected")
    st.subheader("Settings")
    n_quotes = st.slider("Number of quotes", min_value=3, max_value=8, value=5)
    custom_theme = st.text_input("Optional fixed theme (leave blank for auto)")
    st.caption(f"Model: {OPENAI_MODEL}")

cols = st.columns(2)
with cols[0]:
    run_btn = st.button("Generate today's quotes")
with cols[1]:
    clear_btn = st.button("Clear output")

if clear_btn:
    if "md" in st.session_state:
        del st.session_state["md"]
    if hasattr(st, "rerun"):
        st.rerun()

if run_btn:
    # 1) Build team (inject N here so we don't mutate read-only properties later)
    with st.status("Assembling agent team…", expanded=False):
        manager, groupchat, team = build_team(LLM_CONFIG, n_quotes)

    # 2) Collaborate
    with st.status("Curating theme, writing, editing, translating, publishing…", expanded=True) as status:
        status.update(label="Curating theme, writing, editing, translating, publishing…")

        # Kick off via the User agent
        team["User"].initiate_chat(
            manager,
            message=kickoff_message(n_quotes, custom_theme if custom_theme else None)
        )

        # Collect final Markdown
        md = extract_last_content(groupchat.messages)
        if not md.strip():
            st.error("No final Markdown was produced. Please try again.")
        else:
            st.session_state["md"] = md
            status.update(label="Done ✅")

# 3) Render result (outside statuses)
if "md" in st.session_state:
    st.subheader("Final output")
    st.markdown(st.session_state["md"])
    file_path = save_markdown(st.session_state["md"])
    with open(file_path, "rb") as f:
        st.download_button("⬇️ Download Markdown", f, file_name=os.path.basename(file_path), mime="text/markdown")
else:
    st.info("Click **Generate today's quotes** to create a fresh set.")
