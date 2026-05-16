# GuruMaster Carga Colombia

Copiloto inteligente para el sector transporte de carga en Colombia. Permite consultar normatividad, analizar rentabilidad de viajes, revisar costos operativos y controlar activos de flota usando lenguaje natural.

## Estado actual (actualizado 2026-05-16)

### ✅ Módulo 1 — RAG documental (COMPLETADO)

El pipeline RAG está operativo de extremo a extremo:

| Componente | Archivo | Estado |
|---|---|---|
| Extracción de texto | `backend/document_loader.py` | ✅ Operativo |
| Indexado vectorial | `backend/build_vector_index.py` | ✅ Operativo |
| Búsqueda semántica | `backend/rag_service.py` | ✅ Operativo |
| Clasificador de intención | `backend/intent_classifier.py` | ✅ Operativo |
| Endpoint /chat con LLM | `backend/chat_service.py` | ✅ Operativo |
| Backend FastAPI | `backend/main.py` | ✅ Corriendo en puerto 8000 |

**Pipeline de ingesta:**
```
PDF/DOCX/HTML/TXT → document_loader.py → data/processed_text/*.jsonl
                                                  ↓
                               build_vector_index.py → db/chroma/
                                                            ↓
                                         rag_service.search_documents()
```

**Documentos indexados (2,311 chunks en ChromaDB):**
| Pilar | Documento | Páginas |
|---|---|---|
| normatividad | DECRETO 1079 DE 2015.pdf | 528 |
| normatividad | MANUAL RNDC USUARIO Web V2.0.pdf | 105 |
| costos_operativos | ABC_SICE_TAC.txt | 1 |
| gestion_activos | — vacío, pendiente — | — |

**Búsqueda por pilar según intención:**
- `normativa` → busca en normatividad (4 chunks) + costos_operativos (2 chunks)
- `financiera` → busca en costos_operativos (fallback: todos)
- `activos` → busca en gestion_activos (fallback: todos)
- `mixta` → busca en todos los pilares

**Para agregar nuevos documentos:**
```bash
# 1. Copiar PDFs/TXT a data/documents/{pilar}/
# 2. Extraer texto
python backend/document_loader.py
# 3. Reindexar ChromaDB
python backend/build_vector_index.py --reset
```

**LLM:** GPT-4o-mini vía OpenAI API. Key en `.env` (no subir a git).

**Pendiente Módulo 1:**
- Agregar documentos a `gestion_activos/`: guías SOAT, tecnomecánica, pólizas

### ⏳ Módulos 2, 3, 4, 5 — Pendientes

- **Módulo 2** (viajes y gastos): `sql_service.py` esqueleto listo, falta crear SQLite con seed data
- **Módulo 3** (activos/vehículos): esqueleto en `sql_service.py`, falta seed data
- **Módulo 4** (motor de consulta): clasificador operativo, falta conectar SQL al `/chat`
- **Módulo 5** (frontend): pendiente adaptar `GuruMaster.html` de industrial a transporte de carga

### Frontend MVP

- `frontend/GuruMaster.html` — Demo visual React single-file, aún con datos mock de mantenimiento industrial

## Producto

**Usuario objetivo:** Propietarios de vehículos, empresas de transporte, administradores de flota, operadores logísticos.

**Dolor principal:** Dificultad para saber si los viajes son rentables, consultar normatividad, controlar gastos dispersos y gestionar vencimientos y documentos de vehículos.

**Promesa de valor:** Un asistente de IA que responde preguntas sobre viajes, costos, documentos, vehículos y normatividad usando lenguaje natural.

## Stack tecnológico

| Capa | Herramienta |
|---|---|
| Frontend | React 18 (CDN/UMD), JSX/Babel Standalone, HTML5 — single-file |
| Backend | FastAPI (Python) |
| Base estructurada | SQLite o DuckDB |
| RAG / Vector DB | ChromaDB local |
| Documentos | PDF/HTML/Excel descargados manualmente |
| LLM | OpenAI API, Azure OpenAI u Ollama |

