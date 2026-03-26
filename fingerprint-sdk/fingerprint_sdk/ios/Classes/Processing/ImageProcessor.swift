import Accelerate
import CoreImage
import UIKit

// NOTE: OpenCV C++ calls are wrapped in an Objective-C++ helper (OpenCVWrapper)
// to avoid Swift/C++ interop issues. See OpenCVWrapper.h/.mm

/// Full fingerprint processing pipeline using CoreImage + vImage + OpenCVWrapper.
///
/// Pipeline:
///   1. Grayscale conversion
///   2. CLAHE (contrast-limited adaptive histogram equalisation)
///   3. Gaussian blur (noise reduction)
///   4. Ridge enhancement (multi-angle Sobel via OpenCVWrapper)
///   5. Adaptive thresholding (binarisation)
///   6. Skeletonisation (Zhang-Suen via OpenCVWrapper)
enum ImageProcessor {

    // MARK: - Frame Conversion

    static func sampleBufferToCVPixelBuffer(_ buffer: CMSampleBuffer) -> CVPixelBuffer? {
        CMSampleBufferGetImageBuffer(buffer)
    }

    static func sampleBufferToCGImage(_ buffer: CMSampleBuffer) -> CGImage? {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(buffer) else { return nil }
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
        return sharedCIContext.createCGImage(ciImage, from: ciImage.extent)
    }

    // MARK: - Enhancement Pipeline

    /// Full pipeline: CLAHE → Gaussian → Ridge Enhancement → Adaptive Threshold → Skeleton
    static func enhance(_ cgImage: CGImage) -> CGImage? {
        // Step 1: Grayscale
        guard let gray = toGrayCGImage(cgImage) else { return nil }

        // Step 2: CLAHE via vImage histogram equalisation (tile-based approximation)
        guard let clahe = applyCLAHE(gray) else { return nil }

        // Step 3: Gaussian blur (σ=1.0) via CoreImage
        let blurred = applyGaussianBlur(clahe, sigma: 1.0)

        // Step 4: Ridge enhancement — multi-angle Sobel via OpenCVWrapper
        guard let ridgeEnhanced = OpenCVWrapper.enhanceRidges(blurred) else { return blurred }

        // Step 5: Adaptive threshold
        guard let binary = OpenCVWrapper.adaptiveThreshold(ridgeEnhanced) else { return ridgeEnhanced }

        // Step 6: Skeletonisation
        return OpenCVWrapper.skeletonize(binary) ?? binary
    }

    // MARK: - Ridge Detection

    /// Canny edge detection → binary ridge map for quality scoring and template generation.
    static func detectRidges(_ cgImage: CGImage) -> CGImage? {
        OpenCVWrapper.detectEdges(cgImage)
    }

    // MARK: - Finger Segmentation

    struct FingerROI {
        let index: Int
        let rect: CGRect
        let area: Double
    }

    /// YCrCb skin segmentation → contour bounding boxes sorted left→right.
    static func segmentFingers(from pixelBuffer: CVPixelBuffer, maxFingers: Int = 4) -> [FingerROI] {
        guard let rects = OpenCVWrapper.segmentFingers(pixelBuffer, maxFingers: Int32(maxFingers)) as? [[String: Any]] else {
            return fallbackSkinSegmentation(pixelBuffer, maxFingers: maxFingers)
        }
        return rects.enumerated().compactMap { idx, dict -> FingerROI? in
            guard let x = dict["x"] as? Double, let y = dict["y"] as? Double,
                  let w = dict["w"] as? Double, let h = dict["h"] as? Double,
                  let area = dict["area"] as? Double else { return nil }
            return FingerROI(index: idx, rect: CGRect(x: x, y: y, width: w, height: h), area: area)
        }
    }

    // MARK: - Helpers

    static func cgImageToBase64(_ image: CGImage, quality: CGFloat = 0.85) -> String? {
        UIImage(cgImage: image).jpegData(compressionQuality: quality)?.base64EncodedString()
    }

    static func cropCGImage(_ image: CGImage, to rect: CGRect) -> CGImage? {
        // Clamp rect to image bounds
        let bounds = CGRect(x: 0, y: 0, width: image.width, height: image.height)
        let clamped = rect.intersection(bounds)
        guard !clamped.isEmpty else { return nil }
        return image.cropping(to: clamped)
    }

    // MARK: - Private Helpers

    private static let sharedCIContext = CIContext(options: [.useSoftwareRenderer: false])

    private static func toGrayCGImage(_ image: CGImage) -> CGImage? {
        let w = image.width, h = image.height
        var data = [UInt8](repeating: 0, count: w * h)
        guard let ctx = CGContext(data: &data, width: w, height: h,
                                  bitsPerComponent: 8, bytesPerRow: w,
                                  space: CGColorSpaceCreateDeviceGray(),
                                  bitmapInfo: 0) else { return nil }
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
        return ctx.makeImage()
    }

