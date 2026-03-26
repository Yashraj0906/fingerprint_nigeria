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

    struct Minutia {
        let x: Int; let y: Int
        let angle: Int   // 0–255 → 0–360°
        let type: Int    // 1=ending, 2=bifurcation
        let quality: Int // 0–100
    }

    private static let ENDING         = 1
    private static let BIFURCATION    = 2
    private static let BORDER_MARGIN  = 15
    private static let CLUSTER_RADIUS = 12.0
    private static let MAX_MINUTIAE   = 80
    private static let MIN_MINUTIAE   = 10

    /// Returns nil if minutiae count < MIN_MINUTIAE (caller marks LOW_QUALITY).
    static func encode(skeleton: CGImage, fingerPosition: Int = 0, qualityScore: Double = 80.0) -> String? {
        guard let (pixels, w, h) = grayPixels(skeleton) else { return nil }
        let raw      = extractMinutiae(pixels: pixels, width: w, height: h)
        let filtered = filterMinutiae(raw, width: w, height: h)
        guard filtered.count >= MIN_MINUTIAE else { return nil }
        return buildISOTemplate(filtered, width: w, height: h,
                                fingerPosition: fingerPosition,
                                fingerQuality: Int(qualityScore).clamped(to: 0...100))
    }

    // MARK: - Extraction

    private static func extractMinutiae(pixels: [UInt8], width: Int, height: Int) -> [Minutia] {
        var result: [Minutia] = []

        func px(_ r: Int, _ c: Int) -> Int {
            guard r >= 0, r < height, c >= 0, c < width else { return 0 }
            return pixels[r * width + c] > 127 ? 1 : 0
        }

        for r in BORDER_MARGIN..<(height - BORDER_MARGIN) {
            for c in BORDER_MARGIN..<(width - BORDER_MARGIN) {
                guard px(r, c) == 1 else { continue }

                let n = [px(r-1,c-1), px(r-1,c), px(r-1,c+1),
                         px(r,  c+1),
                         px(r+1,c+1), px(r+1,c), px(r+1,c-1),
                         px(r,  c-1)]
                var cn = 0
                for i in 0..<8 { cn += abs(n[i] - n[(i+1) % 8]) }
                cn /= 2

                let type: Int
                switch cn {
                case 1: type = ENDING
                case 3: type = BIFURCATION
                default: continue
                }

                let angle   = ridgeAngle(pixels: pixels, r: r, c: c, width: width, height: height)
                let quality = localQuality(pixels: pixels, r: r, c: c, width: width, height: height)
                result.append(Minutia(x: c, y: r, angle: angle, type: type, quality: quality))
            }
        }
        return result
    }

    private static func ridgeAngle(pixels: [UInt8], r: Int, c: Int, width: Int, height: Int) -> Int {
        func px(_ dr: Int, _ dc: Int) -> Double {
            let nr = (r + dr).clamped(to: 0...(height-1))
            let nc = (c + dc).clamped(to: 0...(width-1))
            return Double(pixels[nr * width + nc])
        }
        // 5×5 Sobel-like gradient
        let gx = (-px(-2,-2) - 2*px(-1,-2) - px(0,-2) + px(0,2) + 2*px(1,2) + px(2,2))
               + (-px(-2,-1) - 2*px(-1,-1)             + px(0,1) + 2*px(1,1) + px(2,1))
        let gy = (-px(-2,-2) - 2*px(-2,-1) - px(-2,0) + px(2,0) + 2*px(2,1) + px(2,2))
               + (-px(-1,-2) - 2*px(-1,-1)             + px(1,0) + 2*px(1,1) + px(1,2))
        let deg = (atan2(gy, gx) * 180.0 / .pi + 360.0).truncatingRemainder(dividingBy: 360.0)
        return Int(deg / 360.0 * 255.0).clamped(to: 0...255)
    }

    private static func localQuality(pixels: [UInt8], r: Int, c: Int, width: Int, height: Int) -> Int {
        func px(_ dr: Int, _ dc: Int) -> Double {
            let nr = (r + dr).clamped(to: 0...(height-1))
            let nc = (c + dc).clamped(to: 0...(width-1))
            return Double(pixels[nr * width + nc])
        }
        let lap = abs(px(-1,0) + px(1,0) + px(0,-1) + px(0,1) - 4 * px(0,0))
        return Int(lap / 4.0 * 100.0).clamped(to: 0...100)
    }

    // MARK: - Filtering

    private static func filterMinutiae(_ raw: [Minutia], width: Int, height: Int) -> [Minutia] {
        let sorted = raw.sorted { $0.quality > $1.quality }
        var accepted: [Minutia] = []
        for m in sorted {
            guard m.x >= BORDER_MARGIN, m.x <= width  - BORDER_MARGIN,
                  m.y >= BORDER_MARGIN, m.y <= height - BORDER_MARGIN else { continue }
            let tooClose = accepted.contains { e in
                let dx = Double(m.x - e.x), dy = Double(m.y - e.y)
                return sqrt(dx*dx + dy*dy) < CLUSTER_RADIUS
            }
            if !tooClose { accepted.append(m) }
            if accepted.count >= MAX_MINUTIAE { break }
        }
        return accepted
    }

    // MARK: - ISO 19794-2 Encoding

    private static func buildISOTemplate(_ minutiae: [Minutia], width: Int, height: Int,
                                          fingerPosition: Int, fingerQuality: Int) -> String {
        let count     = min(minutiae.count, MAX_MINUTIAE)
        let recordLen = 28 + count * 6 + 2
        var buf = Data(capacity: recordLen)

        buf.append(contentsOf: "FMR\0".utf8)
        buf.append(contentsOf: " 20\0".utf8)
        buf.appendBigEndian(UInt32(recordLen))
        buf.appendBigEndian(UInt16(0))           // CBEFF
        buf.appendBigEndian(UInt16(0))           // equipment
        buf.appendBigEndian(UInt16(width))
        buf.appendBigEndian(UInt16(height))
        buf.appendBigEndian(UInt16(197))         // X res ≈500dpi
        buf.appendBigEndian(UInt16(197))         // Y res
        buf.append(1)                            // views
        buf.append(0)                            // reserved
        buf.append(UInt8(fingerPosition))
        buf.append(0x00)                         // live-scan plain
        buf.append(UInt8(fingerQuality))
        buf.append(UInt8(count))

        for m in minutiae.prefix(count) {
            buf.append(UInt8(((m.type & 0x03) << 6) | ((m.x >> 8) & 0x3F)))
            buf.append(UInt8(m.x & 0xFF))
            buf.append(UInt8((m.y >> 8) & 0x3F))
            buf.append(UInt8(m.y & 0xFF))
            buf.append(UInt8(m.angle))
            buf.append(UInt8(m.quality))
        }
        buf.appendBigEndian(UInt16(0))
        return buf.base64EncodedString()
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

// MARK: - Helpers

private extension Data {
    mutating func appendBigEndian(_ v: UInt32) { var x = v.bigEndian; append(contentsOf: withUnsafeBytes(of: &x) { Array($0) }) }
    mutating func appendBigEndian(_ v: UInt16) { var x = v.bigEndian; append(contentsOf: withUnsafeBytes(of: &x) { Array($0) }) }
}

private extension Comparable {
    func clamped(to range: ClosedRange<Self>) -> Self { min(max(self, range.lowerBound), range.upperBound) }
}
