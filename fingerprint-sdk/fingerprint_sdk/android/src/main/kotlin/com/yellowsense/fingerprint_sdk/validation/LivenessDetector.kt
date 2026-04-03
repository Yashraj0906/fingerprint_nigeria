package com.yellowsense.fingerprint_sdk.validation

import org.opencv.core.*
import org.opencv.imgproc.Imgproc

/**
 * Multi-layer liveness detection with challenge-response anti-spoof.
 *
 * Layer 1 — LBP texture variance (printed images are flat)
 * Layer 2 — Specular reflection ratio (screens produce uniform highlights)
 * Layer 3 — Micro-movement with natural tremor range check
 * Layer 4 — DFT high-frequency energy (printed ridges lack HF content)
 * Layer 5 — Reflection consistency across frames (screens flicker uniformly)
 * Layer 6 — Edge distortion check (flat prints have unnaturally sharp edges)
 * Layer 7 — Challenge-response: validates movement direction consistency
 */
class LivenessDetector {

    data class LivenessResult(
        val passed: Boolean,
        val reason: String?,
        val confidence: Double  // 0.0–1.0
    )

    companion object {
        init {
            System.loadLibrary("fingerprint_core")
        }
    }

    private external fun nativeEvaluate(grayAddr: Long, bgrAddr: Long, fullBgrAddr: Long, handMode: String): Map<String, Any>

    fun evaluate(gray: Mat, bgr: Mat, fullBgr: Mat, handMode: String = "SINGLE_FINGER"): LivenessResult {
        val res = nativeEvaluate(gray.nativeObjAddr, bgr.nativeObjAddr, fullBgr.nativeObjAddr, handMode)
        
        return LivenessResult(
            passed     = res["passed"] as? Boolean ?: false,
            reason     = res["reason"] as? String,
            confidence = (res["confidence"] as? Float)?.toDouble() ?: 0.0
        )
    }

    fun reset() {
        // No-op for native implementation
    }
}
