package com.yellowsense.fingerprint_sdk.processing

import org.opencv.core.*
import org.opencv.imgproc.Imgproc

/**
 * Five-metric quality scorer:
 *   score = 0.25*blur + 0.20*contrast + 0.25*ridgeClarity + 0.20*coverage + 0.10*motionStability
 *
 * Thresholds:
 *   < 40  → reject immediately
 *   40–70 → retry
 *   > 70  → accept
 */
object QualityAnalyzer {

    data class QualityResult(
        val score: Double,           // 0–100 composite
        val blurScore: Double,
        val contrastScore: Double,
        val ridgeScore: Double,
        val coverageScore: Double,
        val motionScore: Double,
        val verdict: Verdict
    ) {
        val passed: Boolean get() = verdict == Verdict.ACCEPT
    }

    enum class Verdict { ACCEPT, RETRY, REJECT }

    init {
        System.loadLibrary("fingerprint_core")
        android.util.Log.i("QualityAnalyzer", "JNI Library loaded (v3.0 - final build fix)")
    }

    private external fun nativeAnalyze(imageAddr: Long): Map<String, Any>

    fun analyze(image: Mat, fullGray: Mat? = null): QualityResult {
        val res = nativeAnalyze(image.nativeObjAddr)
        
        return QualityResult(
            score = (res["compositeScore"] as? Number)?.toDouble() ?: 0.0,
            blurScore = (res["blurScore"] as? Number)?.toDouble() ?: 0.0,
            contrastScore = (res["contrastScore"] as? Number)?.toDouble() ?: 0.0,
            ridgeScore = (res["ridgeClarityScore"] as? Number)?.toDouble() ?: 0.0,
            coverageScore = (res["coverageScore"] as? Number)?.toDouble() ?: 0.0,
            motionScore = (res["orientationScore"] as? Number)?.toDouble() ?: 0.0,
            verdict = when (res["decision"] as? String) {
                "ACCEPT" -> Verdict.ACCEPT
                "RETRY"  -> Verdict.RETRY
                else     -> Verdict.REJECT
            }
        )
    }

    fun resetMotionBaseline() {
        // No-op for native implementation
    }
}
