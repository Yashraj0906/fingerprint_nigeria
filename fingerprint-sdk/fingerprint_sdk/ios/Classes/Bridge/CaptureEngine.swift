import AVFoundation
import CoreImage
import Flutter
import Foundation
import os.log

/// Orchestrates the full iOS capture pipeline:
///   Camera → Frame → Feedback → Segmentation → Enhancement →
///   Quality → Liveness → Multi-frame selection → Template → Response
final class CaptureEngine {

    private let camera   = CameraManager()
    private let liveness = LivenessDetector()
    private var feedbackSink: FlutterEventSink?

    private let processingQueue = DispatchQueue(label: "com.yellowsense.processing", qos: .userInteractive)
    private let log = OSLog(subsystem: "com.yellowsense.fingerprint_sdk", category: "CaptureEngine")

    private var config       = CaptureConfig()
    private var fingerResults = [String: FingerCapture]()
    private var candidates   = [String: [FrameCandidate]]()
    private var retryCounts  = [String: Int]()

    @Atomic private var isCapturing = false
    private var timeoutTimer: Timer?
    private var debugMode = false

    private let framesPerFinger = 5

    // MARK: - Config & Data Structures

    struct CaptureConfig {
        var transactionId    = ""
        var fingersRequested = [String]()
        var missingFingers   = [String]()
        var performLiveness  = true
        var performQuality   = true
        var returnTemplate   = true
        var returnProcessed  = false
        var returnRaw        = false
        var maxRetries       = 3
        var timeoutSeconds   = 30
    }

    struct FingerCapture {
        let fingerId: String
        var qualityScore   = 0.0
        var livenessPassed = false
        var template: String?       = nil
        var processedImage: String? = nil
        var rawImage: String?       = nil
        var status         = "failed"
        var errorCode: String?      = nil
        var errorMessage: String?   = nil
    }

    private struct FrameCandidate {
        let qualityScore: Double
        let enhanced: CGImage
        let ridges: CGImage
        let raw: CGImage?
        let livenessPassed: Bool
    }

    // MARK: - Init

    init(feedbackSink: FlutterEventSink?, debugMode: Bool = false) {
        self.feedbackSink = feedbackSink
        self.debugMode    = debugMode
    }

    // MARK: - Public API

    func updateFeedbackSink(_ sink: FlutterEventSink?) {
        feedbackSink = sink
    }

    func configure(_ params: [String: Any]) {
        config.transactionId    = params["transactionId"]    as? String   ?? ""
        config.fingersRequested = params["fingersRequested"] as? [String] ?? []
        config.missingFingers   = params["missingFingers"]   as? [String] ?? []
        let opts = params["options"] as? [String: Any] ?? [:]
        config.performLiveness  = opts["performLivenessCheck"]  as? Bool ?? true
        config.performQuality   = opts["performQualityCheck"]   as? Bool ?? true
        config.returnTemplate   = opts["returnTemplate"]        as? Bool ?? true
        config.returnProcessed  = opts["returnProcessedImage"]  as? Bool ?? false
        config.returnRaw        = opts["returnRawImage"]        as? Bool ?? false
        config.maxRetries       = opts["maxRetries"]            as? Int  ?? 3
        config.timeoutSeconds   = opts["timeoutSeconds"]        as? Int  ?? 30

        config.missingFingers.forEach { fid in
            fingerResults[fid] = FingerCapture(fingerId: fid, status: "missing")
        }

        if debugMode { os_log("Configured: txn=%{public}s fingers=%{public}@",
                               log: log, type: .debug, config.transactionId,
                               config.fingersRequested.joined(separator: ",")) }
    }

    func start(onComplete: @escaping ([String: Any]) -> Void,
               onError: @escaping (String, String) -> Void) throws {
        isCapturing = true
        liveness.reset()
        FeedbackAnalyzer.reset()
        QualityAnalyzer.resetMotionBaseline()

        // Strict timeout on main run loop
        timeoutTimer = Timer.scheduledTimer(withTimeInterval: Double(config.timeoutSeconds), repeats: false) { [weak self] _ in
            guard let self, self.isCapturing else { return }
            self.stop()
            onError("TIMEOUT", "Capture timed out after \(self.config.timeoutSeconds)s")
        }

        camera.onFrame = { [weak self] sampleBuffer in
            self?.processingQueue.async {
                self?.processFrame(sampleBuffer, onComplete: onComplete, onError: onError)
            }
        }
        try camera.start()
    }

