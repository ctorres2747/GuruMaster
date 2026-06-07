# GuruMaster Carga Colombia

Copiloto inteligente para el sector transporte de carga en Colombia. Permite consultar normatividad, analizar rentabilidad de viajes, revisar costos operativos y controlar activos de flota usando lenguaje natural.

## Estado actual (actualizado 2026-06-07) — MVP COMPLETO + MEJORAS POST-MVP

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

### ✅ Módulo 2 — Base de ingresos y gastos (COMPLETADO)

SQLite creado en `db/gurumaster_carga.sqlite` con 7 tablas y 82 filas de seed data.

**Script de inicialización:** `backend/init_db.py`
```bash
python backend/init_db.py   # crea el schema y carga todos los CSVs
```

**Tablas creadas:**
| Tabla | Filas | Descripción |
|---|---|---|
| vehicles | 5 | Tractocamiones, dobles troques, turbos |
| drivers | 5 | Conductores empleados y contratistas |
| routes | 6 | Rutas nacionales (Medellín-Bogotá, Medellín-Barranquilla, etc.) |
| trips | 8 | Viajes de mayo 2026 |
| trip_expenses | 32 | Gastos por viaje (combustible, peajes, conductor, etc.) |
| vehicle_documents | 15 | SOAT, RTM, pólizas, tarjetas de propiedad |
| maintenance_events | 11 | Mantenimientos preventivos y correctivos |

**Endpoints operativos:**
- `GET /api/trips` — lista viajes (filtrable por `vehiculo_id`)
- `GET /api/trips/{viaje_id}/profitability` — rentabilidad con desglose de gastos
- `GET /api/analytics/monthly-summary?year=&month=` — resumen financiero mensual

**Seed data (CSVs en `data/`):**
- `seed_vehicles.csv`, `seed_drivers.csv`, `seed_routes.csv`
- `seed_trips.csv`, `seed_trip_expenses.csv`
- `seed_vehicle_documents.csv`, `seed_maintenance_events.csv`

### ✅ Módulo 3 — Gestión de activos (COMPLETADO)

**Endpoints operativos:**
- `GET /api/vehicles` — lista con conteo de viajes y docs críticos por vehículo
- `GET /api/vehicles/alerts?days=` — alertas con nivel de urgencia: `vencido` / `critico` / `urgente` / `proximo`
- `GET /api/vehicles/{vehiculo_id}` — ficha completa: datos + documentos + últimos mantenimientos
- `GET /api/vehicles/{vehiculo_id}/documents` — documentos con días restantes hasta vencimiento
- `GET /api/vehicles/{vehiculo_id}/maintenance` — historial completo de mantenimiento
- `GET /api/vehicles/{vehiculo_id}/profitability` — rentabilidad del activo: ingresos vs gastos operativos + mantenimiento

**Niveles de urgencia en alertas de documentos:**
- `vencido` → días_restantes < 0
- `critico` → 0–7 días
- `urgente` → 8–15 días
- `proximo` → 16–30 días

**Tablas adicionales cargadas:**
- `odometer_readings` — 12 registros de kilometraje por vehículo (fuente: conductor, GPS, taller)
- `alerts` — 12 alertas preconfiguradas (docs vencidos, llantas críticas, mantenimiento), ordenadas por nivel: Crítica → Alta → Media → Baja

**Endpoints adicionales:**
- `GET /api/vehicles/{vehiculo_id}/odometer` — historial de kilometraje
- `GET /api/alerts` — panel de alertas consolidado (filtrable por `vehiculo_id` y `estado`)

### ✅ Módulo 4 — Motor inteligente de consulta (COMPLETADO)

El motor orquesta RAG + SQL y conecta todo al endpoint `POST /chat`.

**Archivos creados en este módulo:**

| Archivo | Responsabilidad |
|---|---|
| `backend/schemas.py` | Modelos Pydantic: `ChatRequest`, `ChatResponse`, `Filtros`, `Metricas`, `SourceReference` |
| `backend/context_builder.py` | Formatea RAG + SQL en texto estructurado para el LLM |
| `backend/response_generator.py` | Llamada al LLM desacoplada; system prompt de GuruMaster Carga |
| `backend/guardrails.py` | Advertencias cuando falta evidencia documental o datos SQL |

