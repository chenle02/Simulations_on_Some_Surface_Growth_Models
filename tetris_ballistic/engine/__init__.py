"""Provisional reference-engine API.

This subpackage is intentionally not re-exported from :mod:`tetris_ballistic`
during the 2.1 compatibility series.
"""

from .reference import ContactFace, ContactFaceKind, ReferencePlacement, place_one, validate_periodic_law
from .state import SparseAggregate, WorldCell

__all__ = [
    "ContactFace",
    "ContactFaceKind",
    "ReferencePlacement",
    "SparseAggregate",
    "WorldCell",
    "place_one",
    "validate_periodic_law",
]
