"""Consultas SQL sobre viajes, gastos y activos en SQLite."""
import sqlite3
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["data"])

DB_PATH = Path(__file__).parent.parent / "db" / "gurumaster_carga.sqlite"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --- Trips ---

def query_trips(vehiculo_id: str | None = None, limit: int = 50) -> list[dict]:
    conn = get_conn()
    sql = (
        "SELECT t.*, r.ciudad_origen, r.ciudad_destino, r.distancia_km "
        "FROM trips t LEFT JOIN routes r ON t.ruta_id = r.ruta_id"
    )
    params: list = []
    if vehiculo_id:
        sql += " WHERE t.vehiculo_id = ?"
        params.append(vehiculo_id)
    sql += f" ORDER BY t.fecha_viaje DESC LIMIT {limit}"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_trip_profitability(viaje_id: str) -> dict:
    conn = get_conn()
    trip = conn.execute(
        "SELECT t.*, r.ciudad_origen, r.ciudad_destino, r.distancia_km "
        "FROM trips t LEFT JOIN routes r ON t.ruta_id = r.ruta_id "
        "WHERE t.viaje_id = ?",
        [viaje_id],
    ).fetchone()
    if not trip:
        conn.close()
        return {}
    expense_rows = conn.execute(
        "SELECT tipo_gasto, SUM(valor) as total FROM trip_expenses "
        "WHERE viaje_id = ? GROUP BY tipo_gasto",
        [viaje_id],
    ).fetchall()
    conn.close()

    ingreso = trip["ingreso"]
    gastos_detalle = {r["tipo_gasto"]: r["total"] for r in expense_rows}
    total_gastos = sum(gastos_detalle.values())
    utilidad = ingreso - total_gastos
    margen = round(utilidad / ingreso * 100, 1) if ingreso else 0

    return {
        "viaje_id": viaje_id,
        "ruta": f"{trip['ciudad_origen']} → {trip['ciudad_destino']}",
        "fecha": trip["fecha_viaje"],
        "cliente": trip["nombre_cliente"],
        "vehiculo_id": trip["vehiculo_id"],
        "ingreso": ingreso,
        "gastos_total": total_gastos,
        "gastos_detalle": gastos_detalle,
        "utilidad": utilidad,
        "margen_pct": margen,
        "rentable": utilidad > 0,
    }


def query_monthly_summary(year: int, month: int) -> dict:
    conn = get_conn()
    period = f"{year:04d}-{month:02d}"
    summary = conn.execute(
        "SELECT COUNT(*) as total_viajes, SUM(ingreso) as ingresos_brutos "
        "FROM trips WHERE strftime('%Y-%m', fecha_viaje) = ? AND estado_viaje = 'Completado'",
        [period],
    ).fetchone()
    expense_rows = conn.execute(
        "SELECT e.tipo_gasto, SUM(e.valor) as total "
        "FROM trip_expenses e JOIN trips t ON e.viaje_id = t.viaje_id "
        "WHERE strftime('%Y-%m', t.fecha_viaje) = ? "
        "GROUP BY e.tipo_gasto ORDER BY total DESC",
        [period],
    ).fetchall()
    conn.close()

    ingresos = summary["ingresos_brutos"] or 0
    gastos_detalle = {r["tipo_gasto"]: r["total"] for r in expense_rows}
    total_gastos = sum(gastos_detalle.values())
    utilidad = ingresos - total_gastos

    return {
        "periodo": period,
        "total_viajes": summary["total_viajes"],
        "ingresos_brutos": ingresos,
        "gastos_total": total_gastos,
        "gastos_detalle": gastos_detalle,
        "utilidad_neta": utilidad,
        "margen_pct": round(utilidad / ingresos * 100, 1) if ingresos else 0,
    }


# --- Vehicles ---

def query_vehicles() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT v.*, "
        "(SELECT COUNT(*) FROM trips t WHERE t.vehiculo_id = v.vehiculo_id) as total_viajes, "
        "(SELECT COUNT(*) FROM vehicle_documents vd WHERE vd.vehiculo_id = v.vehiculo_id AND vd.estado IN ('Vencido','Por vencer')) as docs_criticos "
        "FROM vehicles v"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_vehicle_detail(vehiculo_id: str) -> dict:
    conn = get_conn()
    vehicle = conn.execute("SELECT * FROM vehicles WHERE vehiculo_id = ?", [vehiculo_id]).fetchone()
    if not vehicle:
        conn.close()
        return {}
    docs = conn.execute(
        "SELECT tipo_documento, fecha_vencimiento, estado, entidad_emisora, observaciones, "
        "CAST(julianday(fecha_vencimiento) - julianday('now') AS INTEGER) as dias_restantes "
        "FROM vehicle_documents WHERE vehiculo_id = ? ORDER BY fecha_vencimiento ASC",
        [vehiculo_id],
    ).fetchall()
    last_maintenance = conn.execute(
        "SELECT fecha_mantenimiento, tipo_mantenimiento, categoria_mantenimiento, valor, estado "
        "FROM maintenance_events WHERE vehiculo_id = ? ORDER BY fecha_mantenimiento DESC LIMIT 3",
        [vehiculo_id],
    ).fetchall()
    conn.close()
    return {
        **dict(vehicle),
        "documentos": [dict(d) for d in docs],
        "ultimos_mantenimientos": [dict(m) for m in last_maintenance],
    }


