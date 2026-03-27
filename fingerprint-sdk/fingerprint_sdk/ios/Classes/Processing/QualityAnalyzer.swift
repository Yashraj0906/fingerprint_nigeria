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

    private static var prevPixels: [UInt8]? = nil
    private static var prevSize: (Int, Int) = (0, 0)

    static func analyze(_ image: CGImage) -> QualityResult {
        let blur     = blurScore(image)
        let contrast = contrastScore(image)
        let ridges   = ridgeClarityScore(image)
        let coverage = coverageScore(image)
        let motion   = motionStabilityScore(image)

        let score = (blur * 0.25 + contrast * 0.20 + ridges * 0.25 +
                     coverage * 0.20 + motion * 0.10).clamped(to: 0...100)

        let verdict: Verdict = score > 70 ? .accept : score >= 40 ? .retry : .reject
        return QualityResult(score: score, blurScore: blur, contrastScore: contrast,
                             ridgeScore: ridges, coverageScore: coverage, motionScore: motion,
                             verdict: verdict)
    }

    static func resetMotionBaseline() {
        prevPixels = nil
        prevSize = (0, 0)
    }

    // MARK: - Metrics

    /// Laplacian variance via vImage — higher = sharper.
    private static func blurScore(_ image: CGImage) -> Double {
        guard let (pixels, w, h) = grayPixels(image) else { return 0 }
        let kernel: [Int16] = [0, 1, 0, 1, -4, 1, 0, 1, 0]
        var srcData = pixels
        var dstData = [UInt8](repeating: 0, count: w * h)
        srcData.withUnsafeMutableBytes { srcPtr in
            dstData.withUnsafeMutableBytes { dstPtr in
                var src = vImage_Buffer(data: srcPtr.baseAddress!, height: vImagePixelCount(h),
                                        width: vImagePixelCount(w), rowBytes: w)
                var dst = vImage_Buffer(data: dstPtr.baseAddress!, height: vImagePixelCount(h),
                                        width: vImagePixelCount(w), rowBytes: w)
                vImageConvolve_Planar8(&src, &dst, nil, 0, 0, kernel, 3, 3, 0,
                                       0, vImage_Flags(kvImageEdgeExtend))
            }
        }
        let variance = dstData.map { Double($0) }.variance()
        return (variance / 5.0).clamped(to: 0...100)
    }

    /// RMS contrast (standard deviation of pixel intensities).
    private static func contrastScore(_ image: CGImage) -> Double {
        guard let (pixels, _, _) = grayPixels(image) else { return 0 }
        return (pixels.map { Double($0) }.standardDeviation() / 0.64).clamped(to: 0...100)
    }

    /// Ridge clarity: Canny edge density, peak at 15%.
    private static func ridgeClarityScore(_ image: CGImage) -> Double {
        guard let edges = OpenCVWrapper.detectEdges(image),
              let (pixels, w, h) = grayPixels(edges) else { return 0 }
        let edgeCount = pixels.filter { $0 > 30 }.count
        let ratio = Double(edgeCount) / Double(w * h)
        return (1.0 - abs(ratio - 0.15) / 0.15).clamped(to: 0...1) * 100.0
    }

    /// Coverage: non-background pixel ratio (Otsu threshold approximation).
    private static func coverageScore(_ image: CGImage) -> Double {
        guard let (pixels, _, _) = grayPixels(image) else { return 0 }
        let sorted = pixels.sorted()
        let otsu = sorted[sorted.count / 2]  // median as Otsu approximation
        let nonZero = pixels.filter { $0 > otsu }.count
        let ratio = Double(nonZero) / Double(pixels.count)
        if ratio < 0.30 { return (ratio / 0.30 * 100).clamped(to: 0...100) }
        if ratio > 0.80 { return ((1.0 - ratio) / 0.20 * 100).clamped(to: 0...100) }
        return 100.0
    }

    /// Motion stability: inverse of mean absolute difference from previous frame.
    private static func motionStabilityScore(_ image: CGImage) -> Double {
        guard let (pixels, w, h) = grayPixels(image) else { return 100 }
        defer {
            prevPixels = pixels
            prevSize = (w, h)
        }
        guard let prev = prevPixels, prevSize == (w, h) else { return 100 }
        var sum = 0.0
        for i in 0..<pixels.count { sum += abs(Double(pixels[i]) - Double(prev[i])) }
        let meanDiff = sum / Double(pixels.count)
        return (1.0 - (meanDiff / 20.0)).clamped(to: 0...1) * 100.0
    }

    // MARK: - Helpers

    private static func grayPixels(_ image: CGImage) -> ([UInt8], Int, Int)? {
        let w = image.width, h = image.height
        var data = [UInt8](repeating: 0, count: w * h)
        guard let ctx = CGContext(data: &data, width: w, height: h,
                                  bitsPerComponent: 8, bytesPerRow: w,
                                  space: CGColorSpaceCreateDeviceGray(),
                                  bitmapInfo: 0) else { return nil }
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
        return (data, w, h)
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
