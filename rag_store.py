import os, json, numpy as np
from sentence_transformers import SentenceTransformer
import faiss

KB_DIR = os.environ.get("KB_DIR", "kb")
EMB_MODEL = os.environ.get("EMB_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

class RAGStore:
    def __init__(self, kb_dir: str = KB_DIR, emb_model: str = EMB_MODEL):
        self.kb_dir = kb_dir
        os.makedirs(self.kb_dir, exist_ok=True)  # Ensure kb directory exists

        self.model = SentenceTransformer(emb_model)
        emb_dim = self.model.get_sentence_embedding_dimension()

        index_path = os.path.join(self.kb_dir, "embeddings.index")
        docstore_path = os.path.join(self.kb_dir, "docstore.json")

        # Ensure FAISS index exists
        if not os.path.exists(index_path):
            print("⚠️ embeddings.index not found, creating new FAISS index...")
            index = faiss.IndexFlatL2(emb_dim)
            faiss.write_index(index, index_path)

        # Load index
        self.index = faiss.read_index(index_path)

        # Ensure docstore exists
        if os.path.exists(docstore_path):
            with open(docstore_path, "r", encoding="utf-8") as f:
                self.docstore = json.load(f)
        else:
            print("⚠️ docstore.json not found, initializing empty docstore...")
            self.docstore = {}

        print("✅ FAISS index loaded successfully:", index_path)
        print("✅ Docstore size:", len(self.docstore))

    def search(self, query: str, k: int = 6):
        qv = self.model.encode(query, normalize_embeddings=True).astype("float32")
        D, I = self.index.search(np.array([qv]), k)
        hits = []
        for score, idx in zip(D[0], I[0]):
            if idx == -1:
                continue
            rec = self.docstore.get(str(int(idx)))
            if not rec:
                continue
            rec_copy = rec.copy()
            rec_copy["score"] = float(score)
            hits.append(rec_copy)
        return hits
