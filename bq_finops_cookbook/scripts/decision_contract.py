#!/usr/bin/env python3
"""Deterministic guardrail for BigQuery FinOps strategy recommendations.

This is not a pricing engine and does not replace Slot Recommender or human review.
It exists to reject obviously invalid or under-evidenced model recommendations.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

STANDARD_MAX_RESERVATION_SLOTS = 1600
REQUIRED_METRICS = ("avg_slots", "p25_slots", "p50_slots", "p95_slots", "max_slots", "cv")


def _burst_ratio(p95: Optional[float], p50: Optional[float]) -> Optional[float]:
    if p95 is None or p50 is None or p50 <= 0:
        return None
    return p95 / p50


def evaluate_strategy(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Return a bounded strategy classification and evidence warnings.

    Required input fields are documented in tests/fixtures. Thresholds are local
    cookbook heuristics, not Google Cloud product rules.
    """
    warnings = []
    burst = _burst_ratio(metrics.get("p95_slots"), metrics.get("p50_slots"))
    if burst is None and metrics.get("evidence_complete"):
        warnings.append("BURST_RATIO_UNDEFINED")

    if not metrics.get("evidence_complete"):
        return {
            "strategy": "INSUFFICIENT_EVIDENCE",
            "confidence": "LOW",
            "burst_ratio": burst,
            "warnings": ["EVIDENCE_INCOMPLETE"] + warnings,
        }

    missing_or_invalid = [
        name
        for name in REQUIRED_METRICS
        if metrics.get(name) is None
        or not isinstance(metrics.get(name), (int, float))
        or not math.isfinite(float(metrics[name]))
        or float(metrics[name]) < 0
    ]
    if missing_or_invalid:
        return {
            "strategy": "INSUFFICIENT_EVIDENCE",
            "confidence": "LOW",
            "burst_ratio": burst,
            "warnings": ["INVALID_REQUIRED_METRICS:" + ",".join(missing_or_invalid)] + warnings,
        }

    avg_slots = float(metrics.get("avg_slots") or 0)
    p25_slots = float(metrics.get("p25_slots") or 0)
    max_slots = float(metrics.get("max_slots") or 0)
    cv = float(metrics.get("cv") or 0)
    monthly_cost = metrics.get("monthly_on_demand_cost")
    standard_cap = STANDARD_MAX_RESERVATION_SLOTS
    if metrics.get("standard_max_slots") not in (None, standard_cap):
        warnings.append("IGNORED_CALLER_SUPPLIED_STANDARD_CAP")

    if avg_slots < 100 and (monthly_cost is None or float(monthly_cost) < 1000):
        candidate = "ON_DEMAND"
    elif standard_cap > 0 and max_slots > standard_cap:
        candidate = "ENTERPRISE_EVALUATION"
        warnings.append("STANDARD_CAP_EXCEEDED")
    elif cv <= 0.5 and p25_slots >= 50:
        candidate = "ENTERPRISE_BASELINE"
    elif cv > 0.7 and max_slots <= standard_cap:
        candidate = "STANDARD_AUTOSCALING"
    else:
        candidate = "HYBRID_EVALUATION"

    recommender = metrics.get("recommender_strategy")
    if recommender is None:
        warnings.append("RECOMMENDER_UNAVAILABLE")
        confidence = "MEDIUM"
    elif recommender != candidate:
        warnings.append("RECOMMENDER_DISAGREES")
        return {
            "strategy": "REVIEW_REQUIRED",
            "confidence": "LOW",
            "burst_ratio": burst,
            "warnings": warnings,
            "heuristic_candidate": candidate,
            "recommender_strategy": recommender,
        }
    else:
        confidence = "HIGH"

    return {
        "strategy": candidate,
        "confidence": confidence,
        "burst_ratio": burst,
        "warnings": warnings,
        "heuristic_candidate": candidate,
        "recommender_strategy": recommender,
    }