**Archivos modificados:**

| Archivo | Cambio |
|---|---|
| `backend/intent_classifier.py` | Reescrito con LLM (GPT-4o-mini) + extracción de entidades; fallback a keywords |
| `backend/sql_service.py` | Agregadas: `query_trips_filtered`, `query_gastos_filtered`, `query_activos_context`, `query_vehicle_id_by_placa` |
| `backend/chat_service.py` | Reescrito: orquesta clasificador → RAG → SQL → contexto → LLM → guardrails |

**Contrato del endpoint `POST /chat` (nuevo schema):**

```json
// Request
{
  "pregunta": "ABC123 fue rentable en mayo",
  "usuario": "demo",
  "filtros": {
    "vehiculo_id": "V001",      // opcional — también se extrae de la pregunta
    "fecha_inicio": "2026-05-01",
    "fecha_fin": "2026-05-31"
  }
}

// Response
{
  "respuesta": "Sí. El vehículo ABC123 tuvo una utilidad de $7,030,000 COP...",
  "intencion": "financiera",
  "confianza": 0.90,
  "fuentes": [
    { "tipo": "sql", "nombre": "trips + trip_expenses" }
  ],
  "datos_consultados": [
    { "tipo": "sql", "nombre": "trips + trip_expenses" }
  ],
  "metricas": {
    "ingreso": 18900000,
    "gastos": 11870000,
    "utilidad": 7030000,
    "margen_pct": 37.2
  },
  "advertencias": []
}
```

**Clasificador de intención (LLM-based):**

- Usa `gpt-4o-mini` con `response_format: json_object` — entiende lenguaje natural colombiano, coloquialismos, falta de tildes, sinónimos
- Extrae entidades: `placa` (formato colombiano ABC123 / ABC-123) y fechas relativas (`"este mes"`, `"la semana pasada"`, `"mayo"`) resueltas a fechas ISO
- La placa extraída de la pregunta se resuelve automáticamente a `vehiculo_id` via `query_vehicle_id_by_placa`
- Los filtros explícitos del request tienen prioridad sobre las entidades extraídas
- Fallback a keywords si el LLM no responde

**Rutas de fuentes por intención:**

| Intención | RAG | SQL |
|---|---|---|
| `normativa` | normatividad (4) + costos_operativos (2) | — |
| `financiera` | costos_operativos (3) | `query_trips_filtered` + `query_gastos_filtered` + `query_vehicle_profitability` |
| `activos` | gestion_activos (3) | `query_activos_context` (alertas + docs + mantenimiento) |
| `mixta` | todos los pilares (6) | financiero + activos |

**Formateo del contexto para el LLM (`context_builder.py`):**

- RAG: muestra título + % de relevancia por chunk
- Financiero: resumen narrativo con COP, gastos desglosados por categoría, tabla compacta de viajes
- Activos: alertas ordenadas por nivel, documentos con días restantes calculados, últimos mantenimientos
- T2SQL: resultados de query dinámico van PRIMERO en el contexto para evitar truncado
- Trunca a 6,000 chars (aumentado de 4,500) si el contexto supera el límite

**Text-to-SQL (`backend/text_to_sql.py`):**
- GPT-4o-mini genera SELECT queries dinámicas para preguntas analíticas de flota sin `vehiculo_id`
- Se activa cuando `intencion in ("financiera", "activos", "mixta")` y no hay vehículo específico
- Seguridad: solo permite SELECT; bloquea INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/ATTACH/PRAGMA
- El LLM recibe schema completo (columnas exactas via `PRAGMA table_info`) para evitar errores
- Resultado se agrega a `sql_data["query_dinamico"]` y se incluye en `datos_panel`

