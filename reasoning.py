"""
Per-candidate reasoning generator.

Produces specific, factual, non-hallucinated 1-2 sentence reasoning for each candidate.
Generated from structured data only — no LLM calls.

Each reasoning string:
- References specific facts from the candidate's profile
- Connects to JD requirements
- Acknowledges concerns honestly
- Matches the tone/sentiment of the rank (top ranks = positive, bottom ranks = mixed)
"""

import re
from datetime import date, datetime


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


# Key IR/ML skills to highlight in reasoning
HIGHLIGHT_SKILLS = {
    "embeddings", "sentence-transformers", "bge", "e5",
    "faiss", "pinecone", "qdrant", "weaviate", "milvus", "opensearch", "elasticsearch",
    "hybrid search", "retrieval", "ranking", "recommendation",
    "ndcg", "mrr", "map", "bm25", "ltr", "learning to rank",
    "nlp", "transformers", "bert", "llm", "rag",
    "lora", "qlora", "peft", "fine-tuning",
    "pytorch", "python",
}

CONSULTING_COMPANIES = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "hcl", "tech mahindra", "mphasis", "hexaware", "mindtree", "ltimindtree",
}


def _get_top_relevant_skills(skills: list, n: int = 3) -> list[str]:
    """Return top N skills most relevant to the JD."""
    relevant = []
    for skill in skills:
        name = skill.get("name", "").lower()
        if any(hs in name or name in hs for hs in HIGHLIGHT_SKILLS):
            relevant.append(skill.get("name", ""))
    return relevant[:n]


def _has_ir_experience(career: list) -> bool:
    """Check if any role description mentions IR/ranking/search."""
    ir_patterns = [
        re.compile(r"\b(retrieval|ranking|recommendation|vector|embedding|search\s+engine|"
                   r"faiss|pinecone|qdrant|weaviate|milvus|opensearch|bm25|hnsw)\b", re.I)
    ]
    for role in career:
        desc = role.get("description", "")
        if any(p.search(desc) for p in ir_patterns):
            return True
    return False


def _is_consulting_career(career: list) -> bool:
    """Check if majority of career is at consulting firms."""
    total = sum(r.get("duration_months", 0) for r in career) or 1
    cons = sum(
        r.get("duration_months", 0) for r in career
        if any(c in r.get("company", "").lower() for c in CONSULTING_COMPANIES)
    )
    return cons / total > 0.70


def _days_since_active(signals: dict) -> int | None:
    last = _parse_date(signals.get("last_active_date", ""))
    if not last:
        return None
    return (date.today() - last).days


def generate_reasoning(candidate: dict, rank: int, score: float,
                       score_breakdown: dict | None = None) -> str:
    """
    Generate a 1-2 sentence reasoning string for the candidate.

    Args:
        candidate: Full candidate dict
        rank: Final rank (1 = best)
        score: Final composite score
        score_breakdown: Dict with individual component scores (optional)

    Returns:
        A specific, factual reasoning string (≤200 chars recommended).
    """
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})

    yoe = profile.get("years_of_experience", 0) or 0
    title = profile.get("current_title", "Unknown")
    company = profile.get("current_company", "")
    location = profile.get("location", "")
    country = profile.get("country", "")

    rr = signals.get("recruiter_response_rate", 0.5) or 0.5
    notice = signals.get("notice_period_days", 60) or 60
    open_to_work = signals.get("open_to_work_flag", False)
    days_inactive = _days_since_active(signals)
    gh_score = signals.get("github_activity_score", -1)

    relevant_skills = _get_top_relevant_skills(skills)
    has_ir = _has_ir_experience(career)
    consulting_career = _is_consulting_career(career)

    # -----------------------------------------------------------------------
    # Sentence 1: Core profile summary
    # -----------------------------------------------------------------------
    parts1 = []

    # YOE + title
    parts1.append(f"{yoe:.1f}yr {title}")

    # Location
    loc_str = location or country
    if loc_str:
        relocate = signals.get("willing_to_relocate", False)
        if "india" in (country or "").lower() or any(
            c in (location or "").lower()
            for c in ["noida", "pune", "bangalore", "bengaluru", "hyderabad",
                      "mumbai", "delhi", "gurgaon", "gurugram"]
        ):
            parts1.append(f"based in {loc_str}")
        elif relocate:
            parts1.append(f"in {loc_str} (willing to relocate)")
        else:
            parts1.append(f"in {loc_str} (relocation not indicated)")

    # Core technical signal
    if has_ir and rank <= 30:
        parts1.append("career history includes IR/retrieval system deployment")
    elif relevant_skills and rank <= 50:
        parts1.append(f"relevant skills: {', '.join(relevant_skills)}")
    elif consulting_career:
        parts1.append("career mostly in consulting/services firms")

    sentence1 = "; ".join(parts1) + "."

    # -----------------------------------------------------------------------
    # Sentence 2: Positive signal OR honest concern
    # -----------------------------------------------------------------------
    parts2 = []

    # Notice period
    if notice <= 30:
        parts2.append(f"notice period {notice}d (ideal)")
    elif notice > 90:
        parts2.append(f"notice period {notice}d (concern)")

    # Recruiter response
    if rr < 0.15 and rank >= 50:
        parts2.append(f"response rate {rr:.0%} (availability concern)")
    elif rr >= 0.70:
        parts2.append(f"high recruiter response rate ({rr:.0%})")

    # Activity
    if days_inactive is not None and days_inactive > 180:
        parts2.append(f"last active {days_inactive}d ago (possible availability issue)")
    elif not open_to_work and rank <= 50:
        parts2.append("not currently marked open-to-work")

    # GitHub
    if gh_score >= 60:
        parts2.append(f"strong GitHub activity ({gh_score:.0f}/100)")

    # Skills detail for top ranks
    if rank <= 10 and relevant_skills and not has_ir:
        parts2.append(f"skills match: {', '.join(relevant_skills)}")

    # Consulting concern
    if consulting_career and rank <= 20:
        parts2.append("full career at services/consulting firms — cultural fit risk per JD")

    if parts2:
        sentence2 = "; ".join(parts2) + "."
        return f"{sentence1} {sentence2}"
    else:
        return sentence1
