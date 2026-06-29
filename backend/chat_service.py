from fastapi import APIRouter

from context_builder import build_context
from guardrails import check
from intent_classifier import classify_intent
from rag_service import search_documents
from response_generator import generate_response
from schemas import ChatRequest, ChatResponse, Filtros, Metricas, SourceReference
from sql_service import (
    query_activos_context,
    query_doc_risk_summary,
    query_fleet_kpis,
    query_gastos_filtered,
    query_trips_filtered,
    query_vehicle_id_by_placa,
    query_vehicle_profitability,
)
from text_to_sql import run_text_to_sql

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
        sql_data["viajes"] = trips
        datos_consultados.append({"tipo": "sql", "nombre": "trips + trip_expenses"})
        fuentes.append(SourceReference(tipo="sql", nombre="trips + trip_expenses"))

        if vehiculo_id:
            # Consulta por vehículo específico: usar veh_prof como fuente única
            # (income y expenses filtrados por viajes completados — consistente)
            veh_prof = query_vehicle_profitability(vehiculo_id)
            if veh_prof:
                sql_data["rentabilidad_vehiculo"] = veh_prof
                datos_consultados.append({"tipo": "sql", "nombre": "rentabilidad_vehiculo"})
                metricas = Metricas(
                    ingreso=veh_prof["ingresos_brutos"],
                    gastos=veh_prof["gastos_total"],
                    utilidad=veh_prof["utilidad"],
                    margen_pct=veh_prof["margen_pct"],
                )
        else:
            # Consulta de flota general: usar resumen financiero agregado
            gastos = query_gastos_filtered(vehiculo_id, fecha_inicio, fecha_fin)
            sql_data["resumen_financiero"] = gastos
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

    # --- Text-to-SQL dinámico ---
    # Se activa cuando la pregunta es de flota general (sin vehículo específico)
    # o cuando la intención es mixta — complementa los queries predefinidos.
    usar_t2sql = intencion in ("financiera", "activos", "mixta") and not vehiculo_id
    if usar_t2sql:
        t2sql = run_text_to_sql(req.pregunta)
        if t2sql and t2sql.get("filas"):
            sql_data["query_dinamico"] = t2sql
            datos_consultados.append({"tipo": "sql_dinamico", "nombre": "text-to-sql"})

    # --- Construir datos_panel para el panel central ---
    datos_panel: dict | None = None

    if intencion == "activos" and sql_data.get("activos"):
        a = sql_data["activos"]
        viz_spec_activos = entidades.get("viz_spec")
        datos_panel = {
            "tipo": "activos",
            "vehiculo_id": vehiculo_id,
            "mantenimientos": a.get("ultimos_mantenimientos") or [],
            "documentos": a.get("documentos_vehiculo") or [],
            "alertas": a.get("alertas_sistema") or [],
            "documentos_por_vencer": a.get("documentos_por_vencer") or [],
            "flota": a.get("flota") or [],
            "viz_spec": viz_spec_activos,
        }
    elif intencion in ("financiera", "mixta"):
        viz_spec = entidades.get("viz_spec")
        needs_fleet = (
            not vehiculo_id
            and isinstance(viz_spec, dict)
            and viz_spec.get("data_key") == "fleet_kpis"
        )
        datos_panel = {
            "tipo": "financiero",
            "vehiculo_id": vehiculo_id,
            "viajes": sql_data.get("viajes") or [],
            "rentabilidad": sql_data.get("rentabilidad_vehiculo"),
            "resumen": sql_data.get("resumen_financiero"),
            "query_dinamico": sql_data.get("query_dinamico"),
            "viz_spec": viz_spec,
        }
        if intencion == "mixta":
            if sql_data.get("activos"):
                alertas = sql_data["activos"].get("alertas_sistema") or []
                datos_panel["alertas_criticas"] = [
                    a for a in alertas if a.get("nivel_alerta") in ("Critica", "Alta")
                ][:6]
            if not vehiculo_id:
                datos_panel["fleet_kpis"] = query_fleet_kpis()
                datos_panel["doc_risk"] = query_doc_risk_summary()
        elif needs_fleet:
            datos_panel["fleet_kpis"] = query_fleet_kpis()

    panel_disponible = datos_panel is not None and bool(sql_data)

    # --- Contexto + respuesta ---
    context = build_context(rag_docs, sql_data)
    respuesta = generate_response(req.pregunta, context, panel_disponible=panel_disponible)

    advertencias = check(respuesta, intencion, has_rag_sources=bool(rag_docs), has_sql_data=bool(sql_data))

    return ChatResponse(
        respuesta=respuesta,
        intencion=intencion,
        confianza=confianza,
        fuentes=fuentes,
        datos_consultados=datos_consultados,
        metricas=metricas,
        advertencias=advertencias,
        datos_panel=datos_panel,
    )
