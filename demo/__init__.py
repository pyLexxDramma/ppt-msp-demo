"""PPT → MSP demo pipeline (parse, Mode1, CSV/MPP update)."""

from .parse_pptx import parse_stroyka_pptx
from .mode1 import compute_mode1_schedule
from .build_update import match_and_build_updates, apply_updates_to_csv
from .field_map import CANONICAL_FIELDS, MPP_INTERNAL_TO_CANON

__all__ = [
    "parse_stroyka_pptx",
    "compute_mode1_schedule",
    "match_and_build_updates",
    "apply_updates_to_csv",
    "CANONICAL_FIELDS",
    "MPP_INTERNAL_TO_CANON",
]
