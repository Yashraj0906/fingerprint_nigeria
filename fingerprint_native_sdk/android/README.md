# Place .aar file here

When the C++ native library is compiled for Android, place the output file here:

```
android/fingerprint-sdk.aar
```

## How the .aar is built

The `.aar` is compiled from:
- `liveness_detector.cpp` — Port of `fingerprint_backend/app/services/liveness_detector.py`
- `hand_detector.cpp` — Port of `fingerprint_backend/app/services/hand_detector.py`
- `quality_analyzer.cpp` — Port of `fingerprint_backend/app/services/quality_analyzer.py`

Using:
- **OpenCV 4.x Android SDK**
- **MediaPipe Tasks Android SDK**
- **Android NDK r25+**

## Build Command (once C++ source is ready)
```bash
./gradlew assembleRelease
# Output: build/outputs/aar/fingerprint-sdk-release.aar
```
