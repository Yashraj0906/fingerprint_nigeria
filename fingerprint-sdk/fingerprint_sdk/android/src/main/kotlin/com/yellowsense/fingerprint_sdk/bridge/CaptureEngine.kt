package com.yellowsense.fingerprint_sdk.bridge

import android.util.Log
import androidx.camera.core.ImageProxy
import androidx.lifecycle.LifecycleOwner
import com.yellowsense.fingerprint_sdk.analytics.DeviceProfiler
import com.yellowsense.fingerprint_sdk.analytics.ValidationManager
import com.yellowsense.fingerprint_sdk.camera.CameraManager
import com.yellowsense.fingerprint_sdk.processing.ImageProcessor
import com.yellowsense.fingerprint_sdk.processing.QualityAnalyzer
import com.yellowsense.fingerprint_sdk.processing.TemplateEncoder
import com.yellowsense.fingerprint_sdk.validation.FeedbackAnalyzer
import com.yellowsense.fingerprint_sdk.validation.LivenessDetector
import io.flutter.plugin.common.EventChannel
import kotlinx.coroutines.*
import org.opencv.core.Mat
import org.opencv.imgproc.Imgproc

/**
 * Production-grade capture orchestrator.
 *
 * Additions over v2:
 *   - ValidationManager: per-session metrics + failure analytics
 *   - DeviceProfiler: adaptive resolution + processing complexity
 *   - Smart retry UX: contextual suggestions after repeated failures
 *   - Auto-fallback to SINGLE_FINGER mode after persistent quality failures
 *   - Confidence score: composite of quality + liveness + segmentation
 *   - failureReason field in per-finger response
 *   - Template null-check: LOW_QUALITY if minutiae < threshold
 *   - Full memory safety: all Mats released in finally blocks
 */
