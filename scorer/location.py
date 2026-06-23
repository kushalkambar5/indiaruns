"""
Location Score (weight: 0.10)

JD prefers: Noida, Pune, Hyderabad, Mumbai, Delhi NCR, Bangalore (open to relocation from).
Outside India: case-by-case, no visa sponsorship.
Notice period: prefers ≤30 days; ≤60 days acceptable; >90 penalized.

Returns a float in [0, 1].
"""

# Preferred cities (in or near these = ideal)
PREFERRED_CITIES = {
    "noida", "pune", "hyderabad", "mumbai", "delhi", "new delhi",
    "gurgaon", "gurugram", "bangalore", "bengaluru", "ncr",
    "delhi ncr", "greater noida",
}

# Tier-1 Indian cities (open for relocation candidates)
TIER1_INDIAN_CITIES = {
    "chennai", "kolkata", "ahmedabad", "jaipur", "lucknow", "chandigarh",
    "kochi", "bhubaneswar", "indore", "surat",
}

# Indian country identifiers
INDIA_INDICATORS = {"india", "in"}


def _city_score(location: str, country: str, willing_to_relocate: bool) -> float:
    loc_lower = (location or "").lower()
    country_lower = (country or "").lower()

    is_india = (
        country_lower in INDIA_INDICATORS
        or "india" in country_lower
        or any(c in loc_lower for c in PREFERRED_CITIES | TIER1_INDIAN_CITIES)
    )

    # Direct hit: preferred city
    if any(c in loc_lower for c in PREFERRED_CITIES):
        return 1.0

    # India Tier-1 city + willing to relocate
    if is_india and any(c in loc_lower for c in TIER1_INDIAN_CITIES):
        return 0.85 if willing_to_relocate else 0.65

    # India, other city, willing to relocate
    if is_india and willing_to_relocate:
        return 0.70

    # India, not willing to relocate
    if is_india:
        return 0.50

    # Outside India, willing to relocate
    if willing_to_relocate:
        return 0.30

    # Outside India, not willing to relocate
    return 0.10


def _notice_period_modifier(notice_days: int) -> float:
    """Returns an additive modifier for notice period."""
    if notice_days <= 0:
        return 0.10   # immediately available
    if notice_days <= 30:
        return 0.08   # ideal
    if notice_days <= 60:
        return 0.0    # acceptable, no change
    if notice_days <= 90:
        return -0.05
    if notice_days <= 120:
        return -0.10
    return -0.18      # >120 days — significant penalty


def location_score(candidate: dict) -> float:
    """
    Compute location + notice period score in [0, 1].
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})

    loc = profile.get("location", "")
    country = profile.get("country", "")
    willing = signals.get("willing_to_relocate", False)
    notice = signals.get("notice_period_days", 60) or 60

    city_s = _city_score(loc, country, willing)
    notice_mod = _notice_period_modifier(int(notice))

    return max(0.0, min(1.0, city_s + notice_mod))
