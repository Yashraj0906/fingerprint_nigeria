# Fingerprint SDK Build Stabilization (V3.9) - Summary

The Fingerprint SDK 


<<<<<<< HEAD
=======
## 🛠️ Environment & Specifications (For Developers)
To replicate this build in Android Studio or Xcode, ensure your environment matches these versions:
>>>>>>> 5dd63d4 (docs: add environment specifications to walkthrough)

| Component | Version / Specification |
| :--- | :--- |
| **Flutter SDK** | `>= 3.10.0` |
| **Android SDK (Compile/Target)** | `34` |
| **Android NDK / CMake** | `3.22.1` |
| **C++ Standard** | `C++17` |
| **OpenCV SDK** | `4.8.0` |
| **Java / JDK** | `17` |
| **Kotlin** | `1.9.0` |
| **iOS Deployment Target** | `13.0` |
| **CameraX (Android)** | `1.3.1` |

### 🔍 How to Check on GitHub:
To integrate this into a Flutter app:
1.  Copy the `fingerprint_sdk` folder (from `fingerprint-sdk/`) into your project.
2.  Add the native binaries (`.aar` and `.xcframework`) as described in the **Integration Guide**.
3.  Call `FingerprintSdk.instance.startCapture()`!


