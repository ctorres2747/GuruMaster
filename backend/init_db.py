"""Crea la base SQLite y carga los CSVs de seed data."""
import csv
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "gurumaster_carga.sqlite"
DATA_PATH = Path(__file__).parent.parent / "data"

SCHEMA = """
CREATE TABLE IF NOT EXISTS vehicles (
    vehiculo_id TEXT PRIMARY KEY,
    placa TEXT,
    tipo_vehiculo TEXT,
    marca TEXT,
    modelo TEXT,
    anio INTEGER,
    capacidad_toneladas REAL,
    tipo_combustible TEXT,
    rendimiento_km_por_galon REAL,
    tipo_propiedad TEXT,
    estado TEXT
);

CREATE TABLE IF NOT EXISTS drivers (
    conductor_id TEXT PRIMARY KEY,
    nombre_conductor TEXT,
    numero_documento TEXT,
    categoria_licencia TEXT,
    telefono TEXT,
    tipo_vinculacion TEXT,
    ciudad_base TEXT,
    estado TEXT
);

CREATE TABLE IF NOT EXISTS routes (
    ruta_id TEXT PRIMARY KEY,
    ciudad_origen TEXT,
    ciudad_destino TEXT,
    departamento_origen TEXT,
    departamento_destino TEXT,
    distancia_km REAL,
    duracion_estimada_horas REAL,
    tipo_ruta TEXT,
    estado TEXT
);

CREATE TABLE IF NOT EXISTS trips (
    viaje_id TEXT PRIMARY KEY,
    fecha_viaje TEXT,
    vehiculo_id TEXT,
    conductor_id TEXT,
    ruta_id TEXT,
    nombre_cliente TEXT,
    tipo_carga TEXT,
    peso_carga_toneladas REAL,
    ingreso REAL,
    moneda TEXT,
    estado_viaje TEXT,
    FOREIGN KEY (vehiculo_id) REFERENCES vehicles(vehiculo_id),
    FOREIGN KEY (conductor_id) REFERENCES drivers(conductor_id),
    FOREIGN KEY (ruta_id) REFERENCES routes(ruta_id)
);

CREATE TABLE IF NOT EXISTS trip_expenses (
    gasto_id TEXT PRIMARY KEY,
    viaje_id TEXT,
    fecha_gasto TEXT,
    tipo_gasto TEXT,
    valor REAL,
    moneda TEXT,
    metodo_pago TEXT,
    proveedor TEXT,
    descripcion TEXT,
    FOREIGN KEY (viaje_id) REFERENCES trips(viaje_id)
);

CREATE TABLE IF NOT EXISTS vehicle_documents (
    documento_id TEXT PRIMARY KEY,
    vehiculo_id TEXT,
    tipo_documento TEXT,
    numero_documento TEXT,
    fecha_emision TEXT,
    fecha_vencimiento TEXT,
    entidad_emisora TEXT,
    estado TEXT,
    archivo_referencia TEXT,
    observaciones TEXT,
    FOREIGN KEY (vehiculo_id) REFERENCES vehicles(vehiculo_id)
);

CREATE TABLE IF NOT EXISTS maintenance_events (
    mantenimiento_id TEXT PRIMARY KEY,
    vehiculo_id TEXT,
    fecha_mantenimiento TEXT,
    tipo_mantenimiento TEXT,
    categoria_mantenimiento TEXT,
    kilometraje INTEGER,
    proveedor TEXT,
    valor REAL,
    moneda TEXT,
    descripcion TEXT,
    proximo_mantenimiento_km INTEGER,
    proximo_mantenimiento_fecha TEXT,
    estado TEXT,
    FOREIGN KEY (vehiculo_id) REFERENCES vehicles(vehiculo_id)
);

CREATE TABLE IF NOT EXISTS odometer_readings (
    odometro_id TEXT PRIMARY KEY,
    vehiculo_id TEXT,
    fecha_registro TEXT,
    kilometraje INTEGER,
    fuente_registro TEXT,
    observaciones TEXT,
    FOREIGN KEY (vehiculo_id) REFERENCES vehicles(vehiculo_id)
);

CREATE TABLE IF NOT EXISTS alerts (
    alerta_id TEXT PRIMARY KEY,
    vehiculo_id TEXT,
    fecha_alerta TEXT,
    tipo_alerta TEXT,
    nivel_alerta TEXT,
    descripcion TEXT,
    fecha_limite TEXT,
    estado TEXT,
    FOREIGN KEY (vehiculo_id) REFERENCES vehicles(vehiculo_id)
);
"""


def load_csv(conn: sqlite3.Connection, table: str, csv_file: Path) -> int:
    with open(csv_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join("?" * len(cols))
    col_names = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"
    conn.executemany(sql, [list(r.values()) for r in rows])
    return len(rows)


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    tables = [
        ("vehicles", "seed_vehicles.csv"),
        ("drivers", "seed_drivers.csv"),
        ("routes", "seed_routes.csv"),
        ("trips", "seed_trips.csv"),
        ("trip_expenses", "seed_trip_expenses.csv"),
        ("vehicle_documents", "seed_vehicle_documents.csv"),
        ("maintenance_events", "seed_maintenance_events.csv"),
        ("odometer_readings", "seed_odometer.csv"),
        ("alerts", "seed_alerts.csv"),
    ]

    for table, csv_name in tables:
        csv_file = DATA_PATH / csv_name
        if csv_file.exists():
            count = load_csv(conn, table, csv_file)
            print(f"  {table}: {count} filas cargadas")
        else:
            print(f"  {table}: archivo no encontrado ({csv_name})")

    conn.commit()
    conn.close()
    print(f"\nBase de datos creada en: {DB_PATH}")


if __name__ == "__main__":
    init_db()
