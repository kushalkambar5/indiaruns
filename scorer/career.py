"""
Career Intelligence Score (weight: 0.35) — OPTIMIZED

Uses pre-compiled single OR-pattern per tier instead of iterating individual patterns.
Reduces per-candidate regex calls from ~70 patterns × N candidates to 4 patterns × N.

Returns a float in [0, 1].
"""

import re

# ---------------------------------------------------------------------------
# Pre-compiled single combined OR-patterns per tier (built once at import time)
# ---------------------------------------------------------------------------

_T1_PATTERN = re.compile(
    r"retrieval|ranking|ranker|recommendation|recommender"
    r"|vector\s*(?:search|database|db|index|store)"
    r"|embeddings?|faiss|pinecone|qdrant|weaviate|milvus"
    r"|opensearch|elasticsearch"
    r"|hybrid\s*search|dense\s*retrieval|ann\b|hnsw\b|bm25\b"
    r"|ndcg|mrr\b|mean\s*reciprocal\s*rank"
    r"|learning[\s-]to[\s-]rank|lambdamart|listwise|pairwise|pointwise"
    r"|sentence[\s-]transformer|information\s*retrieval"
    r"|semantic\s*search|rag\b|retrieval[\s-]augmented",
    re.IGNORECASE,
)

_T2_PATTERN = re.compile(
    r"\bllm\b|large\s+language\s+model|transformer|bert\b"
    r"|nlp\b|natural\s+language\s+processing"
    r"|fine[\s-]tun|lora\b|qlora\b|peft\b|rlhf\b"
    r"|ml\s+(?:pipeline|platform|system|infrastructure|model)"
    r"|feature\s+(?:store|engineering)|model\s+(?:serving|deployment)"
    r"|a/b\s+test|online\s+(?:experiment|evaluation)|hugging\s*face"
    r"|pytorch|tensorflow|applied\s+(?:ml|ai|science)"
    r"|kubeflow|mlflow|mlops|data\s+scientist",
    re.IGNORECASE,
)

_T3_PATTERN = re.compile(
    r"\bpython\b|pyspark|\bspark\b|\bkafka\b|airflow"
    r"|data\s+engineer|backend\s+engineer"
    r"|machine\s+learning|artificial\s+intelligence",
    re.IGNORECASE,
)

_NEG_PATTERN = re.compile(
    r"solidworks|autocad|\bcreo\b|ansys\b|\bfea\b|cad\s+design"
    r"|civil\s+engineer|structural\s+engineer|mechanical\s+design"
    r"|month[\s-]end\s+close|\bgaap\b|\bind[\s-]as\b"
    r"|content\s+writing|editorial\s+calendar|seo\s+strateg"
    r"|customer\s+support\s+team\s+lead"
    r"|picking,\s+packing|warehouse\s+(?:operation|management)"
    r"|digital\s+marketing|brand\s+identity|packaging\s+design"
    r"|\bsix\s+sigma\b|\bscm\b|\bsap\b",
    re.IGNORECASE,
)

_PROD_SIGNAL = re.compile(
    r"\bproduction\b|\bdeployed\b|\bshipped\b|live\s+users?|real\s+users?|\bscale\b",
    re.IGNORECASE,
)

# Services-only companies (as a set for fast O(1) lookup)
_SERVICES_SET = frozenset({
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "hcl", "tech mahindra", "mphasis", "hexaware", "niit technologies",
    "mindtree", "l&t infotech", "ltimindtree", "dunder mifflin",
})

# Exported for experience.py
SERVICES_COMPANIES = _SERVICES_SET


def _is_services_company(name: str) -> bool:
    n = name.lower().strip()
    return any(svc in n for svc in _SERVICES_SET)


def career_score(candidate: dict) -> float:
    """
    Compute career intelligence score in [0, 1].
    Optimized: single OR-pattern per tier, no per-pattern loop.
    """
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])

    if not career:
        return 0.05

    # -----------------------------------------------------------------------
    # 1. Build combined text corpus (title + summary + all role descriptions)
    # -----------------------------------------------------------------------
    parts = [
        profile.get("headline", ""),
        profile.get("summary", ""),
        profile.get("current_title", ""),
    ]
    for role in career:
        parts.append(role.get("title", ""))
        parts.append(role.get("description", ""))
        parts.append(role.get("industry", ""))
    all_text = " ".join(parts)

    # -----------------------------------------------------------------------
    # 2. Count unique keyword matches per tier using findall (single pass each)
    # -----------------------------------------------------------------------
    t1_hits = len(set(_T1_PATTERN.findall(all_text)))
    t2_hits = len(set(_T2_PATTERN.findall(all_text)))
    t3_hits = len(set(_T3_PATTERN.findall(all_text)))
    neg_hits = len(set(_NEG_PATTERN.findall(all_text)))

    raw_keyword = (t1_hits * 3.0 + t2_hits * 1.5 + t3_hits * 0.5) / 30.0
    keyword_score = min(1.0, raw_keyword)

    # -----------------------------------------------------------------------
    # 3. Production deployment signal (check all role descriptions at once)
    # -----------------------------------------------------------------------
    prod_bonus = 0.0
    for role in career:
        desc = role.get("description", "")
        if len(_PROD_SIGNAL.findall(desc)) >= 2:
            prod_bonus = 0.15
            break

    # -----------------------------------------------------------------------
    # 4. Services company ratio (O(len(career)) simple substring checks)
    # -----------------------------------------------------------------------
    total_months = sum(r.get("duration_months", 0) for r in career) or 1
    services_months = sum(
        r.get("duration_months", 0) for r in career if _is_services_company(r.get("company", ""))
    )
    services_ratio = services_months / total_months

    if services_ratio > 0.95:
        consulting_penalty = 0.35
    elif services_ratio > 0.75:
        consulting_penalty = 0.20
    elif services_ratio > 0.50:
        consulting_penalty = 0.10
    else:
        consulting_penalty = 0.0

    # Product bonus: non-services companies at smaller scale
    product_months = sum(
        r.get("duration_months", 0)
        for r in career
        if not _is_services_company(r.get("company", ""))
        and r.get("company_size", "") in ("1-10", "11-50", "51-200", "201-500", "501-1000")
    )
    product_bonus = min(0.15, (product_months / total_months) * 0.20)

    # -----------------------------------------------------------------------
    # 5. Negative domain penalty
    # -----------------------------------------------------------------------
    neg_penalty = min(0.40, neg_hits * 0.12)

    # -----------------------------------------------------------------------
    # 6. Current role relevance bonus
    # -----------------------------------------------------------------------
    current_role = next((r for r in career if r.get("is_current")), None)
    current_relevance = 0.0
    if current_role:
        ct = current_role.get("title", "") + " " + current_role.get("description", "")
        ct1 = len(set(_T1_PATTERN.findall(ct)))
        ct2 = len(set(_T2_PATTERN.findall(ct)))
        current_relevance = min(0.20, ct1 * 0.08 + ct2 * 0.04)

    # -----------------------------------------------------------------------
    # 7. Compose
    # -----------------------------------------------------------------------
    raw = (
        keyword_score * 0.50
        + prod_bonus
        + product_bonus
        + current_relevance
        - consulting_penalty
        - neg_penalty
    )
    return max(0.0, min(1.0, raw))
