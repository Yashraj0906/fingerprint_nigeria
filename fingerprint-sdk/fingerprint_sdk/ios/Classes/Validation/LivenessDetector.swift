import Accelerate
import CoreImage

/// Multi-layer liveness detection matching Android implementation.
///
/// Layer 1 — LBP texture variance (printed images are flat)
/// Layer 2 — Specular reflection ratio (screens produce uniform highlights)
/// Layer 3 — Micro-movement across 3–5 frames (spoofs are static)
/// Layer 4 — High-frequency energy via vDSP FFT (printed ridges lack HF content)
final class LivenessDetector {

    struct LivenessResult {
        let passed: Bool
        let reason: String?
    }

    func evaluate(_ image: CGImage, bgr: CGImage, fullBgr: CGImage, handMode: String) -> LivenessResult {
        guard let (grayData, w, h) = grayPixelsWithDetails(image),
              let (bgrData, _, _) = bgrPixelsWithDetails(bgr),
              let (fullBgrData, fw, fh) = bgrPixelsWithDetails(fullBgr) else {
            return LivenessResult(passed: true, reason: nil)
        }

        let res = FingerprintCoreWrapper.evaluateLiveness(withGray: grayData,
                                                        bgr: bgrData,
                                                        fullBgr: fullBgrData,
                                                        width: Int32(w),
                                                        height: Int32(h),
                                                        fullWidth: Int32(fw),
                                                        fullHeight: Int32(fh),
                                                        handMode: handMode)

        return LivenessResult(
            passed: res["passed"] as? Bool ?? false,
            reason: res["reason"] as? String
        )
    }

    func reset() {
        // No-op for bridge implementation
    }

    // MARK: - Helpers

    private func grayPixelsWithDetails(_ image: CGImage) -> (Data, Int, Int)? {
        let w = image.width, h = image.height
        var data = [UInt8](repeating: 0, count: w * h)
        guard let ctx = CGContext(data: &data, width: w, height: h,
                                  bitsPerComponent: 8, bytesPerRow: w,
                                  space: CGColorSpaceCreateDeviceGray(),
                                  bitmapInfo: 0) else { return nil }
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
        return (Data(data), w, h)
    }

    private func bgrPixelsWithDetails(_ image: CGImage) -> (Data, Int, Int)? {
        let w = image.width, h = image.height
        var data = [UInt8](repeating: 0, count: w * h * 4) // RGBA usually
        guard let ctx = CGContext(data: &data, width: w, height: h,
                                  bitsPerComponent: 8, bytesPerRow: w * 4,
                                  space: CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return nil }
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
        
        // Convert RGBA to BGR for OpenCV
        var bgr = [UInt8](repeating: 0, count: w * h * 3)
        for i in 0..<(w * h) {
            bgr[i*3 + 0] = data[i*4 + 2] // B
            bgr[i*3 + 1] = data[i*4 + 1] // G
            bgr[i*3 + 2] = data[i*4 + 0] // R
        }
        return (Data(bgr), w, h)
    }
}
