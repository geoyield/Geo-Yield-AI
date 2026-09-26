"""
==============================================================================
API ROUTER: ORCHESTRATOR AGENT (VIABILITY REPORTS)
==============================================================================
File: backend/api/routers/reports.py

Exposes the endpoints that allow the Frontend to request the generation of
the final Commercial Viability Report. It merges Phase 1 (Data) and
Phase 2 (RAG) into a single LLM stream.

Design:
    - Synchronous endpoints (`def`, not `async def`) on purpose: the whole
      pipeline underneath (SQLAlchemy, sentence-transformers, the Gemini
      client) is synchronous. FastAPI runs synchronous endpoints in a
      threadpool automatically, so this does not block the event loop --
      rewriting the whole pipeline to async would be a much bigger
      architectural change, with no real need given this MVP's request
      volume.
    - LLM or database errors are caught and translated into a clean 502,
      instead of letting FastAPI leak a raw stack trace to the frontend.
    - /reports/stream delivers the response via Server-Sent Events instead
      of waiting for it to be complete -- see generar_informe_viabilidad_stream.
"""

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.deps import get_session
from backend.api.schemas.reports import DistritoOut, InformeRequest, InformeResponse, ZonaPgmOut
from backend.ia.agent import (
    ZONA_PGM_NOMBRES,
    generar_informe_viabilidad,
    generar_informe_viabilidad_stream,
    zonas_pgm_disponibles,
)
from backend.observability import get_logger

logger = get_logger("api.informes")

router = APIRouter(prefix="/api", tags=["reports"])


# ------------------------------------------------------------------------------
# MANUAL SERIALIZATION HOOK
# ------------------------------------------------------------------------------
def _json_default(obj):
    """
    Type-casting hook for json.dumps().
    When using standard FastAPI endpoints, Pydantic automatically converts
    PostgreSQL 'Numeric' types (parsed as Python Decimals) into JSON floats.
    However, in Server-Sent Events (SSE) streaming, we construct the JSON
    strings manually. Standard `json.dumps` crashes on Decimals, so we must
    explicitly teach it to cast them to floats.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


@router.get("/districts", response_model=list[DistritoOut])
def listar_distritos(db: Session = Depends(get_session)):
    """Fetches the static list of Barcelona districts for the UI Dropdown."""
    rows = db.execute(text("SELECT codi_districte, nom_districte FROM districts ORDER BY codi_districte")).all()
    return [DistritoOut(codi_districte=r.codi_districte, nom_districte=r.nom_districte) for r in rows]


@router.get("/pgm-zones", response_model=list[ZonaPgmOut])
def listar_zonas_pgm(db: Session = Depends(get_session)):
    """
    UX/UI Safeguard:
    Only returns Urban Zones that actually have legal chunks populated in
    the database. This prevents the Frontend UI from offering options that
    would result in a guaranteed empty RAG retrieval.
    """
    zonas = zonas_pgm_disponibles(db)
    return [ZonaPgmOut(id=z, nombre=ZONA_PGM_NOMBRES.get(z, z)) for z in zonas]


# ------------------------------------------------------------------------------
# CONCURRENCY DESIGN: SYNCHRONOUS ENDPOINTS IN FASTAPI
# ------------------------------------------------------------------------------
# Note: We intentionally use `def` instead of `async def` here.
# Why? The underlying pipeline (SQLAlchemy queries and Gemini HTTP requests)
# is strictly synchronous (blocking I/O). If we used `async def`, these blocking
# calls would freeze the main ASGI Event Loop, bringing down the whole server.
# By using standard `def`, FastAPI intelligently detects the blocking nature
# and automatically offloads the execution to an external OS Threadpool,
# maintaining server concurrency without requiring a complex asyncio rewrite.

@router.post("/reports", response_model=InformeResponse)
def crear_informe(payload: InformeRequest, db: Session = Depends(get_session)):
    """Generates the full viability report synchronously (Waits until finished)."""
    try:
        informe = generar_informe_viabilidad(
            db, codi_districte=payload.codi_districte, zona_pgm=payload.zona_pgm
        )
    except Exception:
        # District and zone go in `context`, not interpolated into the
        # message, so Logs Insights can filter on them directly.
        logger.exception(
            "Report generation failed",
            extra={"context": {
                "codi_districte": payload.codi_districte,
                "zona_pgm": payload.zona_pgm,
            }},
        )
        # Security/UX: Never leak raw Python Stack Traces to the Frontend.
        # Translate internal crashes into clean HTTP 502 Bad Gateway responses.
        raise HTTPException(
            status_code=502,
            detail="Could not generate the report (Failed to contact AI model or Database). Please try again later.",
        )
    return informe


@router.post("/reports/stream")
def crear_informe_stream(payload: InformeRequest, db: Session = Depends(get_session)):
    """
    Generates the viability report using Server-Sent Events (SSE).
    This drastically improves Perceived Latency. Instead of staring at a
    loading spinner for 20 seconds, the user sees the LLM typing in real-time.
    """
    def eventos():
        try:
            for evento in generar_informe_viabilidad_stream(
                db, codi_districte=payload.codi_districte, zona_pgm=payload.zona_pgm
            ):
                # Format required by the SSE protocol: 'data: {json}\n\n'
                yield f"data: {json.dumps(evento, ensure_ascii=False, default=_json_default)}\n\n"
        except Exception:
            logger.exception(
                "Report streaming failed",
                extra={"context": {
                    "codi_districte": payload.codi_districte,
                    "zona_pgm": payload.zona_pgm,
                }},
            )
            # Fail gracefully inside the stream
            error = {"type": "error", "detail": "Could not generate the report. Please try again later."}
            yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"

    return StreamingResponse(eventos(), media_type="text/event-stream")