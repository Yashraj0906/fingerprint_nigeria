import Foundation
import os.log

/// Tracks per-session capture metrics. All data is in-memory only.
final class ValidationManager {

    enum FailureReason: String {
        case lowQuality = "LOW_QUALITY"
        case livenessFail = "LIVENESS_FAIL"
        case timeout = "TIMEOUT"
        case lowLight = "LOW_LIGHT"
        case blur = "BLUR"
        case other = "OTHER"
    }

    struct SessionMetrics {
        let captureSuccessRate: Double
        let averageCaptureTimeMs: Int64
        let averageFrameProcessingMs: Int64
        let averageQualityScore: Double
        let failureReasons: [String: Int]
        let qualityDistribution: [String: Int]
    }

    // ─── Session state ────────────────────────────────────────────────────────
    private var sessionStartMs: Int64 = 0
    private var frameCount = 0
    private var totalFrameMs: Int64 = 0
    private var qualityScores: [Double] = []

    // ─── Cumulative counters ──────────────────────────────────────────────────
    private var totalSessions = 0
    private var successSessions = 0
    private var failureCounts: [FailureReason: Int] = Dictionary(
        uniqueKeysWithValues: FailureReason.allCases.map { ($0, 0) }
    )
    private var qualityHistogram = [Int](repeating: 0, count: 11)

    // ─── Session lifecycle ────────────────────────────────────────────────────

    func onSessionStart() {
        sessionStartMs = currentMs()
        frameCount = 0; totalFrameMs = 0
        qualityScores.removeAll()
        totalSessions += 1
    }

    func onSessionSuccess() { successSessions += 1 }

    func onSessionFailure(_ reason: FailureReason) {
        failureCounts[reason] = (failureCounts[reason] ?? 0) + 1
    }

    func onFrameStart() -> Int64 { currentMs() }

    func onFrameEnd(_ startToken: Int64) {
        totalFrameMs += currentMs() - startToken
        frameCount += 1
    }

    func recordQualityScore(_ score: Double) {
        qualityScores.append(score)
        let bucket = min(Int(score / 10.0), 10)
        qualityHistogram[bucket] += 1
    }

    // ─── Snapshot ─────────────────────────────────────────────────────────────

    func snapshot() -> SessionMetrics {
        let elapsed = sessionStartMs > 0 ? currentMs() - sessionStartMs : 0
        let avgFrame = frameCount > 0 ? totalFrameMs / Int64(frameCount) : 0
        let avgQuality = qualityScores.isEmpty ? 0.0 : qualityScores.reduce(0, +) / Double(qualityScores.count)
        let successRate = totalSessions > 0 ? Double(successSessions) / Double(totalSessions) : 0.0

        let distribution = qualityHistogram.enumerated().reduce(into: [String: Int]()) { dict, pair in
            let label = pair.offset < 10 ? "\(pair.offset * 10)-\(pair.offset * 10 + 9)" : "100"
            dict[label] = pair.element
        }

        return SessionMetrics(
            captureSuccessRate:       successRate,
            averageCaptureTimeMs:     elapsed,
            averageFrameProcessingMs: avgFrame,
            averageQualityScore:      avgQuality,
            failureReasons:           failureCounts.reduce(into: [:]) { $0[$1.key.rawValue] = $1.value },
            qualityDistribution:      distribution
        )
    }

    func toResponseMap() -> [String: Any] {
        let s = snapshot()
        return [
            "captureSuccessRate":       s.captureSuccessRate,
            "averageCaptureTimeMs":     s.averageCaptureTimeMs,
            "averageFrameProcessingMs": s.averageFrameProcessingMs,
            "averageQualityScore":      s.averageQualityScore,
            "failureReasons":           s.failureReasons,
            "qualityDistribution":      s.qualityDistribution
        ]
    }

    func logSnapshot() {
        let s = snapshot()
        os_log("successRate=%.1f%% captureTime=%lldms frameTime=%lldms avgQ=%.1f failures=%{public}@",
               log: OSLog(subsystem: "com.yellowsense.fingerprint_sdk", category: "Metrics"),
               type: .debug,
               s.captureSuccessRate * 100, s.averageCaptureTimeMs,
               s.averageFrameProcessingMs, s.averageQualityScore,
               s.failureReasons.filter { $0.value > 0 }.description)
    }

    func reset() {
        sessionStartMs = 0; frameCount = 0; totalFrameMs = 0
        qualityScores.removeAll()
    }

    private func currentMs() -> Int64 { Int64(Date().timeIntervalSince1970 * 1000) }
}

extension ValidationManager.FailureReason: CaseIterable {}
