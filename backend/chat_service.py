import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

from intent_classifier import classify_intent
from rag_service import search_documents

load_dotenv(Path(__file__).parent.parent / ".env")

router = APIRouter(prefix="/chat", tags=["chat"])
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """Eres GuruMaster, un asistente especializado en transporte de carga en Colombia.

Responde usando la información de los documentos de contexto proporcionados.
Si los documentos tienen información parcialmente relacionada, úsala y aclara qué parte responde la pregunta.
Si los documentos no contienen ninguna información relevante, di: "No encontré evidencia en los documentos disponibles para responder esta pregunta."
Nunca inventes normatividad, cifras ni requisitos legales que no estén en el contexto.
Cita el artículo o sección cuando sea posible.
Responde en español, de forma clara y concisa."""


class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    answer: str
    intent: str
    severity: str
    evidence: list
    recommended_actions: list


def _build_context(docs: list[dict]) -> str:
    if not docs:
        return "No se encontraron documentos relevantes."
    parts = []
    for i, doc in enumerate(docs, start=1):
        parts.append(f"[Documento {i} — {doc['title']}]\n{doc['content']}")
    return "\n\n---\n\n".join(parts)


def _call_llm(message: str, context: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Contexto:\n{context}\n\nPregunta: {message}"},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    intent   = classify_intent(req.message)
    evidence = []
    docs     = []

    if intent == "normativa":
        # Normativa puede referenciar tanto decretos como regulaciones de costos (ej: SICE-TAC)
        docs_norm = search_documents(req.message, pillar="normatividad",    n_results=4)
        docs_cost = search_documents(req.message, pillar="costos_operativos", n_results=2)
        docs = docs_norm + docs_cost
    elif intent == "financiera":
        docs = search_documents(req.message, pillar="costos_operativos", n_results=6)
        if not docs:
            docs = search_documents(req.message, n_results=6)
    elif intent == "activos":
        docs = search_documents(req.message, pillar="gestion_activos", n_results=6)
        if not docs:
            docs = search_documents(req.message, n_results=6)
    else:  # mixta
        docs = search_documents(req.message, n_results=6)

    evidence += [
        {"type": "document", "label": d["title"], "source": d["source"], "content": d["content"]}
        for d in docs
    ]

    if intent in ("financiera", "activos", "mixta"):
        # TODO: conectar sql_service en Módulo 2/3
        pass

    context = _build_context(docs)
    answer  = _call_llm(req.message, context)

    return ChatResponse(
        answer=answer,
        intent=intent,
        severity="normal",
        evidence=evidence,
        recommended_actions=[],
    )