class CaptureEngine(
    private val cameraManager: CameraManager,
    private var feedbackSink: EventChannel.EventSink?,
    private val lifecycleOwner: LifecycleOwner,
    private val debugMode: Boolean = false,
    private val deviceProfile: DeviceProfiler.DeviceProfile
) {
    companion object {
        private const val TAG = "CaptureEngine"
        // After this many consecutive quality failures, suggest single-finger mode
        private const val QUALITY_FAIL_THRESHOLD = 6
    }

    private val scope            = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private val livenessDetector = LivenessDetector()
    val validationManager        = ValidationManager()

    @Volatile private var isCapturing = false
    private var captureJob: Job? = null

    // ─── Session config ───────────────────────────────────────────────────────
    private var transactionId    = ""
    private var fingersRequested = listOf<String>()
    private var missingFingers   = listOf<String>()
    private var performLiveness  = true
    private var performQuality   = true
    private var returnTemplate   = true
    private var returnProcessed  = false
    private var returnRaw        = false
    private var maxRetries       = 3
    private var timeoutSeconds   = 30

    // ─── Per-finger state ─────────────────────────────────────────────────────
    private data class FrameCandidate(
        val qualityScore: Double,
        val livenessConfidence: Double,
        val segmentationConfidence: Double,
        val enhanced: Mat,
        val ridges: Mat,
        val raw: Mat?,
        val livenessPassed: Boolean
    ) {
        // Composite confidence score
        val confidenceScore: Double get() =
            qualityScore * 0.50 + livenessConfidence * 100 * 0.30 + segmentationConfidence * 100 * 0.20
    }

    data class FingerCapture(
        val fingerId: String,
        var qualityScore: Double    = 0.0,
        var livenessPassed: Boolean = false,
        var confidenceScore: Double = 0.0,
        var template: String?       = null,
        var processedImage: String? = null,
        var rawImage: String?       = null,
        var status: String          = "failed",
        var errorCode: String?      = null,
        var errorMessage: String?   = null,
        var failureReason: String?  = null   // LOW_LIGHT | BLUR | LIVENESS_FAIL | LOW_QUALITY
    )

    private val candidates    = mutableMapOf<String, MutableList<FrameCandidate>>()
    private val fingerResults = mutableMapOf<String, FingerCapture>()
    private val retryCounts   = mutableMapOf<String, Int>()
    private var totalQualityFailures = 0
    private var singleFingerFallback = false

    // ─── Public API ───────────────────────────────────────────────────────────

    fun updateFeedbackSink(sink: EventChannel.EventSink?) { feedbackSink = sink }

    fun configure(params: Map<*, *>) {
        transactionId    = params["transactionId"] as? String ?: ""
        fingersRequested = (params["fingersRequested"] as? List<*>)?.map { it.toString() } ?: emptyList()
        missingFingers   = (params["missingFingers"]  as? List<*>)?.map { it.toString() } ?: emptyList()

        val opts = params["options"] as? Map<*, *> ?: emptyMap<Any, Any>()
        performLiveness  = opts["performLivenessCheck"]  as? Boolean ?: true
        performQuality   = opts["performQualityCheck"]   as? Boolean ?: true
        returnTemplate   = opts["returnTemplate"]        as? Boolean ?: true
        returnProcessed  = opts["returnProcessedImage"]  as? Boolean ?: false
        returnRaw        = opts["returnRawImage"]        as? Boolean ?: false
        maxRetries       = (opts["maxRetries"]           as? Int)    ?: 3
        timeoutSeconds   = (opts["timeoutSeconds"]       as? Int)    ?: 30

        missingFingers.forEach { fid ->
            fingerResults[fid] = FingerCapture(fid, status = "missing")
        }

        if (debugMode) Log.d(TAG, "Configured txn=$transactionId fingers=$fingersRequested device=${deviceProfile.tier}")
    }

    fun start(onComplete: (Map<String, Any>) -> Unit, onError: (String, String) -> Unit) {
        isCapturing = true
        livenessDetector.reset()
        FeedbackAnalyzer.reset()
        QualityAnalyzer.resetMotionBaseline()
        validationManager.onSessionStart()
        totalQualityFailures = 0
        singleFingerFallback = false

        captureJob = scope.launch {
            val timeoutJob = launch {
                delay(timeoutSeconds * 1000L)
                if (isCapturing) {
                    isCapturing = false
                    releaseCandidates()
                    validationManager.onSessionFailure(ValidationManager.FailureReason.TIMEOUT)
                    validationManager.logSnapshot(TAG)
                    withContext(Dispatchers.Main) {
                        onError("TIMEOUT", "Capture timed out after $timeoutSeconds seconds")
                    }
                }
            }

            cameraManager.onFrame = { frame ->
                if (isCapturing) scope.launch { processFrame(frame, onComplete, onError) }
                else frame.close()
            }

            withContext(Dispatchers.Main) { cameraManager.start(lifecycleOwner) }
            while (isCapturing) delay(50)
            timeoutJob.cancel()
        }
    }

    fun stop() {
        isCapturing = false
        captureJob?.cancel()
        cameraManager.stop()
        livenessDetector.reset()
        FeedbackAnalyzer.reset()
        QualityAnalyzer.resetMotionBaseline()
        releaseCandidates()
        validationManager.reset()
        if (debugMode) Log.d(TAG, "Capture stopped")
    }

    // ─── Frame Processing ─────────────────────────────────────────────────────

    private suspend fun processFrame(
        frame: ImageProxy,
        onComplete: (Map<String, Any>) -> Unit,
        onError: (String, String) -> Unit
    ) {
        val frameToken = validationManager.onFrameStart()
        var bgr: Mat? = null
        var gray: Mat? = null

        try {
            bgr  = ImageProcessor.yuvToMat(frame)
            frame.close()
            gray = Mat()
            Imgproc.cvtColor(bgr, gray, Imgproc.COLOR_BGR2GRAY)

            val maxFingers    = if (singleFingerFallback) 1 else fingersRequested.size
            val segments      = ImageProcessor.segmentFingers(bgr, maxFingers)
            val expectedCount = if (singleFingerFallback) 1
                                else fingersRequested.size - missingFingers.size
            val frameArea     = bgr.rows() * bgr.cols()

            // ── Feedback (throttled) ──
            val feedback = FeedbackAnalyzer.analyze(gray, segments, expectedCount, frameArea)
            if (feedback != null) {
                emitFeedback(feedback)
                if (debugMode) Log.d(TAG, "Feedback: ${feedback.type} — ${feedback.message}")
            }

            // ── Distance guard ──
            if (segments.isNotEmpty()) {
                val roiRatio = segments.sumOf { it.area } / frameArea
                when {
                    roiRatio < 0.05 -> {
                        emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.DISTANCE, "Move closer to the camera", 0.88))
                        return
                    }
                    roiRatio > 0.70 -> {
                        emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.DISTANCE, "Move further from the camera", 0.88))
                        return
                    }
                }
            }

            // ── Only process READY frames ──
            if (feedback != null && feedback.type != FeedbackAnalyzer.FeedbackType.READY) return

            // ── Per-finger processing ──
            for (roi in segments) {
                val fingerId = if (singleFingerFallback) fingersRequested.firstOrNull { !missingFingers.contains(it) }
                               else fingersRequested.getOrNull(roi.index)
                fingerId ?: continue
                if (missingFingers.contains(fingerId)) continue
                if (fingerResults[fingerId]?.status == "success") continue

                val retries = retryCounts.getOrDefault(fingerId, 0)
                if (retries >= maxRetries) continue

                // Segmentation confidence: ratio of ROI area to expected finger area
                val segConfidence = (roi.area / (frameArea / expectedCount.toDouble())).coerceIn(0.0, 1.0)

                var roiMat: Mat? = null
                var rawMat: Mat? = null
                var enhanced: Mat? = null
                var ridges: Mat? = null

                try {
                    roiMat   = Mat(gray, roi.rect)
                    rawMat   = if (returnRaw) Mat(bgr, roi.rect).clone() else null
                    enhanced = ImageProcessor.enhance(roiMat)

                    val quality = if (performQuality) QualityAnalyzer.analyze(enhanced, gray) else null
                    if (debugMode) Log.d(TAG, "[$fingerId] Q=${quality?.score?.toInt()} verdict=${quality?.verdict} seg=${"%.2f".format(segConfidence)}")

                    if (quality != null) validationManager.recordQualityScore(quality.score)

                    // ── Quality rejection ──
                    if (quality != null && quality.verdict == QualityAnalyzer.Verdict.REJECT) {
                        retryCounts[fingerId] = retries + 1
                        totalQualityFailures++

                        // Smart retry UX suggestions
                        val suggestion = buildRetrySuggestion(quality, retries + 1)
                        if (suggestion != null) emitFeedback(suggestion)

                        // Auto-fallback to single finger after persistent failures
                        if (totalQualityFailures >= QUALITY_FAIL_THRESHOLD && !singleFingerFallback) {
                            singleFingerFallback = true
                            emitFeedback(FeedbackAnalyzer.Feedback(
                                FeedbackAnalyzer.FeedbackType.ALIGNMENT,
                                "Switching to single finger capture for better results", 0.80
                            ))
                            if (debugMode) Log.d(TAG, "Auto-switched to single-finger mode")
                        }

                        if (retries + 1 >= maxRetries) {
                            validationManager.onSessionFailure(ValidationManager.FailureReason.LOW_QUALITY)
                            fingerResults[fingerId] = FingerCapture(
                                fingerId, errorCode = "LOW_QUALITY",
                                errorMessage = "Quality ${quality.score.toInt()} below minimum after $maxRetries attempts",
                                failureReason = classifyQualityFailure(quality)
                            )
                        }
                        continue
                    }

                    // ── Liveness check (12-layer C++ Engine) ──
                    val liveness = if (performLiveness) {
                        val bgrRoi = Mat(bgr, roi.rect)
                        val res = livenessDetector.evaluate(
                            gray = roiMat,
                            bgr = bgrRoi,
                            fullBgr = bgr,
                            handMode = fingerId
                        )
                        bgrRoi.release()
                        res
                    } else null

                    if (debugMode) Log.d(TAG, "[$fingerId] liveness=${liveness?.passed} conf=${liveness?.confidence}")

                    if (liveness != null && !liveness.passed) {
                        validationManager.onSessionFailure(ValidationManager.FailureReason.LIVENESS_FAIL)
                        fingerResults[fingerId] = FingerCapture(
                            fingerId, errorCode = "LIVENESS_FAILED",
                            errorMessage = liveness.reason ?: "Liveness check failed",
                            failureReason = "LIVENESS_FAIL"
                        )
                        continue
                    }

                    ridges = ImageProcessor.detectRidges(enhanced)
                    val livenessConf = liveness?.confidence ?: 1.0

                    candidates.getOrPut(fingerId) { mutableListOf() }.add(
                        FrameCandidate(
                            qualityScore           = quality?.score ?: 80.0,
                            livenessConfidence     = livenessConf,
                            segmentationConfidence = segConfidence,
                            enhanced               = enhanced.also { enhanced = null },
                            ridges                 = ridges.also { ridges = null },
                            raw                    = rawMat.also { rawMat = null },
                            livenessPassed         = liveness?.passed ?: true
                        )
                    )

                    val fingerCandidates = candidates[fingerId] ?: continue
                    if (fingerCandidates.size >= deviceProfile.framesPerFinger) {
                        val best = fingerCandidates.maxByOrNull { it.confidenceScore }!!
                        finaliseCapture(fingerId, best)
                        fingerCandidates.filter { it !== best }.forEach {
                            it.enhanced.release(); it.ridges.release(); it.raw?.release()
                        }
                        candidates.remove(fingerId)
                    }

                } finally {
                    roiMat?.release()
                    rawMat?.release()
                    enhanced?.release()
                    ridges?.release()
                }
            }

            // ── Check completion ──
            val allDone = fingersRequested.all { fid ->
                val r = fingerResults[fid]
                r != null && (r.status == "success" || r.status == "missing" ||
                        (r.status == "failed" && retryCounts.getOrDefault(fid, 0) >= maxRetries))
            }

            if (allDone) {
                isCapturing = false
                val hasSuccess = fingerResults.values.any { it.status == "success" }
                if (hasSuccess) validationManager.onSessionSuccess()
                validationManager.logSnapshot(TAG)
                val response = buildResponse()
                if (debugMode) Log.d(TAG, "Complete: ${response["overallStatus"]}")
                withContext(Dispatchers.Main) { onComplete(response) }
            }

        } catch (e: Exception) {
            runCatching { frame.close() }
            Log.e(TAG, "Frame error: ${e.message}", e)
            withContext(Dispatchers.Main) {
                onError("PROCESSING_ERROR", e.message ?: "Frame processing failed")
            }
        } finally {
            bgr?.release()
            gray?.release()
            validationManager.onFrameEnd(frameToken)
        }
    }

    // ─── Finalise ─────────────────────────────────────────────────────────────

    private fun finaliseCapture(fingerId: String, best: FrameCandidate) {
        val confidenceScore = best.confidenceScore.coerceIn(0.0, 100.0)

        var template: String? = null
        if (returnTemplate) {
            template = TemplateEncoder.encode(best.enhanced)
            if (template == null) {
                // Insufficient minutiae — mark as low quality
                fingerResults[fingerId] = FingerCapture(
                    fingerId, errorCode = "LOW_QUALITY",
                    errorMessage = "Insufficient ridge detail for template generation",
                    failureReason = "LOW_QUALITY"
                )
                best.enhanced.release(); best.ridges.release(); best.raw?.release()
                return
            }
        }

        fingerResults[fingerId] = FingerCapture(
            fingerId        = fingerId,
            qualityScore    = best.qualityScore,
            livenessPassed  = best.livenessPassed,
            confidenceScore = confidenceScore,
            template        = template,
            processedImage  = if (returnProcessed) ImageProcessor.matToBase64(best.enhanced) else null,
            rawImage        = if (returnRaw && best.raw != null) ImageProcessor.matToBase64(best.raw) else null,
            status          = "success"
        )

        best.enhanced.release(); best.ridges.release(); best.raw?.release()
        if (debugMode) Log.d(TAG, "[$fingerId] finalised Q=${best.qualityScore.toInt()} conf=${confidenceScore.toInt()}")
    }

    // ─── Smart Retry UX ───────────────────────────────────────────────────────

    private fun buildRetrySuggestion(quality: QualityAnalyzer.QualityResult, attempt: Int): FeedbackAnalyzer.Feedback? {
        if (attempt < 2) return null
        return when {
            quality.blurScore < 30 -> FeedbackAnalyzer.Feedback(
                FeedbackAnalyzer.FeedbackType.MOTION, "Hold very still — try resting your hand on a surface", 0.85)
            quality.contrastScore < 30 -> FeedbackAnalyzer.Feedback(
                FeedbackAnalyzer.FeedbackType.LIGHTING, "Try better lighting — move near a window or lamp", 0.85)
            quality.coverageScore < 30 -> FeedbackAnalyzer.Feedback(
                FeedbackAnalyzer.FeedbackType.DISTANCE, "Move closer — place fingers flat against the camera", 0.85)
            attempt >= maxRetries - 1 -> FeedbackAnalyzer.Feedback(
                FeedbackAnalyzer.FeedbackType.ALIGNMENT, "Try capturing one finger at a time for better results", 0.80)
            else -> null
        }
    }

    private fun classifyQualityFailure(quality: QualityAnalyzer.QualityResult): String = when {
        quality.blurScore < 30     -> "BLUR"
        quality.contrastScore < 30 -> "LOW_LIGHT"
        quality.coverageScore < 30 -> "LOW_COVERAGE"
        else                       -> "LOW_QUALITY"
    }

    // ─── Response Builder ─────────────────────────────────────────────────────

    private fun buildResponse(): Map<String, Any> {
        val allOk = fingerResults.values.all { it.status == "success" || it.status == "missing" }
        return mapOf(
            "transactionId" to transactionId,
            "overallStatus" to if (allOk) "success" else "failed",
            "sessionMetrics" to validationManager.toResponseMap(),
            "results" to fingerResults.values.map { r ->
                mapOf<String, Any?>(
                    "fingerId"        to r.fingerId,
                    "status"          to r.status,
                    "qualityScore"    to r.qualityScore,
                    "confidenceScore" to r.confidenceScore,
                    "livenessPassed"  to r.livenessPassed,
                    "template"        to r.template,
                    "rawImage"        to r.rawImage,
                    "processedImage"  to r.processedImage,
                    "errorCode"       to r.errorCode,
                    "errorMessage"    to r.errorMessage,
                    "failureReason"   to r.failureReason
                )
            }
        )
    }

    // ─── Helpers ─────────────────────────────────────────────────────────────

    private fun emitFeedback(feedback: FeedbackAnalyzer.Feedback) {
        val map = mapOf("type" to feedback.type.name, "message" to feedback.message, "confidence" to feedback.confidence)
        scope.launch(Dispatchers.Main) { feedbackSink?.success(map) }
    }

    private fun releaseCandidates() {
        candidates.values.flatten().forEach { it.enhanced.release(); it.ridges.release(); it.raw?.release() }
        candidates.clear()
    }

    private fun isoFingerPosition(fingerId: String): Int = when (fingerId) {
        "RIGHT_THUMB" -> 1; "RIGHT_INDEX" -> 2; "RIGHT_MIDDLE" -> 3
        "RIGHT_RING"  -> 4; "RIGHT_LITTLE" -> 5; "LEFT_THUMB" -> 6
        "LEFT_INDEX"  -> 7; "LEFT_MIDDLE" -> 8; "LEFT_RING" -> 9
        "LEFT_LITTLE" -> 10; else -> 0
    }
}
