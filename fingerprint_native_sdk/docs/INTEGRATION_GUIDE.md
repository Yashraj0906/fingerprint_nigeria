# Flutter Integration Guide — Fingerprint Liveness SDK v2.0

## Prerequisites
- Flutter 3.0+
- Android: minSdkVersion 24 (Android 7.0+)
- iOS: Deployment target iOS 13+
- Camera permission configured in both platforms

---

## Step 1 — Add the AAR (Android)

1. Copy `android/fingerprint-sdk.aar` into your Flutter project at:
   ```
   android/app/libs/fingerprint-sdk.aar
   ```

2. In `android/app/build.gradle`, add:
   ```gradle
   dependencies {
       implementation fileTree(dir: 'libs', include: ['*.aar'])
   }
   ```

3. Add camera permission in `AndroidManifest.xml`:
   ```xml
   <uses-permission android:name="android.permission.CAMERA" />
   <uses-feature android:name="android.hardware.camera" />
   ```

---

## Step 2 — Add the XCFramework (iOS)

1. Copy `ios/FingerprintSDK.xcframework` into your Flutter project at:
   ```
   ios/Frameworks/FingerprintSDK.xcframework
   ```

2. In Xcode → Target → General → Frameworks, Libraries and Embedded Content:
   - Click `+` → Add `FingerprintSDK.xcframework`
   - Set to **Embed & Sign**

3. Add camera permission in `ios/Runner/Info.plist`:
   ```xml
   <key>NSCameraUsageDescription</key>
   <string>Camera is needed for fingerprint capture</string>
   ```

---

## Step 3 — Use the Flutter Plugin

Add to `pubspec.yaml`:
```yaml
dependencies:
  fingerprint_liveness:
    path: ./fingerprint_native_sdk/flutter_plugin/fingerprint_liveness
```

---

## Step 4 — Capture and Analyze

```dart
import 'package:fingerprint_liveness/fingerprint_liveness.dart';
import 'package:camera/camera.dart';

// Get frame from camera stream
CameraImage frame = ...; // from camera plugin onImageAvailable

// Convert to bytes
final Uint8List imageBytes = await convertCameraImageToJpeg(frame);

// Analyze
final FingerprintResult result = await FingerprintLiveness.analyzeFrame(
  imageBytes: imageBytes,
  hand: 'RIGHT',       // 'RIGHT' or 'LEFT'
  mode: 'RIGHT_FOUR',  // see modes below
);

// Handle result
if (result.handDetected) {
  for (final finger in result.fingers) {
    print('${finger.fingerId}: liveness=${finger.liveness}, quality=${finger.qualityScore}');
    if (!finger.liveness) {
      showAlert(finger.guidance); // Display exact failure reason
    }
  }
}
```

---

## Accepted Mode Values

| Mode | Description |
|---|---|
| `RIGHT_FOUR` | Right hand — Index, Middle, Ring, Little |
| `LEFT_FOUR` | Left hand — Index, Middle, Ring, Little |
| `RIGHT_THUMB` | Right thumb only |
| `LEFT_THUMB` | Left thumb only |
| `SINGLE_FINGER` | Single index finger |

---

## Camera Recommendations (Important)

For best detection accuracy:
- Lock focus to **macro distance (15–25 cm)**
- Use **back camera** (higher resolution than front)
- Minimum recommended: **720p resolution**
- Ensure **adequate lighting** (avoid strong backlighting)

```dart
// Lock macro focus (example using camera plugin)
await cameraController.setFocusMode(FocusMode.locked);
await cameraController.setFocusPoint(Offset(0.5, 0.5));
```

---

## Result Object Reference

See `docs/API_REFERENCE.md` for the full list of all output fields.
