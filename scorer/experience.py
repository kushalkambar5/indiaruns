"""
Experience Fit Score (weight: 0.15)

Evaluates:
- Years of experience fit to the 5-9 yr JD band
- Ratio of product company vs. consulting/services experience
- Recency: are they still writing code or are they purely in architecture?

Returns a float in [0, 1].
"""

from .career import SERVICES_COMPANIES as _SERVICES_SET


def _is_services(co: str) -> bool:
    co_lower = co.lower().strip()
    return any(svc in co_lower for svc in _SERVICES_SET)

# JD ideal range
YOE_IDEAL_MIN = 5.0
YOE_IDEAL_MAX = 9.0


def _yoe_fit(years: float) -> float:
    """Score years-of-experience fit on a smooth curve."""
    if years < 0:
        return 0.0
    if YOE_IDEAL_MIN <= years <= YOE_IDEAL_MAX:
        return 1.0
    if 4.0 <= years < YOE_IDEAL_MIN:
        return 0.80
    if 3.0 <= years < 4.0:
        return 0.55
    if YOE_IDEAL_MAX < years <= 12.0:
        return 0.65
    if 12.0 < years <= 15.0:
        return 0.40
    if years < 3.0:
        return 0.25
    return 0.20  # >15 years — likely over-senior for founding eng role


def experience_score(candidate: dict) -> float:
    """
    Compute experience fit score in [0, 1].
    """
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])

    yoe = profile.get("years_of_experience", 0) or 0
    base = _yoe_fit(yoe)

    if not career:
        return base * 0.5  # can't validate experience without history

    # -----------------------------------------------------------------------
    # Product company vs. services company ratio
    # -----------------------------------------------------------------------
    total_months = sum(r.get("duration_months", 0) for r in career) or 1
    services_months = sum(
        r.get("duration_months", 0) for r in career
        if _is_services(r.get("company", ""))
    )

    services_ratio = services_months / total_months

    # Consulting-only penalty (matches JD disqualifier)
    if services_ratio > 0.95:
        base -= 0.35
    elif services_ratio > 0.75:
        base -= 0.18
    elif services_ratio > 0.50:
        base -= 0.08

    # Product company bonus
    product_ratio = 1.0 - services_ratio
    if product_ratio > 0.70:
        base += 0.10
    elif product_ratio > 0.50:
        base += 0.05

    # -----------------------------------------------------------------------
    # Recency signal: is current role still a hands-on IC role?
    # -----------------------------------------------------------------------
    current_role = next((r for r in career if r.get("is_current")), None)
    if current_role:
        ct = current_role.get("title", "").lower()
        # Penalty for pure management/architecture (not coding)
        if any(kw in ct for kw in ["vp", "director", "chief", "cto", "head of"]):
            base -= 0.25
        elif "tech lead" in ct and "engineer" not in ct:
            base -= 0.10

    return max(0.0, min(1.0, base))
