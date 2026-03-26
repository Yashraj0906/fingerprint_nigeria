# YellowSense Contactless Fingerprint SDK — API Reference

## Overview

Stateless, offline, camera-based fingerprint capture SDK.  
No biometric data is stored. All processing is in-memory.

---

## Quick Start

```dart
// 1. Initialize once
await FingerprintSdk.instance.initialize();

// 2. Subscribe to real-time feedback BEFORE starting capture
FingerprintSdk.instance.feedbackStream.listen((event) {
  print('${event.type.name}: ${event.message} (${event.confidence})');
});

// 3. Start capture
final response = await FingerprintSdk.instance.startCapture(
  CaptureRequest(
    transactionId: 'TXN-001',
    captureMode: CaptureMode.rightFour,
    fingersRequested: [
      FingerId.rightIndex, FingerId.rightMiddle,
      FingerId.rightRing,  FingerId.rightLittle,
    ],
    options: CaptureOptions(
      performLivenessCheck: true,
      performQualityCheck: true,
      returnTemplate: true,
    ),
  ),
);

// 4. Handle response
if (response.overallStatus == CaptureStatus.success) {
  for (final finger in response.results) {
    print('${finger.fingerId}: Q=${finger.qualityScore}');
  }
}
```

---

## Capture Modes

| Mode | Description |
|------|-------------|
| `CaptureMode.leftFour` | Left index, middle, ring, little |
| `CaptureMode.rightFour` | Right index, middle, ring, little |
| `CaptureMode.leftThumb` | Left thumb only |
| `CaptureMode.rightThumb` | Right thumb only |
| `CaptureMode.singleFinger` | Any single finger |
| `CaptureMode.customSequence` | Custom list via `fingersRequested` |
| `CaptureMode.partialCapture` | Supports missing fingers via `missingFingers` |

---

## CaptureRequest

| Field | Type | Description |
|-------|------|-------------|
| `transactionId` | `String` | Unique session ID |
| `captureMode` | `CaptureMode` | Capture mode |
| `fingersRequested` | `List<FingerId>` | Fingers to capture |
| `missingFingers` | `List<FingerId>` | Fingers to skip (amputated etc.) |
| `options` | `CaptureOptions` | Processing options |

### CaptureOptions

| Field | Default | Description |
|-------|---------|-------------|
| `performLivenessCheck` | `true` | Anti-spoof validation |
| `performQualityCheck` | `true` | Quality scoring |
| `returnTemplate` | `true` | Return ISO-style base64 template |
| `returnProcessedImage` | `false` | Return enhanced image (base64) |
| `returnRawImage` | `false` | Return raw crop (base64) |
| `maxRetries` | `3` | Retry attempts before failing |
| `timeoutSeconds` | `30` | Session timeout |

---

## Real-Time Feedback (EventChannel)

Subscribe via `FingerprintSdk.instance.feedbackStream`.

| Type | Trigger | Example Message |
|------|---------|-----------------|
| `ALIGNMENT` | Fingers not detected / misaligned | "Place your fingers in the frame" |
| `LIGHTING` | Under/over-exposed frame | "Too dark — improve lighting" |
| `MOTION` | Blur detected | "Hold steady — motion blur detected" |
| `READY` | All checks passed | "Hold steady — capturing" |
| `PROCESSING` | Post-capture processing | "Processing…" |

---

## CaptureResponse

```
{
  transactionId: String,
  overallStatus: "success" | "failed",
  results: [
    {
      fingerId: String,
      status: "success" | "failed" | "missing",
      qualityScore: double (0–100),
      livenessPassed: bool,
      template: String? (base64),
      rawImage: String? (base64, if enabled),
      processedImage: String? (base64, if enabled),
      errorCode: String?,
      errorMessage: String?
    }
  ]
}
```

---

## Error Codes

| Code | Cause |
|------|-------|
| `CAMERA_PERMISSION_DENIED` | User denied camera access |
| `LOW_QUALITY` | Quality score below threshold after max retries |
| `LIVENESS_FAILED` | Anti-spoof check failed |
| `TIMEOUT` | Session exceeded `timeoutSeconds` |
| `DEVICE_UNSUPPORTED` | Camera or OpenCV unavailable |
| `CAPTURE_ABORTED` | `stopCapture()` called mid-session |
| `UNKNOWN` | Unexpected internal error |

---

## SDK Methods

| Method | Description |
|--------|-------------|
| `initialize()` | Init camera + ML models. Call once. |
| `startCapture(request)` | Begin capture session. Returns `CaptureResponse`. |
| `stopCapture()` | Abort in-progress session. |
| `dispose()` | Release camera + resources. |
| `getVersion()` | Returns SDK version string. |

---

## Security Notes

- Biometric data is **never persisted** to disk
- Raw images are only returned if `returnRawImage: true` is explicitly set
- Set `returnRawImage: false` and `returnProcessedImage: false` for maximum privacy
- Templates are in-memory base64 — integrator is responsible for secure transmission

---

## Platform Requirements

| Platform | Min Version |
|----------|-------------|
| Android | API 21 (Android 5.0) |
| iOS | iOS 13.0 |

### Android Dependencies
- CameraX 1.3.x
- OpenCV Android 4.8.x (add AAR to project)

### iOS Dependencies
- AVFoundation (system)
- CoreImage (system)
- Accelerate (system)
