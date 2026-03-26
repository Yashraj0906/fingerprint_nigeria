import struct
import base64
import numpy as np
from dataclasses import dataclass
from typing import Optional, List

# ── Constants ─────────────────────────────────────────────────────────────────
_ENDING       = 1
_BIFURCATION  = 2
_BORDER       = 15
_CLUSTER_R    = 12.0
_MAX_MINUTIAE = 80
_MIN_MINUTIAE = 10
_HEADER_SIZE  = 30   # bytes before minutiae array


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

            angle   = _ridge_angle(skeleton, r, c, rows, cols)
            quality = _local_quality(skeleton, r, c, rows, cols)
            minutiae.append(Minutia(c, r, angle, mtype, quality))

    return minutiae


def _ridge_angle(data: np.ndarray, r: int, c: int, rows: int, cols: int) -> int:
    def px(dr: int, dc: int) -> float:
        nr = max(0, min(rows - 1, r + dr))
        nc = max(0, min(cols - 1, c + dc))
        return float(data[nr, nc])

    gx = (
        -px(-2,-2) - 2*px(-1,-2) - px(0,-2) + px(0,2) + 2*px(1,2) + px(2,2)
        + -px(-2,-1) - 2*px(-1,-1) + px(0,1) + 2*px(1,1) + px(2,1)
    )
    gy = (
        -px(-2,-2) - 2*px(-2,-1) - px(-2,0) + px(2,0) + 2*px(2,1) + px(2,2)
        + -px(-1,-2) - 2*px(-1,-1) + px(1,0) + 2*px(1,1) + px(1,2)
    )
    angle_deg = float(np.degrees(np.arctan2(gy, gx)))
    return int(((angle_deg + 360.0) % 360.0) / 360.0 * 255.0)


def _local_quality(data: np.ndarray, r: int, c: int, rows: int, cols: int) -> int:
    def px(dr: int, dc: int) -> float:
        nr = max(0, min(rows - 1, r + dr))
        nc = max(0, min(cols - 1, c + dc))
        return float(data[nr, nc])

    lap = px(-1,0) + px(1,0) + px(0,-1) + px(0,1) - 4 * px(0,0)
    return int(np.clip(abs(lap) / 4.0 * 100.0, 0, 100))


# ── Minutiae filtering ────────────────────────────────────────────────────────

def _filter(raw: List[Minutia], width: int, height: int) -> List[Minutia]:
    sorted_m = sorted(raw, key=lambda m: m.quality, reverse=True)
    accepted: List[Minutia] = []

    for m in sorted_m:
        if not (_BORDER <= m.x <= width - _BORDER):
            continue
        if not (_BORDER <= m.y <= height - _BORDER):
            continue

        too_close = any(
            np.hypot(m.x - e.x, m.y - e.y) < _CLUSTER_R
            for e in accepted
        )
        if not too_close:
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
