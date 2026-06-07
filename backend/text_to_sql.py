"""Text-to-SQL: genera y ejecuta consultas SQLite dinámicamente desde lenguaje natural."""
import os
import re
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DB_PATH = Path(__file__).parent.parent / "db" / "gurumaster_carga.sqlite"

_SCHEMA = """
Tablas SQLite de GuruMaster Carga Colombia (datos de mayo 2026):

trips: viaje_id, fecha_viaje (DATE 'YYYY-MM-DD'), vehiculo_id, conductor_id, ruta_id,
       nombre_cliente, tipo_carga, peso_carga_toneladas, ingreso (COP REAL), moneda,
       estado_viaje ('Completado'|'En curso'|'Cancelado')

trip_expenses: gasto_id, viaje_id, fecha_gasto, tipo_gasto ('Combustible'|'Peajes'|
               'Pago conductor'|'Alimentacion'|'Parqueadero'|'Mantenimiento'|
               'Cargue y descargue'), valor (COP REAL), moneda, metodo_pago, proveedor, descripcion

vehicles: vehiculo_id, placa, tipo_vehiculo, marca, modelo, anio, capacidad_toneladas,
          tipo_combustible, rendimiento_km_por_galon, tipo_propiedad,
          estado ('Activo'|'Mantenimiento'|'Inactivo')

drivers: conductor_id, nombre_conductor, numero_documento, categoria_licencia,
         telefono, tipo_vinculacion, ciudad_base, estado

routes: ruta_id, ciudad_origen, ciudad_destino, departamento_origen, departamento_destino,
        distancia_km, duracion_estimada_horas, tipo_ruta, estado

vehicle_documents: documento_id, vehiculo_id, tipo_documento, numero_documento,
                   fecha_emision, fecha_vencimiento (DATE), entidad_emisora, estado,
                   archivo_referencia, observaciones

maintenance_events: mantenimiento_id, vehiculo_id, fecha_mantenimiento (DATE),
                    tipo_mantenimiento, categoria_mantenimiento, kilometraje,
                    proveedor, valor (COP REAL), moneda, descripcion,
                    proximo_mantenimiento_km, proximo_mantenimiento_fecha, estado

odometer_readings: odometro_id, vehiculo_id, fecha_registro (DATE), kilometraje,
                   fuente_registro, observaciones

alerts: alerta_id, vehiculo_id, fecha_alerta, tipo_alerta,
        nivel_alerta ('Critica'|'Alta'|'Media'|'Baja'),
        descripcion, fecha_limite (DATE), estado

Relaciones:
  trips.vehiculo_id → vehicles.vehiculo_id
  trips.conductor_id → drivers.conductor_id
  trips.ruta_id → routes.ruta_id
  trip_expenses.viaje_id → trips.viaje_id
  vehicle_documents.vehiculo_id → vehicles.vehiculo_id
  maintenance_events.vehiculo_id → vehicles.vehiculo_id
  alerts.vehiculo_id → vehicles.vehiculo_id
"""

_SYSTEM_PROMPT = """Eres un experto en SQL para SQLite aplicado a transporte de carga en Colombia.
Generas consultas SELECT basadas en preguntas en español.

REGLAS ESTRICTAS:
- Responde SOLO con el SQL, sin explicaciones, sin markdown, sin bloques de código
- Solo SELECT statements — nunca INSERT, UPDATE, DELETE, DROP, ALTER, PRAGMA
- Usa LIMIT 20 a menos que la pregunta pida todos los registros
- Para agrupar por mes: strftime('%Y-%m', fecha_viaje)
- Para calcular días hasta vencimiento: CAST(julianday(fecha_vencimiento) - julianday('now') AS INTEGER)
- Usa alias legibles: COUNT(*) AS total_viajes, SUM(ingreso) AS ingresos_cop
- SIEMPRE haz JOIN para mostrar nombres legibles en lugar de IDs:
    trips.conductor_id → JOIN drivers d ON t.conductor_id = d.conductor_id → incluye d.nombre_conductor
    trips.vehiculo_id  → JOIN vehicles v ON t.vehiculo_id = v.vehiculo_id   → incluye v.placa
    trips.ruta_id      → JOIN routes r ON t.ruta_id = r.ruta_id             → incluye r.ciudad_origen, r.ciudad_destino
- Si no puedes responder con los datos disponibles, escribe: NO_DATA"""


def generate_sql(pregunta: str) -> str | None:
    """Llama al LLM para generar un SELECT a partir de la pregunta."""
    try:
        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Schema:\n{_SCHEMA}\n\nPregunta: {pregunta}\n\nSQL:",
                },
            ],
            temperature=0,
            max_tokens=400,
        )
        raw = resp.choices[0].message.content.strip()
        # Limpiar bloques markdown por si acaso
        raw = re.sub(r"```sql\s*", "", raw, flags=re.IGNORECASE)
        raw = raw.replace("```", "").strip()
        if not raw or raw == "NO_DATA":
            return None
        return raw
    except Exception:
        return None


_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|PRAGMA|EXEC)\b",
    re.IGNORECASE,
)


def execute_safe_sql(sql: str) -> list[dict]:
    """Valida que sea SELECT y ejecuta. Lanza ValueError si no es seguro."""
    first_word = sql.strip().split()[0].upper()
    if first_word != "SELECT":
        raise ValueError(f"Solo SELECT permitido, se recibió: {first_word}")
    if _FORBIDDEN.search(sql):
        raise ValueError("SQL contiene instrucciones no permitidas")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql).fetchmany(20)
        return [dict(r) for r in rows]
    finally:
        conn.close()


def run_text_to_sql(pregunta: str) -> dict | None:
    """Pipeline completo: pregunta → SQL → ejecución → resultado formateado."""
    sql = generate_sql(pregunta)
    if not sql:
        return None
    try:
        filas = execute_safe_sql(sql)
        return {"sql": sql, "filas": filas, "total": len(filas), "error": None}
    except Exception as e:
        return {"sql": sql, "filas": [], "total": 0, "error": str(e)}
