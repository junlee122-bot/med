"""HelixForge AI — FastAPI application entrypoint.

Integration-first backend: real HTTP clients (PubMed, ClinicalTrials.gov, ChEMBL)
and real local tools (RDKit, TDC) plus honest adapters for Vina/REINVENT4. Every
tool call is audited and labeled with a SourceType. No fabricated real results.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    agentic_api,
    chembl_api,
    data_api,
    evaluation_api,
    export_api,
    health,
    literature,
    rdkit_api,
    reinvent_api,
    settings_api,
    snapshots_api,
    submission_api,
    tdc_api,
    vina_api,
    workflow_api,
)
from app.config import get_settings
from app.storage import db

SAFETY_NOTICE = (
    "Research decision support only. No wet-lab protocol, no synthesis recipe, "
    "no medical advice. Final responsibility belongs to the human research team."
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Integration-first multi-agent AI drug discovery backend. "
            + SAFETY_NOTICE
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list(),
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for module in (health, literature, chembl_api, rdkit_api, tdc_api, vina_api,
                   reinvent_api, workflow_api, settings_api,
                   agentic_api, data_api, evaluation_api, export_api,
                   snapshots_api, submission_api):
        app.include_router(module.router)

    @app.on_event("startup")
    def _startup() -> None:
        db.init_db()

    @app.get("/")
    def root():
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "safety": SAFETY_NOTICE,
            "endpoints": [
                "/api/health", "/api/tools/health",
                "/api/pubmed/search", "/api/clinicaltrials/search",
                "/api/chembl/search-targets", "/api/chembl/search-molecules", "/api/chembl/activities",
                "/api/rdkit/validate", "/api/rdkit/descriptors", "/api/rdkit/similarity",
                "/api/tdc/datasets", "/api/tdc/load", "/api/tdc/benchmark-summary",
                "/api/vina/fixture-dock", "/api/vina/score", "/api/vina/jobs/{job_id}",
                "/api/reinvent/create-config", "/api/reinvent/run", "/api/reinvent/jobs/{job_id}", "/api/reinvent/parse-results",
                "/api/workflow/run-real-pipeline", "/api/workflow/run-target-discovery", "/api/workflow/run-molecule-screening",
                "/api/workflow/runs/{run_id}", "/api/audit/events", "/api/safety/screen",
                "/api/report/generate", "/api/report/{report_id}", "/api/settings",
            ],
        }

    return app


app = create_app()
