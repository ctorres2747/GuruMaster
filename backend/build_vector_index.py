"""
Lee los JSONL de data/processed_text/, divide en chunks y los indexa en ChromaDB.

Uso:
    python build_vector_index.py
    python build_vector_index.py --reset   # borra la colección antes de indexar
    python build_vector_index.py --pillar normatividad
"""
import argparse
import json
import re
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed_text"
CHROMA_DIR    = Path(__file__).parent.parent / "db" / "chroma"
COLLECTION    = "gurumaster_docs"
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150
EMBED_MODEL   = "paraphrase-multilingual-MiniLM-L12-v2"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def split_into_chunks(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Divide el texto en chunks respetando párrafos cuando es posible."""
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 1 <= size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # Si el párrafo solo ya supera el tamaño, lo cortamos por caracteres
            if len(para) > size:
                for i in range(0, len(para), size - overlap):
                    chunks.append(para[i : i + size])
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


# ---------------------------------------------------------------------------
# Indexado
# ---------------------------------------------------------------------------

def load_records(pillar_filter: str | None = None) -> list[dict]:
    if not PROCESSED_DIR.exists():
        print(f"[!] No se encontró {PROCESSED_DIR}. Ejecuta primero document_loader.py")
        return []

    pattern = f"processed_{pillar_filter}.jsonl" if pillar_filter else "processed_*.jsonl"
    files   = sorted(PROCESSED_DIR.glob(pattern))

    if not files:
        print(f"[!] Sin archivos JSONL en {PROCESSED_DIR}. Ejecuta primero document_loader.py")
        return []

    records = []
    for path in files:
        with path.open(encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("status") == "ok" and rec.get("text"):
                    records.append(rec)
    return records


def build_index(pillar_filter: str | None = None, reset: bool = False):
    records = load_records(pillar_filter)
    if not records:
        return

    print(f"=== GuruMaster — Build Vector Index ===")
    print(f"Modelo de embeddings: {EMBED_MODEL}")
    print(f"Páginas a indexar: {len(records)}")

    embed_fn   = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    client     = chromadb.PersistentClient(path=str(CHROMA_DIR))

    if reset and COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
        print("Colección anterior eliminada.")

    collection = client.get_or_create_collection(COLLECTION, embedding_function=embed_fn)

    total_chunks = 0
    for rec in records:
        meta   = rec["metadata"]
        chunks = split_into_chunks(rec["text"])

        ids       = [f"{rec['document_id']}__p{rec['page_number']}__chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "pillar":        meta["pillar"],
                "title":         meta["title"],
                "filename":      meta["filename"],
                "source":        meta["source"],
                "ingested_date": meta["ingested_date"],
                "page_number":   rec["page_number"],
                "chunk_index":   i,
            }
            for i in range(len(chunks))
        ]

        batch = 50
        for start in range(0, len(chunks), batch):
            collection.upsert(
                ids=ids[start : start + batch],
                documents=chunks[start : start + batch],
                metadatas=metadatas[start : start + batch],
            )

        total_chunks += len(chunks)

    print(f"\nTotal chunks indexados: {total_chunks}")
    print(f"ChromaDB en: {CHROMA_DIR}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indexar documentos en ChromaDB")
    parser.add_argument("--pillar", choices=["normatividad", "costos_operativos", "gestion_activos"], default=None)
    parser.add_argument("--reset", action="store_true", help="Borrar colección antes de indexar")
    args = parser.parse_args()

    build_index(pillar_filter=args.pillar, reset=args.reset)
