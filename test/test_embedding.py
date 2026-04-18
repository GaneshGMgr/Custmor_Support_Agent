# test/test_embedding.py
import fitz
import requests
import numpy as np
import faiss
import os

# --- CONFIG ---
OLLAMA_API_URL = "http://127.0.0.1:11434"
PDF_PATH = "server_side/data/files/Self_RAG.pdf"
EMBEDDING_MODEL = "embeddinggemma:300m"

VECTOR_DIR = "server_side/data/vectors"
INDEX_PATH = os.path.join(VECTOR_DIR, "self_rag.index")
CHUNKS_PATH = os.path.join(VECTOR_DIR, "self_rag_chunks.npy")

os.makedirs(VECTOR_DIR, exist_ok=True)

# --- 1. Read PDF ---
pdf_text = ""
with fitz.open(PDF_PATH) as pdf:
    for page in pdf:
        pdf_text += page.get_text("text") + " "

print(f"Extracted {len(pdf_text)} characters.")

# --- 2. Chunk ---
def chunk_text(text, max_len=200):
    words = text.split()
    return [" ".join(words[i:i+max_len]) for i in range(0, len(words), max_len)]

text_chunks = chunk_text(pdf_text)
print(f"Total chunks: {len(text_chunks)}")

# --- 3. Embed ---
embeddings = []
for i, chunk in enumerate(text_chunks):
    res = requests.post(
        f"{OLLAMA_API_URL}/v1/embeddings",
        json={"model": EMBEDDING_MODEL, "input": chunk}
    )
    emb = res.json()["data"][0]["embedding"]
    embeddings.append(np.array(emb, dtype="float32"))

embeddings_array = np.vstack(embeddings)
print(f"Embeddings shape: {embeddings_array.shape}")

# --- 4. FAISS ---
dim = embeddings_array.shape[1]
index = faiss.IndexFlatL2(dim)
index.add(embeddings_array)

# --- 5. SAVE ---
faiss.write_index(index, INDEX_PATH)
np.save(CHUNKS_PATH, text_chunks)

print("✅ Saved FAISS index and chunks!")