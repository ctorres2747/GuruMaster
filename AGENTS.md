# AGENTS.md

GuruMaster Carga Colombia — intelligent copilot for the Colombian cargo-transport
sector (FastAPI backend + ChromaDB RAG + SQLite + a single-file React frontend served
by FastAPI). See `README.md` and `CLAUDE.md` for the full product/architecture overview.

## Cursor Cloud specific instructions

### Services
There is a single service: the FastAPI backend, which also serves the frontend.
- Run (dev) from the `backend/` directory: `python3 -m uvicorn main:app --reload --port 8000`
  (the update script installs deps; `--reload` enables hot reload).
- The frontend is served by the same process at `GET /` (`frontend/GuruMaster.html`).
  Open `http://localhost:8000` — do not open the HTML as a `file://` URL.
- Health check: `GET /health` → `{"status":"ok"}`.

### OPENAI_API_KEY is required just to boot the server (non-obvious)
The OpenAI client is instantiated at *import time* in `intent_classifier.py`,
`response_generator.py`, and `text_to_sql.py`, so the server will not even start if no
key is present. A repo-local `.env` (git-ignored) with a placeholder lets the server
boot, and `load_dotenv(..., override=False)` means a real `OPENAI_API_KEY` injected as
an environment variable always takes precedence over the placeholder.
- Non-LLM features (all `GET /api/*` REST endpoints, RAG semantic search) work fully
  without a valid key.
- The flagship `POST /chat` endpoint needs a **valid** `OPENAI_API_KEY` (GPT-4o-mini).
  With only the placeholder it returns HTTP 500 (OpenAI 401). Set the real key as a
  secret/env var to use chat. Network egress to `api.openai.com` works from the VM.

### Git-ignored databases must exist (regenerate if missing)
`db/gurumaster_carga.sqlite` and `db/chroma/` are git-ignored (not in the repo) but are
required at runtime. They are built from committed seed data and persist via the VM
snapshot, so they are normally already present. If they are missing, rebuild them:
- SQLite (fast): `python3 backend/init_db.py`
- ChromaDB vector index: `python3 backend/build_vector_index.py --reset`
  (reads the committed `data/processed_text/processed_all.jsonl`; the first run downloads
  the `paraphrase-multilingual-MiniLM-L12-v2` embedding model, ~1 min).

### Re-ingesting source documents (rarely needed)
`backend/document_loader.py` (PDF→text extraction) imports `fitz` (PyMuPDF),
`bs4` (beautifulsoup4) and `docx` (python-docx), which are **not** in `requirements.txt`.
It is only needed when adding *new* source documents under `data/documents/<pillar>/`.
For normal runs the committed `processed_all.jsonl` is enough, so the update script does
not install these. Install them ad-hoc only if you need to re-extract:
`python3 -m pip install pymupdf beautifulsoup4 python-docx`.

### Lint / test
There is no lint config and no automated test suite in this repo (no `pytest`,
`ruff`/`flake8`, `pre-commit`, etc.). Validation is done by running the server and
exercising the REST endpoints, RAG search, the frontend dashboard, and `/chat`.
