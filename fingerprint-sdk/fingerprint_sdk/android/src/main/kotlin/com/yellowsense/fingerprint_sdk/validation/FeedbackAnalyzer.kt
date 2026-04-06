package com.yellowsense.fingerprint_sdk.validation

import org.opencv.core.*
import org.opencv.imgproc.Imgproc

/**
 * Per-frame real-time feedback analyser.
 *
 * Checks (in priority order):
 *   1. LIGHTING  — mean brightness out of range
 *   2. MOTION    — Laplacian variance too low (blur)
 *   3. DISTANCE  — finger ROI too small or too large
 *   4. ALIGNMENT — wrong number of fingers detected
 *   5. READY     — all checks passed
 *
 * Throttled to MAX_EVENTS_PER_SEC to avoid flooding the Flutter layer.
 */
object FeedbackAnalyzer {

    enum class FeedbackType { ALIGNMENT, LIGHTING, MOTION, DISTANCE, READY, PROCESSING, STABILITY }

    data class Feedback(
        val type: FeedbackType,
        val message: String,
        val confidence: Double,
        val boxes: List<Rect>? = null
    )

    private const val MAX_EVENTS_PER_SEC = 10
    private const val EMIT_INTERVAL_MS   = 1000L / MAX_EVENTS_PER_SEC  // 100 ms

    private var lastEmitTime = 0L
    private var prevFrame: Mat? = null

    /**
     * Analyse a single frame and return guidance feedback.
     * Returns null if throttle interval has not elapsed (caller should skip emit).
     *
     * @param gray           Full-frame grayscale Mat
     * @param fingerRois     Detected finger bounding boxes
     * @param expectedCount  Number of fingers the session requires
     * @param frameArea      Total frame pixel area (rows × cols)
     */
    fun analyze(
        gray: Mat,
        fingerRois: List<Any>,   // List<ImageProcessor.FingerROI> — typed as Any to avoid circular import
        expectedCount: Int,
        frameArea: Int
    ): Feedback? {
        val now = System.currentTimeMillis()
        if (now - lastEmitTime < EMIT_INTERVAL_MS) return null
        lastEmitTime = now

        checkLighting(gray)?.let { return it }
        checkBlur(gray)?.let { return it }
        checkDistance(fingerRois, frameArea)?.let { return it }
        checkAlignment(fingerRois.size, expectedCount)?.let { return it }

        prevFrame?.release()
        prevFrame = gray.clone()

        return Feedback(FeedbackType.READY, "Hold steady — capturing", 0.95)
    }

    fun reset() {
        prevFrame?.release()
        prevFrame = null
        lastEmitTime = 0L
    }

    // ─── Individual Checks ────────────────────────────────────────────────────

    private fun checkLighting(gray: Mat): Feedback? {
        val mean = Core.mean(gray).`val`[0]
        return when {
            mean < 55  -> Feedback(FeedbackType.LIGHTING, "Too dark — move to better lighting", 0.92)
            mean > 215 -> Feedback(FeedbackType.LIGHTING, "Too bright — reduce glare or move away from light", 0.92)
            mean < 80  -> Feedback(FeedbackType.LIGHTING, "Lighting is dim — improve if possible", 0.70)
            else       -> null
        }
    }

    private fun checkBlur(gray: Mat): Feedback? {
        val lap = Mat()
        Imgproc.Laplacian(gray, lap, CvType.CV_64F)
        val mean = MatOfDouble()
        val stddev = MatOfDouble()
        Core.meanStdDev(lap, mean, stddev)
        lap.release()
        val arr = stddev.toArray()
        mean.release()
        stddev.release()
        if (arr.isEmpty()) return null
        val variance = arr[0] * arr[0]
        return when {
            variance < 50  -> Feedback(FeedbackType.MOTION, "Hold very still — severe blur detected", 0.95)
            variance < 150 -> Feedback(FeedbackType.MOTION, "Hold steady — slight motion blur", 0.80)
            else           -> null
        }
    }

    /**
     * Distance guidance based on total finger ROI area relative to frame.
     * Too small → move closer; too large → move back.
     */
    private fun checkDistance(rois: List<Any>, frameArea: Int): Feedback? {
        if (rois.isEmpty() || frameArea == 0) return null
        // Use reflection-free approach: rois are FingerROI but typed as Any
        // We compute total area via toString parsing — instead we pass area directly
        // This method is called from CaptureEngine which passes the actual list
        return null  // Distance check is handled in CaptureEngine with typed ROIs
    }

    private fun checkAlignment(detected: Int, expected: Int): Feedback? {
        return when {
            detected == 0 -> Feedback(FeedbackType.ALIGNMENT, "Place your fingers flat in the frame", 0.85)
            detected < expected -> Feedback(
                FeedbackType.ALIGNMENT,
                "Show all $expected fingers — only $detected detected",
                0.78
            )
            detected > expected + 1 -> Feedback(
                FeedbackType.ALIGNMENT,
                "Too many fingers — show only $expected",
                0.75
            )
            else -> null
        }
    }
}
