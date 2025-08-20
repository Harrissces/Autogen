1) Create venv and install:
   python -m venv .venv
   # activate: source .venv/bin/activate  (Windows: .venv\Scripts\activate)
   pip install -r requirements.txt

2) Create .env with OPENAI_API_KEY and other values (see .env template).

3) First build KB:
   python crawler.py
   python curate.py

   This creates: kb/crawl_report.json, kb/embeddings.index, kb/docstore.json

4) Run Streamlit:
   streamlit run streamlit_app.py

5) Use the right-side Admin panel to refresh the KB later.
   Use Lead capture or copy model lead requests into Quick Lead.

