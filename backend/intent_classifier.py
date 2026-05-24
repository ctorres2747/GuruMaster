"""Clasifica la intención de una pregunta y extrae entidades usando LLM.

Retorna siempre (intencion, confianza, entidades) para que el orquestador
pueda auto-poblar filtros desde la pregunta, sin que el usuario los indique.
"""
import json
import os
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
- mixta: combina dos o más intenciones anteriores

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

Responde ÚNICAMENTE con JSON válido, sin explicaciones:
{{"intencion": "...", "confianza": 0.0, "entidades": {{"placa": null, "fecha_inicio": null, "fecha_fin": null}}}}
"""

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
        "llanta", "llantas", "alerta", "vencimiento", "flota",
    ],
}


def _keyword_fallback(message: str) -> tuple[str, float, dict]:
    msg = message.lower()
    hits = {k: sum(1 for w in v if w in msg) for k, v in _FALLBACK.items()}
    total = sum(hits.values())
    if total == 0:
        return "normativa", 0.3, {}
    ranked = sorted(hits.items(), key=lambda x: x[1], reverse=True)
    top_name, top_hits = ranked[0]
    second_hits = ranked[1][1]
    if top_hits > second_hits:
        return top_name, min(0.5 + 0.4 * (top_hits / total), 0.9), {}
    return "mixta", 0.5, {}


def classify_intent(message: str) -> tuple[str, float, dict]:
    """
    Retorna (intencion, confianza, entidades).

    entidades = {
        "placa": str | None,
        "fecha_inicio": str | None,  # ISO: 2026-05-01
        "fecha_fin": str | None,
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
            max_tokens=100,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        intencion = data.get("intencion", "normativa")
        confianza = float(data.get("confianza", 0.5))
        entidades = data.get("entidades") or {}
        return intencion, confianza, entidades
    except Exception:
        return _keyword_fallback(message)
