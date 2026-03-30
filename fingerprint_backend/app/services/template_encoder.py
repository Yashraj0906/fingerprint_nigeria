import struct
import base64
import numpy as np
from dataclasses import dataclass
from typing import Optional, List

# ── Constants ─────────────────────────────────────────────────────────────────
_ENDING          = 1
_BIFURCATION     = 2
_BORDER          = 15
_CLUSTER_R       = 12.0
_MAX_MINUTIAE    = 80
_MIN_MINUTIAE    = 10
_HEADER_SIZE     = 30    # bytes before minutiae array
_MIN_RIDGE_PX    = 12    # min skeleton pixels in neighbourhood — filters noise spikes
_FOLLOW_STEPS    = 7     # pixels to follow per branch for angle estimation
_GRID_ROWS       = 4     # spatial distribution grid
_GRID_COLS       = 4
_MAX_PER_CELL    = 5     # max minutiae per grid cell


@dataclass
class Minutia:
    x:       int
    y:       int
    angle:   int   # 0-255  (maps to 0-360°)
    type:    int   # 1=ending  2=bifurcation
    quality: int   # 0-100


# ── Public API ────────────────────────────────────────────────────────────────

def encode(
    skeleton: np.ndarray,
    finger_position: int = 0,
    quality_score: float = 80.0
) -> Optional[str]:
    """
    Extract minutiae from a skeletonised image and return a
    base64-encoded ISO 19794-2 Finger Minutiae Record.
    Returns None when ridge detail is insufficient (< MIN_MINUTIAE).
    """
    minutiae = _extract(skeleton)
    filtered = _filter(minutiae, skeleton.shape[1], skeleton.shape[0])

    if len(filtered) < _MIN_MINUTIAE:
        return None

    return _build_template(
        filtered,
        skeleton.shape[1], skeleton.shape[0],
        finger_position,
        int(np.clip(quality_score, 0, 100))
    )


def parse(b64_template: str) -> List[Minutia]:
    """
    Parse a base64-encoded ISO 19794-2 template back to a list of Minutia.
    Used by the matcher.
    """
    data = base64.b64decode(b64_template)
    if len(data) < _HEADER_SIZE:
        return []

    count = data[29]          # minutiae count is at byte 29
    minutiae: List[Minutia] = []
    offset = _HEADER_SIZE

    for _ in range(count):
        if offset + 6 > len(data):
            break
        b0, b1, b2, b3, angle, quality = data[offset:offset + 6]

        mtype = (b0 >> 6) & 0x03
        x     = ((b0 & 0x3F) << 8) | b1
        y     = ((b2 & 0x3F) << 8) | b3

        minutiae.append(Minutia(x, y, angle, mtype, quality))
        offset += 6

    return minutiae


# ── Minutiae extraction ───────────────────────────────────────────────────────

def _extract(skeleton: np.ndarray) -> List[Minutia]:
    rows, cols = skeleton.shape
    minutiae: List[Minutia] = []

    def px(r: int, c: int) -> int:
        if r < 0 or r >= rows or c < 0 or c >= cols:
            return 0
        return 1 if skeleton[r, c] > 127 else 0

    for r in range(_BORDER, rows - _BORDER):
        for c in range(_BORDER, cols - _BORDER):
            if px(r, c) == 0:
                continue

            n = [
                px(r-1, c-1), px(r-1, c), px(r-1, c+1),
                px(r,   c+1),
                px(r+1, c+1), px(r+1, c), px(r+1, c-1),
                px(r,   c-1)
            ]
            cn = sum(abs(n[i] - n[(i + 1) % 8]) for i in range(8)) // 2

            if cn == 1:
                mtype = _ENDING
            elif cn == 3:
                mtype = _BIFURCATION
            else:
                continue

            # Reject minutiae on very short ridge stubs (noise artifacts)
            if not _has_sufficient_ridge(skeleton, r, c, rows, cols):
                continue

            angle   = _ridge_angle(skeleton, r, c, rows, cols)
            quality = _local_quality(skeleton, r, c, rows, cols)
            minutiae.append(Minutia(c, r, angle, mtype, quality))

    return minutiae


