import Accelerate
import CoreImage

/// Five-metric quality scorer matching Android implementation.
///
/// score = 0.25*blur + 0.20*contrast + 0.25*ridgeClarity + 0.20*coverage + 0.10*motionStability
///
/// Thresholds: <40 reject | 40–70 retry | >70 accept
enum QualityAnalyzer {

    enum Verdict { case accept, retry, reject }

    struct QualityResult {
        let score: Double
        let blurScore: Double
        let contrastScore: Double
        let ridgeScore: Double
        let coverageScore: Double
        let motionScore: Double
        let verdict: Verdict
        var passed: Bool { verdict == .accept }
    }

    static func analyze(_ image: CGImage) -> QualityResult {
        guard let (imageData, w, h) = bgrPixelsWithDetails(image) else {
            return QualityResult(score: 0, blurScore: 0, contrastScore: 0, ridgeScore: 0,
                                 coverageScore: 0, motionScore: 0, verdict: .reject)
        }

        let res = FingerprintCoreWrapper.analyzeQuality(withImage: imageData,
                                                      width: Int32(w),
                                                      height: Int32(h))

        let verdict: Verdict = {
            switch res["decision"] as? String {
            case "ACCEPT": return .accept
            case "RETRY":  return .retry
            default:       return .reject
            }
        }()

        return QualityResult(
            score: res["compositeScore"] as? Double ?? 0.0,
            blurScore: res["blurScore"] as? Double ?? 0.0,
            contrastScore: res["contrastScore"] as? Double ?? 0.0,
            ridgeScore: res["ridgeClarityScore"] as? Double ?? 0.0,
            coverageScore: res["coverageScore"] as? Double ?? 0.0,
            motionScore: res["orientationScore"] as? Double ?? 0.0,
            verdict: verdict
        )
    }

    static func resetMotionBaseline() {
        // No-op for bridge implementation
    }

    // MARK: - Helpers

    private static func bgrPixelsWithDetails(_ image: CGImage) -> (Data, Int, Int)? {
        let w = image.width, h = image.height
        var data = [UInt8](repeating: 0, count: w * h * 4) 
        guard let ctx = CGContext(data: &data, width: w, height: h,
                                  bitsPerComponent: 8, bytesPerRow: w * 4,
                                  space: CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return nil }
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
        
        var bgr = [UInt8](repeating: 0, count: w * h * 3)
        for i in 0..<(w * h) {
            bgr[i*3 + 0] = data[i*4 + 2] // B
            bgr[i*3 + 1] = data[i*4 + 1] // G
            bgr[i*3 + 2] = data[i*4 + 0] // R
        }
        return (Data(bgr), w, h)
    }
}
}

// MARK: - Array Statistics

private extension Array where Element == Double {
    func variance() -> Double {
        guard !isEmpty else { return 0 }
        let mean = reduce(0, +) / Double(count)
        return map { ($0 - mean) * ($0 - mean) }.reduce(0, +) / Double(count)
    }
    func standardDeviation() -> Double { variance().squareRoot() }
}

private extension Comparable {
    func clamped(to range: ClosedRange<Self>) -> Self { min(max(self, range.lowerBound), range.upperBound) }
}
