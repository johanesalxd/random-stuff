#!/usr/bin/env python3
"""Hermetic REST client for Google Cloud Dataplex Knowledge Catalog APIs.

Provides zero-external-dependency HTTP transport (`urllib.request`) with
automatic token resolution (`google.auth.default()` or `gcloud` CLI fallback),
long-running operation (LRO) polling, retry backoff for transient HTTP 429/5xx
and eventual-consistency indexing delays, and strict `[REDACTED]` credential
hygiene in logs and plans.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol


DATAPLEX_BASE_URL = "https://dataplex.googleapis.com/v1"
CRM_BASE_URL = "https://cloudresourcemanager.googleapis.com/v1"


@dataclass(frozen=True)
class HttpResponse:
    """Normalized HTTP response returned by a Transport implementation."""

    status_code: int
    body: Dict[str, Any]
    raw_text: str = ""


class Transport(Protocol):
    """Injectable HTTP transport protocol for hermetic unit testing."""

    def request(
        self,
        method: str,
        url: str,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> HttpResponse:
        """Executes an HTTP request and returns an HttpResponse."""


class DataplexApiError(RuntimeError):
    """Structured exception raised on non-recoverable Dataplex API errors."""

    def __init__(
        self,
        method: str,
        url: str,
        status_code: int,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(f"HTTP {status_code} on {method} {url}: {message}")
        self.method = method
        self.url = url
        self.status_code = status_code
        self.message = message
        self.details = details or {}


def resolve_access_token() -> str:
    """Resolves a Google Cloud OAuth2 bearer token without exposing it in logs."""
    try:
        import google.auth
        import google.auth.transport.requests

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(google.auth.transport.requests.Request())
        if creds.token:
            return str(creds.token).strip()
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        token = res.stdout.strip()
        if token:
            return token
    except Exception as exc:
        raise RuntimeError(
            "Unable to obtain Google Cloud access token via google.auth or gcloud."
        ) from exc
    raise RuntimeError("Empty access token returned by credential provider.")


def redact_headers(headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Returns a copy of HTTP headers with Authorization masked as [REDACTED]."""
    if not headers:
        return {}
    sanitized: Dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in ("authorization", "proxy-authorization"):
            sanitized[k] = "Bearer [REDACTED]"
        else:
            sanitized[k] = v
    return sanitized


