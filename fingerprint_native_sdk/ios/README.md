# Place .xcframework here

When the C++ native library is compiled for iOS, place the output folder here:

```
ios/FingerprintSDK.xcframework/
```

## How the .xcframework is built

The `.xcframework` is compiled from:
- `liveness_detector.cpp` — Port of `fingerprint_backend/app/services/liveness_detector.py`
- `hand_detector.cpp` — Port of `fingerprint_backend/app/services/hand_detector.py`
- `quality_analyzer.cpp` — Port of `fingerprint_backend/app/services/quality_analyzer.py`

Using:
- **OpenCV 4.x iOS framework**
- **MediaPipe Tasks iOS SDK**
- **Xcode 14+ with iOS 13 deployment target**

## Build Command (once C++ source is ready)
```bash
xcodebuild archive \
  -scheme FingerprintSDK \
  -destination "generic/platform=iOS" \
  -archivePath build/ios.xcarchive

xcodebuild -create-xcframework \
  -archive build/ios.xcarchive \
  -framework FingerprintSDK.framework \
  -output FingerprintSDK.xcframework
```
