# API Reference — Fingerprint Liveness SDK v2.0

---

## Method: `FingerprintLiveness.analyzeFrame()`

### Input Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `imageBytes` | `Uint8List` | ✅ | JPEG or PNG image as bytes. Any resolution accepted. |
| `hand` | `String` | ✅ | `"RIGHT"` or `"LEFT"` |
| `mode` | `String` | ✅ | `"RIGHT_FOUR"`, `"LEFT_FOUR"`, `"RIGHT_THUMB"`, `"LEFT_THUMB"`, `"SINGLE_FINGER"` |

---

## Output: `FingerprintResult`

### Top-Level Fields

| Field | Type | Description |
|---|---|---|
| `handDetected` | `bool` | Whether a hand was found in the frame |
| `hand` | `String` | Echo of the requested hand side |
| `guidance` | `String?` | Overall guidance message (null if OK) |
| `fingers` | `List<FingerResult>` | Per-finger results (see below) |

---

### Per-Finger: `FingerResult`

| Field | Type | Description |
|---|---|---|
| `fingerId` | `String` | e.g. `RIGHT_INDEX`, `LEFT_THUMB` |
| `detected` | `bool` | Is this finger visible in the frame? |
| `qualityScore` | `double` | Composite quality 0–100. Accept if ≥ 60 |
| `blurScore` | `double?` | Sharpness 0–100 |
| `illumScore` | `double?` | Illumination / contrast 0–100 |
| `liveness` | `bool` | `true` = real finger, `false` = fake/spoof |
| `livenessConf` | `double?` | Confidence of liveness decision 0.0–1.0 |
| `isAiGenerated` | `bool` | `true` if specifically a deepfake/AI image |
| `guidance` | `String?` | **errorMessage** — exact failure reason (null if passed) |
| `bboxPct` | `BboxPct?` | Finger bounding box as % of image |

---

### Bounding Box: `BboxPct`

| Field | Type | Description |
|---|---|---|
| `x` | `double` | Left edge as fraction of image width (0.0–1.0) |
| `y` | `double` | Top edge as fraction of image height (0.0–1.0) |
| `w` | `double` | Width as fraction of image width (0.0–1.0) |
| `h` | `double` | Height as fraction of image height (0.0–1.0) |

---

## Example `guidance` Values

When `liveness == false`, the `guidance` field contains the exact reason:

| guidance Value | What it means |
|---|---|
| `"Screen replay detected — phone border found"` | Physical phone held in front of camera |
| `"Screen replay detected — pixel grid harmonics"` | Phone/monitor screen detected via FFT |
| `"Screen replay detected — unnatural gradient pattern"` | Screen detected via gradient signature |
| `"Screen replay detected — missing 3D surface detail"` | Flat surface (paper/screen) detected |
| `"Deepfake detected — artificial frequency spectrum"` | GAN/Diffusion AI-generated hand |
| `"Deepfake detected — anatomical anomaly in finger length"` | Impossible finger geometry (AI hallucination) |
| `"Spoof detected — flat texture (possible paper print)"` | Printed paper fingerprint |
| `"Spoof detected — no sub-surface blood flow"` | Silicone mold detected |

---

## Flutter Integration Example

```dart
final result = await FingerprintLiveness.analyzeFrame(
  imageBytes: jpegBytes,
  hand: 'RIGHT',
  mode: 'RIGHT_FOUR',
);

if (!result.handDetected) {
  showGuide(result.guidance ?? 'Place your hand in front of the camera');
  return;
}

for (final finger in result.fingers) {
  if (!finger.detected) continue;

  if (finger.liveness && finger.qualityScore >= 60) {
    // ✅ Accept this finger
    markFingerCaptured(finger.fingerId);
  } else if (!finger.liveness) {
    // ❌ Spoof detected — show exact reason
    showAlert('${finger.fingerId}: ${finger.guidance}');
  } else {
    // ⚠️ Low quality — retry
    showGuide('Improve lighting or hold still');
  }
}
```

---

## Acceptance Thresholds

| Condition | Action |
|---|---|
| `liveness == true && qualityScore >= 70` | ✅ Accept — high quality capture |
| `liveness == true && qualityScore >= 60` | ✅ Accept — acceptable quality |
| `liveness == true && qualityScore >= 40` | ⚠️ Retry — low quality |
| `liveness == true && qualityScore < 40` | ❌ Reject — too blurry/dark |
| `liveness == false` | ❌ Reject — spoof detected, show `guidance` |
