from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import professional_docs, scientific_whitepaper
from app.storage import db

router = APIRouter(prefix="/api", tags=["professional-docs"])


class GenerateDocRequest(BaseModel):
    doc_type: str


@router.post("/professional-docs/generate")
def professional_docs_generate(req: GenerateDocRequest):
    try:
        return professional_docs.generate(req.doc_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/professional-docs")
def professional_docs_list():
    return {"documents": professional_docs.list_docs()}


@router.get("/professional-docs/bundle")
def professional_docs_bundle():
    return professional_docs.bundle()


@router.get("/professional-docs/{doc_id}")
def professional_docs_get(doc_id: str):
    doc = db.get("professional_documents", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


class WhitepaperRequest(BaseModel):
    lang: str = "en"


@router.post("/whitepaper/generate")
def whitepaper_generate(req: WhitepaperRequest):
    return scientific_whitepaper.generate(req.lang)


@router.get("/whitepaper/latest")
def whitepaper_latest(lang: str = "en"):
    wp = scientific_whitepaper.latest(lang)
    return wp or {"error": "no whitepaper yet", "lang": lang}


@router.get("/whitepaper/export")
def whitepaper_export():
    return scientific_whitepaper.export()
