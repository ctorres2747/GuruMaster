# GuruMaster Carga Colombia

Copiloto inteligente para el sector transporte de carga en Colombia. Responde preguntas sobre normatividad, rentabilidad de viajes, costos operativos y vencimientos de documentos usando lenguaje natural.

## ¿Qué hace?

| Pregunta | Fuente |
|---|---|
| ¿Qué documentos necesito para registrar un despacho? | Decreto 1079, Manual RNDC |
| ¿Es obligatorio cumplir el SICE-TAC para fijar el flete? | ABC SICE-TAC |
| ¿El viaje Medellín-Bogotá del vehículo ABC123 fue rentable? | Base de datos de viajes |
| ¿Qué vehículos tienen documentos próximos a vencer? | Base de datos de activos |

## Stack

| Capa | Herramienta |
|---|---|
| Backend | FastAPI + Python |
| RAG / Vector DB | ChromaDB local |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` (local) |
| Base estructurada | SQLite |
| LLM | GPT-4o-mini (OpenAI API) |
| Frontend | React 18 single-file (en desarrollo) |

## Arquitectura

```
Pregunta del usuario
        ↓
  intent_classifier.py   →  normativa / financiera / activos / mixta
  (GPT-4o-mini)             + extrae placa y fechas de la pregunta
        ↓
  chat_service.py  (orquestador)
     ↓                    ↓
  rag_service.py      sql_service.py
  (ChromaDB)          (SQLite — consultas parametrizadas)
     ↓                    ↓
      context_builder.py  (formatea evidencia para el LLM)
              ↓
      response_generator.py (GPT-4o-mini)
              ↓
  Respuesta con fuentes, métricas y advertencias
```

## Instalación

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd GuruMaster

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar API key
echo "OPENAI_API_KEY=sk-..." > .env

# 4. Crear la base de datos SQLite con datos demo
python backend/init_db.py

# 5. Agregar documentos PDF a data/documents/{pilar}/
#    normatividad/ → decretos, manuales RNDC
#    costos_operativos/ → documentos SICE-TAC
#    gestion_activos/ → guías SOAT, tecnomecánica

# 6. Correr el pipeline de ingesta RAG
python backend/document_loader.py
python backend/build_vector_index.py

# 7. Arrancar el backend
cd backend
uvicorn main:app --reload
```

## Probar el API

Abrir en el navegador: `http://localhost:8000/docs`

```bash
# Pregunta normativa (sin filtros — el clasificador lo enruta automáticamente)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "Qué documentos necesito para registrar un despacho de carga"}'

# Pregunta financiera con placa en la pregunta (se extrae automáticamente)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "ABC123 fue rentable en mayo"}'

# Pregunta con filtros explícitos
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "pregunta": "Cuánto gasté en combustible este mes",
    "filtros": { "vehiculo_id": "V001", "fecha_inicio": "2026-05-01", "fecha_fin": "2026-05-31" }
  }'

# Pregunta de activos (alertas, vencimientos, mantenimiento)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "Cuáles llantas hay que cambiar pronto"}'

# Endpoints REST directos
curl http://localhost:8000/api/trips/T001/profitability
curl http://localhost:8000/api/analytics/monthly-summary?year=2026&month=5
curl http://localhost:8000/api/vehicles/alerts?days=30
curl http://localhost:8000/api/vehicles/V001/profitability
```

**Estructura del response de `/chat`:**

```json
{
  "respuesta": "Sí. El vehículo ABC123 tuvo una utilidad de $7,030,000 COP en mayo...",
  "intencion": "financiera",
  "confianza": 0.90,
  "fuentes": [{ "tipo": "sql", "nombre": "trips + trip_expenses" }],
  "datos_consultados": [{ "tipo": "sql", "nombre": "trips + trip_expenses" }],
  "metricas": { "ingreso": 18900000, "gastos": 11870000, "utilidad": 7030000, "margen_pct": 37.2 },
  "advertencias": []
}
```

## Endpoints disponibles

| Endpoint | Descripción |
|---|---|
| `POST /chat` | Chat con RAG + GPT-4o-mini |
| `GET /api/trips` | Lista de viajes (filtrable por `vehiculo_id`) |
| `GET /api/trips/{id}/profitability` | Rentabilidad de un viaje con desglose de gastos |
| `GET /api/analytics/monthly-summary` | Resumen financiero mensual |
| `GET /api/vehicles` | Lista de vehículos con indicadores |
| `GET /api/vehicles/alerts` | Alertas de vencimientos con nivel de urgencia |
| `GET /api/vehicles/{id}` | Ficha completa del vehículo |
| `GET /api/vehicles/{id}/documents` | Documentos con días restantes |
| `GET /api/vehicles/{id}/maintenance` | Historial de mantenimiento |
| `GET /api/vehicles/{id}/profitability` | Rentabilidad del activo |
| `GET /api/vehicles/{id}/odometer` | Historial de kilometraje |
| `GET /api/alerts` | Panel de alertas consolidado por criticidad |