## Arquitectura objetivo

```
Frontend (React / GuruMaster.html adaptado)
        |
Backend API (FastAPI)
        |
        +-- RAG documental: Normatividad, Costos Operativos, Gestión de Activos (ChromaDB)
        +-- SQL/Analytics: viajes, ingresos, gastos, vehículos, vencimientos (SQLite/DuckDB)
        +-- Motor de contexto: combina pregunta + documentos + datos estructurados
        |
LLM económico o local (OpenAI / Ollama)
```

## Estructura del repositorio objetivo

```
gurumaster-carga/
├── frontend/           # GuruMaster.html adaptado a transporte de carga
├── backend/
│   ├── main.py
│   ├── rag_service.py
│   ├── sql_service.py
│   ├── intent_classifier.py
│   └── chat_service.py
├── data/
│   ├── documents/
│   │   ├── normatividad/
│   │   ├── costos_operativos/
│   │   └── gestion_activos/
│   ├── seed_trips.csv
│   ├── seed_trip_expenses.csv
│   ├── seed_vehicles.csv
│   ├── seed_vehicle_documents.csv
│   └── seed_maintenance_events.csv
├── db/
│   └── gurumaster_carga.sqlite
├── notebooks/
│   ├── 01_explore_costs.ipynb
│   └── 02_validate_rag.ipynb
└── docs/
    ├── architecture.md
    ├── demo_script.md
    └── pitch.md
```

## Los 5 módulos del MVP

### Módulo 1 — Ingesta documental (RAG)

Tres pilares documentales:

| Pilar | Contenido | Preguntas que responde |
|---|---|---|
| Normatividad | RNDC, manifiesto de carga, Ministerio de Transporte | ¿Qué documentos se requieren para un despacho? |
| Costos Operativos | SICE-TAC, combustible, peajes, fletes, costos fijos/variables | ¿Qué costos debo considerar en esta ruta? |
| Gestión de Activos | SOAT, tecnomecánica, pólizas, mantenimiento preventivo | ¿Qué documentos vencen pronto? |

Flujo: `PDF/HTML/Excel → extracción → chunks → embeddings → ChromaDB → RAG`

Scripts a crear: `ingest_documents.py`, `build_vector_index.py`

### Módulo 2 — Base de ingresos y gastos

Tablas principales:
- `trips`: trip_id, date, vehicle_id, driver_id, origin, destination, revenue, status
- `trip_expenses`: expense_id, trip_id, expense_type, amount, description
- `expense_categories`: clasificación fijo/variable
- `routes`: rutas frecuentes estandarizadas

Métricas clave: utilidad por viaje, margen, gasto por km, ingreso por km.

Endpoints: `GET /trips`, `GET /trips/{id}/profitability`, `GET /analytics/monthly-summary`

### Módulo 3 — Gestión de activos de transporte

Tablas principales:
- `vehicles`: plate, vehicle_type, brand, model, year, capacity_tons, status
- `vehicle_documents`: document_type, expiration_date, status (SOAT, tecnomecánica, póliza, etc.)
- `maintenance_events`: date, maintenance_type, odometer_km, cost, next_due_km
- `vehicle_cost_summary`: rentabilidad por activo

Alertas en 7, 15 y 30 días para vencimientos.

Endpoints: `GET /vehicles`, `GET /vehicles/alerts`, `GET /vehicles/{id}/profitability`

### Módulo 4 — Motor inteligente de consulta

Clasifica la intención de cada pregunta y decide la fuente:

| Tipo de pregunta | Fuente |
|---|---|
| Normativa/documental | RAG sobre documentos |
| Financiera/analítica | SQL sobre viajes y gastos |
| Activos/vencimientos | SQL sobre vehículos |
| Mixta | RAG + SQL combinados |