def _follow_ridge(skeleton: np.ndarray, start_r: int, start_c: int,
                  from_r: int, from_c: int, rows: int, cols: int) -> tuple:
    """
    Walk the skeleton ridge from (start_r, start_c) away from (from_r, from_c)
    for up to _FOLLOW_STEPS pixels.  Returns the endpoint (end_r, end_c).

    Used by _ridge_angle to get a stable direction vector instead of a noisy
    single-pixel gradient.
    """
    def px(rr: int, cc: int) -> bool:
        return 0 <= rr < rows and 0 <= cc < cols and skeleton[rr, cc] > 127

    prev_r, prev_c = from_r, from_c
    cur_r,  cur_c  = start_r, start_c

    for _ in range(_FOLLOW_STEPS):
        moved = False
        # 4-connected first (prefer straight path), then diagonal
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
            nr, nc = cur_r + dr, cur_c + dc
            if (nr, nc) != (prev_r, prev_c) and px(nr, nc):
                prev_r, prev_c = cur_r, cur_c
                cur_r, cur_c   = nr, nc
                moved = True
                break
        if not moved:
            break

    return cur_r, cur_c


def _ridge_angle(skeleton: np.ndarray, r: int, c: int, rows: int, cols: int) -> int:
    """
    Estimate minutia angle by following each ridge branch for _FOLLOW_STEPS pixels
    and averaging the resulting direction vectors.

    WHY THIS IS BETTER than a single-point gradient:
    A single gradient pixel is highly sensitive to skeleton noise — one stray
    pixel can flip the angle by 90°+.  Following the ridge several steps smooths
    out local perturbations and gives a direction that reflects the true ridge
    trajectory, which is what ISO 19794-2 angle represents.
    """
    def px(rr: int, cc: int) -> bool:
        return 0 <= rr < rows and 0 <= cc < cols and skeleton[rr, cc] > 127

    neighbors = [
        (r + dr, c + dc)
        for dr in (-1, 0, 1) for dc in (-1, 0, 1)
        if not (dr == 0 and dc == 0) and px(r + dr, c + dc)
    ]

    if not neighbors:
        return 0

    dx_sum, dy_sum = 0.0, 0.0
    for nr, nc in neighbors:
        end_r, end_c = _follow_ridge(skeleton, nr, nc, r, c, rows, cols)
        dx_sum += end_c - c
        dy_sum += end_r - r

    angle_deg = float(np.degrees(np.arctan2(dy_sum, dx_sum)))
    return int(((angle_deg + 360.0) % 360.0) / 360.0 * 255.0)


def _local_quality(skeleton: np.ndarray, r: int, c: int, rows: int, cols: int) -> int:
    """
    Local ridge quality score (0-100).

    Measures skeleton pixel density in a 24×24 neighbourhood.
    A minutia on a strong, continuous ridge has high density; one on a short
    noise stub has few surrounding pixels → low score.

    This replaces the Laplacian magnitude which measured edge sharpness
    (always high on the skeleton by construction) rather than actual ridge quality.
    """
    r1 = max(0, r - 12);  r2 = min(rows, r + 12)
    c1 = max(0, c - 12);  c2 = min(cols, c + 12)
    area    = max(1, (r2 - r1) * (c2 - c1))
    nonzero = int(np.count_nonzero(skeleton[r1:r2, c1:c2] > 127))
    # Dense ridge area: nonzero/area ≈ 0.4-0.6 for a good skeleton crop
    return int(np.clip(nonzero / area * 200.0, 0, 100))


def _has_sufficient_ridge(skeleton: np.ndarray, r: int, c: int,
                          rows: int, cols: int) -> bool:
    """
    Return True only if there are at least _MIN_RIDGE_PX skeleton pixels in the
    immediate neighbourhood of (r, c).

    WHY:  The crossing-number algorithm fires on single isolated pixels and
    tiny noise stubs that survived skeletonization.  These produce false minutiae
    that degrade matching.  A real ridge ending or bifurcation always sits on a
    ridge with many surrounding pixels.
    """
    r1 = max(0, r - 8);  r2 = min(rows, r + 8)
    c1 = max(0, c - 8);  c2 = min(cols, c + 8)
    return int(np.count_nonzero(skeleton[r1:r2, c1:c2] > 127)) >= _MIN_RIDGE_PX


