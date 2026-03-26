import CoreImage

/// Per-frame real-time feedback analyser — throttled to 10 events/sec.
enum FeedbackAnalyzer {

    enum FeedbackType: String { case ALIGNMENT, LIGHTING, MOTION, DISTANCE, READY, PROCESSING }

    struct Feedback {
        let type: FeedbackType
        let message: String
        let confidence: Double
    }

    private static let emitIntervalMs: Double = 100  // 10 events/sec max
    private static var lastEmitTime: Double = 0

    static func analyze(
        image: CGImage,
        detectedFingers: Int,
        expectedFingers: Int,
        roiAreaRatio: Double = 0.0   // total finger ROI area / frame area
    ) -> Feedback? {
        let now = Date().timeIntervalSince1970 * 1000
        guard now - lastEmitTime >= emitIntervalMs else { return nil }
        lastEmitTime = now

        if let f = checkLighting(image) { return f }
        if let f = checkBlur(image) { return f }
        if let f = checkDistance(roiAreaRatio) { return f }
        if let f = checkAlignment(detectedFingers, expectedFingers) { return f }
        return Feedback(type: .READY, message: "Hold steady — capturing", confidence: 0.95)
    }

    static func reset() { lastEmitTime = 0 }

    // MARK: - Checks

    private static func checkLighting(_ image: CGImage) -> Feedback? {
        guard let (pixels, _, _) = grayPixels(image), !pixels.isEmpty else { return nil }
        let mean = pixels.map { Double($0) }.reduce(0, +) / Double(pixels.count)
        switch mean {
        case ..<55:  return Feedback(type: .LIGHTING, message: "Too dark — move to better lighting", confidence: 0.92)
        case 215...: return Feedback(type: .LIGHTING, message: "Too bright — reduce glare", confidence: 0.92)
        case ..<80:  return Feedback(type: .LIGHTING, message: "Lighting is dim — improve if possible", confidence: 0.70)
        default:     return nil
        }
    }

    private static func checkBlur(_ image: CGImage) -> Feedback? {
        guard let edges = OpenCVWrapper.detectEdges(image),
              let (pixels, w, h) = grayPixels(edges),
              w * h > 0 else { return nil }
        let edgeRatio = Double(pixels.filter { $0 > 30 }.count) / Double(w * h)
        switch edgeRatio {
        case ..<0.01: return Feedback(type: .MOTION, message: "Hold very still — severe blur detected", confidence: 0.95)
        case ..<0.03: return Feedback(type: .MOTION, message: "Hold steady — slight motion blur", confidence: 0.80)
        default:      return nil
        }
    }

    private static func checkDistance(_ roiRatio: Double) -> Feedback? {
        guard roiRatio > 0 else { return nil }
        if roiRatio < 0.05 { return Feedback(type: .DISTANCE, message: "Move closer to the camera", confidence: 0.88) }
        if roiRatio > 0.70 { return Feedback(type: .DISTANCE, message: "Move further from the camera", confidence: 0.88) }
        return nil
    }

    private static func checkAlignment(_ detected: Int, _ expected: Int) -> Feedback? {
        if detected == 0 { return Feedback(type: .ALIGNMENT, message: "Place your fingers flat in the frame", confidence: 0.85) }
        if detected < expected { return Feedback(type: .ALIGNMENT, message: "Show all \(expected) fingers — only \(detected) detected", confidence: 0.78) }
        if detected > expected + 1 { return Feedback(type: .ALIGNMENT, message: "Too many fingers — show only \(expected)", confidence: 0.75) }
        return nil
    }

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