Endpoint principal:
```
POST /chat
{ "message": "...", "context": { "vehicle_id": "...", "date_range": "..." } }
→ { "answer": "...", "intent": "...", "evidence": [...], "recommended_actions": [...] }
```

### Módulo 5 — Dashboard y demo web

Adaptar el frontend actual (activos industriales → vehículos/rutas):

| Área | Antes | Nuevo |
|---|---|---|
| Chat | Oráculo de mantenimiento industrial | Chat GuruMaster Carga |
| Panel central | Manuales y P&ID | Evidencia documental, tablas de gastos, análisis |
| Panel derecho | Telemetría industrial | Margen mensual, alertas, ranking de gastos |
| Selector | Activos BOM/COM/HEX | Vehículos por placa y estado |

## Escenarios de demo comercial (4 preguntas clave)

1. **Rentabilidad:** "¿El viaje Medellín - Bogotá del vehículo ABC123 fue rentable?"
2. **Normatividad:** "¿Qué debo tener en cuenta para registrar un despacho de carga?"
3. **Costos:** "¿Cuánto gasté en combustible y peajes este mes?"
4. **Activos:** "¿Qué vehículos tienen documentos próximos a vencer?"
5. **Mixta:** "¿Este viaje se pagó bien comparado con los costos operativos de referencia?"

## Roadmap de ejecución (4 semanas)

| Semana | Objetivo |
|---|---|
| 1 | Repo, FastAPI, SQLite/DuckDB, seed de viajes/gastos/vehículos, endpoints básicos |
| 2 | Ingesta de documentos, chunks, embeddings, ChromaDB, búsqueda semántica |
| 3 | Clasificador de intención, consultas SQL, contexto combinado, `POST /chat` |
| 4 | Frontend conectado, dashboard adaptado, escenarios de demo, README, video corto |

## Archivos relevantes

**Backend:**
- `backend/document_loader.py` — Extrae texto por página (PDF/DOCX/HTML/TXT), genera JSONL
- `backend/build_vector_index.py` — Lee JSONL, chunking 800 chars + embeddings MiniLM + ChromaDB
- `backend/rag_service.py` — `search_documents(query, pillar, n_results)` sobre ChromaDB
- `backend/intent_classifier.py` — Clasifica pregunta en normativa/financiera/activos/mixta
- `backend/chat_service.py` — RAG + GPT-4o-mini, endpoint POST /chat
- `backend/main.py` — FastAPI app, arrancar con `uvicorn main:app --reload` desde `/backend`
- `backend/sql_service.py` — Endpoints SQL (esqueleto, falta SQLite con datos)

**Datos:**
- `data/processed_text/processed_all.jsonl` — 634 páginas extraídas de los 3 documentos
- `data/documents/normatividad/` — Decreto 1079 + Manual RNDC
- `data/documents/costos_operativos/` — ABC_SICE_TAC.txt
- `data/seed_*.csv` — CSVs de seed data para SQLite (viajes, gastos, vehículos, etc.)

**DB:**
- `db/chroma/` — 2,311 chunks indexados (modelo: paraphrase-multilingual-MiniLM-L12-v2)
- `db/gurumaster_carga.sqlite` — NO CREADO AÚN (Módulo 2)

## Fuentes documentales recomendadas

- **SICE-TAC** (Ministerio de Transporte): costos de operación por ruta
- **RNDC** (Ministerio de Transporte): registro nacional de despachos de carga
- **Manual RNDC Usuario Web**: proceso de registro de información de carga
- **ABC SICE-TAC** (Portal Logístico de Colombia): explicaciones de costos eficientes

## Notas importantes

- Los datos simulados deben tener rutas, gastos y márgenes plausibles para Colombia.
- Las respuestas documentales deben mostrar fuentes ("no encontré evidencia" si no hay soporte).
- El LLM no debe inventar normatividad — siempre responder con evidencia o declarar ausencia.
- Priorizar los 4 escenarios comerciales antes de intentar cubrir más casos de uso.
