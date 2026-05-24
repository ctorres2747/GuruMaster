def check(
    respuesta: str,
    intencion: str,
    has_rag_sources: bool,
    has_sql_data: bool,
) -> list[str]:
    advertencias = []

    if intencion == "normativa" and not has_rag_sources:
        advertencias.append(
            "No se encontró evidencia documental. La respuesta puede ser incompleta."
        )

    if intencion in ("financiera", "mixta") and not has_sql_data:
        advertencias.append(
            "No se encontraron datos operativos en la base de datos para esta consulta."
        )

    if intencion == "activos" and not has_sql_data:
        advertencias.append(
            "No se encontraron datos de activos o alertas en la base de datos."
        )

    if not respuesta or len(respuesta.strip()) < 20:
        advertencias.append("La respuesta generada fue inesperadamente corta.")

    return advertencias