## Frontend

Abrir directamente en el navegador — no requiere servidor de desarrollo:

```bash
# Windows
start frontend\GuruMaster.html

# O arrastrar el archivo al navegador
```

El backend debe estar corriendo en `http://localhost:8000` antes de abrir el frontend.

**Layout de 3 paneles:**

| Panel | Contenido |
|---|---|
| Izquierdo (370px) | Chat con GuruMaster — input, loading dots, intent badges, warning banners |
| Central (flex) | Tabs: **Evidencia** (fuentes RAG) · **Financiero** (métricas COP) · **Activos** (alertas flota) |
| Derecho (268px) | KPIs de la última consulta, vehículo activo, resumen alertas, fleet list |

**Funcionalidades clave:**
- Selector de placa en el header — se auto-selecciona cuando el usuario menciona una placa en la pregunta
- La placa seleccionada se incluye como `filtros.vehiculo_id` en el payload de `/chat`
- El tab central cambia automáticamente según la intención clasificada por el backend
- Dark mode integrado; alertas cargadas en background desde `/api/vehicles/alerts`

## Estructura del proyecto

```
GuruMaster/
├── backend/
│   ├── main.py                  # FastAPI app — arrancar con uvicorn main:app --reload
│   ├── init_db.py               # Crea SQLite y carga seed data
│   ├── schemas.py               # Pydantic: ChatRequest, ChatResponse, Filtros, Metricas
│   ├── intent_classifier.py     # LLM-based: clasifica + extrae placa y fechas de la pregunta
│   ├── chat_service.py          # Orquestador principal — POST /chat
│   ├── context_builder.py       # Formatea RAG + SQL en texto estructurado para el LLM
│   ├── response_generator.py    # Llamada a GPT-4o-mini con system prompt de GuruMaster Carga
│   ├── guardrails.py            # Advertencias por ausencia de fuentes o datos
│   ├── rag_service.py           # search_documents() sobre ChromaDB
│   ├── sql_service.py           # Todas las consultas SQLite (REST + helpers para /chat)
│   ├── document_loader.py       # Extrae texto de PDF/DOCX/HTML/TXT → JSONL
│   └── build_vector_index.py    # Chunking + embeddings MiniLM + ChromaDB
├── data/
│   ├── documents/
│   │   ├── normatividad/        # Decreto 1079, Manual RNDC
│   │   ├── costos_operativos/   # ABC SICE-TAC
│   │   └── gestion_activos/     # (pendiente: SOAT, tecnomecánica)
│   ├── processed_text/          # JSONL generado por document_loader.py
│   └── seed_*.csv               # Datos demo: viajes, gastos, vehículos, documentos, odómetro, alertas
├── db/
│   ├── chroma/                  # Base vectorial ChromaDB (2,311 chunks)
│   └── gurumaster_carga.sqlite  # Base SQLite (9 tablas, seed data mayo 2026)
├── docs/                        # Documentos de referencia del proyecto
├── frontend/
│   └── GuruMaster.html          # React 18 single-file — 3 paneles, API real, dark mode
├── requirements.txt
└── .env                         # OPENAI_API_KEY (no subir a git)
```

## Estado del proyecto

| Módulo | Descripción | Estado |
|---|---|---|
| 1 — RAG documental | Ingesta, embeddings, búsqueda semántica | ✅ Completo |
| 2 — Viajes y gastos | SQLite con trips, expenses, analytics mensuales | ✅ Completo |
| 3 — Activos | Vehículos, documentos, mantenimiento, odómetro, alertas | ✅ Completo |
| 4 — Motor de consulta | Clasificador LLM + RAG + SQL orquestados en `/chat` | ✅ Completo |
| 5 — Frontend | Dashboard React single-file conectado al backend real | ✅ Completo |

## Documentos recomendados

- **Normatividad:** Decreto 1079 de 2015, Manual RNDC Usuario Web
- **Costos:** ABC SICE-TAC (plc.mintransporte.gov.co)
- **Activos:** Guías SOAT, requisitos tecnomecánica Colombia