# ── Minutiae filtering ────────────────────────────────────────────────────────

def _filter(raw: List[Minutia], width: int, height: int) -> List[Minutia]:
    """
    Filter raw minutiae list to a clean, well-distributed set.

    Three passes in priority order (all operating on quality-sorted input):
      1. Border exclusion  — discard minutiae too close to crop edges
      2. Proximity cluster — keep only one minutia per _CLUSTER_R radius
      3. Spatial grid cap  — limit to _MAX_PER_CELL per grid cell so minutiae
                             are spread across the fingerprint rather than
                             clumped in one high-texture region

    WHY SPATIAL DISTRIBUTION:
    If 60 of 80 minutiae fall in the upper-left quarter, the matcher only has
    meaningful overlap there.  Enforcing a grid cap ensures the template
    represents the whole fingerprint, which dramatically improves match rate
    when the user presents the finger at a slightly different position.
    """
    sorted_m = sorted(raw, key=lambda m: m.quality, reverse=True)
    accepted:    List[Minutia] = []
    cell_counts: dict          = {}

    cell_w = max(1, width  / _GRID_COLS)
    cell_h = max(1, height / _GRID_ROWS)

    for m in sorted_m:
        # 1. Border exclusion
        if not (_BORDER <= m.x <= width  - _BORDER):
            continue
        if not (_BORDER <= m.y <= height - _BORDER):
            continue

        # 2. Proximity cluster
        if any(np.hypot(m.x - e.x, m.y - e.y) < _CLUSTER_R for e in accepted):
            continue

        # 3. Spatial grid cap
        cell = (int(m.y / cell_h), int(m.x / cell_w))
        if cell_counts.get(cell, 0) >= _MAX_PER_CELL:
            continue

        cell_counts[cell] = cell_counts.get(cell, 0) + 1
        accepted.append(m)

        if len(accepted) >= _MAX_MINUTIAE:
            break

    return accepted


# ── ISO 19794-2 binary builder ────────────────────────────────────────────────

def _build_template(
    minutiae: List[Minutia],
    width: int, height: int,
    finger_position: int,
    finger_quality: int
) -> str:
    count = min(len(minutiae), _MAX_MINUTIAE)
    record_length = _HEADER_SIZE + count * 6 + 2

    buf = bytearray(record_length)

    # Format identifier + version
    buf[0:4]  = b'FMR\x00'
    buf[4:8]  = b' 20\x00'

    # Record length, CBEFF, equipment, dimensions, resolution
    struct.pack_into('>I', buf,  8, record_length)
    struct.pack_into('>H', buf, 12, 0)        # CBEFF product ID
    struct.pack_into('>H', buf, 14, 0)        # capture equipment
    struct.pack_into('>H', buf, 16, width)
    struct.pack_into('>H', buf, 18, height)
    struct.pack_into('>H', buf, 20, 197)      # X resolution (~500 dpi)
    struct.pack_into('>H', buf, 22, 197)      # Y resolution

    buf[24] = 1                               # number of views
    buf[25] = 0                               # reserved
    buf[26] = finger_position & 0xFF
    buf[27] = 0x00                            # view 0, live-scan plain
    buf[28] = finger_quality & 0xFF
    buf[29] = count & 0xFF

    offset = _HEADER_SIZE
    for m in minutiae[:count]:
        type_x_high = ((m.type & 0x03) << 6) | ((m.x >> 8) & 0x3F)
        buf[offset]     = type_x_high & 0xFF
        buf[offset + 1] = m.x & 0xFF
        buf[offset + 2] = (m.y >> 8) & 0x3F
        buf[offset + 3] = m.y & 0xFF
        buf[offset + 4] = m.angle & 0xFF
        buf[offset + 5] = m.quality & 0xFF
        offset += 6

    # No extended data
    struct.pack_into('>H', buf, offset, 0)

    return base64.b64encode(bytes(buf)).decode('utf-8')
