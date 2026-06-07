import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_SYSTEM_PROMPT = """Eres GuruMaster, asesor inteligente para transporte de carga en Colombia.

Ayudas a propietarios y operadores de flota con rentabilidad de viajes, costos operativos, vencimientos de documentos y normatividad del sector.

FORMATO — muy importante:
- Responde en texto plano con párrafos cortos. NO uses headers markdown (##, ###). NO uses LaTeX ni fórmulas matemáticas (\[ \]).
- Para listas usa guión simple: "- ítem". Para resaltar usa **negrita**.
- Máximo 5-7 líneas de respuesta principal + recomendación concisa al final.
- Los números financieros van inline en el texto: "utilidad de **$3.150.000 COP** (margen -28.6%)".

REGLAS DE CONTENIDO:
- Responde en español claro, orientado a negocio.
- Cuando haya cálculos financieros, menciona ingreso, gastos, utilidad y margen en el texto.
- Cuando uses documentos normativos, cita el título y sección si están disponibles.
- Nunca inventes normatividad, cifras ni requisitos legales que no estén en el contexto.
- Si no hay datos suficientes, di explícitamente qué información falta.
- Tono de asesor operativo, directo y conciso."""

_ANSWER_TEMPLATE = """Contexto disponible:
{context}

Pregunta: {pregunta}

Responde de forma concisa y directa. Usa texto plano con listas simples, sin headers markdown ni fórmulas matemáticas."""

_ANSWER_TEMPLATE_CORTO = """Contexto disponible:
{context}

Pregunta: {pregunta}

IMPORTANTE: Los datos detallados ya se muestran en el panel central de la aplicación.
Escribe UNA respuesta corta de máximo 2-3 líneas: resume el hallazgo principal con los números clave y termina con "→ Ver detalle en el panel central."
Sin listas largas, sin repetir todos los datos."""


def generate_response(pregunta: str, context: str, panel_disponible: bool = False) -> str:
    template = _ANSWER_TEMPLATE_CORTO if panel_disponible else _ANSWER_TEMPLATE
    prompt = template.format(context=context, pregunta=pregunta)
    resp = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=700,
    )
    return resp.choices[0].message.content.strip()
