"""handle-correlation: evidence-strength scoring for observed handles.

Decides whether handles you have already collected belong to one actor. Does
not discover handles. See README for why that line is where it is.
"""

from .ingest import load
from .mutation import (
    MIN_CANDIDATE_LENGTH,
    MutationMatch,
    Normalized,
    candidates_from_name,
    compare,
    normalize,
    root_key,
)
from .signals import (
    Confidence,
    HandleConfidence,
    HandleCorpus,
    Observation,
    all_claims,
    correlation_points,
    handle_similarity_claims,
    lifespan_contradiction_claims,
    linked_identifier_claims,
    shared_identifier_claims,
    temporal_claims,
)

__version__ = "2.0.0"
__all__ = [
    "MIN_CANDIDATE_LENGTH",
    "Confidence",
    "HandleConfidence",
    "HandleCorpus",
    "MutationMatch",
    "Normalized",
    "Observation",
    "__version__",
    "all_claims",
    "candidates_from_name",
    "compare",
    "correlation_points",
    "handle_similarity_claims",
    "lifespan_contradiction_claims",
    "linked_identifier_claims",
    "load",
    "normalize",
    "root_key",
    "shared_identifier_claims",
    "temporal_claims",
]
