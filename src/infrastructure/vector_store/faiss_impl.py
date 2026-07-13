"""FAISS implementation using cosine similarity (IndexFlatIP + L2 normalization)."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import faiss
import numpy as np

from src.infrastructure.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)

# Bump this version string whenever the index format changes.
# A mismatch will prompt the user to re-run scripts/init_vector_db.py.
_INDEX_VERSION = "v2-cosine"


class FaissVectorStore(BaseVectorStore):
    """FAISS vector store using inner-product search on L2-normalized vectors.

    Normalizing every vector before insertion means inner product == cosine similarity,
    so higher scores are better (range ≈ 0–1 for well-trained sentence embeddings).

    On-disk format
    --------------
    faiss_index.bin  – raw FAISS binary index
    knowledge_base.json – {"version": "v2-cosine", "records": [...]}
    """

    def __init__(self, dimension: int, index_path: str, meta_path: str) -> None:
        self.dimension = dimension
        self.index_path = index_path
        self.meta_path = meta_path
        self.index = faiss.IndexFlatIP(dimension)
        self.metadata: List[Dict[str, Any]] = []
        self._load_if_exists()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_if_exists(self) -> None:
        if not (os.path.exists(self.index_path) and os.path.exists(self.meta_path)):
            return

        with open(self.meta_path, "r", encoding="utf-8") as f:
            stored = json.load(f)

        if isinstance(stored, list):
            # Old v1 flat-list format (L2 index) – incompatible.
            logger.warning(
                "Detected legacy L2 index (v1). "
                "Please re-run `python scripts/init_vector_db.py` "
                "to rebuild with cosine similarity."
            )
            return

        if stored.get("version") != _INDEX_VERSION:
            logger.warning(
                f"Index version mismatch ({stored.get('version')!r} vs {_INDEX_VERSION!r}). "
                "Please re-run `python scripts/init_vector_db.py`."
            )
            return

        self.index = faiss.read_index(self.index_path)
        self.metadata = stored.get("records", [])
        logger.info(f"Loaded FAISS cosine index: {self.index.ntotal} vectors.")

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(
                {"version": _INDEX_VERSION, "records": self.metadata},
                f,
                ensure_ascii=False,
                indent=2,
            )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add_texts(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if len(texts) != len(embeddings):
            raise ValueError("texts and embeddings must have the same length.")
        if metadata and len(metadata) != len(texts):
            raise ValueError("metadata and texts must have the same length.")

        vecs = np.array(embeddings, dtype="float32")
        faiss.normalize_L2(vecs)  # unit norm → cosine sim == inner product
        self.index.add(vecs)

        for i, text in enumerate(texts):
            entry: Dict[str, Any] = {"query_text": text}
            if metadata:
                entry.update(metadata[i])
            self.metadata.append(entry)

        self._save()
        return True

    def search(self, query_embedding: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
        if self.index.ntotal == 0:
            return []

        query_np = np.array([query_embedding], dtype="float32")
        faiss.normalize_L2(query_np)
        similarities, indices = self.index.search(query_np, top_k)

        results = []
        for j, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.metadata):
                entry = self.metadata[idx].copy()
                entry["similarity_score"] = float(similarities[0][j])
                results.append(entry)
        return results
