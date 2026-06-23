"""
Education Score (weight: 0.05)

Evaluates:
- Field relevance: CS / ML / AI / Data Science > Engineering > other
- Institution tier (tier_1 > tier_2 > tier_3 > tier_4 > unknown)
- Degree level: PhD / M.Tech > B.Tech > other

Returns a float in [0, 1].
"""

# Relevant fields of study
CS_ML_FIELDS = {
    "computer science", "cs", "machine learning", "ml", "artificial intelligence",
    "ai", "data science", "software engineering", "information technology", "it",
    "computer engineering", "information systems",
    "electronics and communication", "electrical engineering",  # adjacent, common in India
    "statistics", "mathematics",  # strong quantitative signal
}

ENGINEERING_FIELDS = {
    "mechanical engineering", "civil engineering", "chemical engineering",
    "aerospace engineering", "industrial engineering",
}

# Fields that are strongly off-domain
UNRELATED_FIELDS = {
    "accounting", "finance", "marketing", "management", "hr", "human resources",
    "literature", "history", "biology", "chemistry", "medicine",
}

TIER_SCORES = {
    "tier_1": 1.0,
    "tier_2": 0.75,
    "tier_3": 0.50,
    "tier_4": 0.30,
    "unknown": 0.20,
}

DEGREE_LEVEL_BONUS = {
    "ph.d": 0.10, "phd": 0.10, "doctorate": 0.10,
    "m.tech": 0.05, "m.e.": 0.05, "m.s.": 0.05, "master": 0.05,
    "m.sc": 0.04, "msc": 0.04,
    "b.tech": 0.0, "b.e.": 0.0, "b.sc": 0.0, "bachelor": 0.0,
}


def _field_relevance(field: str) -> float:
    """Returns field relevance score: 1.0, 0.6, 0.3, or 0.1."""
    fl = (field or "").lower()
    if any(f in fl for f in CS_ML_FIELDS):
        return 1.0
    if any(f in fl for f in ENGINEERING_FIELDS):
        return 0.60
    if any(f in fl for f in UNRELATED_FIELDS):
        return 0.10
    return 0.35  # unknown/other


def _degree_bonus(degree: str) -> float:
    dl = (degree or "").lower()
    for key, bonus in DEGREE_LEVEL_BONUS.items():
        if key in dl:
            return bonus
    return 0.0


def education_score(candidate: dict) -> float:
    """
    Compute education score in [0, 1].
    Uses the highest-relevance education entry.
    """
    education = candidate.get("education", [])

    if not education:
        return 0.15  # missing education — small but non-zero

    best_score = 0.0

    for edu in education:
        field = edu.get("field_of_study", "")
        tier = edu.get("tier", "unknown")
        degree = edu.get("degree", "")

        field_rel = _field_relevance(field)
        tier_s = TIER_SCORES.get(tier, 0.20)
        deg_bonus = _degree_bonus(degree)

        # Combined: field × tier (both matter)
        edu_s = field_rel * tier_s + deg_bonus
        best_score = max(best_score, edu_s)

    return max(0.0, min(1.0, best_score))
