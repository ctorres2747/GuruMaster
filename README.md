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
        ↓                          ↓
  rag_service.py          sql_service.py
  (ChromaDB)              (SQLite)
        ↓                          ↓
         chat_service.py (GPT-4o-mini)
                ↓
          Respuesta con evidencia
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
# Chat con RAG
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Qué documentos necesito para registrar un despacho de carga?"}'

# Rentabilidad de un viaje
curl http://localhost:8000/api/trips/T001/profitability

# Resumen financiero del mes
curl http://localhost:8000/api/analytics/monthly-summary?year=2026&month=5

# Alertas de documentos próximos a vencer
curl http://localhost:8000/api/vehicles/alerts?days=30

# Rentabilidad por vehículo
curl http://localhost:8000/api/vehicles/V001/profitability
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

## Estructura del proyecto

```
GuruMaster/
├── backend/
│   ├── main.py                # FastAPI app
│   ├── init_db.py             # Crea SQLite y carga seed data
│   ├── document_loader.py     # Extrae texto de PDF/DOCX/HTML/TXT
│   ├── build_vector_index.py  # Chunking + embeddings + ChromaDB
│   ├── rag_service.py         # Búsqueda semántica
│   ├── intent_classifier.py   # Clasifica intención del usuario
│   ├── chat_service.py        # Orquesta RAG + LLM
│   └── sql_service.py         # Consultas SQLite (viajes, vehículos, activos)
├── data/
│   ├── documents/
│   │   ├── normatividad/      # Decreto 1079, Manual RNDC
│   │   ├── costos_operativos/ # ABC SICE-TAC
│   │   └── gestion_activos/   # (pendiente: SOAT, tecnomecánica)
│   ├── processed_text/        # JSONL generado por document_loader.py
│   └── seed_*.csv             # Datos demo: viajes, gastos, vehículos, documentos, odómetro, alertas
├── db/
│   ├── chroma/                # Base vectorial ChromaDB (generada localmente)
│   └── gurumaster_carga.sqlite# Base estructurada SQLite
├── frontend/                  # GuruMaster.html (en desarrollo)
├── requirements.txt
└── .env                       # OPENAI_API_KEY (no subir a git)
```

## Estado del proyecto

| Módulo | Descripción | Estado |
|---|---|---|
| 1 — RAG documental | Ingesta, embeddings, búsqueda semántica, /chat con LLM | ✅ Completo |
| 2 — Viajes y gastos | SQLite con trips, expenses, analytics mensuales | ✅ Completo |
| 3 — Activos | Vehículos, documentos, mantenimiento, odómetro, alertas consolidadas | ✅ Completo |
| 4 — Motor de consulta | SQL conectado al /chat para preguntas financieras | ⏳ Pendiente |
| 5 — Frontend | Dashboard React adaptado a transporte de carga | ⏳ Pendiente |

## Documentos recomendados

- **Normatividad:** Decreto 1079 de 2015, Manual RNDC Usuario Web
- **Costos:** ABC SICE-TAC (plc.mintransporte.gov.co)
- **Activos:** Guías SOAT, requisitos tecnomecánica Colombia
