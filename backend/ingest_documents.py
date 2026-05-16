"""
Extrae texto de documentos en data/documents/{pilar}/ y guarda metadatos.

Uso:
    python ingest_documents.py
    python ingest_documents.py --pillar normatividad

Soporta: PDF, HTML, TXT
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path

import pdfplumber

DATA_DIR = Path(__file__).parent.parent / "data" / "documents"
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "ingested_documents.json"

PILARES = ["normatividad", "costos_operativos", "gestion_activos"]


# ---------------------------------------------------------------------------
# Extractores por tipo de archivo
# ---------------------------------------------------------------------------

def extract_pdf(path: Path) -> str:
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
    return "\n\n".join(pages)


def extract_html(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    # Eliminar tags HTML
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


EXTRACTORS = {
    ".pdf":  extract_pdf,
    ".html": extract_html,
    ".htm":  extract_html,
    ".txt":  extract_txt,
}


# ---------------------------------------------------------------------------
# Ingesta principal
# ---------------------------------------------------------------------------

def ingest_pillar(pillar: str) -> list[dict]:
    folder = DATA_DIR / pillar
    if not folder.exists():
        print(f"  [!] Carpeta no encontrada: {folder}")
        return []

    docs = []
    files = [f for f in folder.iterdir() if f.suffix.lower() in EXTRACTORS and not f.name.startswith(".")]

    if not files:
        print(f"  [!] Sin documentos en {folder}")
        return []

    for path in files:
        extractor = EXTRACTORS[path.suffix.lower()]
        print(f"  → {path.name}")
        try:
            text = extractor(path)
            if not text:
                print(f"    [!] Sin texto extraído")
                continue
            docs.append({
                "pillar":         pillar,
                "title":          path.stem.replace("_", " ").replace("-", " ").title(),
                "filename":       path.name,
                "source":         str(path.relative_to(DATA_DIR.parent.parent)),
                "ingested_date":  date.today().isoformat(),
                "char_count":     len(text),
                "text":           text,
            })
            print(f"    OK — {len(text):,} caracteres")
        except Exception as e:
            print(f"    [ERROR] {e}")

    return docs


def ingest_all(pillar_filter: str | None = None) -> list[dict]:
    pilares = [pillar_filter] if pillar_filter else PILARES
    all_docs = []
    for pillar in pilares:
        print(f"\n[{pillar}]")
        all_docs.extend(ingest_pillar(pillar))
    return all_docs


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestar documentos para el RAG de GuruMaster")
    parser.add_argument("--pillar", choices=PILARES, default=None, help="Procesar solo un pilar")
    args = parser.parse_args()

    print("=== GuruMaster — Ingesta Documental ===")
    docs = ingest_all(args.pillar)

    OUTPUT_FILE.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal: {len(docs)} documentos → {OUTPUT_FILE}")
