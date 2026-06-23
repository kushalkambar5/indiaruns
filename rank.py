"""
Redrob Hackathon — Main Ranking Script
=======================================

Usage:
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Optional:
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv --debug

Constraints (per submission_spec.md):
    - CPU only, ≤5 min wall-clock, ≤16 GB RAM, no network
    - Output: exactly 100 rows, ranks 1-100, score monotonically non-increasing

Architecture:
    1. Stream-load candidates from JSONL
    2. Extract features using scorer/ package
    3. Detect honeypots → evict from top 100
    4. Compute composite score
    5. Sort, take top 100
    6. Generate per-candidate reasoning
    7. Write submission.csv
"""

import argparse
import csv
import gzip
import json
import sys
import time
from datetime import date
from pathlib import Path

from scorer import (
    career_score,
    skills_score,
    experience_score,
    location_score,
    education_score,
    behavioral_multiplier,
    is_honeypot,
)
from reasoning import generate_reasoning

# ---------------------------------------------------------------------------
# Scoring weights (must sum to 1.0 for the additive components)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "career":     0.35,
    "skills":     0.25,
    "experience": 0.15,
    "location":   0.10,
    "education":  0.05,
}
# behavioral_multiplier is multiplicative (applied after weighted sum)
# Weights above sum to 0.90; the remaining 0.10 is "behavioral boost headroom"
# via the multiplier exceeding 1.0

HONEYPOT_SCORE_PENALTY = 0.001  # effectively evicts from top 100

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_candidates(path: str):
    """
    Generator that yields candidate dicts from:
    - .jsonl (one JSON object per line)
    - .jsonl.gz (gzipped JSONL)
    """
    p = Path(path)

    if p.suffix == ".gz":
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

    elif p.suffix == ".jsonl":
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

    else:
        raise ValueError(f"Unsupported file format: {p.suffix}")


# ---------------------------------------------------------------------------
# Scoring pipeline
# ---------------------------------------------------------------------------