    func stop() {
        isCapturing = false
        timeoutTimer?.invalidate()
        camera.stop()
        liveness.reset()
        FeedbackAnalyzer.reset()
        QualityAnalyzer.resetMotionBaseline()
        candidates.values.forEach { _ in }  // CGImages are ARC-managed
        candidates.removeAll()
        if debugMode { os_log("Capture stopped", log: log, type: .debug) }
    }

    // MARK: - Frame Processing

    private func processFrame(_ buffer: CMSampleBuffer,
                               onComplete: @escaping ([String: Any]) -> Void,
                               onError: @escaping (String, String) -> Void) {
        guard isCapturing,
              let pixelBuffer = CMSampleBufferGetImageBuffer(buffer),
              let cgImage = ImageProcessor.sampleBufferToCGImage(buffer) else { return }

        let segments      = ImageProcessor.segmentFingers(from: pixelBuffer, maxFingers: config.fingersRequested.count)
        let expectedCount = config.fingersRequested.count - config.missingFingers.count
        let frameArea     = CGFloat(cgImage.width * cgImage.height)
        let totalRoiArea  = segments.reduce(0.0) { $0 + $1.area }
        let roiRatio      = Double(totalRoiArea / frameArea)

        // Emit feedback (throttled)
        if let feedback = FeedbackAnalyzer.analyze(
            image: cgImage,
            detectedFingers: segments.count,
            expectedFingers: expectedCount,
            roiAreaRatio: roiRatio
        ) {
            emitFeedback(feedback)
            if debugMode { os_log("Feedback: %{public}s — %{public}s",
                                   log: log, type: .debug, feedback.type.rawValue, feedback.message) }
        }

        // Distance guard
        if roiRatio > 0 {
            if roiRatio < 0.05 {
                emitFeedback(FeedbackAnalyzer.Feedback(type: .DISTANCE, message: "Move closer to the camera", confidence: 0.88))
                return
            }
            if roiRatio > 0.70 {
                emitFeedback(FeedbackAnalyzer.Feedback(type: .DISTANCE, message: "Move further from the camera", confidence: 0.88))
                return
            }
        }

        // Only process when READY
        guard let lastFeedback = FeedbackAnalyzer.analyze(
            image: cgImage, detectedFingers: segments.count,
            expectedFingers: expectedCount, roiAreaRatio: roiRatio
        ), lastFeedback.type == .READY else { return }

        // Process each detected finger
        for roi in segments {
            guard let fingerId = config.fingersRequested[safe: roi.index],
                  !config.missingFingers.contains(fingerId),
                  fingerResults[fingerId]?.status != "success" else { continue }

            let retries = retryCounts[fingerId, default: 0]
            guard retries < config.maxRetries else { continue }

            guard let cropped  = ImageProcessor.cropCGImage(cgImage, to: roi.rect),
                  let enhanced = ImageProcessor.enhance(cropped) else { continue }

            let rawImage = config.returnRaw ? cropped : nil

            // Quality check
            let quality = config.performQuality ? QualityAnalyzer.analyze(enhanced) : nil
            if debugMode { os_log("[%{public}s] quality=%.0f verdict=%{public}s",
                                   log: log, type: .debug, fingerId,
                                   quality?.score ?? 0,
                                   quality?.verdict == .accept ? "ACCEPT" : quality?.verdict == .retry ? "RETRY" : "REJECT") }

            if let q = quality, q.verdict == .reject {
                retryCounts[fingerId] = retries + 1
                if retries + 1 >= config.maxRetries {
                    fingerResults[fingerId] = FingerCapture(
                        fingerId: fingerId, status: "failed",
                        errorCode: "LOW_QUALITY",
                        errorMessage: "Quality \(Int(q.score)) below minimum after \(config.maxRetries) attempts"
                    )
                }
                continue
            }

            // Liveness check
            let live = config.performLiveness ? liveness.evaluate(enhanced) : nil
            if debugMode { os_log("[%{public}s] liveness=%{public}s",
                                   log: log, type: .debug, fingerId,
                                   live?.passed == true ? "PASS" : live?.reason ?? "FAIL") }

            if let l = live, !l.passed {
                fingerResults[fingerId] = FingerCapture(
                    fingerId: fingerId, status: "failed",
                    errorCode: "LIVENESS_FAILED",
                    errorMessage: l.reason ?? "Liveness check failed"
                )
                continue
            }

            guard let ridges = ImageProcessor.detectRidges(enhanced) else { continue }

            let candidate = FrameCandidate(
                qualityScore:   quality?.score ?? 80.0,
                enhanced:       enhanced,
                ridges:         ridges,
                raw:            rawImage,
                livenessPassed: live?.passed ?? true
            )
            candidates[fingerId, default: []].append(candidate)

            // Select best frame once we have enough
            if let fingerCandidates = candidates[fingerId], fingerCandidates.count >= framesPerFinger {
                let best = fingerCandidates.max(by: { $0.qualityScore < $1.qualityScore })!
                finaliseCapture(fingerId: fingerId, best: best)
                candidates.removeValue(forKey: fingerId)
            }
        }

        // Check completion
        let allDone = config.fingersRequested.allSatisfy { fid in
            guard let r = fingerResults[fid] else { return false }
            return r.status == "success" || r.status == "missing" ||
                   (r.status == "failed" && (retryCounts[fid, default: 0] >= config.maxRetries))
        }

        if allDone {
            isCapturing = false
            let response = buildResponse()
            if debugMode { os_log("Complete: %{public}s", log: log, type: .debug,
                                   response["overallStatus"] as? String ?? "") }
            DispatchQueue.main.async { onComplete(response) }
        }
    }

