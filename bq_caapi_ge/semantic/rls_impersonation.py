"""Signed role assertion verification and allowlisted Role-SA impersonation for BigQuery RLS.

Provides zero-trust role-scoped credentials and job auditing labels for multi-tenant
BigQuery row-level security (RLS) execution.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import hmac
import json
import re
import time
from typing import Any
import urllib.parse

__all__ = [
    "ImpersonationError",
    "RoleAssertion",
    "parse_role_sa_map",
    "mint_hmac_role_assertion",
    "verify_role_assertion",
    "build_impersonated_credentials",
    "redact_service_account_emails",
]

_ROLE_REGEX = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
_CUSTOMER_SA_REGEX = re.compile(
    r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$"
)
_SA_EMAIL_REDACTION_REGEX = re.compile(
    r"[A-Za-z0-9._+-]+@[A-Za-z0-9.-]*gserviceaccount\.com"
)


class ImpersonationError(ValueError):
    """Raised when role assertion verification or SA impersonation fails."""


@dataclass(frozen=True)
class RoleAssertion:
    """Verified identity assertion binding a user to an allowlisted BigQuery role."""

    role: str
    subject: str
    expires_at: int
    issuer: str
    job_labels: dict[str, str]


def _is_google_managed_sa(email: str) -> bool:
    """Checks whether an email belongs to a Google-managed service agent."""
    lowered = email.strip().lower()
    return (
        "@gcp-sa-" in lowered
        or lowered.endswith(".cloudservices.gserviceaccount.com")
        or lowered.endswith("cloudservices.gserviceaccount.com")
        or lowered.endswith(".developer.gserviceaccount.com")
        or lowered.endswith("developer.gserviceaccount.com")
    )


def parse_role_sa_map(raw_json: str | None) -> dict[str, str]:
    """Parses and validates a JSON mapping of role slugs to customer-managed service accounts.

    Args:
        raw_json: Raw JSON string mapping role slug to service account email.

    Returns:
        Validated dictionary of role slug -> customer service account email.

    Raises:
        ImpersonationError: On empty/None, duplicate keys, invalid role slugs, or
            non-customer-managed service accounts.
    """
    if raw_json is None or not raw_json.strip():
        raise ImpersonationError("SQL_ROLE_SA_MAP_JSON cannot be empty or None")

    def _pairs_hook(pairs: list[tuple[Any, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, val in pairs:
            if key in result:
                raise ImpersonationError(f"Duplicate role key in role_sa_map: {key!r}")
            result[key] = val
        return result

    try:
        data = json.loads(raw_json, object_pairs_hook=_pairs_hook)
    except json.JSONDecodeError as err:
        raise ImpersonationError(f"Malformed JSON in SQL_ROLE_SA_MAP_JSON: {err}") from err

    if not isinstance(data, dict):
        raise ImpersonationError("SQL_ROLE_SA_MAP_JSON must be a JSON object")

    if not data:
        raise ImpersonationError("SQL_ROLE_SA_MAP_JSON cannot be an empty dictionary")

    validated: dict[str, str] = {}
    for role, sa_email in data.items():
        if not isinstance(role, str) or not _ROLE_REGEX.match(role):
            raise ImpersonationError(
                f"Invalid role slug {role!r}; must match ^[a-z0-9][a-z0-9_-]{{0,62}}$"
            )
        if not isinstance(sa_email, str):
            raise ImpersonationError(
                f"Service account for role {role!r} must be a string, got {type(sa_email).__name__}"
            )
        sa_clean = sa_email.strip()
        if not _CUSTOMER_SA_REGEX.match(sa_clean) or _is_google_managed_sa(sa_clean):
            raise ImpersonationError(
                f"Role {role!r} maps to an invalid service account email: {sa_clean!r}. "
                "Must be a customer-managed service account (*.iam.gserviceaccount.com)."
            )
        validated[role] = sa_clean

    return validated


def mint_hmac_role_assertion(
    role: str,
    subject: str,
    *,
    hmac_secret: str,
    audience: str = "bq-caapi-rls",
    ttl_seconds: int = 300,
    now: int | None = None,
) -> str:
    """Mints a local HMAC-SHA256 signed role assertion for development and testing.

    Args:
        role: Valid role slug (e.g. 'apac_analyst').
        subject: Subject identifier (e.g. user email or ID).
        hmac_secret: Shared secret with minimum 32 characters.
        audience: Target audience claim.
        ttl_seconds: Assertion validity duration (1 to 3600 seconds).
        now: Optional epoch timestamp override.

    Returns:
        Compact signed assertion string: 'v1.<payload_b64>.<sig_b64>'.
    """
    if len(hmac_secret) < 32:
        raise ImpersonationError("HMAC secret must be at least 32 characters")
    if not (1 <= ttl_seconds <= 3600):
        raise ImpersonationError("ttl_seconds must be between 1 and 3600")
    if not _ROLE_REGEX.match(role):
        raise ImpersonationError(f"Invalid role slug: {role!r}")
    sub = subject.strip()
    if not sub:
        raise ImpersonationError("subject must not be empty")

    ts = int(time.time() if now is None else now)
    payload = {
        "aud": audience,
        "bqca_role": role,
        "exp": ts + ttl_seconds,
        "iat": ts,
        "iss": "hmac-local",
        "sub": sub,
    }
    raw_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")
    sig = hmac.new(hmac_secret.encode("utf-8"), raw_bytes, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
    return f"v1.{payload_b64}.{sig_b64}"


def verify_role_assertion(
    assertion: str | None,
    *,
    trusted_caller_sa: str | None = None,
    expected_audience: str = "bq-caapi-rls",
    hmac_secret: str | None = None,
    now: int | None = None,
    request: Any = None,
    max_ttl_seconds: int = 900,
    expected_subject: str | None = None,
) -> RoleAssertion:
    """Verifies a signed role assertion from a trusted caller SA or local HMAC secret.

    Args:
        assertion: Raw assertion token string.
        trusted_caller_sa: Expected service account email that signed the OIDC token.
        expected_audience: Expected audience claim.
        hmac_secret: Optional shared secret for HMAC verification in dev/test.
        now: Optional epoch timestamp override.
        request: Optional Google Auth Transport request shim.
        max_ttl_seconds: Maximum allowed assertion TTL (exp - iat) in seconds (default 900).
        expected_subject: Optional expected subject identifier to enforce (sub == expected_subject).

    Returns:
        Verified RoleAssertion with audit job labels.

    Raises:
        ImpersonationError: If assertion is invalid, expired, tampered, or untrusted.
    """
    if assertion is None or not assertion.strip():
        raise ImpersonationError("Role assertion cannot be empty or None")

    token = assertion.strip()
    current_ts = int(time.time() if now is None else now)

    if trusted_caller_sa is not None and trusted_caller_sa.strip():
        trusted_sa = trusted_caller_sa.strip()
        if not _CUSTOMER_SA_REGEX.match(trusted_sa) or _is_google_managed_sa(trusted_sa):
            raise ImpersonationError(
                f"trusted_caller_sa must be a customer-managed service account: {trusted_sa!r}"
            )

        if token.startswith("v1."):
            raise ImpersonationError(
                "HMAC assertions ('v1.') are rejected when trusted_caller_sa is configured (algorithm downgrade prevention)"
            )

        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token
        except ImportError as err:  # pragma: no cover - dependency guard
            raise ImpersonationError("google-auth is required to verify OIDC role assertions") from err

        req = request or google_requests.Request()
        certs_url = f"https://www.googleapis.com/service_accounts/v1/metadata/x509/{urllib.parse.quote(trusted_sa, safe='')}"

        try:
            claims = id_token.verify_token(
                token,
                req,
                audience=expected_audience,
                certs_url=certs_url,
            )
        except Exception as err:
            raise ImpersonationError(f"Role assertion verification failed: {err}") from err

        if not isinstance(claims, dict):
            raise ImpersonationError("Role assertion verification did not return valid claims")

        iss = str(claims.get("iss", "")).strip()
        if iss != trusted_sa:
            raise ImpersonationError(
                f"Role assertion issuer mismatch: expected {trusted_sa!r}, got {iss!r}"
            )

        iat_raw = claims.get("iat")
        if iat_raw is None:
            raise ImpersonationError("Role assertion missing 'iat' claim")
        exp_raw = claims.get("exp")
        if exp_raw is None:
            raise ImpersonationError("Role assertion missing 'exp' claim")
        try:
            iat = int(iat_raw)
            exp = int(exp_raw)
        except (ValueError, TypeError) as err:
            raise ImpersonationError(
                f"Role assertion has invalid integer timestamps (iat={iat_raw}, exp={exp_raw})"
            ) from err

        if iat <= 0:
            raise ImpersonationError(f"Role assertion 'iat' must be a positive integer: {iat}")
        if iat > current_ts + 60:
            raise ImpersonationError(f"Role assertion issued in the future (iat={iat}, current={current_ts})")
        if exp <= current_ts:
            raise ImpersonationError(f"Role assertion has expired (exp={exp}, current={current_ts})")
        ttl = exp - iat
        if ttl <= 0 or ttl > max_ttl_seconds:
            raise ImpersonationError(
                f"Role assertion TTL ({ttl}s) must be positive and <= {max_ttl_seconds}s"
            )

        sub = str(claims.get("sub", "")).strip()
        if not sub:
            raise ImpersonationError("Role assertion missing non-empty 'sub' claim")
        if expected_subject is not None and expected_subject.strip():
            if sub != expected_subject.strip():
                raise ImpersonationError(
                    f"Role assertion subject mismatch: expected {expected_subject.strip()!r}, got {sub!r}"
                )

        role = str(claims.get("bqca_role", "")).strip()
        if not _ROLE_REGEX.match(role):
            raise ImpersonationError(f"Role assertion contains invalid 'bqca_role': {role!r}")

        issuer = iss
        expires_at = exp

    elif hmac_secret is not None and hmac_secret.strip():
        secret = hmac_secret.strip()
        if len(secret) < 32:
            raise ImpersonationError("HMAC secret must be at least 32 characters")

        parts = token.split(".")
        if len(parts) != 3 or parts[0] != "v1":
            raise ImpersonationError("Invalid HMAC assertion format; expected 'v1.<payload>.<sig>'")

        _, payload_b64, sig_b64 = parts
        try:
            payload_bytes = base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4))
            actual_sig = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
        except Exception as err:
            raise ImpersonationError(f"Malformed base64url encoding in assertion: {err}") from err

        expected_sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ImpersonationError("Invalid role assertion HMAC signature")

        try:
            claims = json.loads(payload_bytes.decode("utf-8"))
        except Exception as err:
            raise ImpersonationError(f"Malformed JSON payload in assertion: {err}") from err

        if not isinstance(claims, dict):
            raise ImpersonationError("Assertion payload must be a JSON object")

        aud = claims.get("aud")
        if aud != expected_audience:
            raise ImpersonationError(
                f"Role assertion audience mismatch: expected {expected_audience!r}, got {aud!r}"
            )

        iss = str(claims.get("iss", "")).strip()
        if iss != "hmac-local":
            raise ImpersonationError(f"HMAC assertion must have iss='hmac-local', got {iss!r}")

        iat_raw = claims.get("iat")
        if iat_raw is None:
            raise ImpersonationError("Role assertion missing 'iat' claim")
        exp_raw = claims.get("exp")
        if exp_raw is None:
            raise ImpersonationError("Role assertion missing 'exp' claim")
        try:
            iat = int(iat_raw)
            exp = int(exp_raw)
        except (ValueError, TypeError) as err:
            raise ImpersonationError(
                f"Role assertion has invalid integer timestamps (iat={iat_raw}, exp={exp_raw})"
            ) from err

        if iat <= 0:
            raise ImpersonationError(f"Role assertion 'iat' must be a positive integer: {iat}")
        if iat > current_ts + 60:
            raise ImpersonationError(f"Role assertion issued in the future (iat={iat}, current={current_ts})")
        if exp <= current_ts:
            raise ImpersonationError(f"Role assertion has expired (exp={exp}, current={current_ts})")
        ttl = exp - iat
        if ttl <= 0 or ttl > max_ttl_seconds:
            raise ImpersonationError(
                f"Role assertion TTL ({ttl}s) must be positive and <= {max_ttl_seconds}s"
            )

        sub = str(claims.get("sub", "")).strip()
        if not sub:
            raise ImpersonationError("Role assertion missing non-empty 'sub' claim")
        if expected_subject is not None and expected_subject.strip():
            if sub != expected_subject.strip():
                raise ImpersonationError(
                    f"Role assertion subject mismatch: expected {expected_subject.strip()!r}, got {sub!r}"
                )

        role = str(claims.get("bqca_role", "")).strip()
        if not _ROLE_REGEX.match(role):
            raise ImpersonationError(f"Role assertion contains invalid 'bqca_role': {role!r}")

        issuer = iss
        expires_at = exp

    else:
        raise ImpersonationError(
            "Neither SQL_ROLE_TRUSTED_CALLER_SA nor SQL_ROLE_ASSERTION_HMAC_SECRET is configured"
        )

    user_hash = hashlib.sha256(f"bqca-audit:{sub}".encode("utf-8")).hexdigest()[:16]
    job_labels = {
        "bqca-role": role,
        "bqca-user-hash": user_hash,
    }
    return RoleAssertion(
        role=role,
        subject=sub,
        expires_at=expires_at,
        issuer=issuer,
        job_labels=job_labels,
    )


def build_impersonated_credentials(
    *,
    role: str,
    role_sa_map: Mapping[str, str],
    target_scopes: Sequence[str],
    lifetime_seconds: int = 300,
    source_credentials: Any = None,
) -> tuple[Any, str]:
    """Generates scoped impersonated credentials for the specified role.

    Args:
        role: Role slug to impersonate.
        role_sa_map: Mapping of role slugs to service account emails.
        target_scopes: OAuth scopes required by the client.
        lifetime_seconds: Impersonated token lifetime in seconds (60 to 3600).
        source_credentials: Base credentials initiating the impersonation.

    Returns:
        Tuple of (google.auth.impersonated_credentials.Credentials, target_sa_email).

    Raises:
        ImpersonationError: If role is not mapped, lifetime is invalid, or scopes empty.
    """
    if not (60 <= lifetime_seconds <= 3600):
        raise ImpersonationError("lifetime_seconds must be between 60 and 3600")
    if not target_scopes:
        raise ImpersonationError("target_scopes cannot be empty")

    if role not in role_sa_map:
        raise ImpersonationError(f"Role {role!r} is not mapped in SQL_ROLE_SA_MAP_JSON")

    target_sa = role_sa_map[role]

    try:
        import google.auth
        from google.auth import impersonated_credentials
    except ImportError as err:  # pragma: no cover - dependency guard
        raise ImpersonationError("google-auth is required for service account impersonation") from err

    src_creds = source_credentials
    if src_creds is None:
        src_creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

    creds = impersonated_credentials.Credentials(
        source_credentials=src_creds,
        target_principal=target_sa,
        target_scopes=list(target_scopes),
        lifetime=lifetime_seconds,
    )
    return creds, target_sa


def redact_service_account_emails(
    text: str,
    replacement: str = "[REDACTED_ROLE_SA]",
) -> str:
    """Replaces service account email addresses in error messages or logs.

    Args:
        text: Arbitrary error message or diagnostic output.
        replacement: String to replace service account email with.

    Returns:
        Sanitized text without sensitive service account emails.
    """
    if not text:
        return ""
    return _SA_EMAIL_REDACTION_REGEX.sub(replacement, text)
