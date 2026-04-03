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

    companion object {
        init {
            System.loadLibrary("fingerprint_core")
        }
    }

    private external fun nativeAnalyze(imageAddr: Long): Map<String, Any>

    fun analyze(image: Mat, fullGray: Mat? = null): QualityResult {
        val res = nativeAnalyze(image.nativeObjAddr)
        
        return QualityResult(
            score = (res["compositeScore"] as? Float)?.toDouble() ?: 0.0,
            blurScore = (res["blurScore"] as? Float)?.toDouble() ?: 0.0,
            contrastScore = (res["contrastScore"] as? Float)?.toDouble() ?: 0.0,
            ridgeScore = (res["ridgeClarityScore"] as? Float)?.toDouble() ?: 0.0,
            coverageScore = (res["coverageScore"] as? Float)?.toDouble() ?: 0.0,
            motionScore = (res["orientationScore"] as? Float)?.toDouble() ?: 0.0,
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

    // ─── Individual Metrics ───────────────────────────────────────────────────

    /**
     * Laplacian variance — measures sharpness.
     * Variance ~500 → score 100; variance ~0 → score 0.
     */
    private fun blurScore(gray: Mat): Double {
        val lap = Mat()
        Imgproc.Laplacian(gray, lap, CvType.CV_64F)
        val mean   = MatOfDouble()
        val stddev = MatOfDouble()
        Core.meanStdDev(lap, mean, stddev)
        lap.release()
        val variance = stddev.toArray()[0].let { it * it }
        // Normalise: 500 → 100, clamp
        return (variance / 5.0).coerceIn(0.0, 100.0)
    }

    /**
     * RMS contrast (standard deviation of pixel intensities).
     * stddev ~64 → score 100.
     */
    private fun contrastScore(gray: Mat): Double {
        val mean   = MatOfDouble()
        val stddev = MatOfDouble()
        Core.meanStdDev(gray, mean, stddev)
        return (stddev.toArray()[0] / 0.64).coerceIn(0.0, 100.0)
    }

    /**
     * Ridge clarity: ratio of Canny edge pixels.
     * Ideal fingerprint has ~10–20% edge density.
     */
    private fun ridgeClarityScore(gray: Mat): Double {
        val edges = Mat()
        Imgproc.Canny(gray, edges, 40.0, 120.0)
        val edgePixels = Core.countNonZero(edges).toDouble()
        edges.release()
        val total = (gray.rows() * gray.cols()).toDouble()
        val ratio = edgePixels / total
        // Peak at 15% → score 100; falls off on either side
        val normalised = 1.0 - Math.abs(ratio - 0.15) / 0.15
        return (normalised * 100.0).coerceIn(0.0, 100.0)
    }

    /**
     * Coverage: percentage of non-background pixels (Otsu threshold).
     * A well-placed finger covers 30–80% of the ROI.
     */
    private fun coverageScore(gray: Mat, fullFrame: Mat?): Double {
        val ref = fullFrame ?: gray
        val binary = Mat()
        Imgproc.threshold(ref, binary, 0.0, 255.0, Imgproc.THRESH_BINARY + Imgproc.THRESH_OTSU)
        val nonZero = Core.countNonZero(binary).toDouble()
        binary.release()
        val total = (ref.rows() * ref.cols()).toDouble()
        val ratio = nonZero / total
        // Ideal 30–80% coverage
        return when {
            ratio < 0.30 -> (ratio / 0.30 * 100.0).coerceIn(0.0, 100.0)
            ratio > 0.80 -> ((1.0 - ratio) / 0.20 * 100.0).coerceIn(0.0, 100.0)
            else -> 100.0
        }
    }

    /**
     * Motion stability: inverse of mean absolute difference from previous frame.
     * Low diff → stable → high score.
     */
    private fun motionStabilityScore(gray: Mat): Double {
        val prev = prevFrame
        prevFrame?.release()
        prevFrame = gray.clone()

        if (prev == null || prev.size() != gray.size()) return 100.0

        val diff = Mat()
        Core.absdiff(prev, gray, diff)
        val meanDiff = Core.mean(diff).`val`[0]
        diff.release()

        // meanDiff ~0 → score 100; meanDiff ~20 → score 0
        return (1.0 - (meanDiff / 20.0)).coerceIn(0.0, 1.0) * 100.0
    }
}
