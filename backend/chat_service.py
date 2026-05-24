from fastapi import APIRouter

from context_builder import build_context
from guardrails import check
from intent_classifier import classify_intent
from rag_service import search_documents
from response_generator import generate_response
from schemas import ChatRequest, ChatResponse, Filtros, Metricas, SourceReference
from sql_service import (
    query_activos_context,
    query_gastos_filtered,
    query_trips_filtered,
    query_vehicle_id_by_placa,
    query_vehicle_profitability,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    f: Filtros = req.filtros or Filtros()
    intencion, confianza, entidades = classify_intent(req.pregunta)

    # Filtros explícitos tienen prioridad; las entidades extraídas del LLM los complementan
    placa_extraida = entidades.get("placa")
    vehiculo_id = (
        f.vehiculo_id
        or (query_vehicle_id_by_placa(placa_extraida) if placa_extraida else None)
    )
    fecha_inicio = f.fecha_inicio or entidades.get("fecha_inicio")
    fecha_fin    = f.fecha_fin    or entidades.get("fecha_fin")

    rag_docs: list[dict] = []
    sql_data: dict = {}
    fuentes: list[SourceReference] = []
    datos_consultados: list[dict] = []
    metricas: Metricas | None = None

    # --- RAG ---
    if intencion == "normativa":
        rag_docs = (
            search_documents(req.pregunta, pillar="normatividad", n_results=4)
            + search_documents(req.pregunta, pillar="costos_operativos", n_results=2)
        )
    elif intencion == "financiera":
        rag_docs = search_documents(req.pregunta, pillar="costos_operativos", n_results=3)
    elif intencion == "activos":
        rag_docs = search_documents(req.pregunta, pillar="gestion_activos", n_results=3)
    else:  # mixta
        rag_docs = search_documents(req.pregunta, n_results=6)

    for d in rag_docs:
        fuentes.append(SourceReference(
            tipo="documento",
            nombre=d["title"],
            pilar=d.get("pillar"),
            contenido=d["content"][:300],
        ))

    # --- SQL financiero ---
    if intencion in ("financiera", "mixta"):
        trips = query_trips_filtered(vehiculo_id, fecha_inicio, fecha_fin)
        gastos = query_gastos_filtered(vehiculo_id, fecha_inicio, fecha_fin)
        sql_data["viajes"] = trips
        sql_data["resumen_financiero"] = gastos
        datos_consultados.append({"tipo": "sql", "nombre": "trips + trip_expenses"})
        fuentes.append(SourceReference(tipo="sql", nombre="trips + trip_expenses"))

        if vehiculo_id:
            veh_prof = query_vehicle_profitability(vehiculo_id)
            if veh_prof:
                sql_data["rentabilidad_vehiculo"] = veh_prof
                datos_consultados.append({"tipo": "sql", "nombre": "rentabilidad_vehiculo"})

        if gastos["ingresos"] > 0:
            metricas = Metricas(
                ingreso=gastos["ingresos"],
                gastos=gastos["total_gastos"],
                utilidad=gastos["utilidad"],
                margen_pct=gastos["margen_pct"],
            )

    # --- SQL activos ---
    if intencion in ("activos", "mixta"):
        activos = query_activos_context(vehiculo_id)
        sql_data["activos"] = activos
        datos_consultados.append({"tipo": "sql", "nombre": "alerts + vehicle_documents + maintenance_events"})
        fuentes.append(SourceReference(tipo="sql", nombre="gestión de activos"))

    # --- Contexto + respuesta ---
    context = build_context(rag_docs, sql_data)
    respuesta = generate_response(req.pregunta, context)

    advertencias = check(respuesta, intencion, has_rag_sources=bool(rag_docs), has_sql_data=bool(sql_data))

    return ChatResponse(
        respuesta=respuesta,
        intencion=intencion,
        confianza=confianza,
        fuentes=fuentes,
        datos_consultados=datos_consultados,
        metricas=metricas,
        advertencias=advertencias,
    )
