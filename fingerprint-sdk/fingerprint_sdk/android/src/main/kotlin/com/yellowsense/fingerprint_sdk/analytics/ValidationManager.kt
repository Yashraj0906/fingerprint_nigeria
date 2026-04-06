package com.yellowsense.fingerprint_sdk.analytics

import android.util.Log

/**
 * Tracks per-session and cumulative capture metrics.
 * All data is in-memory only — never persisted.
 *
 * Metrics:
 *   captureSuccessRate, averageCaptureTimeMs, failureReasons,
 *   qualityScoreDistribution, averageFrameProcessingMs
 */
class ValidationManager {

    enum class FailureReason {
        LOW_QUALITY, LIVENESS_FAIL, TIMEOUT, LOW_LIGHT, BLUR, OTHER
    }

    data class SessionMetrics(
        val captureSuccessRate: Double,
        val averageCaptureTimeMs: Long,
        val averageFrameProcessingMs: Long,
        val averageQualityScore: Double,
        val failureReasons: Map<String, Int>,
        val qualityDistribution: Map<String, Int>
    )

    // ─── Session state ────────────────────────────────────────────────────────
    private var sessionStartMs = 0L
    private var frameCount = 0
    private var totalFrameMs = 0L
    private val sessionQualityScores = mutableListOf<Double>()

    // ─── Cumulative counters ──────────────────────────────────────────────────
    private var totalSessions = 0
    private var successSessions = 0
    private val failureCounts = FailureReason.values().associateWith { 0 }.toMutableMap()
    // Histogram: index = floor(score/10), clamped 0..10
    private val qualityHistogram = IntArray(11)

    // ─── Session lifecycle ────────────────────────────────────────────────────

    fun onSessionStart() {
        sessionStartMs = System.currentTimeMillis()
        frameCount = 0
        totalFrameMs = 0L
        sessionQualityScores.clear()
        totalSessions++
    }

    fun onSessionSuccess() { successSessions++ }

    fun onSessionFailure(reason: FailureReason) {
        failureCounts[reason] = (failureCounts[reason] ?: 0) + 1
    }

    // ─── Per-frame tracking ───────────────────────────────────────────────────

    /** Returns a start token; pass to onFrameEnd. */
    fun onFrameStart(): Long = System.currentTimeMillis()

    fun isFrameStable(): Boolean = frameCount >= 3

    fun onFrameEnd(startToken: Long) {
        totalFrameMs += System.currentTimeMillis() - startToken
        frameCount++
    }

    // ─── Quality tracking ─────────────────────────────────────────────────────

    fun recordQualityScore(score: Double) {
        sessionQualityScores.add(score)
        qualityHistogram[(score / 10.0).toInt().coerceIn(0, 10)]++
    }

    // ─── Snapshot ─────────────────────────────────────────────────────────────

    fun snapshot(): SessionMetrics {
        val elapsed = if (sessionStartMs > 0) System.currentTimeMillis() - sessionStartMs else 0L
        return SessionMetrics(
            captureSuccessRate       = if (totalSessions > 0) successSessions.toDouble() / totalSessions else 0.0,
            averageCaptureTimeMs     = elapsed,
            averageFrameProcessingMs = if (frameCount > 0) totalFrameMs / frameCount else 0L,
            averageQualityScore      = if (sessionQualityScores.isNotEmpty()) sessionQualityScores.average() else 0.0,
            failureReasons           = failureCounts.mapKeys { it.key.name },
            qualityDistribution      = qualityHistogram.mapIndexed { i, c ->
                (if (i < 10) "${i * 10}-${i * 10 + 9}" else "100") to c
            }.toMap()
        )
    }

    fun logSnapshot(tag: String = "ValidationManager") {
        val s = snapshot()
        Log.d(tag, "successRate=${s.captureSuccessRate.format()} " +
                "captureTime=${s.averageCaptureTimeMs}ms " +
                "frameTime=${s.averageFrameProcessingMs}ms " +
                "avgQuality=${s.averageQualityScore.format()} " +
                "failures=${s.failureReasons.filter { it.value > 0 }}")
    }

    fun toResponseMap(): Map<String, Any> = mapOf(
        "captureSuccessRate"       to snapshot().captureSuccessRate,
        "averageCaptureTimeMs"     to snapshot().averageCaptureTimeMs,
        "averageFrameProcessingMs" to snapshot().averageFrameProcessingMs,
        "averageQualityScore"      to snapshot().averageQualityScore,
        "failureReasons"           to snapshot().failureReasons,
        "qualityDistribution"      to snapshot().qualityDistribution
    )

    fun reset() {
        sessionStartMs = 0L; frameCount = 0; totalFrameMs = 0L
        sessionQualityScores.clear()
    }

    private fun Double.format() = "%.1f".format(this)
}