def query_vehicle_documents(vehiculo_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT tipo_documento, numero_documento, fecha_emision, fecha_vencimiento, "
        "entidad_emisora, estado, observaciones, "
        "CAST(julianday(fecha_vencimiento) - julianday('now') AS INTEGER) as dias_restantes "
        "FROM vehicle_documents WHERE vehiculo_id = ? ORDER BY fecha_vencimiento ASC",
        [vehiculo_id],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_vehicle_maintenance(vehiculo_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM maintenance_events WHERE vehiculo_id = ? ORDER BY fecha_mantenimiento DESC",
        [vehiculo_id],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_vehicle_profitability(vehiculo_id: str) -> dict:
    conn = get_conn()
    vehicle = conn.execute(
        "SELECT vehiculo_id, placa, tipo_vehiculo, marca, modelo FROM vehicles WHERE vehiculo_id = ?",
        [vehiculo_id],
    ).fetchone()
    if not vehicle:
        conn.close()
        return {}
    trips = conn.execute(
        "SELECT COUNT(*) as total_viajes, SUM(ingreso) as ingresos_brutos "
        "FROM trips WHERE vehiculo_id = ? AND estado_viaje = 'Completado'",
        [vehiculo_id],
    ).fetchone()
    expenses = conn.execute(
        "SELECT e.tipo_gasto, SUM(e.valor) as total "
        "FROM trip_expenses e JOIN trips t ON e.viaje_id = t.viaje_id "
        "WHERE t.vehiculo_id = ? AND t.estado_viaje = 'Completado' "
        "GROUP BY e.tipo_gasto ORDER BY total DESC",
        [vehiculo_id],
    ).fetchall()
    maintenance_cost = conn.execute(
        "SELECT SUM(valor) as total FROM maintenance_events WHERE vehiculo_id = ?",
        [vehiculo_id],
    ).fetchone()
    conn.close()

    ingresos = trips["ingresos_brutos"] or 0
    gastos_operativos = {r["tipo_gasto"]: r["total"] for r in expenses}
    total_operativos = sum(gastos_operativos.values())
    costo_mantenimiento = maintenance_cost["total"] or 0
    total_gastos = total_operativos + costo_mantenimiento
    utilidad = ingresos - total_gastos

    return {
        "vehiculo_id": vehiculo_id,
        "placa": vehicle["placa"],
        "tipo_vehiculo": vehicle["tipo_vehiculo"],
        "total_viajes": trips["total_viajes"],
        "ingresos_brutos": ingresos,
        "gastos_operativos": gastos_operativos,
        "costo_mantenimiento": costo_mantenimiento,
        "gastos_total": total_gastos,
        "utilidad": utilidad,
        "margen_pct": round(utilidad / ingresos * 100, 1) if ingresos else 0,
    }


def query_vehicle_alerts(days: int = 30) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT vd.vehiculo_id, v.placa, vd.tipo_documento, vd.fecha_vencimiento, vd.estado, "
        "CAST(julianday(vd.fecha_vencimiento) - julianday('now') AS INTEGER) as dias_restantes "
        "FROM vehicle_documents vd JOIN vehicles v ON vd.vehiculo_id = v.vehiculo_id "
        "WHERE vd.fecha_vencimiento != '' AND vd.fecha_vencimiento IS NOT NULL "
        "AND julianday(vd.fecha_vencimiento) - julianday('now') <= ? "
        "ORDER BY vd.fecha_vencimiento ASC",
        [days],
    ).fetchall()
    conn.close()

    def urgencia(dias: int) -> str:
        if dias < 0:
            return "vencido"
        if dias <= 7:
            return "critico"
        if dias <= 15:
            return "urgente"
        return "proximo"

    return [{**dict(r), "urgencia": urgencia(r["dias_restantes"])} for r in rows]


# --- Odometer & Alerts ---

def query_vehicle_odometer(vehiculo_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT fecha_registro, kilometraje, fuente_registro, observaciones "
        "FROM odometer_readings WHERE vehiculo_id = ? ORDER BY fecha_registro DESC",
        [vehiculo_id],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_alerts(vehiculo_id: str | None = None, estado: str | None = None) -> list[dict]:
    conn = get_conn()
    sql = (
        "SELECT a.*, v.placa FROM alerts a "
        "JOIN vehicles v ON a.vehiculo_id = v.vehiculo_id WHERE 1=1"
    )
    params: list = []
    if vehiculo_id:
        sql += " AND a.vehiculo_id = ?"
        params.append(vehiculo_id)
    if estado:
        sql += " AND a.estado = ?"
        params.append(estado)
    sql += " ORDER BY CASE a.nivel_alerta WHEN 'Critica' THEN 1 WHEN 'Alta' THEN 2 WHEN 'Media' THEN 3 ELSE 4 END, a.fecha_limite ASC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Fleet KPIs (comparación por vehículo) ---

def query_fleet_kpis() -> list[dict]:
    """Rentabilidad por vehículo: ingresos, gastos, utilidad, margen, viajes, costo/km."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT v.vehiculo_id, v.placa, v.tipo_vehiculo, v.marca, "
        "COUNT(CASE WHEN t.estado_viaje = 'Completado' THEN 1 END) as viajes_completados, "
        "COUNT(CASE WHEN t.estado_viaje NOT IN ('Completado','Cancelado') THEN 1 END) as viajes_en_curso, "
        "COALESCE(SUM(CASE WHEN t.estado_viaje = 'Completado' THEN t.ingreso END), 0) as ingresos, "
        "COALESCE(SUM(CASE WHEN t.estado_viaje = 'Completado' THEN eg.total_gasto END), 0) as gastos, "
        "COALESCE(SUM(CASE WHEN t.estado_viaje = 'Completado' THEN r.distancia_km END), 0) as km_recorridos "
        "FROM vehicles v "
        "LEFT JOIN trips t ON t.vehiculo_id = v.vehiculo_id "
        "LEFT JOIN routes r ON r.ruta_id = t.ruta_id "
        "LEFT JOIN (SELECT viaje_id, SUM(valor) as total_gasto FROM trip_expenses GROUP BY viaje_id) eg "
        "  ON eg.viaje_id = t.viaje_id "
        "GROUP BY v.vehiculo_id, v.placa, v.tipo_vehiculo, v.marca "
        "ORDER BY ingresos DESC"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        row = dict(r)
        utilidad = row["ingresos"] - row["gastos"]
        row["utilidad"] = utilidad
        row["margen_pct"] = round(utilidad / row["ingresos"] * 100, 1) if row["ingresos"] > 0 else 0
        km = row["km_recorridos"]
        row["costo_por_km"] = round(row["gastos"] / km) if km > 0 else None
        result.append(row)
    return result


def query_doc_risk_summary() -> dict:
    """Conteo de documentos por nivel de riesgo en toda la flota."""
    conn = get_conn()
    row = conn.execute(
        "SELECT "
        "SUM(CASE WHEN julianday(fecha_vencimiento) - julianday('now') < 0 THEN 1 ELSE 0 END) as vencidos, "
        "SUM(CASE WHEN julianday(fecha_vencimiento) - julianday('now') BETWEEN 0 AND 7 THEN 1 ELSE 0 END) as criticos, "
        "SUM(CASE WHEN julianday(fecha_vencimiento) - julianday('now') BETWEEN 8 AND 15 THEN 1 ELSE 0 END) as urgentes, "
        "SUM(CASE WHEN julianday(fecha_vencimiento) - julianday('now') BETWEEN 16 AND 30 THEN 1 ELSE 0 END) as proximos "
        "FROM vehicle_documents "
        "WHERE fecha_vencimiento IS NOT NULL AND fecha_vencimiento != ''"
    ).fetchone()
    conn.close()
    return {
        "vencidos": row["vencidos"] or 0,
        "criticos": row["criticos"] or 0,
        "urgentes": row["urgentes"] or 0,
        "proximos": row["proximos"] or 0,
    }


# --- Filtered queries for /chat ---

def query_vehicle_id_by_placa(placa: str) -> str | None:
    """Resuelve una placa (ABC123) al vehiculo_id interno (V001)."""
    conn = get_conn()
    row = conn.execute(
        "SELECT vehiculo_id FROM vehicles WHERE UPPER(REPLACE(placa, '-', '')) = UPPER(REPLACE(?, '-', ''))",
        [placa],
    ).fetchone()
    conn.close()
    return row["vehiculo_id"] if row else None


def query_trips_filtered(
    vehiculo_id: str | None = None,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    limit: int = 20,
) -> list[dict]:
    conn = get_conn()
    sql = (
        "SELECT t.viaje_id, t.fecha_viaje, t.vehiculo_id, t.nombre_cliente, "
        "t.ingreso, t.estado_viaje, r.ciudad_origen, r.ciudad_destino, r.distancia_km "
        "FROM trips t LEFT JOIN routes r ON t.ruta_id = r.ruta_id WHERE 1=1"
    )
    params: list = []
    if vehiculo_id:
        sql += " AND t.vehiculo_id = ?"
        params.append(vehiculo_id)
    if fecha_inicio:
        sql += " AND t.fecha_viaje >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        sql += " AND t.fecha_viaje <= ?"
        params.append(fecha_fin)
    sql += f" ORDER BY t.fecha_viaje DESC LIMIT {limit}"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_gastos_filtered(
    vehiculo_id: str | None = None,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> dict:
    conn = get_conn()
    base_where = " WHERE 1=1"
    params: list = []
    if vehiculo_id:
        base_where += " AND t.vehiculo_id = ?"
        params.append(vehiculo_id)
    if fecha_inicio:
        base_where += " AND t.fecha_viaje >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        base_where += " AND t.fecha_viaje <= ?"
        params.append(fecha_fin)

    gastos_rows = conn.execute(
        "SELECT e.tipo_gasto, SUM(e.valor) as total "
        "FROM trip_expenses e JOIN trips t ON e.viaje_id = t.viaje_id"
        + base_where
        + " GROUP BY e.tipo_gasto ORDER BY total DESC",
        params,
    ).fetchall()
    income_row = conn.execute(
        "SELECT SUM(t.ingreso) as total FROM trips t" + base_where, params
    ).fetchone()
    conn.close()

    gastos_detalle = {r["tipo_gasto"]: r["total"] for r in gastos_rows}
    total_gastos = sum(gastos_detalle.values())
    ingresos = income_row["total"] or 0
    utilidad = ingresos - total_gastos

    return {
        "ingresos": ingresos,
        "gastos_detalle": gastos_detalle,
        "total_gastos": total_gastos,
        "utilidad": utilidad,
        "margen_pct": round(utilidad / ingresos * 100, 1) if ingresos else 0,
    }


def query_activos_context(vehiculo_id: str | None = None) -> dict:
    """Contexto consolidado de activos: alertas, documentos y mantenimiento."""
    alerts = query_alerts(vehiculo_id=vehiculo_id)
    doc_alerts = query_vehicle_alerts(days=30)

    if vehiculo_id:
        doc_alerts = [d for d in doc_alerts if d.get("vehiculo_id") == vehiculo_id]
        docs = query_vehicle_documents(vehiculo_id)
        maintenance = query_vehicle_maintenance(vehiculo_id)[:5]
        return {
            "alertas_sistema": alerts,
            "documentos_por_vencer": doc_alerts,
            "documentos_vehiculo": docs,
            "ultimos_mantenimientos": maintenance,
        }

    vehicles = query_vehicles()
    return {
        "flota": vehicles,
        "alertas_sistema": alerts[:10],
        "documentos_por_vencer": doc_alerts[:10],
    }


# --- FastAPI endpoints ---

@router.get("/trips")
def list_trips(vehiculo_id: str | None = None):
    return query_trips(vehiculo_id)


@router.get("/trips/{viaje_id}/profitability")
def trip_profitability(viaje_id: str):
    result = query_trip_profitability(viaje_id)
    if not result:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    return result


@router.get("/analytics/monthly-summary")
def monthly_summary(year: int = 2026, month: int = 5):
    return query_monthly_summary(year, month)


@router.get("/vehicles")
def list_vehicles():
    return query_vehicles()


@router.get("/vehicles/alerts")
def vehicle_alerts(days: int = 30):
    return query_vehicle_alerts(days)


@router.get("/vehicles/{vehiculo_id}")
def vehicle_detail(vehiculo_id: str):
    result = query_vehicle_detail(vehiculo_id)
    if not result:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return result


@router.get("/vehicles/{vehiculo_id}/documents")
def vehicle_documents(vehiculo_id: str):
    return query_vehicle_documents(vehiculo_id)


@router.get("/vehicles/{vehiculo_id}/maintenance")
def vehicle_maintenance(vehiculo_id: str):
    return query_vehicle_maintenance(vehiculo_id)


@router.get("/vehicles/{vehiculo_id}/profitability")
def vehicle_profitability(vehiculo_id: str):
    result = query_vehicle_profitability(vehiculo_id)
    if not result:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return result


@router.get("/vehicles/{vehiculo_id}/odometer")
def vehicle_odometer(vehiculo_id: str):
    return query_vehicle_odometer(vehiculo_id)


@router.get("/alerts")
def list_alerts(vehiculo_id: str | None = None, estado: str | None = None):
    return query_alerts(vehiculo_id, estado)
