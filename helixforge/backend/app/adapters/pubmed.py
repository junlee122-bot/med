"""PubMed adapter — real NCBI E-utilities (ESearch + EFetch).

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
Uses ESearch to get PMIDs, then EFetch (XML) for full records. Honors optional
NCBI_API_KEY / NCBI_EMAIL. Returns REAL_TOOL_OUTPUT on success, TOOL_ERROR on
failure — never fabricated citations.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from app.adapters.base import ToolAdapter
from app.config import get_settings
from app.models.schemas import (
    HealthStatus,
    SourceType,
    ToolHealth,
    ValidationStatus,
    utcnow,
)
from app.services.httpclient import fetch_text

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedAdapter(ToolAdapter):
    id = "pubmed"
    name = "PubMed"
    category = "literature"
    required_config = ["NCBI_API_KEY (optional)", "NCBI_EMAIL (optional)"]
    mode = "http"

    def _params(self, extra: dict[str, Any]) -> dict[str, Any]:
        s = get_settings()
        p = {"db": "pubmed", "retmode": "xml", **extra}
        if s.ncbi_api_key:
            p["api_key"] = s.ncbi_api_key
        if s.ncbi_email:
            p["email"] = s.ncbi_email
        p["tool"] = "HelixForgeAI"
        return p

    def health_check(self) -> ToolHealth:
        s = get_settings()
        res = fetch_text(
            f"{EUTILS}/einfo.fcgi",
            params=self._params({}),
            headers={"User-Agent": s.http_user_agent},
            timeout=min(10, s.timeout_seconds),
        )
        if res.ok:
            return ToolHealth(
                tool_id=self.id, name=self.name, category=self.category,
                status=HealthStatus.AVAILABLE, mode=self.mode,
                detail=f"E-utilities reachable (HTTP {res.status_code} via {res.transport})"
                + ("" if s.ncbi_api_key else "; no API key set (lower rate limit)"),
                required_config=self.required_config,
            )
        return ToolHealth(
            tool_id=self.id, name=self.name, category=self.category,
            status=HealthStatus.ERROR, mode=self.mode,
            detail=f"E-utilities unreachable: {res.error}", required_config=self.required_config,
        )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        s = get_settings()
        query = payload.get("query", "").strip()
        max_results = int(payload.get("max_results", 10))
        input_summary = f'query="{query}", max_results={max_results}'
        if not query:
            return self._error(input_summary, ["Empty query"])

        headers = {"User-Agent": s.http_user_agent}
        timeout = s.timeout_seconds
        try:
            es = fetch_text(
                f"{EUTILS}/esearch.fcgi",
                params=self._params({"term": query, "retmax": max_results, "sort": "relevance"}),
                headers=headers, timeout=timeout,
            )
            if not es.ok:
                return self._error(input_summary, [f"ESearch failed: {es.error} (HTTP {es.status_code})"])
            root = ET.fromstring(es.text)
            pmids = [e.text for e in root.findall(".//IdList/Id") if e.text]
            if not pmids:
                return {
                    "tool_name": self.name, "source": self.name,
                    "source_type": SourceType.REAL_TOOL_OUTPUT.value,
                    "input_summary": input_summary,
                    "output_summary": "0 results from PubMed (real query, empty result set).",
                    "validation_status": ValidationStatus.PASSED.value,
                    "items": [], "errors": [], "warnings": [],
                }
            ef = fetch_text(
                f"{EUTILS}/efetch.fcgi",
                params=self._params({"id": ",".join(pmids), "rettype": "abstract"}),
                headers=headers, timeout=timeout,
            )
            if not ef.ok:
                return self._error(input_summary, [f"EFetch failed: {ef.error} (HTTP {ef.status_code})"])
            items = self._parse_articles(ef.text)
            transport = ef.transport
        except Exception as exc:
            return self._error(input_summary, [f"{type(exc).__name__}: {exc}"])

        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.REAL_TOOL_OUTPUT.value,
            "input_summary": input_summary,
            "output_summary": f"{len(items)} PubMed records retrieved (real E-utilities via {transport}).",
            "validation_status": ValidationStatus.PASSED.value,
            "items": items, "errors": [], "warnings": [],
        }

    def _parse_articles(self, xml_text: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return items
        for art in root.findall(".//PubmedArticle"):
            pmid_el = art.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""
            title_el = art.find(".//ArticleTitle")
            title = "".join(title_el.itertext()).strip() if title_el is not None else ""
            abstract_parts = [
                "".join(ab.itertext()).strip()
                for ab in art.findall(".//Abstract/AbstractText")
            ]
            abstract = " ".join(p for p in abstract_parts if p)
            journal_el = art.find(".//Journal/Title")
            journal = journal_el.text if journal_el is not None else ""
            year_el = art.find(".//JournalIssue/PubDate/Year")
            if year_el is None:
                medline = art.find(".//JournalIssue/PubDate/MedlineDate")
                year = (medline.text[:4] if medline is not None and medline.text else "")
            else:
                year = year_el.text or ""
            authors = []
            for a in art.findall(".//AuthorList/Author"):
                ln = a.find("LastName")
                init = a.find("Initials")
                if ln is not None:
                    authors.append(f"{ln.text} {init.text}" if init is not None else ln.text)
            items.append({
                "pmid": pmid, "title": title, "abstract": abstract,
                "journal": journal, "year": year, "authors": authors,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                "retrieved_at": utcnow(),
            })
        return items

    def _error(self, input_summary: str, errors: list[str]) -> dict[str, Any]:
        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.TOOL_ERROR.value,
            "input_summary": input_summary,
            "output_summary": "PubMed query failed; no fabricated data returned.",
            "validation_status": ValidationStatus.FAILED.value,
            "items": [], "errors": errors, "warnings": [],
        }
