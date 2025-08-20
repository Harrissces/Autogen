# good_morning_autogen.py
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ---- Autogen imports ----
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

# ---- Model / LLM config ----
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    raise SystemExit("Set OPENAI_API_KEY in .env first.")

LLM_CONFIG = {
    "timeout": 60,
    "cache_seed": 42,
    "config_list": [
        {
            "model": OPENAI_MODEL,
            "api_key": OPENAI_API_KEY,
        }
    ],
}

# ---- Role definitions (system prompts) ----
DIRECTOR_SYS = """You are the Orchestrator/Director of a small creative team.
Goal: Produce simple, original, upbeat *Good morning* motivation quotes every day.
Process:
1) Ask Theme Curator for today's theme and a 1-line rationale.
2) Ask Quote Writer for 5 short original quotes (<=18 words each), themed, no hashtags, no clichés, no emojis.
3) Ask Editor to polish, deduplicate, and enforce positivity and brevity. No religion/politics/medical/finance advice.
4) Ask Translator to create Tamil versions and present EN ↔ TA side-by-side.
5) Ask Publisher to assemble final Markdown and save to file.
Keep the team on track; if something is missing, request a revision from the specific agent.
"""

CURATOR_SYS = """Role: Theme Curator.
Pick today's micro-theme for a 'Good morning' motivational set.
Output exactly in this JSON:
{"theme": "<2-3 words>", "rationale": "<one crisp sentence>"}"""

WRITER_SYS = """Role: Quote Writer.
Write 5 short, original 'Good morning' motivational quotes tied to the given theme.
Constraints:
- 10–18 words each, imperative or declarative.
- No clichés, no emojis, no hashtags, no religion/politics.
- Avoid rhymes and superlatives; sound fresh, grounded, and kind.
Output JSON:
{"quotes_en": ["...", "...", "...", "...", "..."]}"""

EDITOR_SYS = """Role: Editor & Tone Stylist.
Input: JSON with English quotes.
Tasks:
- Remove duplicates/near-duplicates.
- Tighten wording for clarity, warmth, and brevity (<=18 words).
- Keep them motivating but calm and credible; no promises, no advice requiring expertise.
Output JSON:
{"quotes_en_final": ["...", "...", "...", "...", "..."]}"""

TRANSLATOR_SYS = """Role: Tamil Translator.
Translate each English quote to natural, simple Tamil that preserves tone and brevity.
Avoid transliteration unless necessary.
Output JSON:
{"pairs": [{"en": "...", "ta": "..."}, ...]}"""

PUBLISHER_SYS = """Role: Publisher.
Assemble a clean Markdown document for today's set.
Sections:
- Title with today's date
- Theme + one-line rationale
- A numbered list showing each English quote and the Tamil below it in italics.
- Footer line: "Have a great day!"
Only output Markdown (no code fences). Save-friendly formatting.
"""

# ---- Build agents ----
director = AssistantAgent(
    name="Director",
    system_message=DIRECTOR_SYS,
    llm_config=LLM_CONFIG,
)

curator = AssistantAgent(
    name="ThemeCurator",
    system_message=CURATOR_SYS,
    llm_config=LLM_CONFIG,
)

writer = AssistantAgent(
    name="QuoteWriter",
    system_message=WRITER_SYS,
    llm_config=LLM_CONFIG,
)

editor = AssistantAgent(
    name="Editor",
    system_message=EDITOR_SYS,
    llm_config=LLM_CONFIG,
)

translator = AssistantAgent(
    name="TamilTranslator",
    system_message=TRANSLATOR_SYS,
    llm_config=LLM_CONFIG,
)

publisher = AssistantAgent(
    name="Publisher",
    system_message=PUBLISHER_SYS,
    llm_config=LLM_CONFIG,
)

# A user proxy that will kick off the conversation (no interactive input required)
user = UserProxyAgent(
    name="User",
    human_input_mode="NEVER",
    code_execution_config=False,
)

# ---- Create the group chat & manager ----
agents = [director, curator, writer, editor, translator, publisher, user]
groupchat = GroupChat(
    agents=agents,
    messages=[],
    max_round=12,
    speaker_selection_method="auto",
)
manager = GroupChatManager(groupchat=groupchat, llm_config=LLM_CONFIG)

# ---- Conversation plan prompt (given to Director) ----
kickoff = f"""It's morning ({datetime.now().strftime('%Y-%m-%d')}). 
Produce the daily set:
- theme (Curator)
- 5 quotes (Writer)
- polish (Editor)
- Tamil translations (Translator)
- final Markdown (Publisher).
When Publisher outputs Markdown, make sure it is the final message.
"""

def extract_markdown_from_last_message(messages):
    """Returns the last assistant message content."""
    for m in reversed(messages):
        if isinstance(m, dict) and "content" in m:
            return m["content"]
    return ""

def save_markdown(md_text: str):
    d = datetime.now().strftime("%Y-%m-%d")
    path = f"good_morning_quotes_{d}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"\nSaved: {path}")

def main():
    # Start the orchestration: User asks Director to run the flow.
    user.initiate_chat(
        manager,
        message=kickoff
    )

    # Grab the final Markdown from Publisher’s output (should be last message)
    md = extract_markdown_from_last_message(groupchat.messages)
    if md.strip():
        print("\n" + "="*80 + "\nFINAL MARKDOWN\n" + "="*80 + "\n")
        print(md)
        save_markdown(md)
    else:
        print("No final Markdown was produced. Check the chat above for issues.")

if __name__ == "__main__":
    main()
