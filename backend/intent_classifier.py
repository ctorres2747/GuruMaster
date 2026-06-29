"""Clasifica la intención de una pregunta y extrae entidades usando LLM.

Retorna siempre (intencion, confianza, entidades) para que el orquestador
pueda auto-poblar filtros desde la pregunta, sin que el usuario los indique.
"""
import json
import os
import re
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_SYSTEM_PROMPT = """\
Eres el clasificador de intenciones de GuruMaster Carga Colombia.

INTENCIONES DISPONIBLES:
- normativa: leyes, decretos, RNDC, manifiestos de carga, requisitos legales,
  habilitaciones, registros oficiales, SICE-TAC como norma de referencia
- financiera: rentabilidad, ingresos, gastos, combustible, peajes, márgenes,
  utilidad, tarifas, costos de un viaje, cuánto se ganó o gastó
- activos: vehículos, placas, SOAT, RTM, tecnomecánica, pólizas, mantenimiento,
  llantas, neumáticos, alertas, vencimientos, estado de la flota
- mixta: combina dos o más intenciones anteriores. ÚSALA cuando la pregunta pide
  un resumen general, KPIs, indicadores, dashboard, panorama o rendimiento de la
  flota sin especificar solo financiero o solo activos. Ejemplos: "KPIs de mi
  flota", "cómo va mi negocio", "resumen del mes", "cómo está la flota"

ENTIDADES A EXTRAER:
- placa: placa del vehículo si se menciona (formato colombiano: ABC123 o ABC-123).
  Extrae solo la placa, sin guiones.
- fecha_inicio / fecha_fin: período consultado en formato ISO 8601 (YYYY-MM-DD).
  Resuelve expresiones relativas usando la fecha actual {today}:
  "este mes" → primer y último día del mes actual
  "el mes pasado" → primer y último día del mes anterior
  "hoy" → {today}
  "mayo" → 2026-05-01 / 2026-05-31
  Si solo se menciona un mes sin rango, usa primer y último día de ese mes.

VIZ_SPEC — elige el gráfico más útil (o null si no aplica):
REGLAS ESTRICTAS (prioridad de arriba hacia abajo):
1. intencion normativa (ley, decreto, RNDC, manifiesto, requisito legal) → viz_spec: null
2. UN solo vehículo (placa presente) + pregunta por gastos/costos/combustible/peajes/distribución → type: "donut", data_key: "gastos_operativos", color: "danger"
3. Comparar vehículos o flota (comparar, versus, cuál rinde más, ingresos vs gastos por placa) → type: "composed", data_key: "fleet_kpis", color: "teal"
4. Tendencia en el tiempo (evolución, histórico, mes a mes, por fecha, últimos viajes) → type: "line" o "area", data_key: "viajes", color: "teal"
5. Ranking (mejor, peor, top, ranking, ordenar, quién ganó más) → type: "bar_h", data_key: "fleet_kpis", color: "warn"
6. Porcentaje o margen específico (margen de X, % utilidad, qué tan rentable en %) → type: "radial", data_key: "margen", color: "warn"
7. Caso financiero genérico sin regla anterior → type: "bar", data_key: "resumen", color: "teal"

TÍTULO (title): descriptivo en español colombiano, con placa y período cuando aplique.
Ejemplos buenos: "Gastos de ABC123 en mayo", "Margen de DEF456 en mayo 2026",
"Comparativo de ingresos por vehículo", "Evolución de ingresos en mayo".
Evita títulos genéricos como "Distribución de gastos" o "Gráfico financiero".

Responde ÚNICAMENTE con JSON válido, sin explicaciones:
{{"intencion": "...", "confianza": 0.0, "entidades": {{"placa": null, "fecha_inicio": null, "fecha_fin": null, "viz_spec": null}}}}

viz_spec cuando aplica:
{{"type": "donut", "title": "Gastos de ABC123 en mayo", "data_key": "gastos_operativos", "color": "danger"}}
"""

