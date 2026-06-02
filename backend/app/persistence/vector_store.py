"""ChromaDB-backed vector store for table/column embeddings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger("shuyu.vector")

CHROMA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "chromadb"


class VectorStore:
    """ChromaDB-backed vector store for table and column embeddings."""

    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir is None:
            persist_dir = str(CHROMA_DIR)
        persist_dir_path = Path(persist_dir)
        persist_dir_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(persist_dir_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="shuyu_rag",
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_table(self, database_id: str, table_id: str, table_name: str,
                     text: str, embedding: list[float]):
        """Upsert a single table embedding."""
        self._collection.upsert(
            ids=[f"table_{database_id}_{table_id}"],
            embeddings=[embedding],
            metadatas=[{
                "database_id": database_id,
                "table_id": table_id,
                "table_name": table_name,
                "type": "table",
            }],
            documents=[text],
        )

    def upsert_batch_tables(self, database_id: str,
                            items: list[tuple[str, str, str, list[float]]]):
        """Batch upsert: [(table_id, table_name, text, embedding), ...]"""
        ids = []
        embeddings = []
        metadatas = []
        documents = []
        for table_id, table_name, text, emb in items:
            ids.append(f"table_{database_id}_{table_id}")
            embeddings.append(emb)
            metadatas.append({
                "database_id": database_id,
                "table_id": table_id,
                "table_name": table_name,
                "type": "table",
            })
            documents.append(text)
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def upsert_column(self, database_id: str, table_id: str, column_id: str,
                      column_name: str, text: str, embedding: list[float]):
        """Upsert a single column embedding."""
        self._collection.upsert(
            ids=[f"col_{database_id}_{column_id}"],
            embeddings=[embedding],
            metadatas=[{
                "database_id": database_id,
                "table_id": table_id,
                "column_id": column_id,
                "column_name": column_name,
                "type": "column",
            }],
            documents=[text],
        )

    def search_tables(self, query_embedding: list[float], database_id: str,
                      top_k: int = 5, min_score: float = 0.3) -> list[dict]:
        """Search tables by cosine similarity. Returns [{table_id, table_name, text, score}]."""
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"$and": [
                {"database_id": {"$eq": database_id}},
                {"type": {"$eq": "table"}},
            ]},
        )
        if not results["ids"] or not results["ids"][0]:
            return []
        output = []
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            score = 1.0 - distance
            if score >= min_score:
                output.append({
                    "table_id": meta.get("table_id", doc_id),
                    "table_name": meta.get("table_name", ""),
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "score": round(score, 4),
                })
        return output

    def delete_database(self, database_id: str):
        """Delete all embeddings for a given database."""
        self._collection.delete(
            where={"database_id": {"$eq": database_id}},
        )

    def close(self):
        """Cleanup ChromaDB client."""
        if self._client:
            self._client = None