def score_candidate(candidate: dict, today: date) -> dict:
    """
    Score a single candidate and return a result dict.
    """
    cid = candidate.get("candidate_id", "UNKNOWN")

    # Component scores
    c_score = career_score(candidate)
    s_score = skills_score(candidate)
    e_score = experience_score(candidate)
    l_score = location_score(candidate)
    edu_score = education_score(candidate)
    beh_mult = behavioral_multiplier(candidate, reference_date=today)
    honeypot = is_honeypot(candidate, reference_date=today)

    # Weighted composite
    raw = (
        WEIGHTS["career"]     * c_score +
        WEIGHTS["skills"]     * s_score +
        WEIGHTS["experience"] * e_score +
        WEIGHTS["location"]   * l_score +
        WEIGHTS["education"]  * edu_score
    )

    # Apply behavioral multiplier
    final = raw * beh_mult

    # Cap at 1.0 (behavioral multiplier > 1.0 can push it over)
    final = min(1.0, final)

    # Minimum relevance gate: if both career and skills are near-zero,
    # this candidate is not in the right domain — cap score hard
    # (prevents location/education pulling up Civil Engineers / Accountants)
    if c_score < 0.05 and s_score < 0.05:
        final = min(final, 0.08)  # hard cap: can't reach top 100 naturally

    # Honeypot penalty
    if honeypot:
        final = HONEYPOT_SCORE_PENALTY

    return {
        "candidate_id": cid,
        "score": final,
        "is_honeypot": honeypot,
        "_breakdown": {
            "career":    c_score,
            "skills":    s_score,
            "experience": e_score,
            "location":  l_score,
            "education": edu_score,
            "behavioral": beh_mult,
        },
        "_candidate": candidate,  # kept for reasoning generation
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run(candidates_path: str, output_path: str, debug: bool = False):
    today = date.today()
    t0 = time.time()

    print(f"[rank.py] Loading candidates from: {candidates_path}", flush=True)

    results = []
    total = 0
    honeypots_found = 0

    for candidate in load_candidates(candidates_path):
        total += 1
        result = score_candidate(candidate, today)
        results.append(result)
        if result["is_honeypot"]:
            honeypots_found += 1

        if total % 10000 == 0:
            elapsed = time.time() - t0
            print(f"  [{total:,} candidates processed in {elapsed:.1f}s]", flush=True)

    t1 = time.time()
    print(f"[rank.py] Scored {total:,} candidates in {t1 - t0:.1f}s", flush=True)
    print(f"[rank.py] Honeypots detected: {honeypots_found}", flush=True)

    # Sort by ROUNDED score descending; break ties by candidate_id ascending.
    # Rounding first ensures the sort key matches the written value exactly,
    # satisfying the validator's tie-break check.
    for r in results:
        r["score_rounded"] = round(r["score"], 4)
    results.sort(key=lambda r: (-r["score_rounded"], r["candidate_id"]))

    # Take top 100
    if len(results) < 100:
        raise ValueError(f"Expected at least 100 candidates for ranking, but only found {len(results)}.")
    top100 = results[:100]

    # Verify score monotonicity (it should be guaranteed by sort, but double-check)
    for i in range(1, len(top100)):
        if top100[i]["score"] > top100[i - 1]["score"] + 1e-9:
            # This shouldn't happen — just a safeguard
            top100[i]["score"] = top100[i - 1]["score"]

    # Generate reasoning and write output
    print(f"[rank.py] Generating reasoning and writing to: {output_path}", flush=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])

        for rank_idx, result in enumerate(top100, start=1):
            cid = result["candidate_id"]
            score = result["score_rounded"]  # already rounded
            candidate = result["_candidate"]

            reasoning = generate_reasoning(
                candidate=candidate,
                rank=rank_idx,
                score=score,
                score_breakdown=result["_breakdown"],
            )

            writer.writerow([cid, rank_idx, score, reasoning])

            if debug:
                bd = result["_breakdown"]
                print(
                    f"  #{rank_idx:3d} | {cid} | score={score:.4f} | "
                    f"C={bd['career']:.2f} S={bd['skills']:.2f} "
                    f"E={bd['experience']:.2f} L={bd['location']:.2f} "
                    f"Edu={bd['education']:.2f} Beh={bd['behavioral']:.2f} "
                    f"{'[HONEYPOT]' if result['is_honeypot'] else ''}"
                )
                print(f"         Reasoning: {reasoning}")

    t2 = time.time()
    print(f"[rank.py] Done. Total time: {t2 - t0:.1f}s", flush=True)
    print(f"[rank.py] Output written to: {output_path}", flush=True)

    if debug:
        # Sanity checks
        import pandas as pd
        df = pd.read_csv(output_path)
        print("\n[DEBUG] Top 10 candidates:")
        print(df.head(10).to_string(index=False))

        # Check score monotonicity
        diffs = df["score"].diff().dropna()
        if (diffs > 1e-9).any():
            print("[WARNING] Score is not monotonically non-increasing!")
        else:
            print("[OK] Score is monotonically non-increasing.")

        # Check unique ranks
        if len(df) != 100:
            print(f"[WARNING] Expected exactly 100 rows in submission, got {len(df)}")
        elif df["rank"].nunique() != 100:
            print("[WARNING] Ranks are not unique!")
        else:
            print("[OK] All 100 ranks are unique (1-100).")

        honeypot_count = (df["score"] <= HONEYPOT_SCORE_PENALTY + 1e-5).sum()
        print(f"[DEBUG] Honeypots in top 100: {honeypot_count}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Redrob Hackathon — Candidate Ranker",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--candidates",
        required=True,
        help="Path to candidates.jsonl or candidates.jsonl.gz",
    )
    parser.add_argument(
        "--out",
        default="./submission.csv",
        help="Output path for the submission CSV",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print detailed per-candidate debug output",
    )
    args = parser.parse_args()

    run(candidates_path=args.candidates, output_path=args.out, debug=args.debug)


if __name__ == "__main__":
    main()
