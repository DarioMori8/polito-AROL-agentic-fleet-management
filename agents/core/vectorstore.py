import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from core.config import settings

EMBEDDING_TIMEOUT = 120  # seconds — needed for Ollama cold-start model loading
INGESTION_BATCH_SIZE = 20  # chunks per embedding call

COLLECTION_NAME = "manuals"


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
        # Increase timeout to survive Ollama cold-start model loading
        self.embedding_fn = OllamaEmbeddingFunction(
            url=settings.OLLAMA_BASE_URL,
            model_name=settings.EMBEDDING_MODEL,
            timeout=EMBEDDING_TIMEOUT,
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_fn,
        )

    def add(self, ids: list[str], chunks: list[str], metadatas: list[dict]) -> None:
        """Add chunks in batches to avoid Ollama embedding timeouts on large PDFs."""
        for start in range(0, len(ids), INGESTION_BATCH_SIZE):
            end = start + INGESTION_BATCH_SIZE
            self.collection.add(
                ids=ids[start:end],
                documents=chunks[start:end],
                metadatas=metadatas[start:end],
            )

    def has_chunks(self, where: dict) -> bool:
        return bool(self.collection.get(where=where, limit=1)["ids"])

    def query(self, text: str, k: int = 5, where: dict | None = None) -> list[dict]:
        results = self.collection.query(
            query_texts=[text],
            n_results=k,
            where=where,
        )
        return [
            {"text": doc, **meta}
            for doc, meta in zip(results["documents"][0], results["metadatas"][0])
        ]


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
