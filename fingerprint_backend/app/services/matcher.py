import math
import numpy as np
from typing import Dict, Tuple
from .template_encoder import Minutia, parse

# ── Tuning ────────────────────────────────────────────────────────────────────
_DIST_THRESHOLD  = 20.0   # pixels — max spatial distance for a pair to match
_ANGLE_THRESHOLD = 30.0   # degrees — max angle difference for a pair to match
_MATCH_THRESHOLD = 0.35   # min ratio of matched minutiae to call it a match


def match_templates(template_a: str, template_b: str) -> float:
    """
    Compare two ISO 19794-2 templates.
    Returns a score in [0.0, 1.0].
    Score >= MATCH_THRESHOLD means the two fingers are the same.
    """
    mins_a = parse(template_a)
    mins_b = parse(template_b)

    if not mins_a or not mins_b:
        return 0.0

    matched = 0
    used_b  = set()

    for a in mins_a:
        best_dist  = float('inf')
        best_idx   = -1

        for idx, b in enumerate(mins_b):
            if idx in used_b:
                continue

            dist = math.hypot(a.x - b.x, a.y - b.y)
            if dist >= _DIST_THRESHOLD:
                continue

            angle_diff = abs(_angle_diff_deg(a.angle, b.angle))
            if angle_diff >= _ANGLE_THRESHOLD:
                continue

            if dist < best_dist:
                best_dist = dist
                best_idx  = idx

        if best_idx != -1:
            matched += 1
            used_b.add(best_idx)

    denominator = max(len(mins_a), len(mins_b))
    return matched / denominator if denominator > 0 else 0.0


def is_match(template_a: str, template_b: str) -> Tuple[bool, float]:
    """
    Returns (matched: bool, score: float).
    """
    score = match_templates(template_a, template_b)
    return score >= _MATCH_THRESHOLD, score


def match_against_set(
    probe_templates: Dict[str, str],
    stored_templates: Dict[str, str]
) -> float:
    """
    Compare a set of probe finger templates against a stored set.
    Both dicts are {finger_id → base64_template}.
    Returns the average match score across common fingers.
    """
    common = set(probe_templates.keys()) & set(stored_templates.keys())
    if not common:
        return 0.0

    scores = [
        match_templates(probe_templates[fid], stored_templates[fid])
        for fid in common
    ]
    return float(np.mean(scores))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _angle_diff_deg(a: int, b: int) -> float:
    """
    Compute the smallest angular difference between two ISO angle values (0-255).
    Converts to degrees first.
    """
    deg_a = a / 255.0 * 360.0
    deg_b = b / 255.0 * 360.0
    diff  = abs(deg_a - deg_b) % 360.0
    return diff if diff <= 180.0 else 360.0 - diff