    private func finaliseCapture(fingerId: String, best: FrameCandidate) {
        var capture = FingerCapture(
            fingerId:       fingerId,
            qualityScore:   best.qualityScore,
            livenessPassed: best.livenessPassed,
            status:         "success"
        )
        if config.returnTemplate {
            capture.template = TemplateEncoder.encode(skeleton: best.ridges,
                                                       fingerPosition: isoFingerPosition(fingerId))
        }
        if config.returnProcessed { capture.processedImage = ImageProcessor.cgImageToBase64(best.enhanced) }
        if config.returnRaw, let raw = best.raw { capture.rawImage = ImageProcessor.cgImageToBase64(raw) }
        fingerResults[fingerId] = capture
        if debugMode { os_log("[%{public}s] finalised quality=%.0f", log: log, type: .debug,
                               fingerId, best.qualityScore) }
    }

    // MARK: - Helpers

    private func emitFeedback(_ f: FeedbackAnalyzer.Feedback) {
        let map: [String: Any] = ["type": f.type.rawValue, "message": f.message, "confidence": f.confidence]
        DispatchQueue.main.async { self.feedbackSink?(map) }
    }

    private func buildResponse() -> [String: Any] {
        let allOk = fingerResults.values.allSatisfy { $0.status == "success" || $0.status == "missing" }
        return [
            "transactionId": config.transactionId,
            "overallStatus": allOk ? "success" : "failed",
            "results": fingerResults.values.map { r -> [String: Any?] in
                ["fingerId": r.fingerId, "status": r.status,
                 "qualityScore": r.qualityScore, "livenessPassed": r.livenessPassed,
                 "template": r.template, "rawImage": r.rawImage,
                 "processedImage": r.processedImage,
                 "errorCode": r.errorCode, "errorMessage": r.errorMessage]
            }
        ]
    }

    private func isoFingerPosition(_ fingerId: String) -> Int {
        switch fingerId {
        case "RIGHT_THUMB":  return 1
        case "RIGHT_INDEX":  return 2
        case "RIGHT_MIDDLE": return 3
        case "RIGHT_RING":   return 4
        case "RIGHT_LITTLE": return 5
        case "LEFT_THUMB":   return 6
        case "LEFT_INDEX":   return 7
        case "LEFT_MIDDLE":  return 8
        case "LEFT_RING":    return 9
        case "LEFT_LITTLE":  return 10
        default:             return 0
        }
    }
}

// MARK: - Thread-safe property wrapper

@propertyWrapper
final class Atomic<T> {
    private var value: T
    private let lock = NSLock()
    init(wrappedValue: T) { value = wrappedValue }
    var wrappedValue: T {
        get { lock.lock(); defer { lock.unlock() }; return value }
        set { lock.lock(); defer { lock.unlock() }; value = newValue }
    }
}

// MARK: - Safe array subscript

private extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
