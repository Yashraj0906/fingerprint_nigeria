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

    private var frameHistory: [[UInt8]] = []
    private var frameSize: (Int, Int) = (0, 0)

    private let maxFrames          = 5
    private let minFramesRequired  = 3
    private let lbpVarianceMin     = 600.0
    private let specularRatioMax   = 0.12
    private let minMotion          = 0.08
    private let maxMotion          = 8.0
    private let freqEnergyMin      = 0.05

    func evaluate(_ image: CGImage) -> LivenessResult {
        guard let (pixels, w, h) = grayPixels(image) else {
            return LivenessResult(passed: true, reason: nil)
        }

        if frameHistory.count >= maxFrames { frameHistory.removeFirst() }
        frameHistory.append(pixels)
        frameSize = (w, h)

        guard frameHistory.count >= minFramesRequired else {
            return LivenessResult(passed: true, reason: nil)
        }

        // Layer 1: Texture variance
        let lbpVar = lbpVariance(pixels)
        if lbpVar < lbpVarianceMin {
            return LivenessResult(passed: false, reason: "Printed or flat image detected (variance: \(Int(lbpVar)))")
        }

        // Layer 2: Specular reflection
        let specRatio = specularRatio(pixels)
        if specRatio > specularRatioMax {
            return LivenessResult(passed: false, reason: "Screen replay or glare detected")
        }

        // Layer 3: Micro-movement
        let motion = averageMotion()
        if motion < minMotion {
            return LivenessResult(passed: false, reason: "No micro-movement — possible spoof")
        }
        if motion > maxMotion {
            return LivenessResult(passed: false, reason: "Excessive movement — hold steady")
        }

        // Layer 4: Frequency energy
        let freqEnergy = highFrequencyEnergy(pixels, width: w, height: h)
        if freqEnergy < freqEnergyMin {
            return LivenessResult(passed: false, reason: "Low ridge frequency — possible printed image")
        }

        return LivenessResult(passed: true, reason: nil)
    }

    func reset() {
        frameHistory.removeAll()
        frameSize = (0, 0)
    }

    // MARK: - Layer 1: LBP Texture Variance

    private func lbpVariance(_ pixels: [UInt8]) -> Double {
        let values = pixels.map { Double($0) }
        let mean = values.reduce(0, +) / Double(values.count)
        // Approximate Laplacian variance
        var variance = 0.0
        for i in 1..<(pixels.count - 1) {
            let lap = Double(pixels[i-1]) - 2.0 * Double(pixels[i]) + Double(pixels[i+1])
            variance += lap * lap
        }
        return variance / Double(pixels.count)
    }

    // MARK: - Layer 2: Specular Reflection

    private func specularRatio(_ pixels: [UInt8]) -> Double {
        let bright = pixels.filter { $0 > 240 }.count
        return Double(bright) / Double(pixels.count)
    }

    // MARK: - Layer 3: Micro-Movement

    private func averageMotion() -> Double {
        guard frameHistory.count >= 2 else { return 1.0 }
        var total = 0.0
        for i in 1..<frameHistory.count {
            let a = frameHistory[i-1], b = frameHistory[i]
            guard a.count == b.count else { continue }
            var sum = 0.0
            for j in 0..<a.count { sum += abs(Double(a[j]) - Double(b[j])) }
            total += sum / Double(a.count) / 255.0
        }
        return total / Double(frameHistory.count - 1)
    }

    // MARK: - Layer 4: High-Frequency Energy via vDSP FFT

    private func highFrequencyEnergy(_ pixels: [UInt8], width: Int, height: Int) -> Double {
        let n = pixels.count
        // Next power of 2 for FFT
        let log2n = vDSP_Length(log2(Double(n)).rounded(.up))
        let fftSize = Int(1 << log2n)

        var real = [Float](repeating: 0, count: fftSize)
        var imag = [Float](repeating: 0, count: fftSize)
        for i in 0..<min(n, fftSize) { real[i] = Float(pixels[i]) / 255.0 }

        guard let fftSetup = vDSP_create_fftsetup(log2n, FFTRadix(kFFTRadix2)) else { return 0.5 }
        defer { vDSP_destroy_fftsetup(fftSetup) }

        real.withUnsafeMutableBufferPointer { rPtr in
            imag.withUnsafeMutableBufferPointer { iPtr in
                var split = DSPSplitComplex(realp: rPtr.baseAddress!, imagp: iPtr.baseAddress!)
                vDSP_fft_zip(fftSetup, &split, 1, log2n, FFTDirection(kFFTDirection_Forward))
            }
        }

        // Compute magnitude spectrum
        var magnitudes = [Float](repeating: 0, count: fftSize / 2)
        real.withUnsafeMutableBufferPointer { rPtr in
            imag.withUnsafeMutableBufferPointer { iPtr in
                var split = DSPSplitComplex(realp: rPtr.baseAddress!, imagp: iPtr.baseAddress!)
                vDSP_zvmags(&split, 1, &magnitudes, 1, vDSP_Length(fftSize / 2))
            }
        }

        let totalEnergy = Double(magnitudes.reduce(0, +))
        guard totalEnergy > 0 else { return 0.5 }

        // Low-frequency region: first 30% of spectrum
        let lowFreqCount = Int(Double(magnitudes.count) * 0.30)
        let lowEnergy = Double(magnitudes.prefix(lowFreqCount).reduce(0, +))

        return 1.0 - (lowEnergy / totalEnergy)
    }

    // MARK: - Helpers

    private func grayPixels(_ image: CGImage) -> ([UInt8], Int, Int)? {
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
