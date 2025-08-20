# curate.py
import os, json, hashlib, orjson, time
from bs4 import BeautifulSoup
import requests
from markdownify import markdownify as md
import nltk
from sentence_transformers import SentenceTransformer
import faiss
from tqdm import tqdm

nltk.download("punkt", quiet=True)
SITE_ROOT = os.environ.get("SITE_ROOT", "https://harrissces.com/")
KB_DIR = os.environ.get("KB_DIR", "kb")
EMB_MODEL = os.environ.get("EMB_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "900"))
OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "120"))

def now_iso(): return time.strftime("%Y-%m-%d")

def fetch_text(url):
    r = requests.get(url, timeout=20, headers={"User-Agent":"harriss-autobot/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    main = soup.body or soup
    return md(str(main), strip=["script","style"])

def chunk_text(text):
    from nltk import sent_tokenize
    sents = sent_tokenize(text)
    chunks = []
    buff = ""
    for s in sents:
        if len(buff) + len(s) < CHUNK_SIZE:
            buff += (" " + s)
        else:
            chunks.append(buff.strip())
            buff = s
    if buff.strip():
        chunks.append(buff.strip())
    # add small overlap
    out = []
    for i,c in enumerate(chunks):
        prev = chunks[i-1][-OVERLAP:] if i>0 else ""
        out.append((prev + "\n" + c).strip())
    return out

def tag_chunk(text):
    tl = text.lower()
    tags=[]
    if any(k in tl for k in ["service","offer","solution","we provide"]): tags.append("services")
    if any(k in tl for k in ["price","pricing","cost","quote"]): tags.append("pricing")
    if any(k in tl for k in ["contact","address","phone","email","location"]): tags.append("contact")
    if any(k in tl for k in ["faq","frequently asked"]): tags.append("faq")
    if not tags: tags.append("general")
    return tags

def build_kb():
    os.makedirs(KB_DIR, exist_ok=True)
    crawl_file = os.path.join(KB_DIR, "crawl_report.json")
    assert os.path.exists(crawl_file), "Run crawler.py first."
    with open(crawl_file, "r", encoding="utf-8") as f:
        pages = json.load(f)
    model = SentenceTransformer(EMB_MODEL)
    docs = []
    meta_map = {}
    idx = 0
    for p in tqdm(pages, desc="Curating pages"):
        try:
            text = fetch_text(p["url"])
            title = p.get("title","")
            chunks = chunk_text(text)
            for ch in chunks:
                checksum = hashlib.sha256(ch.encode("utf-8")).hexdigest()
                md = {"url": p["url"], "title": title, "last_seen": now_iso(), "checksum": checksum, "tags": tag_chunk(ch)}
                meta_map[str(idx)] = md
                emb = model.encode(ch, normalize_embeddings=True)
                docs.append((emb, ch))
                idx += 1
        except Exception:
            continue
    if not docs:
        raise RuntimeError("No docs to index. Check crawl output.")
    import numpy as np
    X = np.vstack([d[0] for d in docs]).astype("float32")
    dim = X.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(X)
    faiss.write_index(index, os.path.join(KB_DIR, "embeddings.index"))
    # Save text docstore separately
    doc_texts = {str(i): {"content": docs[i][1], **meta_map[str(i)]} for i in range(len(docs))}
    with open(os.path.join(KB_DIR, "docstore.json"), "w", encoding="utf-8") as f:
        json.dump(doc_texts, f, ensure_ascii=False, indent=2)
    print("KB built:", os.path.join(KB_DIR, "embeddings.index"), os.path.join(KB_DIR, "docstore.json"))

if __name__ == "__main__":
    build_kb()

