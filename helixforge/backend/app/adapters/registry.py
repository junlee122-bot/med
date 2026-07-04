"""Adapter registry — single source of truth for tool instances."""
from __future__ import annotations

from app.adapters.chembl import ChEMBLAdapter
from app.adapters.clinicaltrials import ClinicalTrialsGovAdapter
from app.adapters.pubmed import PubMedAdapter
from app.adapters.rdkit_adapter import RDKitAdapter
from app.adapters.reinvent_adapter import REINVENT4Adapter
from app.adapters.report_adapter import ReportAdapter
from app.adapters.safety_adapter import SafetyAdapter
from app.adapters.tdc_adapter import TDCAdapter
from app.adapters.vina_adapter import VinaAdapter

pubmed = PubMedAdapter()
clinicaltrials = ClinicalTrialsGovAdapter()
chembl = ChEMBLAdapter()
rdkit = RDKitAdapter()
tdc = TDCAdapter()
vina = VinaAdapter()
reinvent = REINVENT4Adapter()
safety = SafetyAdapter()
report = ReportAdapter()

ALL = [pubmed, clinicaltrials, chembl, rdkit, tdc, vina, reinvent, safety, report]
BY_ID = {a.id: a for a in ALL}


def health_all() -> list:
    return [a.health() for a in ALL]
