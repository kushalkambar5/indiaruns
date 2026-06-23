"""
Behavioral Multiplier (multiplicative, range: 0.30–1.20)

A great skill-match candidate who is inactive or unresponsive is, for hiring purposes,
NOT actually available. This multiplier down-weights such candidates significantly.

Signals used (from redrob_signals):
- open_to_work_flag
- last_active_date (recency)
- recruiter_response_rate
- profile_completeness_score
- github_activity_score
- interview_completion_rate
- applications_submitted_30d (actively looking signal)
- saved_by_recruiters_30d (market validation)
"""

from datetime import date, datetime


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def behavioral_multiplier(candidate: dict, reference_date: date | None = None) -> float:
    """
    Returns a multiplier in [0.30, 1.20].
    1.0 = neutral (average candidate with normal signals).
    > 1.0 = high engagement bonus.
    < 1.0 = low engagement penalty.
    """
    signals = candidate.get("redrob_signals", {})
    if not signals:
        return 0.70  # missing signals — assume low engagement

    today = reference_date or date.today()
    multiplier = 1.0

    # -----------------------------------------------------------------------
    # 1. Open to work flag
    # -----------------------------------------------------------------------
    if not signals.get("open_to_work_flag", True):
        multiplier *= 0.88  # not actively looking — still reachable but lower priority

    # -----------------------------------------------------------------------
    # 2. Last active date — recency of platform engagement
    # -----------------------------------------------------------------------
    last_active = _parse_date(signals.get("last_active_date", ""))
    if last_active:
        days_inactive = (today - last_active).days
        if days_inactive > 365:
            multiplier *= 0.45   # over a year inactive — effectively ghosted
        elif days_inactive > 180:
            multiplier *= 0.60
        elif days_inactive > 90:
            multiplier *= 0.78
        elif days_inactive > 30:
            multiplier *= 0.92
        else:
            multiplier *= 1.0    # recently active — no penalty
    else:
        multiplier *= 0.75  # unknown activity date — conservative

    # -----------------------------------------------------------------------
    # 3. Recruiter response rate
    # -----------------------------------------------------------------------
    rr = signals.get("recruiter_response_rate", 0.5)
    if rr is not None:
        if rr < 0.05:
            multiplier *= 0.50   # basically never responds
        elif rr < 0.15:
            multiplier *= 0.70
        elif rr < 0.30:
            multiplier *= 0.87
        elif rr < 0.50:
            multiplier *= 1.0    # neutral
        elif rr < 0.70:
            multiplier *= 1.05
        else:
            multiplier *= 1.10   # high responsiveness is a positive signal

    # -----------------------------------------------------------------------
    # 4. Profile completeness
    # -----------------------------------------------------------------------
    completeness = signals.get("profile_completeness_score", 50) or 50
    if completeness >= 90:
        multiplier *= 1.05
    elif completeness >= 70:
        multiplier *= 1.0
    elif completeness < 40:
        multiplier *= 0.90

    # -----------------------------------------------------------------------
    # 5. GitHub activity (technical credibility signal)
    # -----------------------------------------------------------------------
    gh = signals.get("github_activity_score", -1)
    if gh is not None:
        if gh == -1:
            pass  # no GitHub — neutral (many good engineers don't have public GitHub)
        elif gh >= 70:
            multiplier *= 1.08
        elif gh >= 40:
            multiplier *= 1.03
        elif gh < 10:
            multiplier *= 0.97  # very low GitHub activity — minor flag

    # -----------------------------------------------------------------------
    # 6. Interview completion rate
    # -----------------------------------------------------------------------
    icr = signals.get("interview_completion_rate", 0.5)
    if icr is not None:
        if icr < 0.30:
            multiplier *= 0.85   # bails on interviews — bad signal
        elif icr >= 0.80:
            multiplier *= 1.05

    # -----------------------------------------------------------------------
    # 7. Active applications (are they actually searching?)
    # -----------------------------------------------------------------------
    apps_30d = signals.get("applications_submitted_30d", 0) or 0
    if apps_30d >= 3:
        multiplier *= 1.04   # actively job searching
    elif apps_30d == 0:
        multiplier *= 0.95   # passive — slight downweight

    # -----------------------------------------------------------------------
    # 8. Market validation (recruiters saving profile)
    # -----------------------------------------------------------------------
    saved = signals.get("saved_by_recruiters_30d", 0) or 0
    if saved >= 5:
        multiplier *= 1.03

    # -----------------------------------------------------------------------
    # Cap and return
    # -----------------------------------------------------------------------
    return max(0.30, min(1.20, multiplier))
