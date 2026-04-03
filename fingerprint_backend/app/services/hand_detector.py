"""
Hand Detector Module
Contactless Fingerprint Backend - Finger Detection/Segmentation

ML-based finger detection using MediaPipe Hands.
Supports single-finger mode (backward compat) and 4-finger slap capture.
"""

import cv2
import numpy as np
import mediapipe as mp
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict


# ── Landmark indices ──────────────────────────────────────────────────────────
# Each finger: [MCP base, PIP, DIP, TIP]
_FINGER_LANDMARKS: Dict[str, list] = {
    "THUMB":  [1, 2, 3, 4],
    "INDEX":  [5, 6, 7, 8],
    "MIDDLE": [9, 10, 11, 12],
    "RING":   [13, 14, 15, 16],
    "LITTLE": [17, 18, 19, 20],
}

# Bounding box padding in pixels
_BBOX_PADDING = 15


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class FingerCrop:
    detected:    bool
    crop:        Optional[np.ndarray]
    bbox:        Optional[Tuple[int, int, int, int]]  # x, y, w, h
    is_vertical: bool = False


@dataclass
class HandDetectionResult:
    """Unified result for both single-finger and 4-finger detection."""
    detected:    bool
    confidence:  float
    # Single-finger mode (backward-compatible with liveness_detector)
    finger_crop: Optional[np.ndarray] = None
    bbox:        Optional[Tuple[int, int, int, int]] = None
    # Multi-finger mode
    hand_side:   Optional[str] = None           # "Right" | "Left"
    fingers:     Dict[str, FingerCrop] = field(default_factory=dict)
    guidance:    Optional[str] = None           # real-time guidance text
    raw_landmarks: Optional[object] = None      # Raw MediaPipe NormalizedLandmarkList


# ── Detector class ────────────────────────────────────────────────────────────

