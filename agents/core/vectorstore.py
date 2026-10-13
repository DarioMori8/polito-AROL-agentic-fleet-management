import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from core.config import settings
from core.observability import get_langfuse

EMBEDDING_TIMEOUT = 120  # seconds — needed for Ollama cold-start model loading
INGESTION_BATCH_SIZE = 20  # chunks per embedding call

COLLECTION_NAME = "manuals"


class TracedOllamaEmbeddingFunction(OllamaEmbeddingFunction):
    # Keep the original Chroma name/config and __call__ signature so existing
    # collections remain compatible. Do not store the large vectors in traces.
    def __call__(self, input):
        with get_langfuse().start_as_current_observation(
            name="ollama.embed", as_type="embedding",
            model=self.model_name, input=list(input),
        ) as observation:
            embeddings = super().__call__(input)
            observation.update(output={
                "count": len(embeddings),
                "dimensions": len(embeddings[0]) if len(embeddings) else 0,
            })
            return embeddings


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
        # Increase timeout to survive Ollama cold-start model loading
        self.embedding_fn = TracedOllamaEmbeddingFunction(
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

    def get_languages(self, where: dict) -> list[str]:
        with get_langfuse().start_as_current_observation(
            name="manuals.languages", as_type="retriever", input={"where": where},
        ) as observation:
            records = self.collection.get(where=where, include=["metadatas"])
            languages = sorted({m["language"] for m in records["metadatas"] if m.get("language")})
            observation.update(output=languages)
            return languages

    def query(self, text: str, k: int = 5, where: dict | None = None) -> list[dict]:
        with get_langfuse().start_as_current_observation(
            name="manuals.retrieve", as_type="retriever",
            input={"query": text, "k": k, "where": where},
        ) as observation:
            results = self.collection.query(
                query_texts=[text], n_results=k, where=where,
            )
            chunks = [
                {"text": doc, **meta}
                for doc, meta in zip(results["documents"][0], results["metadatas"][0])
            ]
            observation.update(output=chunks)
            return chunks


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