**Nuevo campo `datos_panel` en ChatResponse:**
- Lleva datos estructurados (listas de dicts) al frontend para renderizado en tablas
- `tipo: "financiero"` → `viajes[]`, `rentabilidad`, `resumen`, `query_dinamico`
- `tipo: "activos"` → `mantenimientos[]`, `documentos[]`, `alertas[]`, `documentos_por_vencer[]`, `flota[]`
- Cuando `panel_disponible=True`, el LLM usa un template corto (2-3 líneas + "→ Ver detalle en el panel central")

**Decisiones de diseño del Módulo 4:**
- Se mantienen 4 intenciones (no se expandió a 9) para el MVP
- `llantas` se maneja vía intención `activos` → tablas `maintenance_events` + `alerts`
- El LLM nunca genera SQL predefinido; T2SQL solo para queries analíticos de flota
- 2 llamadas LLM por `/chat`: clasificador + generador de respuesta (3 cuando T2SQL activo)
- `query_vehicle_profitability` filtra gastos por viajes completados (consistencia con ingresos)

### ✅ Módulo 5 — Frontend (COMPLETADO + ACTUALIZADO)

**Archivo:** `frontend/GuruMaster.html` — single-file React 18 (CDN + Babel Standalone).

**Para abrir:** doble clic en `iniciar_gurumaster.bat` — levanta el backend y abre `http://localhost:8000` en el navegador. El frontend se sirve directamente desde FastAPI (sin CORS, misma origin).

**Arranque:**
- `iniciar_gurumaster.bat` — mata cualquier proceso en puerto 8000, arranca uvicorn, abre navegador
- Backend sirve el HTML en `GET /` vía `FileResponse(FRONTEND_DIR / "GuruMaster.html")`

**Layout — 3 paneles:**

| Panel | Ancho | Contenido |
|---|---|---|
| Izquierdo | 370px | Chat: mensajes, input, chips de sugerencias |
| Central | flex | Tabs: Evidencia / Financiero / Activos |
| Derecho | 268px | KPIs, vehículo activo, resumen alertas, fleet list |

**Header:**
- Logo GuruMaster Carga Colombia
- Pill de estado del backend (verde/rojo — llama `GET /health` al cargar)
- Selector de placa (dropdown ABC123/DEF456/GHI789/JKL321/MNO654) — se auto-selecciona cuando el usuario menciona una placa en la pregunta (regex `[A-Z]{3}-?[0-9]{3}` sobre el texto del usuario antes de enviar)
- Toggle dark/light mode

**Chat (panel izquierdo):**
- `POST /chat` con payload `{pregunta, filtros: {vehiculo_id}}` (vehiculo_id incluido si hay vehículo seleccionado)
- Loading dots (animación dot-blink) mientras espera respuesta
- Cada mensaje Guru muestra: respuesta formateada con `GuruText` + badge de intención coloreado (`normativa`/`financiera`/`activos`/`mixta`) + % confianza + conteo de fuentes
- Warning banners para `advertencias[]` del backend
- Burbujas de error con estilo diferenciado si el fetch falla
- 3 chips de sugerencias rápidas en el footer (primeras 3 de SUGGESTIONS)

**Panel central — 3 tabs (se cambia automáticamente según intención de la respuesta):**
- **Evidencia** (activa para `normativa`): fuentes documentales del campo `fuentes[]` — título, pilar, primeros 300 chars del contenido
- **Financiero** (activa para `financiera`/`mixta`): 4 KPI cards (Ingresos/Gastos/Utilidad/Margen) + tabla de viajes con columnas fecha/placa/ruta/ingreso/estado + tabla T2SQL (query dinámico) con headers generados automáticamente desde las columnas del resultado
- **Activos** (activa para `activos`): tabla de historial de mantenimientos + tabla de documentos con badges de días (colores por urgencia: rojo=vencido/critico, naranja=urgente, amarillo=proximo, verde=vigente) + tabla de docs próximos a vencer de toda la flota; fallback a alertas genéricas si no hay `datos_panel`

**Filosofía UI (split chat/panel):**
- Chat (izquierdo): respuesta LLM corta de 2-3 líneas con número clave + "→ Ver detalle en el panel central"
- Panel central: datos estructurados completos en tablas, renderizados directamente desde `datos_panel` sin pasar por el LLM

