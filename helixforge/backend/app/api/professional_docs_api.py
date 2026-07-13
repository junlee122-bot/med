from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import professional_docs, scientific_whitepaper

router = APIRouter(prefix="/api", tags=["professional-docs"])


class GenerateDocRequest(BaseModel):
    doc_type: str
    run_id: str | None = None


@router.post("/professional-docs/generate")
def professional_docs_generate(req: GenerateDocRequest):
    try:
        return professional_docs.generate(req.doc_type, req.run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/professional-docs")
def professional_docs_list(run_id: str | None = None):
    try:
        return {"documents": professional_docs.list_docs(run_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/professional-docs/bundle")
def professional_docs_bundle(run_id: str | None = None):
    try:
        return professional_docs.bundle(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/professional-docs/{doc_id}")
def professional_docs_get(doc_id: str, run_id: str | None = None):
    try:
        doc = professional_docs.get_doc(doc_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


class WhitepaperRequest(BaseModel):
    lang: str = "en"
    run_id: str | None = None


@router.post("/whitepaper/generate")
def whitepaper_generate(req: WhitepaperRequest):
    try:
        return scientific_whitepaper.generate(req.lang, req.run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/whitepaper/latest")
def whitepaper_latest(lang: str = "en", run_id: str | None = None):
    try:
        wp = scientific_whitepaper.latest(lang, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wp or {"error": "no whitepaper yet", "lang": lang}


@router.get("/whitepaper/export")
def whitepaper_export(run_id: str | None = None):
    try:
        return scientific_whitepaper.export(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
