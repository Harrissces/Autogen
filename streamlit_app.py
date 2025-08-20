# streamlit_app.py
from dotenv import load_dotenv
load_dotenv()

import os, subprocess, sys
import streamlit as st
from agents import answer
from leads import save_lead

st.set_page_config(page_title="HarrissCES Autobot", layout="wide", page_icon="🤖")
st.title("🤖 HarrissCES — Multi-Agent Autobot (retrieval-first)")

col_main, col_right = st.columns([3, 1])

with col_right:
    st.header("Admin / Lead")
    admin_pwd = st.text_input("Admin password (to refresh KB)", type="password")
    if st.button("Refresh KB (crawl + curate)", key="refresh"):
        if admin_pwd == os.environ.get("ADMIN_PASS", "change-me"):
            st.info("Running crawler + curate (this may take a while). Output will appear in console.")
            try:
                subprocess.run([sys.executable, "crawler.py"], check=True)
                subprocess.run([sys.executable, "curate.py"], check=True)
                st.success("Refresh complete — KB updated.")
            except subprocess.CalledProcessError as e:
                st.error(f"Refresh failed: {e}")
        else:
            st.error("Incorrect admin password.")

    st.divider()
    st.subheader("Quick Lead")
    lead_name = st.text_input("Name", key="lead_name")
    lead_contact = st.text_input("Email or phone", key="lead_contact")
    lead_notes = st.text_area("Notes / requirement", key="lead_notes")
    if st.button("Save lead", key="save_lead"):
        if lead_name.strip() and lead_contact.strip():
            save_lead(lead_name, lead_contact, lead_notes or "")
            st.success("Lead saved.")
        else:
            st.error("Please provide name and contact.")

    st.divider()
    st.subheader("Handoff History")
    if "handoff_history" not in st.session_state:
        st.session_state.handoff_history = []
    for h in st.session_state.handoff_history[-20:]:
        st.write(h)

with col_main:
    if "history" not in st.session_state:
        st.session_state.history = []
    if "router_state" not in st.session_state:
        st.session_state.router_state = {}

    # render chat history
    for m in st.session_state.history:
        if m["role"] == "user":
            st.markdown(f"**You:** {m['text']}")
        else:
            label = m.get("label", "Agent")
            st.markdown(f"**{label} Agent:** {m['text']}")
            if m.get("sources"):
                with st.expander("Sources"):
                    st.text(m["sources"])

    user_q = st.text_input(
        "Ask anything about HarrissCES (products, pricing, support, contact):",
        key="user_q"
    )

    if st.button("Send", key="send"):
        if not user_q.strip():
            st.warning("Type a question first.")
        else:
            st.session_state.history.append({"role": "user", "text": user_q})
            try:
                out = answer(user_q, st.session_state.router_state)
                label = out["label"].replace("_", " ").title()
                reply = out["reply"]
                st.session_state.history.append({
                    "role": "assistant",
                    "label": label,
                    "text": reply,
                    "sources": out.get("sources", "")
                })
                if out.get("handoff"):
                    st.session_state.handoff_history.append(out["handoff"])
            except Exception as e:
                st.session_state.history.append({
                    "role": "assistant",
                    "label": "Error",
                    "text": f"Sorry, something went wrong while generating the answer:\n\n{e}",
                    "sources": ""
                })

            # force UI refresh for immediate rendering (Streamlit ≥ 1.27)
            if hasattr(st, "rerun"):
                st.rerun()
            # If you're pinned to very old Streamlit, comment the line above out.

