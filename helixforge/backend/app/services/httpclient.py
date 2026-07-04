"""Resilient HTTP GET helper.

Tries httpx first (the normal path in any real deployment). If httpx fails or is
rejected (some corporate proxies / CDN WAFs block non-browser TLS fingerprints
with a 403 even when the API is public and reachable), it falls back to a `curl`
subprocess, which negotiates TLS differently and typically succeeds.

Either way the request hits the REAL upstream API and returns REAL data — this
is a transport-resilience shim, not a data fallback. The chosen transport is
reported so callers can surface it. If both transports fail, the caller decides
whether that is a TOOL_ERROR.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Optional

import httpx


@dataclass
class HttpResult:
    status_code: int
    text: str
    transport: str  # "httpx" | "curl" | "none"
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300 and bool(self.text)


def _via_curl(url: str, params: Optional[dict[str, Any]], headers: Optional[dict[str, str]], timeout: int) -> HttpResult:
    sentinel = "\n__HELIX_HTTP_STATUS__:"
    cmd = ["curl", "-sS", "-G", "--max-time", str(timeout), "-w", f"{sentinel}%{{http_code}}"]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    for k, v in (params or {}).items():
        cmd += ["--data-urlencode", f"{k}={v}"]
    cmd.append(url)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        return HttpResult(0, "", "curl", error="curl timeout")
    except FileNotFoundError:
        return HttpResult(0, "", "none", error="curl not installed")
    out = proc.stdout
    if sentinel in out:
        body, _, status = out.rpartition(sentinel)
        try:
            code = int(status.strip())
        except ValueError:
            code = 0
        return HttpResult(code, body, "curl", error=None if 200 <= code < 300 else f"HTTP {code}")
    return HttpResult(0, out, "curl", error=proc.stderr.strip() or "curl produced no status")


def fetch_text(
    url: str,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: int = 30,
) -> HttpResult:
    # 1) httpx (normal path)
    try:
        r = httpx.get(url, params=params, headers=headers, timeout=timeout, follow_redirects=True)
        if 200 <= r.status_code < 300:
            return HttpResult(r.status_code, r.text, "httpx")
        # Non-2xx (e.g. 403 from a WAF) — try curl before giving up.
        curl_res = _via_curl(url, params, headers, timeout)
        if curl_res.ok:
            return curl_res
        return HttpResult(r.status_code, r.text, "httpx", error=f"HTTP {r.status_code}")
    except Exception as exc:
        curl_res = _via_curl(url, params, headers, timeout)
        if curl_res.ok:
            return curl_res
        return HttpResult(curl_res.status_code, curl_res.text, curl_res.transport, error=f"httpx: {exc}; curl: {curl_res.error}")