**Panel derecho:**
- KPI rows de la última respuesta con métricas (colores: teal=ingresos, rojo=gastos, verde/rojo según signo para utilidad y margen)
- Vehículo activo (placa, tipo, marca) si hay selección
- Resumen de alertas agrupadas por nivel (vencido/critico/urgente/proximo) con conteo y colores
- 3 sugerencias adicionales clickeables (últimas 3 de SUGGESTIONS) que envían la pregunta al chat
- Fleet list: 5 vehículos con placa + marca, clickeables para seleccionar

**Design system — idéntico al original:**
- Mismas variables CSS: `--base`, `--surface`, `--raised`, `--border`, `--teal`, `--ink-1/2/3`, `--warn`, `--danger`, `--shadow-sm/md/lg`, `--r-sm/md/lg/xl`
- Mismas fuentes: Inter (UI) + IBM Plex Mono (datos/placas)
- Dark mode vía `[data-theme="dark"]` en `<html>`
- Animaciones: `slide-up`, `fade-in`, `dot-blink`, `pulse-live`
- Componentes reutilizados: `Icon` (Lucide CDN), `GuruText` (markdown-lite), `LogoMark` (SVG hexagonal)
- TweaksPanel simplificado (solo toggle dark mode, draggable)

**Decisiones de diseño del Módulo 5:**
- No hay datos mock — todo viene del backend real (si el backend está offline, muestra error en burbuja con instrucciones de arranque)
- No hay selector de pilar — la IA clasifica la intención automáticamente
- La placa del selector se incluye como `filtros.vehiculo_id` en el payload de `/chat`; la placa extraída por el LLM del texto de la pregunta tiene menor prioridad que el filtro explícito
- El tab activo del panel central cambia automáticamente según `intencion` de la respuesta
- El campo `fuentes[].contenido` viene truncado a 300 chars desde `chat_service.py`
- Frontend servido desde FastAPI (mismo origen) — no se abre como `file://`; eliminado el problema de CORS con `null` origin

### Frontend MVP

- `frontend/GuruMaster.html` — Dashboard React single-file. Servido por FastAPI en `GET /`. Chat muestra resumen corto; panel central muestra tablas detalladas desde `datos_panel`.
- `iniciar_gurumaster.bat` — Script de arranque único: mata proceso en :8000, lanza uvicorn, abre navegador.

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

**Backend — Motor de consulta (Módulo 4):**
- `backend/schemas.py` — Pydantic: `ChatRequest`, `ChatResponse` (incluye `datos_panel: Optional[dict]`), `Filtros`, `Metricas`, `SourceReference`
- `backend/intent_classifier.py` — `classify_intent(msg) → (str, float, dict)`: LLM-based, extrae placa + fechas, fallback a keywords
- `backend/context_builder.py` — `build_context(rag_docs, sql_data) → str`: T2SQL primero, límite 6,000 chars
- `backend/response_generator.py` — `generate_response(pregunta, context, panel_disponible) → str`: template corto cuando hay panel
- `backend/guardrails.py` — `check(...) → list[str]`: advertencias por ausencia de fuentes o datos
- `backend/chat_service.py` — orquestador: clasificador → RAG → SQL → T2SQL → datos_panel → LLM
- `backend/text_to_sql.py` — `run_text_to_sql(pregunta) → dict`: GPT-4o-mini genera SELECT; solo para queries de flota sin vehiculo_id; bloquea comandos peligrosos

**Backend — Datos estructurados (Módulos 2 y 3):**
- `backend/main.py` — FastAPI app; sirve frontend en `GET /` vía FileResponse; CORS middleware que hace echo del origin (maneja `null`); `uvicorn main:app --port 8000` desde `/backend`
- `backend/sql_service.py` — todas las consultas SQLite; `query_vehicle_profitability` filtra gastos por viajes completados
- `backend/init_db.py` — crea schema y carga todos los CSVs de seed data

