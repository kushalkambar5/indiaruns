"""
Redrob Candidate Ranking — Scorer Package
Each module returns a normalized score in [0, 1] unless noted.
"""
from .career import career_score
from .skills import skills_score
from .experience import experience_score
from .location import location_score
from .education import education_score
from .behavioral import behavioral_multiplier
from .honeypot import is_honeypot

__all__ = [
    "career_score",
    "skills_score",
    "experience_score",
    "location_score",
    "education_score",
    "behavioral_multiplier",
    "is_honeypot",
]
