# server_side\services\vector_kb.py
"""Vector-based knowledge base service using FAISS and Ollama embeddings."""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import faiss
import numpy as np

from server_side.core.config import settings
from server_side.core.logger import logger
from server_side.core.yaml_config import load_yaml_config
from server_side.services.base import BaseService


class VectorKBService(BaseService):
    """Vector-based knowledge base using FAISS for similarity search."""

    # Embedding model dimensions
    EMBEDDING_DIMENSIONS = {
        # OpenAI
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "embeddinggemma:300m": 768,
    }

    # Keep classifier and KB file categories compatible.
    CATEGORY_ALIASES = {
        "billing": "billing_issues",
        "billing_issues": "billing_issues",
        "delivery": "delivery_issues",
        "delivery_issues": "delivery_issues",
        "password": "password_reset",
        "password_reset": "password_reset",
        "api_error": "api_errors",
        "api_errors": "api_errors",
    }

    def __init__(self):
        """Initialize vector KB service."""
        self.yaml_conf = load_yaml_config()
        # self.embedding_model = settings.OPENAI_EMBEDDING_MODEL
        # self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = self.yaml_conf["embedding_model"]["local"]["model_name"]
        self.ollama_url = self.yaml_conf["llm"]["ollama"].get("base_url", "http://localhost:11434")

        self.faiss_index = None
        self.documents_metadata: Dict[int, Dict[str, Any]] = {}
        self.doc_counter = 0
        self.vector_store_path = settings.VECTOR_STORE_PATH
        self.index_path = os.path.join(self.vector_store_path, "faiss_index.bin")
        self.metadata_path = os.path.join(self.vector_store_path, "documents.json")

        # Create directory if it doesn't exist
        os.makedirs(self.vector_store_path, exist_ok=True)

    async def initialize(self) -> None:
        """Initialize the vector KB service with embeddings."""
        await super().initialize()  # Parent setup
        try:
            logger.info(f"Initializing embeddings with model: {self.embedding_model}")

            # Get embedding dimension from model
            embedding_dim = self.EMBEDDING_DIMENSIONS.get(self.embedding_model, 768)

            # Load existing FAISS index if available
            if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
                await self._load_index()
                logger.info(f"Loaded existing FAISS index (dimension: {embedding_dim})")
            else:
                # Create new empty index
                self.faiss_index = faiss.IndexFlatL2(embedding_dim)
                logger.info(f"Created new FAISS index (dimension: {embedding_dim})")

        except Exception as e:
            logger.error(f"Failed to initialize vector KB: {e}")
            raise

    async def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text using Ollama.
    
        Args:
            text: Text to embed
    
        Returns:
            Embedding as numpy array (2D for FAISS)
        """
        try:
            # response = await self.client.embeddings.create(model=self.embedding_model, input=text)
            # embedding = np.array(response.data[0].embedding, dtype=np.float32)

            payload = {"model": self.embedding_model, "input": text}
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{self.ollama_url}/v1/embeddings", json=payload)
                response.raise_for_status()
                data = response.json()

            embedding = np.array(data["data"][0]["embedding"], dtype=np.float32)
            return np.array([embedding], dtype=np.float32)
    
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            raise

    async def _load_index(self) -> None: # load FAISS index and metadata from disk
        """Load FAISS index and metadata from disk."""
        try:
            self.faiss_index = faiss.read_index(self.index_path)

            with open(self.metadata_path, "r") as f:
                data = json.load(f)
                self.documents_metadata = {int(k): v for k, v in data.items()}
                self.doc_counter = len(self.documents_metadata)

            logger.info(f"Loaded {self.doc_counter} documents from disk")

        except Exception as e: 
            logger.error(f"Failed to load index: {e}")
            raise

    async def _save_index(self) -> None: # save FAISS index and metadata to disk for later use
        """Save FAISS index and metadata to disk."""
        try:
            faiss.write_index(self.faiss_index, self.index_path)

            with open(self.metadata_path, "w") as f:
                json.dump(self.documents_metadata, f, indent=2)

            logger.debug("Saved FAISS index to disk")

        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise

    async def add_document( # convert text to embedding, store in FAISS index and metadata dict, then save to disk
        self,
        title: str,
        content: str,
        category: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> int:
        """Add document to knowledge base with embeddings.

        Args:
            title: Document title
            content: Document content
            category: Optional category
            source_url: Optional source URL

        Returns:
            Document ID
        """
        try:
            # Generate embedding using the configured embedding model
            embedding = await self._get_embedding(content)

            # Add to FAISS index
            self.faiss_index.add(embedding)

            # Store metadata
            self.doc_counter += 1 # counting documents like pdf1, pdf2, etc. and assigning a unique ID to each document
            doc_id = self.doc_counter

            self.documents_metadata[doc_id] = { # store metadata for each document in a dict with unique ID(doc_id)
                "id": doc_id,
                "title": title,
                "content": content,
                "category": category,
                "source_url": source_url,
            }

            # Save to disk
            await self._save_index()

            logger.info(f"Added document {doc_id}: {title}")
            return doc_id

        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            raise

    async def load_knowledge_base_from_files(self) -> int:
        """Load KB .txt files into the vector index if not already present.

        Returns:
            Number of newly loaded documents
        """
        kb_dir = Path(__file__).resolve().parent.parent / "data" / "knowledge_base"

        if not kb_dir.exists():
            logger.warning(f"Knowledge base directory not found: {kb_dir}")
            return 0

        txt_files = sorted(kb_dir.glob("*.txt"))
        newly_loaded = 0
        skipped = 0

        for kb_file in txt_files:
            try:
                raw_content = kb_file.read_text(encoding="utf-8")

                frontmatter = ""
                content = raw_content
                if raw_content.startswith("---"):
                    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", raw_content, flags=re.DOTALL)
                    if fm_match:
                        frontmatter = fm_match.group(1)
                        content = raw_content[fm_match.end():]

                category_match = re.search(r"category:\s*(\S+)", frontmatter)
                category = category_match.group(1) if category_match else None

                title_match = re.search(r"^#\s*(.+)$", content, flags=re.MULTILINE)
                title = title_match.group(1).strip() if title_match else kb_file.stem

                already_loaded = any(
                    d["title"] == title
                    for d in self.documents_metadata.values()
                    if "title" in d
                )
                if already_loaded:
                    skipped += 1
                    logger.info(f"Skipping already loaded: {title}")
                    continue

                logger.info(f"Loading KB: {kb_file.name} -> title: {title}, category: {category}")
                await self.add_document(title, content, category)
                newly_loaded += 1

            except Exception as e:
                logger.error(f"Failed loading KB file {kb_file.name}: {e}")

        logger.info(
            "Knowledge base loading complete: "
            f"{newly_loaded} new documents loaded, {skipped} skipped (already loaded)"
        )
        return newly_loaded

    async def search(
        self, query: str, category: Optional[str] = None, limit: int = 5, threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Search knowledge base by semantic similarity using embeddings.

        Args:
            query: Search query
            category: Optional category filter
            limit: Max results to return
            threshold: Similarity threshold (0-1)

        Returns:
            List of similar documents with scores
        """
        try:
            if self.faiss_index is None or self.doc_counter == 0:
                logger.debug("Knowledge base is empty")
                return []

            # Generate query embedding using Ollama
            query_embedding = await self._get_embedding(query)

            # Search in FAISS index
            # distances: L2 distances between query embedding and retrieved document embeddings
            # indices: corresponding document IDs in the FAISS index
            distances, indices = self.faiss_index.search(query_embedding, k=min(limit * 2, self.doc_counter))

            normalized_category = None
            if category:
                normalized_category = self.CATEGORY_ALIASES.get(str(category).lower(), str(category).lower())

            results = []
            for distance, idx in zip(distances[0], indices):
                if idx == -1:  # Invalid index skipped if idx is -1
                    continue

                doc_id = idx + 1  # Convert from 0-indexed to 1-indexed
                if doc_id not in self.documents_metadata: # Skip if doc_id not in documents
                    continue

                doc = self.documents_metadata[doc_id] # Retrieve document metadata using only available doc_id

                # Convert L2 distance to similarity (0-1)
                similarity = 1 / (1 + distance)

                if similarity < threshold: # skip if similarity is below threshold
                    continue

                if normalized_category:
                    doc_category = str(doc.get("category") or "").lower()
                    normalized_doc_category = self.CATEGORY_ALIASES.get(doc_category, doc_category)
                    if normalized_doc_category != normalized_category:
                        continue

                # Only include documents matching the specified category
                if category and not normalized_category and doc.get("category") != category:
                    continue

                results.append({
                    "id": doc_id,
                    "title": doc["title"],
                    "content": doc["content"],
                    "category": doc.get("category"),
                    "source_url": doc.get("source_url"),
                    "similarity_score": float(similarity),
                })

            results = results[:limit]
            logger.debug(f"Found {len(results)} documents for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
        
    async def format_context(self, documents: List[Dict[str, Any]]) -> str:
        """Format documents into context string for LLM.

        Args:
            documents: List of document dicts

        Returns:
            Formatted context string
        """
        if not documents:
            return "No relevant documentation found."

        context_parts = ["Relevant documentation:"] # first item heading/title (Relevant documentation:) later apend more lines
        for i, doc in enumerate(documents, 1): # i = 1,2,3,... (counter for display), doc = each document in the list
            similarity = doc.get("similarity_score", 0) # fetch similarity score if no similarity score, default to 0
            context_parts.append(f"\n{i}. **{doc['title']}** (Relevance: {similarity:.1%})") # combine e.g. [1. **PDF 1** (Relevance: 95.2%)]
            context_parts.append(f"   {doc['content'][:300]}...") # first 300 characters of content only for context

        return "\n".join(context_parts)
    
    async def get_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """Get document by ID.

        Args:
            doc_id: Document ID

        Returns:
            Document dict or None and dict keys are str, values can be any type
        """
        try:
            if doc_id not in self.documents_metadata:
                logger.warning(f"Document {doc_id} not found")
                return None

            return self.documents_metadata[doc_id] # Fetch document metadata by doc_id from stored dictionary

        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            return None

    async def get_by_category(self, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get documents by category.

        Args:
            category: Category name
            limit: Max documents

        Returns:
            List of documents
        """
        try: 
            results = [ 
                doc for doc in self.documents_metadata.values()
                if doc.get("category") == category
            ][:limit] # [EXPRESSION(doc) for LOOP_VAR(doc) in ITERABLE(self.documents_metadata.values()) if CONDITION(doc.get("category") == category)][:limit]

            logger.debug(f"Retrieved {len(results)} documents from category: {category}")
            return results

        except Exception as e:
            logger.error(f"Failed to get documents by category: {e}")
            return []

    async def delete_document(self, doc_id: int) -> bool:
        """Delete document from knowledge base.

        Note: FAISS doesn't support deletion, so we mark as deleted.

        Args:
            doc_id: Document ID

        Returns:
            True if deleted
        """
        try:
            if doc_id not in self.documents_metadata:
                logger.warning(f"Document {doc_id} not found")
                return False

            del self.documents_metadata[doc_id]
            await self._save_index()

            logger.info(f"Deleted document {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    async def clear_all(self) -> bool:
        """Clear all documents and reset index.

        Returns:
            True if successful
        """
        try:
            embedding_dim = self.EMBEDDING_DIMENSIONS.get(self.embedding_model, 1536)
            self.faiss_index = faiss.IndexFlatL2(embedding_dim)
            self.documents_metadata = {} # Reset documents metadata to an empty dictionary, clearing previous metadata
            self.doc_counter = 0
            await self._save_index()

            logger.info("Cleared all documents from knowledge base")
            return True

        except Exception as e:
            logger.error(f"Failed to clear knowledge base: {e}")
            return False

    async def health_check(self) -> dict:
        """Check KB service health."""
        try:
            return {
                "status": "healthy",
                "service": "vector_kb",
                "documents_count": len(self.documents_metadata),
                "embedding_model": self.embedding_model,
                "index_dimension": self.faiss_index.d if self.faiss_index else 0,
            }
        except Exception as e:
            logger.error(f"KB service health check failed: {e}")
            return {
                "status": "unhealthy",
                "service": "vector_kb",
                "error": str(e),
            }
