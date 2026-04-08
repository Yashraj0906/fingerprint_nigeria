package com.yellowsense.fingerprint_sdk.bridge

import android.content.Context
import android.util.Log
import androidx.camera.core.ImageProxy
import androidx.lifecycle.LifecycleOwner
import com.yellowsense.fingerprint_sdk.analytics.DeviceProfiler
import com.yellowsense.fingerprint_sdk.analytics.ValidationManager
import com.yellowsense.fingerprint_sdk.camera.CameraManager
import com.yellowsense.fingerprint_sdk.handpose.FingerRole
import com.yellowsense.fingerprint_sdk.handpose.HandPoseEstimator
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
import java.net.HttpURLConnection
import java.net.URL

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
    var brightnessScore: Double = 0.0,
    var centeringScore: Double  = 0.0,
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
        "brightnessScore" to brightnessScore,
        "centeringScore" to centeringScore,
        "livenessConfidence" to livenessConfidence
    )
}

class CaptureEngine(
    private val cameraManager: CameraManager,
    private var feedbackSink: EventChannel.EventSink?,
    private val lifecycleOwner: LifecycleOwner,
    private val debugMode: Boolean = false,
    private val deviceProfile: DeviceProfiler.DeviceProfile,
    private val appContext: Context
) {
    // #region agent log
    private fun debugLog(runId: String, hypothesisId: String, location: String, message: String, data: String) {
        try {
            val esc = { s: String -> s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n") }
            val body = "{\"sessionId\":\"305b62\",\"runId\":\"${esc(runId)}\",\"hypothesisId\":\"${esc(hypothesisId)}\",\"location\":\"${esc(location)}\",\"message\":\"${esc(message)}\",\"data\":{\"detail\":\"${esc(data)}\"},\"timestamp\":${System.currentTimeMillis()}}"
            Log.i("FP_DEBUG_305b62", body)
            Thread {
                try {
                    val conn = (URL("http://127.0.0.1:7814/ingest/f54ad1cf-5e22-4aff-91cf-0c077823e4af").openConnection() as HttpURLConnection)
                    conn.requestMethod = "POST"
                    conn.setRequestProperty("Content-Type", "application/json")
                    conn.setRequestProperty("X-Debug-Session-Id", "305b62")
                    conn.doOutput = true
                    conn.outputStream.use { os -> os.write(body.toByteArray(Charsets.UTF_8)) }
                    conn.responseCode
                    conn.disconnect()
                } catch (_: Throwable) { }
                try {
                    val conn = (URL("http://10.0.2.2:7814/ingest/f54ad1cf-5e22-4aff-91cf-0c077823e4af").openConnection() as HttpURLConnection)
                    conn.requestMethod = "POST"
                    conn.setRequestProperty("Content-Type", "application/json")
                    conn.setRequestProperty("X-Debug-Session-Id", "305b62")
                    conn.doOutput = true
                    conn.outputStream.use { os -> os.write(body.toByteArray(Charsets.UTF_8)) }
                    conn.responseCode
                    conn.disconnect()
                } catch (_: Throwable) { }
            }.start()
        } catch (_: Throwable) { }
    }
    // #endregion

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
    private var timeoutJob: Job? = null

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
    private var requestedMode    = "CUSTOM_SEQUENCE"
    private var strictMode       = false
    private var wrongHandStreak  = 0
    /** Set when MediaPipe resolves SINGLE_FINGER to the real id (e.g. LEFT_RING). */
    private var activeSingleFingerId: String? = null
    /** Session preview image (full frame) returned as rawImage to avoid zoomed ROIs in UI. */
    private var sessionPreviewBase64: String? = null
    private var lastFingerTargetKey  = ""
    private var lastFingerTargetEmitMs = 0L

    private data class FrameCandidate(
        val qualityScore: Double,
        val livenessConfidence: Double,
        val segmentationConfidence: Double,
        val enhanced: Mat,
        val ridges: Mat,
        val raw: Mat?,
        val livenessPassed: Boolean,
        val sharpnessScore: Double,
        val brightnessScore: Double,
        val centeringScore: Double
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
        requestedMode    = inferModeFromRequestedFingers()
        strictMode       = requestedMode in setOf("LEFT_FOUR", "RIGHT_FOUR", "LEFT_THUMB", "RIGHT_THUMB", "SINGLE_FINGER")

        missingFingers.forEach { fid ->
            fingerResults[fid] = FingerCapture(fid, status = "missing")
        }
        activeSingleFingerId = null
        sessionPreviewBase64 = null
        lastFingerTargetKey = ""
        lastFingerTargetEmitMs = 0L
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
            timeoutJob = launch {
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
        sessionPreviewBase64 = null
        FeedbackAnalyzer.reset()
        QualityAnalyzer.resetMotionBaseline()
        validationManager.reset()
        android.util.Log.i(TAG, "Capture session stopped and resources released.")
    }

    fun destroy() {
        stop()
        scope.cancel()
        android.util.Log.i(TAG, "CaptureEngine scope cancelled and destroyed.")
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

            val maxFingers = if (singleFingerFallback) 1 else fingersRequested.size

            HandPoseEstimator.ensureInitialized(appContext)
            val handEstimate = HandPoseEstimator.analyze(appContext, bgr)
            var usedMediaPipe = false
            /** When MediaPipe resolves single-finger capture, use this id (not the placeholder from Dart, e.g. RIGHT_INDEX). */
            var mpSingleFingerId: String? = null

            var segments: List<ImageProcessor.FingerROI> = when (requestedMode) {
                "LEFT_FOUR", "RIGHT_FOUR" -> {
                    if (handEstimate == null) {
                        emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "No hand detected — center your hand", 0.92))
                        emptyList()
                    } else {
                        val want = if (requestedMode.startsWith("LEFT_")) "LEFT" else "RIGHT"
                        if (handEstimate.handedness != want) {
                            emitFeedback(
                                FeedbackAnalyzer.Feedback(
                                    FeedbackAnalyzer.FeedbackType.WARNING,
                                    "Wrong hand detected — you selected $want. Show your ${want.lowercase()} hand only",
                                    0.99
                                )
                            )
                            // Prevent later generic "No hand detected" overwrite for strict gating frames.
                            usedMediaPipe = true
                            emptyList()
                        } else if (handEstimate.isThumbExtended()) {
                            emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "Hide your thumb — show 4 fingers only", 0.95))
                            usedMediaPipe = true
                            emptyList()
                        } else {
                            val slap = handEstimate.extendedSlapFingers()
                            if (slap.size < 4) {
                                emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "Raise all 4 fingers — index through little", 0.93))
                                usedMediaPipe = true
                                emptyList()
                            } else {
                                val rects = listOf(
                                    FingerRole.INDEX, FingerRole.MIDDLE, FingerRole.RING, FingerRole.LITTLE
                                ).mapNotNull { handEstimate.bboxForFinger(it) }
                                if (rects.size < 4) {
                                    emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.DISTANCE, "Move closer — fingers too small in frame", 0.90))
                                    usedMediaPipe = true
                                    emptyList()
                                } else {
                                    usedMediaPipe = true
                                    rects.mapIndexed { idx, r ->
                                        ImageProcessor.FingerROI(idx, r, r.area().toDouble())
                                    }
                                }
                            }
                        }
                    }
                }
                "LEFT_THUMB", "RIGHT_THUMB" -> {
                    if (handEstimate == null) {
                        emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "No hand detected", 0.92))
                        emptyList()
                    } else {
                        val want = if (requestedMode.startsWith("LEFT_")) "LEFT" else "RIGHT"
                        if (handEstimate.handedness != want) {
                            emitFeedback(
                                FeedbackAnalyzer.Feedback(
                                    FeedbackAnalyzer.FeedbackType.WARNING,
                                    "Wrong hand detected — you selected $want thumb. Show your ${want.lowercase()} thumb only",
                                    0.99
                                )
                            )
                            // Prevent later generic "No hand detected" overwrite for strict gating frames.
                            usedMediaPipe = true
                            emptyList()
                        } else if (handEstimate.extendedSlapFingers().isNotEmpty()) {
                            emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "Fold your other fingers — show thumb only", 0.95))
                            usedMediaPipe = true
                            emptyList()
                        } else {
                            val r = handEstimate.bboxForFinger(FingerRole.THUMB)
                            if (r == null) {
                                emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.DISTANCE, "Move closer to the camera", 0.90))
                                usedMediaPipe = true
                                emptyList()
                            } else {
                                // If ROI is clearly visible but the extension heuristic is borderline, still proceed.
                                // This avoids cases where the user points the thumb toward camera (foreshortening).
                                if (!handEstimate.isThumbExtended()) {
                                    emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "Point your thumb toward the camera", 0.93))
                                }
                                usedMediaPipe = true
                                listOf(ImageProcessor.FingerROI(0, r, r.area().toDouble()))
                            }
                        }
                    }
                }
                "SINGLE_FINGER" -> {
                    if (handEstimate == null) {
                        emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "No hand detected", 0.92))
                        emptyList()
                    } else {
                        // Label capture from MediaPipe (Dart often sends a placeholder e.g. RIGHT_INDEX for all single-finger flows).
                        val slap = handEstimate.extendedSlapFingers()
                        val n = slap.size
                        val thumbUp = handEstimate.isThumbExtended()
                        when {
                            n == 0 && thumbUp -> {
                                // Only thumb is extended.
                                val r = handEstimate.bboxForFinger(FingerRole.THUMB)
                                if (r == null) {
                                    usedMediaPipe = true
                                    emptyList()
                                } else {
                                    mpSingleFingerId = "${handEstimate.handedness}_THUMB"
                                    usedMediaPipe = true
                                    listOf(ImageProcessor.FingerROI(0, r, r.area().toDouble()))
                                }
                            }
                            n == 0 -> {
                                // Neither thumb nor any non-thumb finger is detected as extended.
                                emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "Raise exactly one finger toward the camera", 0.93))
                                usedMediaPipe = true
                                emptyList()
                            }
                            n > 1 -> {
                                emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "Show only ONE finger at a time", 0.94))
                                usedMediaPipe = true
                                emptyList()
                            }
                            else -> {
                                // Exactly one non-thumb finger is extended.
                                // Even if thumb is mistakenly flagged as extended, prefer the non-thumb finger
                                // to avoid missing middle/little captures.
                                val role = slap.first()
                                val r = handEstimate.bboxForFinger(role)
                                if (r == null) {
                                    usedMediaPipe = true
                                    emptyList()
                                } else {
                                    mpSingleFingerId = "${handEstimate.handedness}_${role.name}"
                                    usedMediaPipe = true
                                    listOf(ImageProcessor.FingerROI(0, r, r.area().toDouble()))
                                }
                            }
                        }
                    }
                }
                else -> ImageProcessor.segmentFingers(bgr, maxFingers)
            }

            if (!usedMediaPipe && segments.isEmpty() && requestedMode !in setOf("LEFT_FOUR", "RIGHT_FOUR", "LEFT_THUMB", "RIGHT_THUMB", "SINGLE_FINGER")) {
                segments = ImageProcessor.segmentFingers(bgr, maxFingers)
            }

            if (mpSingleFingerId != null) activeSingleFingerId = mpSingleFingerId

            if (debugMode) Log.d(TAG, "Segmentation: mp=$usedMediaPipe count=${segments.size} mode=$requestedMode")
            // #region agent log
            debugLog("baseline", "H2", "CaptureEngine.kt:frame", "Frame segmented", "mode=$requestedMode segments=${segments.size} requested=${fingersRequested.size} missing=${missingFingers.size} strict=$strictMode")
            // #endregion
            
            if (segments.isEmpty()) {
                if (!usedMediaPipe) {
                    emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "No hand detected", 0.1))
                }
                return
            }
            val expectedCount = if (singleFingerFallback) 1 else fingersRequested.size - missingFingers.size
            val frameArea     = bgr.rows() * bgr.cols()

            // Store a full-frame preview once per session so the app displays the hand/fingers,
            // not a zoomed-in ROI crop.
            if (returnRaw && sessionPreviewBase64 == null) {
                val src = bgr
                val w = src.cols()
                val h = src.rows()
                if (w > 0 && h > 0) {
                    val maxW = 720
                    val scale = if (w > maxW) (maxW.toDouble() / w.toDouble()) else 1.0
                    val newW = (w * scale).toInt().coerceAtLeast(1)
                    val newH = (h * scale).toInt().coerceAtLeast(1)
                    val resized = Mat()
                    try {
                        if (scale < 1.0) {
                            Imgproc.resize(src, resized, org.opencv.core.Size(newW.toDouble(), newH.toDouble()))
                        } else {
                            src.copyTo(resized)
                        }
                        sessionPreviewBase64 = ImageProcessor.matToBase64(resized, quality = 92)
                    } catch (_: Throwable) {
                        // Ignore preview failures; ROI still works for capture.
                    } finally {
                        resized.release()
                    }
                }
            }

            val feedback = FeedbackAnalyzer.analyze(gray, segments, expectedCount, frameArea)
            if (feedback != null) {
                val toEmit =
                    if (feedback.type == FeedbackAnalyzer.FeedbackType.READY && usedMediaPipe && handEstimate != null) {
                        val fix = handEstimate.capturePoseHint(requestedMode)
                        val msg = fix ?: handEstimate.readyCoachingLine(requestedMode)
                        FeedbackAnalyzer.Feedback(feedback.type, msg, feedback.confidence)
                    } else {
                        feedback
                    }
                emitFeedback(toEmit)
            }

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
            // In strict mode, allow a short warmup bypass to reduce perceived latency.
            val strictBypassMs = if (requestedMode == "LEFT_FOUR" || requestedMode == "RIGHT_FOUR") 800L else 1200L
            val bypassReady = if (strictMode) elapsed > strictBypassMs else elapsed > 700
            if (strictMode) {
                val expectedStrictCount = when (requestedMode) {
                    // Keep strict guidance, but do not over-block real devices.
                    "LEFT_FOUR", "RIGHT_FOUR" -> 2
                    "LEFT_THUMB", "RIGHT_THUMB", "SINGLE_FINGER" -> 1
                    else -> expectedCount
                }
                if (segments.size < expectedStrictCount) {
                    // #region agent log
                    debugLog("baseline", "H2", "CaptureEngine.kt:strictCount", "Strict count rejected", "mode=$requestedMode segments=${segments.size} expectedStrict=$expectedStrictCount elapsed=$elapsed")
                    // #endregion
                    val msg = when (requestedMode) {
                        "LEFT_FOUR", "RIGHT_FOUR" -> when (segments.size) {
                            0 -> "Place your hand in the guide — palm toward camera, 4 fingers up"
                            1 -> "Move closer — spread index through little finger inside the box"
                            2 -> "Lift the missing finger — keep palm flat, fingers vertical"
                            else -> "Almost there — align all 4 fingertips in the guide, hold still"
                        }
                        "LEFT_THUMB" -> "Show only your left thumb — fold all other fingers"
                        "RIGHT_THUMB" -> "Show only your right thumb — fold all other fingers"
                        "SINGLE_FINGER" -> "Show exactly ONE finger clearly"
                        else -> "Adjust finger position"
                    }
                    emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, msg, 0.95))
                    return
                }
                if ((requestedMode == "LEFT_THUMB" || requestedMode == "RIGHT_THUMB" || requestedMode == "SINGLE_FINGER") && segments.size > 2) {
                    // #region agent log
                    debugLog("baseline", "H3", "CaptureEngine.kt:thumbCount", "Thumb/single rejected due to extra segments", "mode=$requestedMode segments=${segments.size}")
                    // #endregion
                    val msg = when (requestedMode) {
                        "LEFT_THUMB" -> "Show only your left thumb — hide other fingers"
                        "RIGHT_THUMB" -> "Show only your right thumb — hide other fingers"
                        else -> "Show exactly ONE finger clearly"
                    }
                    emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, msg, 0.95))
                    return
                }
            }

            // Hand-side check with streaking to reduce false positives.
            val expectedSide = when {
                requestedMode.startsWith("LEFT_") -> "LEFT"
                requestedMode.startsWith("RIGHT_") -> "RIGHT"
                else -> null
            }
            // OpenCV-only heuristic — MediaPipe already validated handedness for strict modes.
            if (expectedSide != null && segments.isNotEmpty() && !usedMediaPipe) {
                val avgCenterX = segments.map { it.rect.x + (it.rect.width / 2.0) }.average()
                val ratio = if (gray.cols() > 0) (avgCenterX / gray.cols().toDouble()) else 0.5
                val sideLooksWrong =
                    // Wider dead-zone so correct hands don't get falsely blocked.
                    (expectedSide == "LEFT" && ratio > 0.62) ||
                    (expectedSide == "RIGHT" && ratio < 0.38)
                // #region agent log
                debugLog("baseline", "H1", "CaptureEngine.kt:sideGate", "Side gate evaluated", "mode=$requestedMode expectedSide=$expectedSide ratio=$ratio sideLooksWrong=$sideLooksWrong streak=$wrongHandStreak")
                // #endregion
                if (sideLooksWrong) {
                    wrongHandStreak += 1
                    val msg = if (expectedSide == "LEFT") {
                        "Wrong hand detected — you selected LEFT. Show your left hand only"
                    } else {
                        "Wrong hand detected — you selected RIGHT. Show your right hand only"
                    }
                    val conf = if (wrongHandStreak >= 3) 0.99 else 0.88
                    emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.WARNING, msg, conf))
                    if (wrongHandStreak >= 3) {
                        releaseCandidates()
                        retryCounts.clear()
                        candidates.clear()
                    }
                    // Do not process/capture any ROIs while wrong-hand is active.
                    return
                } else {
                    wrongHandStreak = 0
                }
            }
            
            if (!bypassReady && feedback != null && feedback.type != FeedbackAnalyzer.FeedbackType.READY) return
            if (!bypassReady && !hasRequiredFingerCount) {
                emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, "Ensure all fingers are visible", 0.90))
                return
            }
            // Stability gating is expensive for real users; in 4-finger modes allow bypass earlier.
            if (!bypassReady && !isStable && requestedMode !in setOf("LEFT_FOUR", "RIGHT_FOUR")) {
                emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.STABILITY, "Now capturing, hold still", 0.95))
                return
            }

            // Hard gate: never process ROIs if the visible hand does not match selected side (MediaPipe truth).
            val requiredSideGate = when {
                requestedMode.startsWith("LEFT_") -> "LEFT"
                requestedMode.startsWith("RIGHT_") -> "RIGHT"
                else -> null
            }
            if (requiredSideGate != null && handEstimate != null && handEstimate.handedness != requiredSideGate) {
                emitFeedback(
                    FeedbackAnalyzer.Feedback(
                        FeedbackAnalyzer.FeedbackType.WARNING,
                        "Wrong hand detected — you selected $requiredSideGate. Show your ${requiredSideGate.lowercase()} hand only",
                        0.99
                    )
                )
                return
            }

            // Stable ordering for finger-ID mapping:
            // RIGHT_FOUR expects index→little left-to-right; LEFT_FOUR expects index→little right-to-left.
            val sortedSegments = when (requestedMode) {
                "LEFT_FOUR" -> segments.sortedByDescending { it.rect.x }
                else -> segments.sortedBy { it.rect.x }
            }
            
            // Map the detected segments to the remaining requested fingers progressively
            val remainingFingers = if (requestedMode == "SINGLE_FINGER" && activeSingleFingerId != null) {
                listOf(activeSingleFingerId!!).filter { fingerResults[it]?.status != "success" }
            } else {
                fingersRequested.filter { !missingFingers.contains(it) && fingerResults[it]?.status != "success" }
            }

            emitCurrentFingerCaptureHint(remainingFingers, mpSingleFingerId)

            for ((segIdx, roi) in sortedSegments.withIndex()) {
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
                    // Use sorted-segment order, not original roi.index, for stable mapping.
                    remainingFingers.getOrNull(segIdx)
                }

                finalFingerId ?: continue

                // Thumb side guard: block LEFT/RIGHT thumb swaps explicitly.
                if (requestedMode == "LEFT_THUMB" || requestedMode == "RIGHT_THUMB") {
                    val centerX = roi.rect.x + (roi.rect.width / 2.0)
                    val frameCenterX = gray.cols() / 2.0
                    val normalizedX = if (gray.cols() > 0) centerX / gray.cols().toDouble() else 0.5
                    val wrongSide =
                        (requestedMode == "LEFT_THUMB" && (centerX > frameCenterX * 1.08 || normalizedX > 0.58)) ||
                        (requestedMode == "RIGHT_THUMB" && (centerX < frameCenterX * 0.92 || normalizedX < 0.42))
                    // #region agent log
                    debugLog("baseline", "H3", "CaptureEngine.kt:thumbSide", "Thumb side evaluated", "mode=$requestedMode centerX=$centerX frameCenterX=$frameCenterX normalizedX=$normalizedX wrongSide=$wrongSide")
                    // #endregion
                    if (wrongSide) {
                        val msg = if (requestedMode == "LEFT_THUMB") {
                            "Left thumb mode: show only your LEFT thumb"
                        } else {
                            "Right thumb mode: show only your RIGHT thumb"
                        }
                        emitFeedback(FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.ALIGNMENT, msg, 0.98))
                        // Do not hard-block on geometric side only (camera mirroring varies by device).
                    }
                }

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

                    val centering = if (gray.empty()) 100.0 else {
                        val fx = gray.cols() / 2.0; val fy = gray.rows() / 2.0
                        val rx = roi.rect.x + roi.rect.width / 2.0; val ry = roi.rect.y + roi.rect.height / 2.0
                        val dist = Math.sqrt(Math.pow(rx - fx, 2.0) + Math.pow(ry - fy, 2.0))
                        val maxD = Math.sqrt(Math.pow(gray.cols().toDouble(), 2.0) + Math.pow(gray.rows().toDouble(), 2.0)) / 2.0
                        ((1.0 - (dist / maxD)) * 100).coerceIn(0.0, 100.0)
                    }

                    val adaptiveReject = if (quality == null) false
                    else if (elapsed > 500) quality.verdict == QualityAnalyzer.Verdict.REJECT
                    else quality.verdict == QualityAnalyzer.Verdict.REJECT || quality.verdict == QualityAnalyzer.Verdict.RETRY

                    val minAcceptScore = when {
                        requestedMode == "LEFT_FOUR" || requestedMode == "RIGHT_FOUR" -> 32.0
                        requestedMode == "LEFT_THUMB" || requestedMode == "RIGHT_THUMB" -> 34.0
                        requestedMode == "SINGLE_FINGER" -> 36.0
                        strictMode -> 32.0
                        else -> 24.0
                    }
                    if (adaptiveReject && (quality?.score ?: 0.0) < minAcceptScore) {
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

                    // Block only high-confidence liveness failures to avoid false rejects.
                    val mustBlockByLiveness = when (requestedMode) {
                        "LEFT_THUMB", "RIGHT_THUMB" -> (liveness != null && !liveness.passed && liveness.confidence >= 0.80)
                        else -> (liveness != null && !liveness.passed && liveness.confidence >= 0.75)
                    }
                    if (mustBlockByLiveness) {
                        // #region agent log
                        debugLog("baseline", "H4", "CaptureEngine.kt:livenessBlock", "Liveness blocked candidate", "mode=$requestedMode finger=$finalFingerId conf=${liveness?.confidence} reason=${liveness?.reason}")
                        // #endregion
                        val liveReason = liveness?.reason ?: "Liveness check failed"
                        val liveConfidence = liveness?.confidence ?: 0.0
                        retryCounts[finalFingerId] = retries + 1
                        if (retryCounts[finalFingerId]!! >= maxRetries) {
                            fingerResults[finalFingerId] = FingerCapture(
                                fingerId = finalFingerId,
                                status = "failed",
                                livenessPassed = false,
                                errorCode = "LIVENESS_FAILED",
                                errorMessage = liveReason,
                                livenessConfidence = liveConfidence
                            )
                        }
                        emitFeedback(
                            FeedbackAnalyzer.Feedback(
                                FeedbackAnalyzer.FeedbackType.ALIGNMENT,
                                liveReason,
                                0.95
                            )
                        )
                        continue
                    }

                    // Keep a hard spoof guard for low-confidence artifacts.
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
                            sharpnessScore = quality?.sharpnessScore ?: 0.0,
                            brightnessScore = quality?.brightnessScore ?: 0.0,
                            centeringScore = centering
                        )
                    )

                    val fingerCandidates = candidates[finalFingerId] ?: continue
                    val minStableCandidates = when {
                        requestedMode == "LEFT_FOUR" || requestedMode == "RIGHT_FOUR" -> 3
                        requestedMode == "LEFT_THUMB" || requestedMode == "RIGHT_THUMB" -> 3
                        requestedMode == "SINGLE_FINGER" -> 4
                        strictMode -> 2
                        else -> 1
                    }
                    if (fingerCandidates.size >= minStableCandidates) {
                        // Prefer the highest quality frame among the stable window.
                        // If livenessPassed candidates exist, prefer quality from those first.
                        val livenessPool = fingerCandidates.filter { it.livenessPassed }
                        val pool = if (livenessPool.isNotEmpty()) livenessPool else fingerCandidates
                        val best = pool.maxByOrNull { it.qualityScore }!!
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

            val sessionFingerIds =
                if (requestedMode == "SINGLE_FINGER" && activeSingleFingerId != null) listOf(activeSingleFingerId!!)
                else fingersRequested.filter { !missingFingers.contains(it) }

            val allDone = sessionFingerIds.all { fid ->
                val r = fingerResults[fid]
                r != null && (r.status == "success" || r.status == "missing" || r.status == "failed")
            }

            // Finalization safety: near timeout, mark any remaining fingers as failed
            // so the session completes instead of stalling forever.
            val timeLeftMs = (timeoutSeconds * 1000L) - elapsed
            if (timeLeftMs in 0..1200) {
                sessionFingerIds.forEach { fid ->
                    if (fingerResults[fid] == null) {
                        fingerResults[fid] = FingerCapture(
                            fingerId = fid,
                            status = "failed",
                            errorCode = "FINGER_NOT_DETECTED",
                            errorMessage = "Finger not detected before timeout"
                        )
                    }
                }
            }
            // #region agent log
            val successCount = fingerResults.values.count { it.status == "success" }
            debugLog("baseline", "H4", "CaptureEngine.kt:completion", "Completion evaluated", "mode=$requestedMode allDone=$allDone successCount=$successCount elapsed=$elapsed")
            // #endregion

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
            processedImage = if (returnProcessed) ImageProcessor.matToBase64(best.enhanced) else null,
            rawImage = if (returnRaw) {
                sessionPreviewBase64 ?: (if (best.raw != null) ImageProcessor.matToBase64(best.raw, quality = 92) else null)
            } else null,
            sharpnessScore = best.sharpnessScore, brightnessScore = best.brightnessScore,
            centeringScore = best.centeringScore, livenessConfidence = best.livenessConfidence
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

    /**
     * Live UI hint: show which finger is being captured (e.g. "left_index capture").
     * Throttled; updates when the next finger in the queue changes.
     */
    private fun emitCurrentFingerCaptureHint(remainingFingers: List<String>, mpSingleFingerId: String?) {
        if (remainingFingers.isEmpty()) return
        val nextId = when (requestedMode) {
            "SINGLE_FINGER" -> mpSingleFingerId ?: activeSingleFingerId ?: remainingFingers.firstOrNull()
            else -> remainingFingers.firstOrNull()
        } ?: return
        if (requestedMode !in setOf(
                "LEFT_FOUR", "RIGHT_FOUR", "LEFT_THUMB", "RIGHT_THUMB", "SINGLE_FINGER"
            )) return

        val now = System.currentTimeMillis()
        val key = "$requestedMode|$nextId"
        if (key == lastFingerTargetKey && now - lastFingerTargetEmitMs < 1000) return
        lastFingerTargetKey = key
        lastFingerTargetEmitMs = now

        val line = "${nextId.lowercase()} capture"
        emitFeedback(
            FeedbackAnalyzer.Feedback(FeedbackAnalyzer.FeedbackType.PROCESSING, line, 0.94),
            fingerId = nextId
        )
    }

    private fun emitFeedback(feedback: FeedbackAnalyzer.Feedback, fingerId: String? = null) {
        val payload = LinkedHashMap<String, Any>()
        payload["type"] = feedback.type.name
        payload["message"] = feedback.message
        payload["confidence"] = feedback.confidence
        feedback.boxes?.let { payload["boxes"] = it }
        if (fingerId != null) payload["fingerId"] = fingerId
        scope.launch(Dispatchers.Main) { feedbackSink?.success(payload) }
    }

    private fun releaseCandidates() {
        candidates.values.flatten().forEach { it.enhanced.release(); it.ridges.release(); it.raw?.release() }
        candidates.clear()
    }

    private fun inferModeFromRequestedFingers(): String {
        val active = fingersRequested.filter { !missingFingers.contains(it) }
        if (active.size == 1) {
            return when (active.first()) {
                "LEFT_THUMB" -> "LEFT_THUMB"
                "RIGHT_THUMB" -> "RIGHT_THUMB"
                else -> "SINGLE_FINGER"
            }
        }
        val rightFour = listOf("RIGHT_INDEX", "RIGHT_MIDDLE", "RIGHT_RING", "RIGHT_LITTLE")
        val leftFour = listOf("LEFT_INDEX", "LEFT_MIDDLE", "LEFT_RING", "LEFT_LITTLE")
        return when {
            active.containsAll(rightFour) && active.size == 4 -> "RIGHT_FOUR"
            active.containsAll(leftFour) && active.size == 4 -> "LEFT_FOUR"
            else -> "CUSTOM_SEQUENCE"
        }
    }
}