class UrllibTransport:
    """Standard-library urllib HTTP transport with bearer authentication."""

    def __init__(
        self,
        quota_project: str,
        token_provider: Callable[[], str] = resolve_access_token,
        timeout_sec: int = 30,
    ) -> None:
        self.quota_project = quota_project
        self._token_provider = token_provider
        self._token: Optional[str] = None
        self.timeout_sec = timeout_sec

    def _get_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        if not self._token:
            self._token = self._token_provider()
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=utf-8",
            "x-goog-user-project": self.quota_project,
        }
        if extra:
            headers.update(extra)
        return headers

    def request(
        self,
        method: str,
        url: str,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> HttpResponse:
        req_headers = self._get_headers(headers)
        data_bytes = (
            json.dumps(body, sort_keys=True).encode("utf-8")
            if body is not None
            else None
        )
        req = urllib.request.Request(
            url, data=data_bytes, headers=req_headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw_text = resp.read().decode("utf-8")
                parsed = json.loads(raw_text) if raw_text.strip() else {}
                return HttpResponse(
                    status_code=resp.getcode(), body=parsed, raw_text=raw_text
                )
        except urllib.error.HTTPError as exc:
            raw_err = exc.read().decode("utf-8", errors="replace")
            try:
                parsed_err = json.loads(raw_err) if raw_err.strip() else {}
            except json.JSONDecodeError:
                parsed_err = {"error": {"message": raw_err}}
            return HttpResponse(
                status_code=exc.code, body=parsed_err, raw_text=raw_err
            )


class DataplexClient:
    """High-level idempotent client for Dataplex Glossaries, EntryLinks & DataProducts."""

    def __init__(
        self,
        transport: Transport,
        verbose: bool = False,
        sleep_fn: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
    ) -> None:
        self.transport = transport
        self.verbose = verbose
        self.sleep_fn = sleep_fn
        self.max_retries = max_retries

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  [REST] {msg}")

    def request_with_retry(
        self,
        method: str,
        url: str,
        body: Optional[Dict[str, Any]] = None,
        allow_statuses: tuple[int, ...] = (200, 201),
    ) -> HttpResponse:
        """Executes HTTP request with exponential backoff on 429/5xx."""
        attempt = 0
        while True:
            attempt += 1
            self._log(f"{method} {url}")
            resp = self.transport.request(method=method, url=url, body=body)
            if resp.status_code in allow_statuses:
                return resp

            err_obj = resp.body.get("error", {}) if isinstance(resp.body, dict) else {}
            err_msg = err_obj.get("message", resp.raw_text or f"HTTP {resp.status_code}")

            if resp.status_code in (429, 500, 502, 503, 504) and attempt <= self.max_retries:
                delay = float(2 ** (attempt - 1))
                self._log(
                    f"Transient HTTP {resp.status_code} on {method} {url}; retrying in {delay}s..."
                )
                self.sleep_fn(delay)
                continue

            if resp.status_code == 403:
                hint = (
                    "Ensure caller holds roles/dataplex.catalogEditor, "
                    "roles/dataplex.dataProductsAdmin, and roles/dataplex.entryOwner."
                )
                raise DataplexApiError(
                    method,
                    url,
                    resp.status_code,
                    f"{err_msg} ({hint})",
                    details=resp.body,
                )

            raise DataplexApiError(
                method, url, resp.status_code, err_msg, details=resp.body
            )

    def wait_operation(
        self, operation_Response: Dict[str, Any], timeout_sec: float = 120.0
    ) -> Dict[str, Any]:
        """Polls a Google Cloud Long-Running Operation (LRO) until done=True."""
        if not isinstance(operation_Response, dict):
            return {}
        op_name = operation_Response.get("name", "")
        if not op_name or "/operations/" not in op_name:
            return operation_Response
        if operation_Response.get("done") is True:
            if "error" in operation_Response:
                err = operation_Response["error"]
                raise DataplexApiError(
                    "LRO",
                    op_name,
                    int(err.get("code", 500)),
                    str(err.get("message", "Operation failed")),
                    details=operation_Response,
                )
            return operation_Response.get("response", operation_Response)

        url = f"{DATAPLEX_BASE_URL}/{op_name}"
        elapsed = 0.0
        interval = 1.0
        while elapsed < timeout_sec:
            self.sleep_fn(interval)
            elapsed += interval
            resp = self.request_with_retry("GET", url, allow_statuses=(200,))
            if resp.body.get("done") is True:
                if "error" in resp.body:
                    err = resp.body["error"]
                    raise DataplexApiError(
                        "LRO",
                        op_name,
                        int(err.get("code", 500)),
                        str(err.get("message", "Operation failed")),
                        details=resp.body,
                    )
                return resp.body.get("response", resp.body)
            interval = min(interval * 1.5, 5.0)

        raise TimeoutError(f"Operation {op_name} did not complete within {timeout_sec}s")

    def resolve_project_number(self, project_id: str) -> str:
        """Looks up the numeric projectNumber for a project ID via CRM API."""
        url = f"{CRM_BASE_URL}/projects/{project_id}"
        resp = self.request_with_retry("GET", url, allow_statuses=(200,))
        pnum = str(resp.body.get("projectNumber", "")).strip()
        if not pnum:
            raise RuntimeError(f"Could not resolve projectNumber for {project_id}")
        return pnum

    def get_or_none(self, url: str) -> Optional[Dict[str, Any]]:
        """Returns GET response body or None on HTTP 404."""
        resp = self.request_with_retry("GET", url, allow_statuses=(200, 404))
        if resp.status_code == 404:
            return None
        return resp.body

    def create_or_update(
        self,
        create_url: str,
        resource_url: str,
        body: Dict[str, Any],
        update_mask: Optional[str] = None,
        is_lro: bool = False,
    ) -> Dict[str, Any]:
        """Idempotently creates a resource or patches it if it already exists."""
        existing = self.get_or_none(resource_url)
        if existing is None:
            resp = self.request_with_retry(
                "POST", create_url, body=body, allow_statuses=(200, 201, 409)
            )
            if resp.status_code == 409:
                existing = self.get_or_none(resource_url) or {}
            elif is_lro:
                return self.wait_operation(resp.body)
            else:
                return resp.body

        if update_mask:
            sep = "&" if "?" in resource_url else "?"
            patch_url = f"{resource_url}{sep}updateMask={update_mask}"
            patch_body = {k: v for k, v in body.items() if k != "parent"}
            resp = self.request_with_retry(
                "PATCH", patch_url, body=patch_body, allow_statuses=(200, 201)
            )
            return self.wait_operation(resp.body) if is_lro else resp.body

        return existing or {}

    def delete_if_exists(self, resource_url: str, is_lro: bool = False) -> bool:
        """Idempotently deletes a resource if it exists (ignores 404)."""
        resp = self.request_with_retry(
            "DELETE", resource_url, allow_statuses=(200, 204, 404)
        )
        if resp.status_code == 404:
            return False
        if is_lro and resp.body:
            self.wait_operation(resp.body)
        return True
