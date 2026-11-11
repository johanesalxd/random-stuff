"""Pure stdlib assumption and numeric reconciliation engine.

Audits analytical prose responses against query result rows and question echo.
Has zero dependencies on gRPC, geminidataanalytics, or ADK.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
import re
from typing import Any

_ASSUMPTION_PATTERN = re.compile(
    r"\b(i\s+assumed|i\s+have\s+assumed|assuming|under\s+the\s+assumption|by\s+assuming)\b",
    re.IGNORECASE,
)

_NUMERIC_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"("
    r"(?:[-+][$€£]|[$€£][-+]|[-+]|[$€£])?[ \t]*"
    r"((\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"(?:[ \t]*(%)|([A-Za-z%]+))?"
    r")"
    r"(?![A-Za-z0-9_])"
)

_ISO_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_MONTH_NAME_DATE_PATTERN = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b"
    r"|\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b",
    re.IGNORECASE,
)

_BENIGN_IDENTIFIER_PATTERN = re.compile(
    r"\b(?:Q[1-4]|H[1-2]|FY\d{2,4}|v\d+(?:\.\d+)*)\b",
    re.IGNORECASE,
)

_SCIENTIFIC_NOTATION_PATTERN = re.compile(r"\b\d+(?:\.\d+)?[eE][+-]?\d+\b")
_UNDERSCORE_NUMBER_PATTERN = re.compile(r"\b\d+_\d+(?:_\d+)*\b")

_ROW_COUNT_NOUN_PATTERN = re.compile(r"^(?:of\s+)?(rows?|records?|results?)\b", re.IGNORECASE)

_ISO_CURRENCY_CODES = frozenset({"usd", "sgd", "eur", "gbp", "jpy", "aud", "cad"})


def has_assumption_markers(prose: str) -> bool:
    """Returns True if the prose contains assumption phrases."""
    return bool(_ASSUMPTION_PATTERN.search(prose))


def reconcile_prose_numbers(
    prose: str,
    *,
    question: str,
    result_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """Reconciles numeric tokens in prose response against result rows and question echo.

    Returns:
        tuple[str, ...]: Unverified numeric tokens found in prose.
    """
    # Normalize Unicode minus to ASCII minus
    clean = prose.replace("\u2212", "-")
    question_clean = question.replace("\u2212", "-")

    # Strip code fences, inline code, numbered lists, markdown bullets
    clean = re.sub(r"```[\s\S]*?```", " ", clean)
    clean = re.sub(r"`[^`]*`", " ", clean)
    clean = re.sub(r"(?m)^\s*\d+[.)]\s+", " ", clean)
    clean = re.sub(r"(?m)^\s*[-*+]\s+", " ", clean)

    # Strip matched ISO dates and month-name dates from prose BEFORE range neutralisation
    valid_dates: set[str] = set(_ISO_DATE_PATTERN.findall(question_clean))
    for m in _MONTH_NAME_DATE_PATTERN.finditer(question_clean):
        valid_dates.add(m.group(0))

    for row in result_rows:
        for val in row.values():
            if isinstance(val, str):
                for d_match in _ISO_DATE_PATTERN.findall(val):
                    valid_dates.add(d_match)
                for m_match in _MONTH_NAME_DATE_PATTERN.finditer(val):
                    valid_dates.add(m_match.group(0))

    for vd in valid_dates:
        clean = clean.replace(vd, " ")

    # Strip benign identifiers (Q1-Q4, H1-H2, FY2026, v1.2)
    clean = _BENIGN_IDENTIFIER_PATTERN.sub(" ", clean)

    unverified: list[str] = []

    # Detect scientific notation and underscore-grouped numbers; flag as unverified
    for sn_match in _SCIENTIFIC_NOTATION_PATTERN.finditer(clean):
        unverified.append(sn_match.group(0))
    clean = _SCIENTIFIC_NOTATION_PATTERN.sub(" ", clean)

    for us_match in _UNDERSCORE_NUMBER_PATTERN.finditer(clean):
        unverified.append(us_match.group(0))
    clean = _UNDERSCORE_NUMBER_PATTERN.sub(" ", clean)

    # Neutralize unsigned hyphenated ranges (tight and space-balanced)
    clean = re.sub(r"(?<![-+.$€£\d])(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(?!\.\d|\d)", r"\1 to \2", clean)
    clean = re.sub(r"(?<![-+.$€£\d])(\d+(?:\.\d+)?)[ \t]+-[ \t]+(\d+(?:\.\d+)?)(?!\.\d|\d)", r"\1 to \2", clean)

    # Standalone calendar years in question (1900-2100)
    question_years: set[float] = set()
    for ym in re.finditer(r"(?<![A-Za-z0-9_])(\d{4})(?![A-Za-z0-9_])", question_clean):
        try:
            y_val = float(ym.group(1))
            if 1900 <= y_val <= 2100:
                question_years.add(y_val)
        except ValueError:
            pass

    # Limit numbers in question (top 5, limit 10)
    question_limit_numbers: set[float] = set()
    for lm in re.finditer(r"\b(?:top|first|last|limit)\s+(\d+)\b", question_clean, flags=re.IGNORECASE):
        try:
            question_limit_numbers.add(float(lm.group(1)))
        except ValueError:
            pass

    cell_numbers: list[float] = []
    for row in result_rows:
        for val in row.values():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                cell_numbers.append(float(val))
            elif isinstance(val, str):
                try:
                    cell_numbers.append(float(val.replace(",", "")))
                except ValueError:
                    pass

    for match in _NUMERIC_TOKEN_PATTERN.finditer(clean):
        raw_token = match.group(1).strip()
        num_str = match.group(2).replace(",", "")
        is_negative = "-" in match.group(1)
        suffix = match.group(4) or match.group(5) or ""
        has_currency = any(c in raw_token for c in ("$", "€", "£"))

        if suffix and suffix.lower() in _ISO_CURRENCY_CODES:
            has_currency = True
            suffix = ""

        has_currency_or_suffix = has_currency or bool(suffix)

        try:
            abs_val = float(num_str)
            token_val = -abs_val if is_negative else abs_val
        except ValueError:
            continue

        # Reject unsupported attached alphanumeric units (3x, 45pct, $2.5bn, 10ms)
        if suffix not in ("", "%", "k", "K", "m", "M", "b", "B"):
            unverified.append(raw_token)
            continue

        # Narrow question-echo exemption: ONLY 4-digit calendar years or explicit limit phrases
        if not has_currency_or_suffix:
            if 1900 <= int(abs_val) <= 2100 and token_val in question_years and "." not in num_str and not is_negative:
                continue
            if token_val in question_limit_numbers and not is_negative and "." not in num_str:
                prefix_context = clean[max(0, match.start() - 20) : match.end()]
                if re.search(rf"\b(?:top|first|last|limit)\s+{re.escape(num_str)}\b", prefix_context, re.IGNORECASE):
                    continue

        # Row-count exemption: ONLY when not currency/suffix, not negative, integer, and followed by row noun
        remainder = clean[match.end() : match.end() + 20].strip()
        if (
            not has_currency_or_suffix
            and not is_negative
            and "." not in num_str
            and _ROW_COUNT_NOUN_PATTERN.match(remainder)
        ):
            if len(result_rows) >= 2 and math.isclose(token_val, len(result_rows), abs_tol=1e-6):
                continue
            if len(result_rows) == 1 and math.isclose(token_val, 1.0, abs_tol=1e-6):
                continue

        decimals = len(num_str.split(".")[1]) if "." in num_str else 0

        if suffix == "%":
            scales = (1.0, 0.01)
        elif suffix in ("k", "K"):
            scales = (1000.0,)
        elif suffix in ("m", "M"):
            scales = (1_000_000.0,)
        elif suffix in ("b", "B"):
            scales = (1_000_000_000.0,)
        else:
            scales = (1.0,)

        matched = False
        for scale in scales:
            nominal_val = token_val * scale
            if decimals > 0 or scale != 1.0 or suffix == "%":
                tol = 0.5 * (10**-decimals) * scale + 1e-9
                if any(abs(c - nominal_val) <= tol for c in cell_numbers):
                    matched = True
                    break
            else:
                for c in cell_numbers:
                    tol = 1e-6 if c.is_integer() else 0.5
                    if abs(c - nominal_val) <= tol:
                        matched = True
                        break
            if matched:
                break

        if not matched:
            unverified.append(raw_token)

    return tuple(unverified)
