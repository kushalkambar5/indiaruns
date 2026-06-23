# Redrob Intelligent Candidate Discovery & Ranking — INDIARUNS

A CPU-only, zero-network, <5-minute candidate ranker for the **Senior AI Engineer (Founding Team)** role at Redrob AI.

## Architecture

```
candidates.jsonl (100K)
    → Feature Extraction (career / skills / experience / location / education)
    → Behavioral Multiplier (platform engagement signals)
    → Honeypot Detection (timeline impossibility, expert+zero-duration)
    → Composite Score
    → Top 100 Ranked with Per-Candidate Reasoning
    → submission.csv
```

### Scoring Formula

```
score = (
    0.35 × career_score        # IR/ranking/search career evidence
  + 0.25 × skills_score        # Relevant skills × proficiency × duration × endorsements
  + 0.15 × experience_score    # YOE band fit + product company ratio
  + 0.10 × location_score      # India Tier-1 cities + notice period
  + 0.05 × education_score     # CS/ML degree × institution tier
) × behavioral_multiplier      # [0.30, 1.20] based on activity / responsiveness
```

Honeypots are penalized to score ≈ 0.001 (effectively evicted from top 100).

## Quick Start

### Prerequisites
```bash
# Python 3.10+ required
python --version

# Install dependencies (only pandas, for --debug mode)
pip install -r requirements.txt
```

### Run Ranking
```bash
python rank.py \
  --candidates ./candidates.jsonl \
  --out ./submission.csv
```

### Validate Submission
```bash
python "[PUB] India_runs_data_and_ai_challenge/[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge/validate_submission.py" \
  --submission ./submission.csv \
  --candidates ./candidates.jsonl
```

## File Structure

```
INDIARUNS/
├── rank.py                    # Main entrypoint
├── reasoning.py               # Per-candidate reasoning generator
├── scorer/
│   ├── __init__.py
│   ├── career.py              # Career intelligence score (0.35)
│   ├── skills.py              # Skills trust score (0.25)
│   ├── experience.py          # Experience fit score (0.15)
│   ├── location.py            # Location + notice period score (0.10)
│   ├── education.py           # Education score (0.05)
│   ├── behavioral.py          # Behavioral multiplier
│   └── honeypot.py            # Honeypot detection
├── requirements.txt
├── submission_metadata.yaml
└── README.md
```

## Design Decisions

### Why not keyword counting?
The sample submission (provided as a "bad example") ranks HR Managers and Accountants #1-3 because they have many AI keywords. Our `career.py` scorer weights keywords in context — appearing in a role description for an ML/search system is worth far more than appearing in a skills list.

### Why multiplicative behavioral modifier?
A candidate with perfect skills who hasn't logged in for 6 months and has a 5% recruiter response rate is not actually hirable. Down-weighting them multiplicatively (not just additively) ensures they don't appear in our top 100 even if their profile is otherwise excellent.

### How do we avoid honeypots?
Two main signals:
1. `proficiency = "expert"` + `duration_months = 0` → impossible — expert at a skill you've never used
2. Career timeline impossibility — total claimed experience months > months since graduation

### Runtime
- Runtime: ~60-90s on CPU (well within 5-minute budget) for 100K candidates
- No pre-computation required
- No network required during ranking

## Compute Environment
- Python 3.11, CPU only, no GPU
- No external API calls during ranking
- Memory: ~2 GB peak for 100K candidates (profile data is held in memory only briefly)

## Reproduction (Stage 3)
```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```
This single command produces the submission CSV from scratch. Runtime ≤ 5 minutes on any 16 GB CPU machine.
