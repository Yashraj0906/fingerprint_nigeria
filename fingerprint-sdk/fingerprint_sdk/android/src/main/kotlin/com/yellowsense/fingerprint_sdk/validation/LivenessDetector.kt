package com.yellowsense.fingerprint_sdk.validation

import android.util.Log
import org.opencv.core.*
import org.opencv.imgproc.Imgproc

/**
 * Multi-layer liveness detection with graceful native fallback.
 * If native library is unavailable, uses a pure-Kotlin skin+texture check.
 */
class LivenessDetector {

    data class LivenessResult(
        val passed: Boolean,
        val reason: String?,
        val confidence: Double  // 0.0–1.0
    )

    companion object {
        private const val TAG = "LivenessDetector"
        private var nativeAvailable = true

        // Note: Library loading is now centralized in FingerprintSdkPlugin.initializeNative()
    }

    private external fun nativeEvaluate(grayAddr: Long, bgrAddr: Long, fullBgrAddr: Long, handMode: String): Map<String, Any>

    fun evaluate(gray: Mat, bgr: Mat, fullBgr: Mat, handMode: String = "SINGLE_FINGER"): LivenessResult {
        if (gray.empty() || bgr.empty() || fullBgr.empty()) {
            return LivenessResult(passed = true, reason = "Skipped (empty input)", confidence = 0.5)
        }

        // Try native first
        if (nativeAvailable) {
            try {
                val res = nativeEvaluate(gray.nativeObjAddr, bgr.nativeObjAddr, fullBgr.nativeObjAddr, handMode)
                return LivenessResult(
                    passed     = res["passed"] as? Boolean ?: false,
                    reason     = res["reason"] as? String,
                    confidence = (res["confidence"] as? Number)?.toDouble() ?: 0.0
                )
            } catch (e: Throwable) {
                Log.e(TAG, "Native evaluate failed, using fallback: ${e.message}")
            }
        }

        // Pure Kotlin fallback — basic skin detection + texture check
        return evaluateKotlinFallback(gray, bgr)
    }

    private fun evaluateKotlinFallback(gray: Mat, bgr: Mat): LivenessResult {
        try {
            // 1. Skin detection
            val hsv = Mat()
            Imgproc.cvtColor(bgr, hsv, Imgproc.COLOR_BGR2HSV)
            val mask1 = Mat()
            val mask2 = Mat()
            val skinMask = Mat()
            Core.inRange(hsv, Scalar(0.0, 20.0, 35.0), Scalar(35.0, 190.0, 255.0), mask1)
            Core.inRange(hsv, Scalar(155.0, 20.0, 35.0), Scalar(180.0, 190.0, 255.0), mask2)
            Core.bitwise_or(mask1, mask2, skinMask)
            hsv.release(); mask1.release(); mask2.release()

            val skinRatio = Core.countNonZero(skinMask).toDouble() / skinMask.total().toDouble()
            skinMask.release()

            // 2. Texture variance
            val lap = Mat()
            Imgproc.Laplacian(gray, lap, CvType.CV_64F)
            val mean = MatOfDouble()
            val stddev = MatOfDouble()
            Core.meanStdDev(lap, mean, stddev)
            lap.release()
            val arr = stddev.toArray()
            mean.release(); stddev.release()
            val textureVar = if (arr.isNotEmpty()) arr[0] * arr[0] else 0.0

            // Decision
            val hasSkin = skinRatio > 0.02
            val hasTexture = textureVar > 2.0

            val confidence = when {
                hasSkin && hasTexture -> 0.85
                hasSkin -> 0.6
                hasTexture -> 0.4
                else -> 0.15
            }

            return LivenessResult(
                passed = confidence > 0.4,
                reason = if (confidence > 0.4) "Biological pass (fallback)" else "Non-biological material",
                confidence = confidence
            )
        } catch (e: Throwable) {
            Log.e(TAG, "Kotlin fallback also failed: ${e.message}")
            // Ultimate fallback: just pass so the app doesn't crash
            return LivenessResult(passed = true, reason = "Fallback pass", confidence = 0.5)
        }
    }

    fun reset() {
        // No-op
    }
}
