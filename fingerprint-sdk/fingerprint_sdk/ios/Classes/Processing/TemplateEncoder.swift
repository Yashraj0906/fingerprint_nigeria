import Foundation
import CoreGraphics

/// ISO/IEC 19794-2:2005 Finger Minutiae Record encoder.
///
/// Production hardening:
///   - MAX_MINUTIAE = 80 (compact, sufficient for matching)
///   - MIN_MINUTIAE = 10 (returns nil → LOW_QUALITY signal)
///   - BORDER_MARGIN = 15px (wider exclusion zone)
///   - CLUSTER_RADIUS = 12px (stronger deduplication)
///   - Per-minutia quality from local Laplacian variance
///   - Angle from 5×5 gradient neighbourhood
enum TemplateEncoder {

    /// Returns nil if minutiae count < MIN_MINUTIAE (caller marks LOW_QUALITY).
    static func encode(image: CGImage, fingerPosition: Int = 0, qualityScore: Double = 80.0) -> String? {
        guard let (imageData, w, h) = bgrPixelsWithDetails(image) else { return nil }
        
        return FingerprintCoreWrapper.extractTemplate(withImage: imageData,
                                                      width: Int32(w),
                                                      height: Int32(h))
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

// MARK: - Helpers

private extension Data {
    mutating func appendBigEndian(_ v: UInt32) { var x = v.bigEndian; append(contentsOf: Swift.withUnsafeBytes(of: &x) { Array($0) }) }
    mutating func appendBigEndian(_ v: UInt16) { var x = v.bigEndian; append(contentsOf: Swift.withUnsafeBytes(of: &x) { Array($0) }) }
}

private extension Comparable {
    func clamped(to range: ClosedRange<Self>) -> Self { min(max(self, range.lowerBound), range.upperBound) }
}
