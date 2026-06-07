"""Construye el contexto que recibe el LLM combinando evidencia documental y datos operativos.

Cada sección tiene su propio formateador para que el LLM reciba texto
estructurado y legible, no volcados de dicts.
"""

MAX_CONTEXT_CHARS = 6000


def build_context(rag_docs: list[dict], sql_data: dict) -> str:
    parts = []

    if rag_docs:
        parts.append(_format_rag(rag_docs))

    if sql_data:
        sql_section = _format_sql(sql_data)
        if sql_section:
            parts.append(sql_section)

    if not parts:
        return "No se encontró información relevante para esta pregunta."

    context = "\n\n---\n\n".join(parts)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n\n[Contexto truncado por límite de tokens]"

    return context


# ── RAG ──────────────────────────────────────────────────────────────────────

def _format_rag(docs: list[dict]) -> str:
    lines = ["=== EVIDENCIA DOCUMENTAL ==="]
    for i, doc in enumerate(docs, 1):
        score_pct = int(doc.get("score", 0) * 100)
        lines.append(
            f"[Doc {i} | {doc['title']} | relevancia {score_pct}%]\n{doc['content']}"
        )
    return "\n\n".join(lines)


# ── SQL ───────────────────────────────────────────────────────────────────────

def _format_sql(sql_data: dict) -> str:
    sections = []

    # T2SQL va primero: es el dato más específico para la pregunta actual
    if "query_dinamico" in sql_data:
        sections.append(_fmt_query_dinamico(sql_data["query_dinamico"]))

    if "resumen_financiero" in sql_data:
        sections.append(_fmt_resumen_financiero(sql_data["resumen_financiero"]))

    if "viajes" in sql_data:
        sections.append(_fmt_viajes(sql_data["viajes"]))

    if "rentabilidad_vehiculo" in sql_data:
        sections.append(_fmt_rentabilidad_vehiculo(sql_data["rentabilidad_vehiculo"]))

    if "activos" in sql_data:
        sections.append(_fmt_activos(sql_data["activos"]))

    if not sections:
        return ""

    return "=== DATOS OPERATIVOS ===\n\n" + "\n\n".join(sections)


def _cop(v) -> str:
    """Formatea un valor numérico como pesos colombianos."""
    if v is None:
        return "$0"
    return f"${float(v):,.0f} COP"


def _fmt_resumen_financiero(r: dict) -> str:
    lines = ["RESUMEN FINANCIERO:"]
    lines.append(f"  Ingresos totales : {_cop(r.get('ingresos'))}")

    gastos = r.get("gastos_detalle") or {}
    if gastos:
        lines.append("  Gastos por categoría:")
        for tipo, total in sorted(gastos.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"    • {tipo}: {_cop(total)}")

    lines.append(f"  Total gastos     : {_cop(r.get('total_gastos'))}")
    lines.append(f"  Utilidad         : {_cop(r.get('utilidad'))}")
    lines.append(f"  Margen           : {r.get('margen_pct', 0)}%")
    return "\n".join(lines)


def _fmt_viajes(trips: list[dict]) -> str:
    if not trips:
        return "VIAJES: Sin registros en el período consultado."
    lines = [f"VIAJES ({len(trips)} registros):"]
    for t in trips[:12]:
        origen  = t.get("ciudad_origen", "?")
        destino = t.get("ciudad_destino", "?")
        ingreso = _cop(t.get("ingreso"))
        lines.append(
            f"  {t.get('fecha_viaje','')}  {t.get('vehiculo_id','')}  "
            f"{origen}->{destino}  {ingreso}  "
            f"{t.get('nombre_cliente','')}  [{t.get('estado_viaje','')}]"
        )
    return "\n".join(lines)


