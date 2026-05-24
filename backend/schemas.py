from typing import Optional
from pydantic import BaseModel


class Filtros(BaseModel):
    vehiculo_id: Optional[str] = None
    fecha_inicio: Optional[str] = None  # ISO: 2026-05-01
    fecha_fin: Optional[str] = None     # ISO: 2026-05-31


class ChatRequest(BaseModel):
    pregunta: str
    usuario: Optional[str] = None
    filtros: Optional[Filtros] = None


class SourceReference(BaseModel):
    tipo: str  # "documento" | "sql"
    nombre: str
    pilar: Optional[str] = None
    contenido: Optional[str] = None


class Metricas(BaseModel):
    ingreso: Optional[float] = None
    gastos: Optional[float] = None
    utilidad: Optional[float] = None
    margen_pct: Optional[float] = None


class ChatResponse(BaseModel):
    respuesta: str
    intencion: str
    confianza: float
    fuentes: list[SourceReference]
    datos_consultados: list[dict]
    metricas: Optional[Metricas] = None
    advertencias: list[str]