    /// Tile-based CLAHE approximation using vImage histogram equalisation per tile.
    private static func applyCLAHE(_ gray: CGImage, tileSize: Int = 64) -> CGImage? {
        let w = gray.width, h = gray.height
        var pixels = [UInt8](repeating: 0, count: w * h)
        guard let ctx = CGContext(data: &pixels, width: w, height: h,
                                  bitsPerComponent: 8, bytesPerRow: w,
                                  space: CGColorSpaceCreateDeviceGray(),
                                  bitmapInfo: 0) else { return nil }
        ctx.draw(gray, in: CGRect(x: 0, y: 0, width: w, height: h))

        var output = pixels  // copy

        let tilesX = max(1, w / tileSize)
        let tilesY = max(1, h / tileSize)

        for ty in 0..<tilesY {
            for tx in 0..<tilesX {
                let x0 = tx * tileSize, y0 = ty * tileSize
                let x1 = min(x0 + tileSize, w), y1 = min(y0 + tileSize, h)
                let tw = x1 - x0, th = y1 - y0
                guard tw > 0, th > 0 else { continue }

                // Extract tile pixels
                var tile = [UInt8](repeating: 0, count: tw * th)
                for row in 0..<th {
                    let srcOff = (y0 + row) * w + x0
                    let dstOff = row * tw
                    tile[dstOff..<dstOff+tw] = pixels[srcOff..<srcOff+tw]
                }

                // Build histogram
                var hist = [Int](repeating: 0, count: 256)
                tile.forEach { hist[Int($0)] += 1 }

                // Clip histogram (CLAHE clip limit ≈ 2× average)
                let clipLimit = max(1, (tw * th) / 128)
                var excess = 0
                for i in 0..<256 {
                    if hist[i] > clipLimit { excess += hist[i] - clipLimit; hist[i] = clipLimit }
                }
                let redistrib = excess / 256
                for i in 0..<256 { hist[i] += redistrib }

                // CDF → LUT
                var cdf = [Int](repeating: 0, count: 256)
                cdf[0] = hist[0]
                for i in 1..<256 { cdf[i] = cdf[i-1] + hist[i] }
                let cdfMin = cdf.first(where: { $0 > 0 }) ?? 1
                let total = tw * th
                var lut = [UInt8](repeating: 0, count: 256)
                for i in 0..<256 {
                    lut[i] = UInt8(max(0, min(255, (cdf[i] - cdfMin) * 255 / max(1, total - cdfMin))))
                }

                // Apply LUT back to output
                for row in 0..<th {
                    let srcOff = (y0 + row) * w + x0
                    for col in 0..<tw {
                        output[srcOff + col] = lut[Int(pixels[srcOff + col])]
                    }
                }
            }
        }

        guard let outCtx = CGContext(data: &output, width: w, height: h,
                                     bitsPerComponent: 8, bytesPerRow: w,
                                     space: CGColorSpaceCreateDeviceGray(),
                                     bitmapInfo: 0) else { return nil }
        return outCtx.makeImage()
    }

    private static func applyGaussianBlur(_ image: CGImage, sigma: Double) -> CGImage {
        let ci = CIImage(cgImage: image)
        let blurred = ci.applyingFilter("CIGaussianBlur", parameters: [kCIInputRadiusKey: sigma])
        return sharedCIContext.createCGImage(blurred, from: ci.extent) ?? image
    }

    /// Fallback skin segmentation using pure Swift when OpenCV is unavailable.
    private static func fallbackSkinSegmentation(_ pixelBuffer: CVPixelBuffer, maxFingers: Int) -> [FingerROI] {
        CVPixelBufferLockBaseAddress(pixelBuffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pixelBuffer, .readOnly) }

        let width  = CVPixelBufferGetWidth(pixelBuffer)
        let height = CVPixelBufferGetHeight(pixelBuffer)
        guard let base = CVPixelBufferGetBaseAddress(pixelBuffer) else { return [] }
        let bytesPerRow = CVPixelBufferGetBytesPerRow(pixelBuffer)
        let buf = base.assumingMemoryBound(to: UInt8.self)

        var mask = [Bool](repeating: false, count: width * height)
        for y in 0..<height {
            for x in 0..<width {
                let off = y * bytesPerRow + x * 4
                let b = Float(buf[off]), g = Float(buf[off+1]), r = Float(buf[off+2])
                // YCrCb-like skin heuristic
                mask[y * width + x] = r > 95 && g > 40 && b > 20 && r > g && r > b && (r - g) > 15
            }
        }

        return extractBoxes(mask: mask, width: width, height: height)
            .filter { $0.width * $0.height > 2000 }
            .sorted { $0.minX < $1.minX }
            .prefix(maxFingers)
            .enumerated()
            .map { FingerROI(index: $0.offset, rect: $0.element, area: $0.element.width * $0.element.height) }
    }

    private static func extractBoxes(mask: [Bool], width: Int, height: Int) -> [CGRect] {
        var visited = [Bool](repeating: false, count: mask.count)
        var boxes: [CGRect] = []
        for start in 0..<mask.count where mask[start] && !visited[start] {
            var minX = width, maxX = 0, minY = height, maxY = 0
            var stack = [start]
            while !stack.isEmpty {
                let idx = stack.removeLast()
                guard idx >= 0, idx < mask.count, mask[idx], !visited[idx] else { continue }
                visited[idx] = true
                let x = idx % width, y = idx / width
                minX = min(minX, x); maxX = max(maxX, x)
                minY = min(minY, y); maxY = max(maxY, y)
                for n in [idx-1, idx+1, idx-width, idx+width] { stack.append(n) }
            }
            if maxX > minX && maxY > minY {
                boxes.append(CGRect(x: minX, y: minY, width: maxX-minX, height: maxY-minY))
            }
        }
        return boxes
    }
}
