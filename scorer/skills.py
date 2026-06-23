"""
Skills Trust Score (weight: 0.25) — OPTIMIZED

Does NOT score by raw skill count. Scores by:
  relevance × proficiency_weight × log(duration_months+1) × log(endorsements+1)

Uses a frozen set lookup (O(1)) for skill relevance classification instead of
iterating over a large keyword set per skill.

Returns a float in [0, 1].
"""

import math

# ---------------------------------------------------------------------------
# JD-relevant skill taxonomy (frozen sets for O(1) lookup)
# ---------------------------------------------------------------------------

MUST_HAVE = frozenset({
    "embeddings", "sentence-transformers", "sentence transformers", "bge", "e5",
    "vector database", "vector db", "vector store",
    "pinecone", "qdrant", "weaviate", "milvus", "faiss",
    "opensearch", "elasticsearch",
    "hybrid search", "dense retrieval", "ann", "hnsw",
    "approximate nearest neighbor",
    "information retrieval", "ranking", "bm25", "learning to rank",
    "l2r", "recommendation system", "recommender system",
    "collaborative filtering", "ndcg", "mrr", "map",
    "nlp", "natural language processing", "text classification",
    "semantic search", "rag", "retrieval augmented generation",
    "python", "pytorch", "transformers", "huggingface", "hugging face",
})

NICE_TO_HAVE = frozenset({
    "lora", "qlora", "peft", "fine-tuning llms", "fine-tuning", "rlhf",
    "xgboost", "lightgbm", "gradient boosting", "learning-to-rank",
    "langchain", "llamaindex", "llm", "large language model",
    "bert", "gpt", "openai", "anthropic",
    "mlflow", "kubeflow", "mlops", "model serving",
    "tensorflow", "keras", "scikit-learn", "sklearn",
    "a/b testing", "experiment design",
    "feature engineering", "feature store",
    "spark", "pyspark", "airflow", "kafka",
    "aws", "gcp", "azure",
    "docker", "kubernetes",
    "sql", "postgresql", "redis",
    "distributed systems",
})

RED_FLAG = frozenset({
    "solidworks", "autocad", "creo", "ansys", "fea",
    "sap", "six sigma", "photoshop", "figma", "illustrator", "adobe",
    "excel", "powerpoint", "word", "content writing", "seo", "marketing",
    "accounting", "tally", "tailwind", "css", "html",
})

PROFICIENCY_WEIGHTS = {
    "expert": 1.0,
    "advanced": 0.75,
    "intermediate": 0.50,
    "beginner": 0.25,
}

# Precomputed log constants for common values
_LOG_CACHE: dict[int, float] = {}


def _log1p_cached(n: int) -> float:
    if n not in _LOG_CACHE:
        _LOG_CACHE[n] = math.log1p(n)
    return _LOG_CACHE[n]


def _log_cached(n: int) -> float:
    key = -n  # use negative key to avoid collision with log1p cache
    if key not in _LOG_CACHE:
        _LOG_CACHE[key] = math.log(n)
    return _LOG_CACHE[key]


def _skill_relevance(name_lower: str) -> tuple[float, bool]:
    """
    O(1) lookup: returns (relevance_score, is_red_flag).
    Falls back to substring matching for compound skill names.
    """
    # Exact match first (O(1))
    if name_lower in MUST_HAVE:
        return 1.0, False
    if name_lower in NICE_TO_HAVE:
        return 0.5, False
    if name_lower in RED_FLAG:
        return 0.0, True

    # Substring match (for compound names like "Fine-tuning LLMs")
    for mh in MUST_HAVE:
        if mh in name_lower or name_lower in mh:
            return 1.0, False
    for nth in NICE_TO_HAVE:
        if nth in name_lower or name_lower in nth:
            return 0.5, False
    for rf in RED_FLAG:
        if rf in name_lower:
            return 0.0, True

    return 0.1, False  # neutral


def skills_score(candidate: dict) -> float:
    """
    Compute skills trust score in [0, 1].
    """
    skills = candidate.get("skills", [])
    if not skills:
        return 0.0

    signals = candidate.get("redrob_signals", {})
    assessment_scores = signals.get("skill_assessment_scores") or {}

    # Lowercase assessment keys once
    assessment_lower = {k.lower(): v for k, v in assessment_scores.items()}

    total_trust = 0.0
    must_have_hits = 0
    red_flag_count = 0

    for skill in skills:
        name = skill.get("name", "").lower().strip()
        proficiency = skill.get("proficiency", "beginner")
        endorsements = int(skill.get("endorsements", 0) or 0)
        duration_months = int(skill.get("duration_months", 0) or 0)

        relevance, is_red_flag = _skill_relevance(name)

        if is_red_flag:
            red_flag_count += 1
            continue
        if relevance == 0.0:
            continue

        pw = PROFICIENCY_WEIGHTS.get(proficiency, 0.25)

        trust = (
            relevance
            * pw
            * _log1p_cached(duration_months)
            * math.log(endorsements + 2)
        )

        # Assessment verification bonus (O(N_assessments) per skill, small)
        for assess_key, assess_val in assessment_lower.items():
            if name in assess_key or assess_key in name:
                if assess_val >= 80:
                    trust *= 1.25
                elif assess_val >= 60:
                    trust *= 1.10
                elif assess_val < 40:
                    trust *= 0.80
                break

        total_trust += trust
        if relevance == 1.0:
            must_have_hits += 1

    # Normalize (50 = ~5 must-have skills at expert/24mo/20 endorsements)
    normalized = total_trust / 50.0
    must_have_bonus = min(0.15, must_have_hits * 0.05)
    red_flag_penalty = min(0.15, red_flag_count * 0.03)

    return max(0.0, min(1.0, normalized + must_have_bonus - red_flag_penalty))
