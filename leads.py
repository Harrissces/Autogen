# leads.py
import os, csv, requests
from datetime import datetime

LEADS_CSV = os.path.join(os.environ.get("KB_DIR", "kb"), "leads.csv")
WEBHOOK = os.environ.get("LEADS_WEBHOOK_URL", "")

def ensure_csv():
    os.makedirs(os.path.dirname(LEADS_CSV), exist_ok=True)
    if not os.path.exists(LEADS_CSV):
        with open(LEADS_CSV, "w", newline="", encoding="utf-8") as f:
            f.write("ts_iso,name,contact,notes,source\n")

def save_lead(name: str, contact: str, notes: str = "", source: str = "streamlit"):
    ensure_csv()
    row = [datetime.utcnow().isoformat(), name.strip(), contact.strip(), notes.replace("\n"," ").strip(), source]
    with open(LEADS_CSV, "a", newline="", encoding="utf-8") as f:
        f.write(",".join([r.replace(",", " ") for r in row]) + "\n")
    if WEBHOOK:
        try:
            requests.post(WEBHOOK, json={
                "timestamp": row[0], "name": row[1], "contact": row[2], "notes": row[3], "source": source
            }, timeout=8)
        except Exception:
            pass
    return True

