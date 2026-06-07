from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from chat_service import router as chat_router
from sql_service import router as sql_router

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app = FastAPI(title="GuruMaster Carga Colombia", version="0.1.0")


@app.middleware("http")
async def cors_everywhere(request: Request, call_next):
    origin = request.headers.get("origin", "*")
    if request.method == "OPTIONS":
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "86400",
            },
        )
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


app.include_router(chat_router)
app.include_router(sql_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def serve_frontend():
    return FileResponse(FRONTEND_DIR / "GuruMaster.html")


@app.get("/architecture")
def serve_architecture():
    return FileResponse(FRONTEND_DIR / "GuruMaster_Architecture.html")


@app.get("/c4")
def serve_c4():
    return FileResponse(FRONTEND_DIR / "GuruMaster_C4.html")