def _fmt_rentabilidad_vehiculo(r: dict) -> str:
    placa = r.get("placa") or r.get("vehiculo_id", "?")
    lines = [
        f"RENTABILIDAD VEHÍCULO {placa} ({r.get('tipo_vehiculo', '')}):",
        f"  Viajes completados : {r.get('total_viajes', 0)}",
        f"  Ingresos brutos    : {_cop(r.get('ingresos_brutos'))}",
        f"  Gastos operativos  : {_cop(r.get('gastos_total'))}",
        f"  Utilidad neta      : {_cop(r.get('utilidad'))}",
        f"  Margen             : {r.get('margen_pct', 0)}%",
    ]
    gastos = r.get("gastos_operativos") or {}
    if gastos:
        lines.append("  Detalle gastos:")
        for tipo, total in sorted(gastos.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"    • {tipo}: {_cop(total)}")
    return "\n".join(lines)


def _fmt_activos(activos: dict) -> str:
    lines = []

    flota = activos.get("flota") or []
    if flota:
        lines.append(f"FLOTA TOTAL ({len(flota)} vehículos):")
        for v in flota:
            lines.append(
                f"  {v.get('placa','')} — {v.get('tipo_vehiculo','')} {v.get('marca','')} "
                f"{v.get('modelo','')} — Estado: {v.get('estado','')}"
            )

    alerts = activos.get("alertas_sistema") or []
    if alerts:
        lines.append(f"ALERTAS ACTIVAS ({len(alerts)}):")
        for a in alerts[:6]:
            lines.append(
                f"  [{a.get('nivel_alerta','?').upper()}] "
                f"{a.get('placa','')} — {a.get('tipo_alerta','')} — "
                f"{a.get('descripcion','')} (límite: {a.get('fecha_limite','')})"
            )

    doc_alerts = activos.get("documentos_por_vencer") or []
    if doc_alerts:
        lines.append(f"\nDOCUMENTOS PRÓXIMOS A VENCER ({len(doc_alerts)}):")
        for d in doc_alerts:
            dias = d.get("dias_restantes")
            if dias is None:
                estado_str = "Sin fecha"
            else:
                estado_str = "VENCIDO" if dias < 0 else f"vence en {dias} días"
            lines.append(
                f"  [{d.get('urgencia','?').upper()}] {d.get('placa','')} — "
                f"{d.get('tipo_documento','')} — {estado_str} ({d.get('fecha_vencimiento','')})"
            )

    docs_veh = activos.get("documentos_vehiculo") or []
    if docs_veh:
        lines.append("\nDOCUMENTOS DEL VEHÍCULO:")
        for d in docs_veh:
            dias = d.get("dias_restantes")
            if dias is None:
                estado_str = "Sin fecha"
            else:
                estado_str = "VENCIDO" if dias < 0 else f"{dias} días restantes"
            lines.append(
                f"  {d.get('tipo_documento','')} — "
                f"{d.get('estado','')} — {estado_str}"
            )

    maintenance = activos.get("ultimos_mantenimientos") or []
    if maintenance:
        lines.append("\nÚLTIMOS MANTENIMIENTOS:")
        for m in maintenance:
            lines.append(
                f"  [{m.get('fecha_mantenimiento','')}] "
                f"{m.get('categoria_mantenimiento','')} "
                f"({m.get('tipo_mantenimiento','')}) — "
                f"{_cop(m.get('valor'))} — {m.get('proveedor','')}"
            )

    return "\n".join(lines) if lines else "Sin datos de activos disponibles."


def _fmt_query_dinamico(r: dict) -> str:
    if r.get("error"):
        return f"CONSULTA DINÁMICA (error al ejecutar): {r['error']}"

    filas = r.get("filas", [])
    if not filas:
        return "CONSULTA DINÁMICA: Sin resultados."

    lines = [f"CONSULTA DINÁMICA ({r.get('total', 0)} filas):"]
    keys = list(filas[0].keys())
    lines.append("  " + " | ".join(keys))
    lines.append("  " + "-" * min(80, len(" | ".join(keys)) + 2))
    for row in filas[:15]:
        values = " | ".join(
            f"{v:,.0f}" if isinstance(v, float) else str(v if v is not None else "—")
            for v in row.values()
        )
        lines.append(f"  {values}")
    return "\n".join(lines)
