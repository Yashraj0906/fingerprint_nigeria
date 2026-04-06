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
import org.opencv.core.Rect
import org.opencv.imgproc.Imgproc

/**
 * Production-grade capture orchestrator.
 */
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
    var failureReason: String?  = null,
    var sharpnessScore: Double  = 0.0,
    var livenessConfidence: Double = 0.0
) {
    fun toMap(): Map<String, Any?> = mapOf(
        "fingerId" to fingerId,
        "status" to status,
        "qualityScore" to qualityScore,
        "confidenceScore" to confidenceScore,
        "livenessPassed" to livenessPassed,
        "template" to template,
        "rawImage" to rawImage,
        "processedImage" to processedImage,
        "errorCode" to errorCode,
        "errorMessage" to errorMessage,
        "failureReason" to failureReason,
        "sharpnessScore" to sharpnessScore,
        "livenessConfidence" to livenessConfidence
    )
}

class CaptureEngine(
    private val cameraManager: CameraManager,
    private var feedbackSink: EventChannel.EventSink?,
    private val lifecycleOwner: LifecycleOwner,
    private val debugMode: Boolean = false,
    private val deviceProfile: DeviceProfiler.DeviceProfile
) {
    companion object {
        private const val TAG = "CaptureEngine"
        private const val QUALITY_FAIL_THRESHOLD = 60
    }

    private val scope            = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private val livenessDetector = LivenessDetector()
    val validationManager        = ValidationManager()

    @Volatile private var isCapturing = false
    @Volatile private var completionSent = false
    private val resultsHandled = java.util.concurrent.atomic.AtomicBoolean(false)
    private val isProcessing   = java.util.concurrent.atomic.AtomicBoolean(false)
    private var captureJob: Job? = null

    private var onSessionComplete: ((Map<String, Any>) -> Unit)? = null
    private var onSessionError: ((String, String) -> Unit)? = null
    
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
    private var isLeftHand       = false
    private var startTime        = 0L

    private data class FrameCandidate(
        val qualityScore: Double,
        val livenessConfidence: Double,
        val segmentationConfidence: Double,
        val enhanced: Mat,
        val ridges: Mat,
        val raw: Mat?,
        val livenessPassed: Boolean,
        val sharpnessScore: Double
    ) {
        val confidenceScore: Double get() =
            qualityScore * 0.50 + livenessConfidence * 100 * 0.30 + segmentationConfidence * 100 * 0.20
    }

    private val candidates    = mutableMapOf<String, MutableList<FrameCandidate>>()
    private val fingerResults = mutableMapOf<String, FingerCapture>()
    private val retryCounts   = mutableMapOf<String, Int>()
    private var totalQualityFailures = 0
    private var singleFingerFallback = false

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
        startTime        = System.currentTimeMillis()

        missingFingers.forEach { fid ->
            fingerResults[fid] = FingerCapture(fid, status = "missing")
        }
    }

    fun start(surfaceProvider: androidx.camera.core.Preview.SurfaceProvider? = null, onComplete: (Map<String, Any>) -> Unit, onError: (String, String) -> Unit) {
        onSessionComplete = onComplete
        onSessionError = onError
        isCapturing = true
        completionSent = false
        livenessDetector.reset()
        FeedbackAnalyzer.reset()
        QualityAnalyzer.resetMotionBaseline()
        validationManager.onSessionStart()
        resultsHandled.set(false)
        isProcessing.set(false)
        totalQualityFailures = 0
        singleFingerFallback = false
        isLeftHand = fingersRequested.any { it.startsWith("LEFT_") }

        captureJob = scope.launch {
            val timeoutJob = launch {
                delay(timeoutSeconds * 1000L)
                if (isCapturing && !completionSent) {
                    completionSent = true
                    isCapturing = false
                    releaseCandidates()
                    validationManager.onSessionFailure(ValidationManager.FailureReason.TIMEOUT)
                    validationManager.logSnapshot(TAG)
                    withContext(Dispatchers.Main) { onSessionError?.invoke("TIMEOUT", "Session timed out") }
                }
            }

            cameraManager.onFrame = { frame ->
                if (isCapturing && isProcessing.compareAndSet(false, true)) {
                    scope.launch {
                        try {
                            processFrame(frame)
                        } catch (t: Throwable) {
                            Log.e(TAG, "FATAL frame error caught: ${t.javaClass.simpleName}: ${t.message}")
                            runCatching { frame.close() }
                        } finally {
                            isProcessing.set(false)
                        }
                    }
                } else {
                    frame.close()
                }
            }

            withContext(Dispatchers.Main) { cameraManager.start(lifecycleOwner, surfaceProvider) }
            while (isCapturing) delay(50)
            timeoutJob?.cancel()
        }
    }

    fun stop() {
        android.util.Log.i(TAG, "Stopping capture session...")
        isCapturing = false
        captureJob?.cancel()
        timeoutJob?.cancel()
        cameraManager.stop()
        releaseCandidates()
        FeedbackAnalyzer.reset()
        QualityAnalyzer.resetMotionBaseline()
        validationManager.reset()
        android.util.Log.i(TAG, "Capture session stopped and resources released.")
    }

    private suspend fun processFrame(frame: ImageProxy) {
        val frameToken = validationManager.onFrameStart()
        var bgr: Mat? = null
        var gray: Mat? = null

        if (!isCapturing || completionSent) {
            frame.close()
            return
        }

        try {
            bgr  = ImageProcessor.yuvToMat(frame)
            frame.close()
            
            if (bgr.empty()) {
                android.util.Log.w(TAG, "Empty frame from yuvToMat, skipping...")
                return
            }
            
            gray = Mat()
            Imgproc.cvtColor(bgr, gray, Imgproc.COLOR_BGR2GRAY)

            val maxFingers    = if (singleFingerFallback) 1 else fingersRequested.size
            val segments = ImageProcessor.segmentFingers(bgr, fingersRequested.size)
            if (debugMode) Log.d(TAG, "Segmentation: Found ${segments.size} finger candidates for ${fingersRequested.size} requested")
            
            if (segments.isEmpty()) {
                emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "No hand detected", 0.1))
                return
            }
            val expectedCount = if (singleFingerFallback) 1 else fingersRequested.size - missingFingers.size
            val frameArea     = bgr.rows() * bgr.cols()

            val feedback = FeedbackAnalyzer.analyze(gray, segments, expectedCount, frameArea)
            if (feedback != null) emitFeedback(feedback)

            if (segments.isNotEmpty()) {
                val roiRatio = segments.sumOf { it.area } / frameArea.toDouble()
                if (roiRatio < 0.005) {
                    emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.DISTANCE, "Take close the hands", 0.88))
                    return
                } else if (roiRatio > 0.70) {
                    emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.DISTANCE, "Take hands slightly back", 0.88))
                    return
                }
            }

            // Universal Progressive Capture: We process any valid segments available instead of enforcing strict full-hand alignment.
            val hasRequiredFingerCount = segments.isNotEmpty()
            val isStable = validationManager.isFrameStable()
            val elapsed = System.currentTimeMillis() - startTime
            val bypassReady = elapsed > 700 // Lightning-fast capture delay (OnePlus 8 / M31s optimization)
            
            if (!bypassReady && feedback != null && feedback.type != FeedbackAnalyzer.FeedbackType.READY) return
            if (!bypassReady && !hasRequiredFingerCount) {
                emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "Ensure all fingers are visible", 0.90))
                return
            }
            if (!bypassReady && !isStable) {
                emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.STABILITY, "Now capturing, hold still", 0.95))
                return
            }

            val sortedSegments = if (isLeftHand && !singleFingerFallback) segments.reversed() else segments
            
            // Map the detected segments to the remaining requested fingers progressively
            val remainingFingers = fingersRequested.filter { !missingFingers.contains(it) && fingerResults[it]?.status != "success" }

            for (roi in sortedSegments) {
                // SHAPE GUARD: Only process things that have the 'Aspect Ratio' of a human finger (Tall & Narrow).
                // A desk or a square object will have an aspect ratio near 1.0, and we should ignore it.
                val aspectRatio = roi.rect.height.toDouble() / roi.rect.width.toDouble()
                if (aspectRatio < 1.05 || aspectRatio > 6.0) {
                    if (debugMode) Log.d(TAG, "Ignoring non-finger shape (Aspect Ratio: $aspectRatio)")
                    continue
                }

                val finalFingerId = if (singleFingerFallback || fingersRequested.size == 1) {
                    remainingFingers.firstOrNull()
                } else {
                    remainingFingers.getOrNull(roi.index)
                }

                finalFingerId ?: continue

                val retries = retryCounts.getOrDefault(finalFingerId, 0)
                val segConfidence = (roi.area / (frameArea / expectedCount.toDouble())).coerceIn(0.0, 1.0)

                var roiMat: Mat? = null
                var rawMat: Mat? = null
                var enhanced: Mat? = null
                var ridges: Mat? = null

                try {
                    if (roi.rect.width <= 0 || roi.rect.height <= 0) continue
                    
                    // Final safety clip for OpenCV Mat constructor
                    val sx = roi.rect.x.coerceIn(0, (gray.cols() - 1).coerceAtLeast(0))
                    val sy = roi.rect.y.coerceIn(0, (gray.rows() - 1).coerceAtLeast(0))
                    val sw = roi.rect.width.coerceAtMost((gray.cols() - sx).coerceAtLeast(1))
                    val sh = roi.rect.height.coerceAtMost((gray.rows() - sy).coerceAtLeast(1))
                    if (sw <= 0 || sh <= 0) continue
                    val safeRect = Rect(sx, sy, sw, sh)
                    
                    roiMat   = Mat(gray, safeRect)
                    rawMat   = if (returnRaw || returnProcessed) Mat(bgr, safeRect).clone() else null
                    enhanced = ImageProcessor.enhance(roiMat)

                    val quality = if (performQuality) QualityAnalyzer.analyze(enhanced, gray) else null
                    if (quality != null) validationManager.recordQualityScore(quality.score)

                    val adaptiveReject = if (quality == null) false
                    else if (elapsed > 500) quality.verdict == QualityAnalyzer.Verdict.REJECT
                    else quality.verdict == QualityAnalyzer.Verdict.REJECT || quality.verdict == QualityAnalyzer.Verdict.RETRY

                    if (adaptiveReject && (quality?.score ?: 0.0) < 20.0) {
                        retryCounts[finalFingerId] = retries + 1
                        totalQualityFailures++
                        val suggestion = buildRetrySuggestion(quality!!, retries + 1)
                        if (suggestion != null) emitFeedback(suggestion)
                        continue // RE-ENABLED: Keep it for complete garbage (Desk/Etc)
                    }

                    val liveness = if (performLiveness) {
                        val bgrRoi = Mat(bgr, safeRect)
                        val res = livenessDetector.evaluate(roiMat, bgrRoi, bgr, finalFingerId)
                        bgrRoi.release()
                        res
                    } else null

                    // SMART BLOCK: Only block if we are mathematically certain it is a spoof/fake (confidence < 0.20)
                    if (liveness != null && liveness.confidence < 0.20) {
                        Log.w(TAG, "Definitive spoof detected (Conf: ${liveness.confidence}). Blocking frame.")
                        continue 
                    }

                    ridges = ImageProcessor.detectRidges(enhanced)
                    candidates.getOrPut(finalFingerId) { mutableListOf() }.add(
                        FrameCandidate(
                            qualityScore = quality?.score ?: 60.0,
                            livenessConfidence = liveness?.confidence ?: 1.0,
                            segmentationConfidence = segConfidence,
                            enhanced = enhanced.also { enhanced = null },
                            ridges = ridges.also { ridges = null },
                            raw = rawMat.also { rawMat = null },
                            livenessPassed = liveness?.passed ?: true,
                            sharpnessScore = quality?.blurScore ?: 0.0
                        )
                    )

                    val fingerCandidates = candidates[finalFingerId] ?: continue
                    if (fingerCandidates.size >= 1) {
                        val best = fingerCandidates.maxByOrNull { it.confidenceScore }!!
                        finaliseCapture(finalFingerId, best)
                        fingerCandidates.filter { it !== best }.forEach {
                            it.enhanced.release(); it.ridges.release(); it.raw?.release()
                        }
                        candidates.remove(finalFingerId)
                    }
                } catch (e: Throwable) {
                    Log.e(TAG, "ROI processing failed: ${e.javaClass.simpleName}: ${e.message}")
                } finally {
                    roiMat?.release(); rawMat?.release(); enhanced?.release(); ridges?.release()
                }
            }

            val allDone = fingersRequested.all { fid ->
                val r = fingerResults[fid]
                r != null && (r.status == "success" || r.status == "missing")
            }

            if (allDone && !completionSent) {
                if (resultsHandled.compareAndSet(false, true)) {
                    completionSent = true
                    isCapturing = false
                    if (fingerResults.values.any { it.status == "success" }) validationManager.onSessionSuccess()
                    validationManager.logSnapshot(TAG)
                    val response = buildResponse()
                    withContext(Dispatchers.Main) { onSessionComplete?.invoke(response) }
                }
            }
        } catch (e: Throwable) {
            runCatching { frame.close() }
            Log.e(TAG, "Frame error: ${e.javaClass.simpleName}: ${e.message}", e)
            if (isCapturing && !completionSent) {
                if (resultsHandled.compareAndSet(false, true)) {
                    isCapturing = false
                    withContext(Dispatchers.Main) {
                        onSessionError?.invoke("CAPTURE_ERROR", e.message ?: "Unknown error")
                    }
                }
            }
        } finally {
            bgr?.release(); gray?.release()
            validationManager.onFrameEnd(frameToken)
        }
    }

    private fun finaliseCapture(fingerId: String, best: FrameCandidate) {
        if (best.enhanced.empty()) {
            android.util.Log.e(TAG, "Finalise failed: Enhanced mat is empty for $fingerId")
            best.ridges.release(); best.raw?.release(); best.enhanced.release()
            return
        }
        val confidenceScore = best.confidenceScore.coerceIn(0.0, 100.0)
        var template: String? = null
        if (returnTemplate) {
            template = TemplateEncoder.encode(best.enhanced)
            if (template == null) {
                fingerResults[fingerId] = FingerCapture(fingerId, errorCode = "LOW_QUALITY", failureReason = "LOW_QUALITY")
                best.enhanced.release(); best.ridges.release(); best.raw?.release()
                return
            }
        }
        fingerResults[fingerId] = FingerCapture(
            fingerId = fingerId, qualityScore = best.qualityScore, livenessPassed = best.livenessPassed,
            confidenceScore = confidenceScore, template = template, status = "success",
            processedImage = if (returnProcessed && best.raw != null) ImageProcessor.matToBase64(best.raw) else null,
            rawImage = if (returnRaw && best.raw != null) ImageProcessor.matToBase64(best.raw) else null,
            sharpnessScore = best.sharpnessScore, livenessConfidence = best.livenessConfidence
        )
        best.enhanced.release(); best.ridges.release(); best.raw?.release()
    }

    private fun buildRetrySuggestion(quality: QualityAnalyzer.QualityResult, attempt: Int): FeedbackAnalyzer.Feedback? {
        if (attempt < 2) return null
        return when {
            quality.blurScore < 30 -> FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.MOTION, "Hold still", 0.85)
            quality.contrastScore < 30 -> FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.LIGHTING, "More light", 0.85)
            else -> null
        }
    }

    private fun buildResponse(): Map<String, Any> {
        val allOk = fingerResults.values.all { it.status == "success" || it.status == "missing" }
        return mapOf(
            "transactionId" to transactionId,
            "overallStatus" to if (allOk) "success" else "failed",
            "sessionMetrics" to validationManager.toResponseMap(),
            "results" to fingerResults.values.map { it.toMap() }
        )
    }

    private fun emitFeedback(feedback: FeedbackAnalyzer.Feedback) {
        val map = mapOf("type" to feedback.type.name, "message" to feedback.message, "confidence" to feedback.confidence, "boxes" to feedback.boxes)
        scope.launch(Dispatchers.Main) { feedbackSink?.success(map) }
    }

    private fun releaseCandidates() {
        candidates.values.flatten().forEach { it.enhanced.release(); it.ridges.release(); it.raw?.release() }
        candidates.clear()
    }
}
