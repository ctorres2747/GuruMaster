"""RAG sobre documentos de los tres pilares: normatividad, costos_operativos, gestion_activos."""
from pathlib import Path
from functools import lru_cache

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHROMA_DIR  = Path(__file__).parent.parent / "db" / "chroma"
COLLECTION  = "gurumaster_docs"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
PILARES     = {"normatividad", "costos_operativos", "gestion_activos"}


@lru_cache(maxsize=1)
def _get_collection():
    embed_fn   = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    client     = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(COLLECTION, embedding_function=embed_fn)


def search_documents(query: str, pillar: str | None = None, n_results: int = 4) -> list[dict]:
    """
    Busca fragmentos relevantes en ChromaDB.

    Args:
        query:     Pregunta o texto a buscar.
        pillar:    Filtrar por pilar ('normatividad', 'costos_operativos', 'gestion_activos').
        n_results: Número máximo de resultados.

    Returns:
        Lista de dicts con: content, title, source, pillar, score.
    """
    col = _get_collection()

    if col.count() == 0:
        return []

    where = {"pillar": pillar} if pillar and pillar in PILARES else None

    results = col.query(
        query_texts=[query],
        n_results=min(n_results, col.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    docs = []
    for i, content in enumerate(results["documents"][0]):
        meta  = results["metadatas"][0][i]
        score = 1 - results["distances"][0][i]  # distancia coseno → similitud
        docs.append({
            "content": content,
            "title":   meta.get("title", ""),
            "source":  meta.get("source", ""),
            "pillar":  meta.get("pillar", ""),
            "score":   round(score, 3),
        })

    # Ordenar por relevancia descendente
    return sorted(docs, key=lambda d: d["score"], reverse=True)


def index_is_ready() -> bool:
    """Devuelve True si ChromaDB tiene documentos indexados."""
    try:
        return _get_collection().count() > 0
    except Exception:
        return False
