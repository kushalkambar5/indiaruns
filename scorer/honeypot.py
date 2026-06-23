"""
Honeypot Detection

The dataset contains ~80 honeypot candidates with subtly impossible profiles.
Submissions with >10% honeypots in top 100 are disqualified.

Heuristics:
1. Skill contradiction: proficiency="expert" AND duration_months=0
2. Over-perfection: many skills all at "expert" with impossibly high endorsements
3. Experience date impossibility: career role duration >> years since plausible start
4. Impossible YOE: claims 20+ years of experience but education shows recent graduation
5. Title-skills mismatch: title is completely unrelated to skills listed (with extreme values)

Returns True if candidate is likely a honeypot (score should be penalized to near-zero).
"""

from datetime import date, datetime


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def is_honeypot(candidate: dict, reference_date: date | None = None) -> bool:
    """
    Returns True if the candidate profile appears to be a honeypot.
    Conservative: prefer false negatives (missing a honeypot) over false positives
    (wrongly evicting a real candidate).
    """
    today = reference_date or date.today()
    flags = 0

    skills = candidate.get("skills", [])
    career = candidate.get("career_history", [])
    profile = candidate.get("profile", {})
    education = candidate.get("education", [])

    # -----------------------------------------------------------------------
    # Heuristic 1: Expert proficiency with zero months of use
    # -----------------------------------------------------------------------
    expert_zero_duration = sum(
        1 for s in skills
        if s.get("proficiency") == "expert" and (s.get("duration_months") or 0) == 0
    )
    if expert_zero_duration >= 3:
        flags += 2  # multiple "expert" skills with 0 months used = impossible

    # -----------------------------------------------------------------------
    # Heuristic 2: Suspiciously perfect skills (10+ expert skills with high endorsements)
    # -----------------------------------------------------------------------
    expert_skills = [s for s in skills if s.get("proficiency") == "expert"]
    if len(expert_skills) >= 10:
        avg_endorsements = sum(s.get("endorsements", 0) for s in expert_skills) / len(expert_skills)
        if avg_endorsements > 60:
            flags += 2  # 10+ expert skills all with 60+ endorsements — suspicious

    # -----------------------------------------------------------------------
    # Heuristic 3: Career timeline impossibility
    # Total claimed months >> months since graduation
    # NOTE: Only flag if discrepancy is extreme (>2x) — synthetic data has
    # YOE fields set independently from education dates in many normal profiles
    # -----------------------------------------------------------------------
    earliest_grad_year = None
    for edu in education:
        ey = edu.get("end_year")
        if ey and isinstance(ey, int):
            if earliest_grad_year is None or ey < earliest_grad_year:
                earliest_grad_year = ey

    if earliest_grad_year:
        grad_date = date(earliest_grad_year, 6, 1)
        max_work_months = max(0, (today - grad_date).days // 30)
        claimed_total_months = sum(r.get("duration_months", 0) for r in career)
        # Only flag if claimed is MORE THAN 2× what's possible (very conservative)
        # and the claimed total is large enough to matter (>180 months = 15 yrs)
        if claimed_total_months > max_work_months * 2.0 and claimed_total_months > 180:
            flags += 2

    # -----------------------------------------------------------------------
    # Heuristic 4: Individual role impossible duration
    # -----------------------------------------------------------------------
    for role in career:
        start = _parse_date(role.get("start_date", ""))
        dur = role.get("duration_months", 0) or 0
        if start and dur > 0:
            # Role started before 1985 — suspicious for any tech role
            if start.year < 1985:
                flags += 1
            # A single role claims > 25 years (300 months)
            if dur > 300:
                flags += 2

    # NOTE: H5 (YOE vs education gap) removed — synthetic dataset has
    # years_of_experience set independently from education dates, causing
    # 7%+ false positive rate. Real honeypots are caught by H1+H2.

    # -----------------------------------------------------------------------
    # Heuristic 6: All skills at "expert" level
    # -----------------------------------------------------------------------
    if len(skills) >= 15 and len(expert_skills) == len(skills):
        flags += 1

    # -----------------------------------------------------------------------
    # Verdict: honeypot if flags >= 3
    # -----------------------------------------------------------------------
    return flags >= 3