class HandDetector:
    """
    Detects and segments fingers from a camera frame using MediaPipe Hands.

    MediaPipe Hands provides:
    - 21 hand landmarks (knuckles, fingertips, etc.)
    - Real-time performance
    - No model training required

    Follows Track A reference implementation structure.
    """

    INDEX_FINGER_BASE = 5
    INDEX_FINGER_TIP  = 8

    def __init__(self, detection_confidence: float = 0.5,
                 tracking_confidence: float = 0.5):
        """
        Args:
            detection_confidence: min confidence for hand detection (0–1)
            tracking_confidence:  min confidence for tracking (0–1)
        0.5 balances accuracy vs. recall for contactless capture.
        """
        self.mp_hands   = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils

        self.hands = self.mp_hands.Hands(
            static_image_mode=True,     # per-frame, no cross-frame tracking
            max_num_hands=1,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        self.BBOX_PADDING = _BBOX_PADDING

    # ── Public API ────────────────────────────────────────────────────────────

    def detect_finger(self, frame: np.ndarray) -> HandDetectionResult:
        """
        Single-finger detection (index finger, TRACK_A compatible).

        Process:
        1. Convert BGR → RGB
        2. Run MediaPipe hand detection
        3. Extract index finger landmarks (5-8)
        4. Build bounding box with padding
        5. Return crop + HandDetectionResult

        Returns HandDetectionResult with finger_crop populated.
        """
        height, width = frame.shape[:2]
        results = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        if not results.multi_hand_landmarks:
            return HandDetectionResult(
                detected=False, confidence=0.0,
                guidance="No hand detected — place your finger in the frame"
            )

        lm   = results.multi_hand_landmarks[0]
        ids  = [self.INDEX_FINGER_BASE, 6, 7, self.INDEX_FINGER_TIP]
        bbox = self._landmarks_to_bbox(lm, ids, width, height)

        if bbox is None:
            return HandDetectionResult(detected=True, confidence=0.6,
                                       guidance="Finger too small — move closer")

        x, y, w, h = bbox
        crop = frame[y:y + h, x:x + w].copy()

        return HandDetectionResult(
            detected=True, confidence=0.88,
            finger_crop=crop, bbox=bbox,
            raw_landmarks=lm,
        )

    def detect_all_fingers(self, frame: np.ndarray) -> HandDetectionResult:
        """
        Detect all 4 fingers (index, middle, ring, little) from one hand.

        Returns individual crops for each finger plus real-time guided capture
        instructions derived from full hand geometry analysis.

        Guidance priority chain (highest to lowest):
          1. Distance  — too far / too close based on wrist-to-fingertip span
          2. Centering — hand outside safe zone of frame
          3. Tilt      — hand rolled sideways (index vs little knuckle height)
          4. Spread    — fingers bunched together
          5. Extension — specific fingers not raised
          6. Orientation — fingers not pointing upward
        """
        height, width = frame.shape[:2]
        results = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        empty = {name: FingerCrop(detected=False, crop=None, bbox=None)
                 for name in _FINGER_LANDMARKS}

        if not results.multi_hand_landmarks:
            return HandDetectionResult(
                detected=False, confidence=0.0, fingers=empty,
                guidance="Place your hand flat in front of the camera"
            )

        # Hand side from MediaPipe classification
        hand_side = None
        if results.multi_handedness:
            hand_side = results.multi_handedness[0].classification[0].label

        lm = results.multi_hand_landmarks[0]

        # ── Geometry guidance (runs before per-finger checks) ─────────────────
        geometry_guidance = self._analyze_hand_geometry(lm)
        if geometry_guidance:
            # Still extract fingers so caller has bbox data, but guidance takes priority
            fingers = self._extract_finger_crops(lm, frame, width, height)
            detected_count = sum(1 for f in fingers.values() if f.detected)
            index_crop  = fingers.get("INDEX")
            finger_crop = index_crop.crop if index_crop and index_crop.detected else None
            return HandDetectionResult(
                detected=True,
                confidence=0.55 + 0.1 * detected_count,
                finger_crop=finger_crop,
                hand_side=hand_side,
                fingers=fingers,
                guidance=geometry_guidance,
                raw_landmarks=lm,
            )

        # ── Per-finger extension + crop ───────────────────────────────────────
        fingers      = self._extract_finger_crops(lm, frame, width, height)
        all_vertical = all(f.is_vertical for f in fingers.values() if f.detected)

        detected_count = sum(1 for f in fingers.values() if f.detected)
        confidence     = 0.88 if detected_count == 4 else 0.55 + 0.1 * detected_count

        # ── Finger-level guidance ─────────────────────────────────────────────
        missing = [n.capitalize() for n, f in fingers.items() if not f.detected]
        if detected_count == 0:
            guidance = "Raise your fingers and point them toward the camera"
        elif missing:
            guidance = "Raise your " + ", ".join(missing) + " finger" + ("s" if len(missing) > 1 else "")
        elif not all_vertical:
            guidance = "Point your fingers straight up toward the camera"
        else:
            guidance = None  # all good — ready to capture

        index_crop  = fingers.get("INDEX")
        finger_crop = index_crop.crop if index_crop and index_crop.detected else None

        return HandDetectionResult(
            detected=True, confidence=confidence,
            finger_crop=finger_crop,
            hand_side=hand_side,
            fingers=fingers,
            guidance=guidance,
            raw_landmarks=lm,
        )

    def is_finger_vertical(self, frame: np.ndarray, tolerance: int = 35) -> bool:
        """
        Check if index finger is roughly vertical (pointing up).
        Returns True if within ±tolerance degrees of vertical.
        """
        results = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if not results.multi_hand_landmarks:
            return False
        lm = results.multi_hand_landmarks[0]
        return self._is_landmarks_vertical(lm, [5, 6, 7, 8])

    def cleanup(self):
        """Release MediaPipe resources."""
        self.hands.close()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _analyze_hand_geometry(self, lm) -> Optional[str]:
        """
        Derive actionable placement guidance from hand landmark geometry.

        All coordinates are MediaPipe-normalized (0.0–1.0 of frame dimensions).
        Returns the single highest-priority guidance string, or None if geometry is good.

        Measurements used:
          - span       : wrist(0) → middle-tip(12) vertical distance → proxy for distance
          - palm_x/y   : centroid of palm landmarks [0,5,9,13,17] → centering
          - tilt       : |index_mcp.y − little_mcp.y| → hand roll (sideways tilt)
          - spread     : |index_tip.x − little_tip.x| → finger spacing
        """
        # ── 1. Distance: wrist-to-middle-fingertip vertical span ─────────────
        # span < 0.30 → hand too small/far away; span > 0.72 → too large/close
        wrist = lm.landmark[0]
        m_tip = lm.landmark[12]
        span  = abs(m_tip.y - wrist.y)
        if span < 0.30:
            return "Move your hand closer to the camera"
        if span > 0.72:
            return "Move your hand back from the camera"

        # ── 2. Centering: palm centroid should stay inside the middle 60% ────
        palm_xs = [lm.landmark[i].x for i in [0, 5, 9, 13, 17]]
        palm_ys = [lm.landmark[i].y for i in [0, 5, 9, 13, 17]]
        palm_x  = float(np.mean(palm_xs))
        palm_y  = float(np.mean(palm_ys))
        if palm_x < 0.20:
            return "Move your hand to the right"
        if palm_x > 0.80:
            return "Move your hand to the left"
        if palm_y < 0.12:
            return "Move your hand down"
        if palm_y > 0.88:
            return "Move your hand up"

        # ── 3. Tilt: index and little MCP knuckles should be at similar heights
        # A large vertical gap means the hand is rolled sideways
        idx_mcp    = lm.landmark[5]
        little_mcp = lm.landmark[17]
        tilt       = abs(idx_mcp.y - little_mcp.y)
        if tilt > 0.10:
            return "Keep your hand level — don't tilt it sideways"

        # ── 4. Spread: index-tip to little-tip horizontal gap ─────────────────
        # spread < 0.12 (normalized) means fingers are bunched together
        idx_tip    = lm.landmark[8]
        little_tip = lm.landmark[20]
        spread     = abs(idx_tip.x - little_tip.x)
        if spread < 0.12:
            return "Spread your fingers apart"

        return None  # geometry is good

    def _extract_finger_crops(self, lm, frame: np.ndarray,
                              width: int, height: int) -> Dict[str, "FingerCrop"]:
        """Extract per-finger crops and extension state from hand landmarks."""
        fingers: Dict[str, FingerCrop] = {}
        for name, ids in _FINGER_LANDMARKS.items():
            if not self._is_finger_extended(lm, ids):
                fingers[name] = FingerCrop(detected=False, crop=None, bbox=None)
                continue
            bbox = self._landmarks_to_bbox(lm, ids, width, height)
            if bbox is None:
                fingers[name] = FingerCrop(detected=False, crop=None, bbox=None)
                continue
            x, y, w, h = bbox
            crop        = frame[y:y + h, x:x + w].copy()
            is_vert     = self._is_landmarks_vertical(lm, ids)
            fingers[name] = FingerCrop(detected=True, crop=crop,
                                       bbox=bbox, is_vertical=is_vert)
        return fingers

    def _landmarks_to_bbox(self, lm, ids: list, width: int, height: int
                           ) -> Optional[Tuple[int, int, int, int]]:
        """Convert landmark indices to a padded bounding box (x, y, w, h)."""
        xs = [lm.landmark[i].x * width  for i in ids]
        ys = [lm.landmark[i].y * height for i in ids]

        x1 = max(0,      int(min(xs)) - self.BBOX_PADDING)
        x2 = min(width,  int(max(xs)) + self.BBOX_PADDING)
        y1 = max(0,      int(min(ys)) - self.BBOX_PADDING)
        y2 = min(height, int(max(ys)) + self.BBOX_PADDING)

        w, h = x2 - x1, y2 - y1
        if w < 40 or h < 40:
            return None
        return (x1, y1, w, h)

    def _is_finger_extended(self, lm, ids: list) -> bool:
        """
        Returns True only if the finger is actually raised/extended.

        Check: tip.y must be clearly ABOVE the MCP base joint in image coordinates
        (y increases downward, so tip.y < mcp.y means the tip is higher on screen).

        A folded/curled finger has its tip near or below the MCP joint.
        Threshold of 0.04 (4% of normalised image height) prevents false positives
        on nearly-flat palms.
        """
        tip_y  = lm.landmark[ids[-1]].y   # fingertip
        base_y = lm.landmark[ids[0]].y    # MCP knuckle
        return tip_y < base_y - 0.04

    def _is_landmarks_vertical(self, lm, ids: list, tolerance: int = 40) -> bool:
        """Check if the finger defined by ids is roughly vertical."""
        tip  = lm.landmark[ids[-1]]
        base = lm.landmark[ids[0]]
        dx   = tip.x - base.x
        dy   = tip.y - base.y
        # angle from vertical (0 = pointing straight up)
        angle = abs(np.degrees(np.arctan2(abs(dx), abs(dy))))
        return angle < tolerance


# ── Module-level singleton + convenience functions ───────────────────────────

_detector = HandDetector(detection_confidence=0.45, tracking_confidence=0.45)


def detect_finger(bgr: np.ndarray) -> HandDetectionResult:
    """Single-finger detection (index finger). Backward-compatible entry point."""
    return _detector.detect_finger(bgr)


def detect_all_fingers(bgr: np.ndarray) -> HandDetectionResult:
    """4-finger detection (index, middle, ring, little) from one hand."""
    return _detector.detect_all_fingers(bgr)
