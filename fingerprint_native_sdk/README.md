# Fingerprint Liveness SDK — Native Package

This folder contains the native C++ compiled binaries of the Fingerprint Liveness SDK for mobile integration.

## Folder Structure

```
fingerprint_native_sdk/
│
├── android/
│   └── fingerprint-sdk.aar          ← Drop this into your Android project
│
├── ios/
│   └── FingerprintSDK.xcframework/  ← Drop this into your iOS/Xcode project
│
├── flutter_plugin/
│   └── fingerprint_liveness/        ← Flutter plugin that wraps both .aar and .xcframework
│
└── docs/
    ├── INTEGRATION_GUIDE.md         ← Step-by-step Flutter integration instructions
    ├── API_REFERENCE.md             ← All input/output fields documented
    └── CHANGELOG.md                 ← Version history
```

## Quick Start

### Flutter (Recommended)
Add the `flutter_plugin/fingerprint_liveness` folder as a local package in your `pubspec.yaml`:
```yaml
dependencies:
  fingerprint_liveness:
    path: ./fingerprint_native_sdk/flutter_plugin/fingerprint_liveness
```

Then call:
```dart
import 'package:fingerprint_liveness/fingerprint_liveness.dart';

final result = await FingerprintLiveness.analyzeFrame(
  imageBytes: frameBytes,
  hand: 'RIGHT',
  mode: 'RIGHT_FOUR',
);

if (result.liveness) {
  // Real hand — proceed
} else {
  // Fake detected — show result.guidance to user
}
```

## SDK Version
- Version: 2.0.0
- Core: OpenCV 4.x + MediaPipe C++
- Platforms: Android 7.0+ (API 24+), iOS 13+
