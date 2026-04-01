# Contactless Biometric SDK - Backend Service

This repository contains the Python (FastAPI/OpenCV) backend and algorithm validation engine for the Contactless Fingerprint Capture SDK. 

## 🛡️ Liveness Detection Engine (AIML Implementation)
**Owner/Developer:** Yashraj Kumar (AIML Intern)

The core focus of this implementation is the highly performant, fully stateless **10-Layer Liveness Detection System**. This system was designed to detect physical presentation attacks (Spoofing) entirely via Mathematical Computer Vision algorithms, avoiding the heavy memory overhead of deep learning models to ensure offline, mid-range mobile compatibility.

### Attack Vectors Defended Against:
1. **Screen Spoofing**: Blocked via Glare Ratios & DFT Moiré grid detection.
2. **Printed Photos**: Blocked via Uniform Reflection & Flat Texture (LBP) checkers.
3. **AI Generated / Deepfake Hands**: Blocked via Frequency Spectra Artifact matching & Anatomical Geometry logic.
4. **3D Physical Molds (Latex/Silicone)**: Blocked via Sub-Surface Blood Scattering (Cr Chroma variance).

### ✅ Core Modified Files (Liveness Integration)
The following files were written/modified to implement this biometric defense architecture:

*   **`app/services/liveness_detector.py`**
    *   **Description:** The core engine. Contains the implementation of the 10-layer mathematical defense system (including the new Spectral AI Anomaly, Anatomical checks, and Sub-Surface Silicone Mold detection).
*   **`app/api/capture.py`**
    *   **Description:** The primary API endpoint router. Modified so that the Liveness engine evaluates each finger crop individually, and outputs explicit AI/Deepfake flags directly in the JSON response payload.
*   **`app/models/schemas.py`**
    *   **Description:** The data structure definitions. `FingerResult` and `AnalyzeFingerResult` were updated to map the liveness confidence scores and the `is_ai_generated` boolean strictly back to the mobile client.
*   **`app/services/hand_detector.py`**
    *   **Description:** The MediaPipe wrapper. Modified to securely pass raw 3D hand structural landmarks directly through to the liveness engine to detect physically impossible AI joint hallucinations.
*   **`app/services/quality_analyzer.py`**
    *   **Description:** The image quality module. Updated to ensure that severe Liveness failures (like Spoofs or Deepfakes) take UI priority over basic quality warnings (like "Move closer").

***

### SDK Handoff Documentation
For instructions on transitioning this Python-OpenCV algorithm logic into Native Android (`.aar`) and Native iOS (`.framework`) C++ binaries for Flutter, please consult the `walkthrough.md` document included in this repository.
