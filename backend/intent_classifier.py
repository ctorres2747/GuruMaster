NORMATIVA_KEYWORDS = [
    "rndc", "manifiesto", "despacho", "decreto", "normatividad",
    "reglamento", "ministerio", "registrar", "requisito", "permiso",
    "habilitación", "licencia", "obligatorio", "exigido", "legal",
    "sice-tac", "sicetac", "costo eficiente", "costo mínimo", "flete mínimo",
]

FINANCIERA_KEYWORDS = [
    "rentable", "ingreso", "gasto", "combustible", "peaje", "margen",
    "utilidad", "viaje", "ruta", "ganancia", "tarifa",
    "gasté", "cuánto gasté", "cuánto ingresé", "presupuesto", "cuánto cobré",
]

ACTIVOS_KEYWORDS = [
    "vehículo", "placa", "soat", "tecnomecánica", "póliza", "vence",
    "mantenimiento", "vencimiento", "flota", "camión", "tractocamión",
]


def classify_intent(message: str) -> str:
    msg = message.lower()
    hits = {
        "normativa": sum(1 for k in NORMATIVA_KEYWORDS if k in msg),
        "financiera": sum(1 for k in FINANCIERA_KEYWORDS if k in msg),
        "activos":    sum(1 for k in ACTIVOS_KEYWORDS if k in msg),
    }

    total = sum(hits.values())
    if total == 0:
        return "normativa"

    ranked      = sorted(hits.items(), key=lambda x: x[1], reverse=True)
    top_name, top_hits   = ranked[0]
    second_hits          = ranked[1][1]

    if top_hits > second_hits:
        return top_name

    return "mixta"
