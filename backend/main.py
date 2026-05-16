from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chat_service import router as chat_router
from sql_service import router as sql_router

app = FastAPI(title="GuruMaster Carga Colombia", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(sql_router)


@app.get("/health")
def health():
    return {"status": "ok"}
