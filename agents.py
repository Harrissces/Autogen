# agents.py
from dotenv import load_dotenv
load_dotenv()  # <-- make env vars from .env visible to this process

import os, openai, json
from typing import List, Dict
from rag_store import RAGStore

openai.api_key = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
TOP_K = int(os.environ.get("TOP_K", "6"))
RTCFR_PATH = "rtcfr_system_prompt.md"

# Read RTCFR system prompt (the long system prompt you saved)
with open(RTCFR_PATH, "r", encoding="utf-8") as f:
    RTCFR_TEXT = f.read()

rag = RAGStore()

def route_intent(user_text: str, hits: List[Dict]) -> str:
    t = user_text.lower()
    if any(k in t for k in ["price","pricing","quote","cost","package","buy","purchase","service","lead"]):
        return "sales_services"
    if any(k in t for k in ["refund","warranty","policy","support","repair","return"]):
        return "support_policies"
    if any(k in t for k in ["contact","phone","email","address","where","location","hours","timing"]):
        return "logistics_contact"
    if any(k in t for k in ["about","team","who are you","case study","projects","portfolio"]):
        return "general_about"
    # fallback: examine tags in hits
    votes = {"sales_services":0,"support_policies":0,"logistics_contact":0,"general_about":0}
    for h in hits:
        for tag in h.get("tags",[]):
            if tag in ("services","pricing"): votes["sales_services"]+=1
            if tag in ("faq","policy","support"): votes["support_policies"]+=1
            if tag in ("contact","location"): votes["logistics_contact"]+=1
            if tag in ("about","general","case_studies"): votes["general_about"]+=1
    winner = max(votes, key=votes.get)
    return winner if votes[winner]>0 else "general_about"

def build_system_for_agent(agent_label: str) -> str:
    agent_suffix = {
        "sales_services": "You are Sales & Services Specialist — answer only from retrieved site documents. Use the Answer Contract.",
        "support_policies": "You are Support & Policies Specialist — answer only from retrieved site documents. Use the Answer Contract.",
        "logistics_contact": "You are Logistics & Contact Specialist — answer only from retrieved site documents. Use the Answer Contract.",
        "general_about": "You are General Info Specialist — answer only from retrieved site documents. Use the Answer Contract."
    }
    return RTCFR_TEXT + "\n\n" + agent_suffix.get(agent_label, "")

def compose_user_prompt(user_text: str, hits: List[Dict]) -> str:
    # Build a short summary of top-k retrieved docs to be used as context
    context_parts = []
    for i, h in enumerate(hits[:TOP_K]):
        context_parts.append(f"[{i+1}] TITLE: {h.get('title','(untitled)')}\nURL: {h.get('url')}\nLAST_SEEN: {h.get('last_seen','')}\n\nCONTENT:\n{h.get('content')}\n\n---\n")
    context = "\n".join(context_parts) or "No retrieved docs."
    prompt = (
        "You MUST use only the following retrieved documents as factual ground (do NOT hallucinate).\n\n"
        f"{context}\n\n"
        f"User question:\n{user_text}\n\n"
        "Follow the Answer Contract exactly:\n"
        "- Short answer (2-4 sentences)\n"
        "- Key facts (3–6 bullet points)\n"
        "- Sources: list the docs used with last-seen dates\n"
        "- Next step / CTA (link / contact / lead-capture) or say 'Not enough data' and provide closest contact path.\n"
    )
    return prompt

def call_llm(system_prompt: str, user_prompt: str) -> str:
    messages = [
        {"role":"system", "content": system_prompt},
        {"role":"user", "content": user_prompt}
    ]
    # Use chat completion
    resp = openai.ChatCompletion.create(model=OPENAI_MODEL, messages=messages, temperature=0.0, max_tokens=700)
    txt = ""
    try:
        txt = resp["choices"][0]["message"]["content"].strip()
    except Exception:
        txt = "Error: LLM did not return content."
    return txt

def answer(user_text: str, session_state: dict) -> dict:
    hits = rag.search(user_text, k=TOP_K)
    label = route_intent(user_text, hits)
    prev = session_state.get("label")
    handoff = None
    if prev and prev != label:
        handoff = f"{prev} -> {label}"
    session_state["label"] = label
    system = build_system_for_agent(label)
    user_prompt = compose_user_prompt(user_text, hits)
    reply = call_llm(system, user_prompt)
    # Build sources summary
    sources = "\n".join([f"{i+1}) {h.get('title','(untitled)')} — {h.get('url')} (last_seen: {h.get('last_seen')})" for i,h in enumerate(hits[:TOP_K])])
    return {"label": label, "reply": reply, "sources": sources, "handoff": handoff}
