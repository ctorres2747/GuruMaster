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
        "WHERE t.vehiculo_id = ? GROUP BY e.tipo_gasto ORDER BY total DESC",
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
