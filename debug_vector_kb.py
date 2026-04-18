"""Quick debug script to inspect saved FAISS index and metadata."""

import json
from pathlib import Path

try:
    import faiss
except ModuleNotFoundError:
    faiss = None


def main() -> None:
    root = Path(__file__).resolve().parent
    vector_store = root / "data" / "vectors"
    index_path = vector_store / "faiss_index.bin"
    metadata_path = vector_store / "documents.json"

    print("=== Vector KB Debug ===")
    print(f"Vector store: {vector_store}")
    print(f"FAISS index path: {index_path}")
    print(f"Metadata path: {metadata_path}")

    if not index_path.exists():
        print("FAISS index file not found.")
        return

    if not metadata_path.exists():
        print("documents.json not found.")
        return

    with open(metadata_path, "r", encoding="utf-8") as f:
        docs = json.load(f)

    if faiss is None:
        print("FAISS module is not installed in this Python environment.")
        print("Install faiss-cpu in the active environment to inspect binary index vectors.")
        print("You can still inspect metadata below.")
        index = None
    else:
        index = faiss.read_index(str(index_path))
        print(f"Index vectors (ntotal): {int(index.ntotal)}")
        print(f"Index dimension (d): {int(index.d)}")

    print(f"Metadata documents: {len(docs)}")

    category_counts = {}
    titles = []
    for _, doc in docs.items():
        category = doc.get("category") or "uncategorized"
        category_counts[category] = category_counts.get(category, 0) + 1

        title = doc.get("title")
        if title:
            titles.append(title)

    print("Category counts:")
    for category, count in sorted(category_counts.items()):
        print(f"- {category}: {count}")

    print("Sample titles (up to 10):")
    for title in titles[:10]:
        print(f"- {title}")

    if index is not None and index.ntotal > 0:
        vector0 = index.reconstruct(0)
        preview = [float(x) for x in vector0[:8]]
        print(f"First vector preview (8 dims): {preview}")


if __name__ == "__main__":
    main()
