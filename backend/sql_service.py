"""Consultas SQL sobre viajes, gastos y activos en SQLite."""
import sqlite3
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["data"])

DB_PATH = Path(__file__).parent.parent / "db" / "gurumaster_carga.sqlite"


def get_conn():
    return sqlite3.connect(DB_PATH)


# --- Trips ---

def query_trips(vehicle_id: str | None = None, limit: int = 50) -> list[dict]:
    conn = get_conn()
    sql = "SELECT * FROM trips"
    params = []
    if vehicle_id:
        sql += " WHERE vehicle_id = ?"
        params.append(vehicle_id)
    sql += f" LIMIT {limit}"
    rows = conn.execute(sql, params).fetchall()
    cols = [d[0] for d in conn.execute(sql, params).description] if rows else []
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


def query_trip_profitability(trip_id: str) -> dict:
    conn = get_conn()
    trip = conn.execute("SELECT * FROM trips WHERE trip_id = ?", [trip_id]).fetchone()
    expenses = conn.execute(
        "SELECT SUM(amount) as total FROM trip_expenses WHERE trip_id = ?", [trip_id]
    ).fetchone()
    conn.close()
    if not trip:
        return {}
    revenue = trip[9]  # column index for revenue
    total_expenses = expenses[0] or 0
    profit = revenue - total_expenses
    return {"trip_id": trip_id, "revenue": revenue, "expenses": total_expenses, "profit": profit, "margin": round(profit / revenue * 100, 1) if revenue else 0}


# --- Vehicles ---

def query_vehicles() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM vehicles").fetchall()
    conn.close()
    return [{"vehicle_id": r[0], "plate": r[1], "type": r[2], "brand": r[3], "status": r[7]} for r in rows]


def query_vehicle_alerts(days: int = 30) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT vehicle_id, document_type, expiration_date FROM vehicle_documents "
        "WHERE date(expiration_date) <= date('now', ? || ' days') AND status != 'vencido'",
        [f"+{days}"],
    ).fetchall()
    conn.close()
    return [{"vehicle_id": r[0], "document": r[1], "expires": r[2]} for r in rows]


# --- FastAPI endpoints ---

@router.get("/trips")
def list_trips(vehicle_id: str | None = None):
    return query_trips(vehicle_id)


@router.get("/trips/{trip_id}/profitability")
def trip_profitability(trip_id: str):
    return query_trip_profitability(trip_id)


@router.get("/vehicles")
def list_vehicles():
    return query_vehicles()


@router.get("/vehicles/alerts")
def vehicle_alerts(days: int = 30):
    return query_vehicle_alerts(days)