_MESES = (
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

_VALID_TYPES = {"donut", "composed", "line", "area", "bar_h", "radial", "bar", "pie"}
_VALID_DATA_KEYS = {"gastos_operativos", "viajes", "fleet_kpis", "margen", "resumen"}
_VALID_COLORS = {"teal", "danger", "warn"}

# Fallback basado en keywords cuando el LLM no está disponible
_FALLBACK = {
    "normativa": [
        "rndc", "manifiesto", "despacho", "decreto", "normatividad",
        "ministerio", "requisito", "licencia", "habilitación", "sice-tac",
    ],
    "financiera": [
        "rentable", "ingreso", "gasto", "combustible", "peaje", "margen",
        "utilidad", "viaje", "ganancia", "tarifa", "gasté", "cobré",
    ],
    "activos": [
        "vehículo", "placa", "soat", "tecnomecánica", "póliza", "mantenimiento",
        "llanta", "llantas", "alerta", "vencimiento",
    ],
    "mixta": [
        "kpi", "kpis", "indicador", "indicadores", "dashboard", "resumen",
        "panorama", "rendimiento", "cómo va", "como va", "cómo está la flota",
        "estado general", "visión general",
    ],
}

_GASTO_KW = ("gasto", "gastos", "gasté", "costo", "costos", "combustible", "peaje", "peajes", "distribución", "distribucion")
_COMPARE_KW = ("comparar", "comparativo", "versus", "vs", "entre vehículos", "entre vehiculos", "por vehículo", "por vehiculo", "cada placa", "flota")
_TREND_KW = ("tendencia", "evolución", "evolucion", "histórico", "historico", "mes a mes", "en el tiempo", "por fecha", "últimos viajes", "ultimos viajes", "a lo largo")
_RANK_KW = ("ranking", "mejor", "peor", "top", "ordenar", "quién ganó", "quien gano", "más rentable", "mas rentable", "mayor utilidad")
_MARGIN_KW = ("margen", "porcentaje", "por ciento", "%", "qué tan rentable", "que tan rentable", "en porcentaje")


def _format_period(fecha_inicio: str | None, fecha_fin: str | None) -> str:
    if fecha_inicio and fecha_fin and fecha_inicio[:7] == fecha_fin[:7]:
        try:
            month = int(fecha_inicio[5:7])
            year = fecha_inicio[:4]
            mes = _MESES[month] if 1 <= month <= 12 else fecha_inicio[5:7]
            return f"en {mes} {year}"
        except (ValueError, IndexError):
            pass
    if fecha_inicio and fecha_fin:
        return f"del {fecha_inicio} al {fecha_fin}"
    if fecha_inicio:
        return f"desde {fecha_inicio}"
    return ""


def _period_suffix(fecha_inicio: str | None, fecha_fin: str | None) -> str:
    period = _format_period(fecha_inicio, fecha_fin)
    return f" {period}".rstrip() if period else ""


def _build_viz_title(
    chart_type: str,
    data_key: str,
    placa: str | None,
    fecha_inicio: str | None,
    fecha_fin: str | None,
) -> str:
    period = _period_suffix(fecha_inicio, fecha_fin)
    placa_txt = placa.upper().replace("-", "") if placa else None

    if chart_type == "donut" and placa_txt:
        return f"Gastos de {placa_txt}{period}".strip()
    if chart_type == "radial" and placa_txt:
        return f"Margen de {placa_txt}{period}".strip()
    if chart_type == "radial":
        return f"Margen del período{period}".strip()
    if chart_type == "composed":
        return f"Comparativo de ingresos por vehículo{period}".strip()
    if chart_type == "bar_h":
        return f"Ranking de utilidad por vehículo{period}".strip()
    if chart_type in ("line", "area"):
        if placa_txt:
            return f"Evolución de ingresos de {placa_txt}{period}".strip()
        return f"Evolución de ingresos{period}".strip()
    if data_key == "gastos_operativos" and placa_txt:
        return f"Gastos de {placa_txt}{period}".strip()
    if placa_txt:
        return f"Resumen financiero de {placa_txt}{period}".strip()
    return f"Resumen financiero{period}".strip()


def _resolve_viz_spec(message: str, intencion: str, entidades: dict) -> dict | None:
    """Reglas determinísticas para viz_spec; complementa o corrige al LLM."""
    if intencion == "normativa":
        return None

    msg = message.lower()
    placa = entidades.get("placa")
    fecha_inicio = entidades.get("fecha_inicio")
    fecha_fin = entidades.get("fecha_fin")
    period = _period_suffix(fecha_inicio, fecha_fin)
    placa_txt = placa.upper().replace("-", "") if placa else None

    if any(w in msg for w in _MARGIN_KW):
        spec = {"type": "radial", "data_key": "margen", "color": "warn"}
        spec["title"] = _build_viz_title("radial", "margen", placa, fecha_inicio, fecha_fin)
        return spec

    if any(w in msg for w in _RANK_KW):
        spec = {"type": "bar_h", "data_key": "fleet_kpis", "color": "warn"}
        spec["title"] = _build_viz_title("bar_h", "fleet_kpis", placa, fecha_inicio, fecha_fin)
        return spec

    if any(w in msg for w in _TREND_KW):
        chart_type = "area" if any(w in msg for w in ("área", "area", "relleno")) else "line"
        spec = {"type": chart_type, "data_key": "viajes", "color": "teal"}
        spec["title"] = _build_viz_title(chart_type, "viajes", placa, fecha_inicio, fecha_fin)
        return spec

    if any(w in msg for w in _COMPARE_KW) or (not placa and "flota" in msg):
        spec = {"type": "composed", "data_key": "fleet_kpis", "color": "teal"}
        spec["title"] = _build_viz_title("composed", "fleet_kpis", placa, fecha_inicio, fecha_fin)
        return spec

    if placa_txt and any(w in msg for w in _GASTO_KW):
        spec = {"type": "donut", "data_key": "gastos_operativos", "color": "danger"}
        spec["title"] = f"Gastos de {placa_txt}{period}".strip()
        return spec

    if intencion in ("financiera", "mixta"):
        if placa_txt:
            spec = {"type": "donut", "data_key": "gastos_operativos", "color": "danger"}
            spec["title"] = f"Gastos de {placa_txt}{period}".strip()
            return spec
        spec = {"type": "composed", "data_key": "fleet_kpis", "color": "teal"}
        spec["title"] = _build_viz_title("composed", "fleet_kpis", placa, fecha_inicio, fecha_fin)
        return spec

    return None


def _normalize_viz_spec(raw: dict | None, message: str, intencion: str, entidades: dict) -> dict | None:
    if intencion == "normativa":
        return None

    fallback = _resolve_viz_spec(message, intencion, entidades)
    if not isinstance(raw, dict):
        return fallback

    chart_type = (raw.get("type") or "").lower().strip()
    if chart_type in ("null", "none", ""):
        return None if intencion == "normativa" else fallback

    if chart_type == "pie":
        chart_type = "donut"

    data_key = raw.get("data_key") or (fallback or {}).get("data_key", "resumen")
    color = raw.get("color") or (fallback or {}).get("color", "teal")
    if chart_type not in _VALID_TYPES:
        chart_type = (fallback or {}).get("type", "bar")
    if data_key not in _VALID_DATA_KEYS:
        data_key = (fallback or {}).get("data_key", "resumen")
    if color not in _VALID_COLORS:
        color = (fallback or {}).get("color", "teal")

    # Corregir desajustes frecuentes entre pregunta y elección del LLM
    msg = message.lower()
    placa = entidades.get("placa")
    if placa and any(w in msg for w in _GASTO_KW) and chart_type not in ("donut", "pie"):
        chart_type, data_key, color = "donut", "gastos_operativos", "danger"
    elif any(w in msg for w in _COMPARE_KW) and chart_type not in ("composed",):
        chart_type, data_key, color = "composed", "fleet_kpis", "teal"
    elif any(w in msg for w in _TREND_KW) and chart_type not in ("line", "area"):
        chart_type, data_key, color = "line", "viajes", "teal"
    elif any(w in msg for w in _RANK_KW) and chart_type != "bar_h":
        chart_type, data_key, color = "bar_h", "fleet_kpis", "warn"
    elif any(w in msg for w in _MARGIN_KW) and chart_type != "radial":
        chart_type, data_key, color = "radial", "margen", "warn"

    title = raw.get("title") or ""
    generic_titles = (
        "distribución de gastos", "distribucion de gastos", "gráfico financiero",
        "grafico financiero", "visualización", "visualizacion", "comparativo",
    )
    if not title or title.lower().strip() in generic_titles or len(title) < 8:
        title = _build_viz_title(chart_type, data_key, placa, entidades.get("fecha_inicio"), entidades.get("fecha_fin"))

    return {
        "type": chart_type,
        "title": title,
        "data_key": data_key,
        "color": color,
    }


def _keyword_fallback(message: str) -> tuple[str, float, dict]:
    msg = message.lower()
    hits = {k: sum(1 for w in v if w in msg) for k, v in _FALLBACK.items()}
    total = sum(hits.values())
    if total == 0:
        intencion, confianza = "normativa", 0.3
    else:
        ranked = sorted(hits.items(), key=lambda x: x[1], reverse=True)
        top_name, top_hits = ranked[0]
        second_hits = ranked[1][1]
        if top_hits > second_hits:
            intencion = top_name
            confianza = min(0.5 + 0.4 * (top_hits / total), 0.9)
        else:
            intencion, confianza = "mixta", 0.5

    placa_match = re.search(r"\b([A-Za-z]{3}-?[0-9]{3})\b", message, re.IGNORECASE)
    entidades: dict = {}
    if placa_match:
        entidades["placa"] = placa_match.group(1).upper().replace("-", "")

    entidades["viz_spec"] = _resolve_viz_spec(message, intencion, entidades)
    return intencion, confianza, entidades


def classify_intent(message: str) -> tuple[str, float, dict]:
    """
    Retorna (intencion, confianza, entidades).

    entidades = {
        "placa": str | None,
        "fecha_inicio": str | None,  # ISO: 2026-05-01
        "fecha_fin": str | None,
        "viz_spec": dict | None,     # tipo, title, data_key, color
    }

    Hace fallback a keywords si el LLM falla.
    """
    today = date.today().isoformat()
    try:
        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT.format(today=today)},
                {"role": "user", "content": message},
            ],
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        intencion = data.get("intencion", "normativa")
        confianza = float(data.get("confianza", 0.5))
        entidades = data.get("entidades") or {}
        entidades["viz_spec"] = _normalize_viz_spec(
            entidades.get("viz_spec"), message, intencion, entidades
        )
        return intencion, confianza, entidades
    except Exception:
        return _keyword_fallback(message)
