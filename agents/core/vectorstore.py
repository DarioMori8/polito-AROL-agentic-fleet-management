import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from core.config import settings

COLLECTION_NAME = "manuals"


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
        self.embedding_fn = OllamaEmbeddingFunction(
            url=settings.OLLAMA_BASE_URL,
            model_name=settings.EMBEDDING_MODEL,
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_fn,
        )

    def add(self, ids: list[str], chunks: list[str], metadatas: list[dict]) -> None:
        self.collection.add(ids=ids, documents=chunks, metadatas=metadatas)

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