**Backend — RAG (Módulo 1):**
- `backend/document_loader.py` — Extrae texto por página (PDF/DOCX/HTML/TXT), genera JSONL
- `backend/build_vector_index.py` — chunking 800 chars + embeddings MiniLM + ChromaDB
- `backend/rag_service.py` — `search_documents(query, pillar, n_results)` sobre ChromaDB

**Datos:**
- `data/processed_text/processed_all.jsonl` — 634 páginas extraídas de los 3 documentos
- `data/documents/normatividad/` — Decreto 1079 + Manual RNDC
- `data/documents/costos_operativos/` — ABC_SICE_TAC.txt
- `data/seed_*.csv` — CSVs de seed data: viajes, gastos, vehículos, documentos, odómetro, alertas

**DB:**
- `db/chroma/` — 2,311 chunks indexados (modelo: paraphrase-multilingual-MiniLM-L12-v2)
- `db/gurumaster_carga.sqlite` — SQLite con 9 tablas y seed data de mayo 2026

**Vehículos en la demo (para referencia en preguntas de prueba):**
| vehiculo_id | placa | tipo | marca |
|---|---|---|---|
| V001 | ABC123 | Tractocamion | Kenworth |
| V002 | DEF456 | Camion sencillo | Hino |
| V003 | GHI789 | Doble troque | Chevrolet |
| V004 | JKL321 | Turbo | NPR |
| V005 | MNO654 | Tractocamion | Freightliner |

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

## Bugs corregidos (sesión 2026-06-07)

| Bug | Causa raíz | Fix |
|---|---|---|
| Métricas inconsistentes (LLM decía -$3.15M, UI mostraba +$7M) | `query_vehicle_profitability` filtraba ingresos por viajes completados pero gastos de todos los viajes | Agregar `JOIN trips t ON e.viaje_id = t.viaje_id WHERE t.estado_viaje = 'Completado'` en el query de gastos |
| Flota mostraba 3 vehículos en lugar de 5 | `query_activos_context` sin `vehiculo_id` solo retornaba alertas (3 vehículos con alertas) | Agregar `flota = query_vehicles()` al contexto de activos cuando no hay vehículo específico |
| CORS bloqueado desde `file://` | `file://` envía `Origin: null`; el header `Access-Control-Allow-Origin: *` Chrome lo rechaza para null origin | Middleware custom que hace echo del origin recibido (incluyendo `null`) |
| Error 500 en mantenimiento de ABC123 | `dias_restantes` puede ser `None` para documentos sin fecha; `dias < 0` lanzaba `TypeError` | Guard `if dias is None: estado_str = "Sin fecha"` en `context_builder.py` |
| T2SQL truncado en intención mixta | Con límite 4,500 chars y contexto RAG + activos + financiero, el bloque T2SQL quedaba fuera | Mover T2SQL a primera posición en `_format_sql()` + subir límite a 6,000 |
| Puerto 8000 ya en uso al relanzar | Proceso anterior seguía corriendo | `iniciar_gurumaster.bat` mata el proceso en :8000 antes de arrancar |

## Próximos pasos — Mejoras visuales (prioridad alta)

El MVP está funcional. La siguiente iteración debe continuar mejorando la salida visual de respuestas:

1. **Panel central — Financiero:** agregar gráfico de barras (recharts o Chart.js CDN) para gastos por categoría del vehículo
2. **Panel central — Activos:** mostrar odómetro del vehículo activo + próximo mantenimiento por km
3. **Panel central — T2SQL:** mejorar renderizado de tablas dinámicas (formatear moneda automáticamente cuando la columna contiene "valor", "ingreso", "gasto", "total")
4. **Chat:** agregar indicador visual del tipo de consulta que está procesando ("Consultando documentos... / Analizando datos SQL... / Generando respuesta...")
5. **RAG — gestion_activos:** agregar documentos (guías SOAT, tecnomecánica, pólizas) para mejorar respuestas en preguntas de activos
6. **Panel derecho:** agregar mini-chart de tendencia de margen (últimos 30 días) usando datos de `GET /api/analytics/monthly-summary`
