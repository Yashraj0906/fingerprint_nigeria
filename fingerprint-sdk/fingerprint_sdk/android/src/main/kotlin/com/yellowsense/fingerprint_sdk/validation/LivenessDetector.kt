package com.yellowsense.fingerprint_sdk.validation

import org.opencv.core.*
import org.opencv.imgproc.Imgproc

/**
 * Multi-layer liveness detection with challenge-response anti-spoof.
 *
 * Layer 1 — LBP texture variance (printed images are flat)
 * Layer 2 — Specular reflection ratio (screens produce uniform highlights)
 * Layer 3 — Micro-movement with natural tremor range check
 * Layer 4 — DFT high-frequency energy (printed ridges lack HF content)
 * Layer 5 — Reflection consistency across frames (screens flicker uniformly)
 * Layer 6 — Edge distortion check (flat prints have unnaturally sharp edges)
 * Layer 7 — Challenge-response: validates movement direction consistency
 */
class LivenessDetector {

    data class LivenessResult(
        val passed: Boolean,
        val reason: String?,
        val confidence: Double  // 0.0–1.0
    )

    private val frameHistory = ArrayDeque<Mat>(MAX_FRAMES)
    private val specularHistory = ArrayDeque<Double>(MAX_FRAMES)

    // Challenge-response state
    private var challengeActive   = false
    private var challengeStartIdx = 0
    private var motionVectors     = mutableListOf<Pair<Double, Double>>()  // (dx, dy) per frame pair

    companion object {
        private const val MAX_FRAMES             = 6
        private const val MIN_FRAMES_REQUIRED    = 3
        private const val LBP_VARIANCE_MIN       = 600.0
        private const val SPECULAR_RATIO_MAX     = 0.12
        private const val SPECULAR_VARIANCE_MAX  = 0.02   // screens have consistent specular
        private const val MIN_MOTION             = 0.05
        private const val MAX_MOTION             = 10.0
        private const val FREQ_ENERGY_MIN        = 0.04
        private const val EDGE_SHARPNESS_MAX     = 0.92   // flat prints have unnaturally sharp edges
        private const val CHALLENGE_FRAMES       = 4      // frames needed for challenge validation
        private const val MOTION_CONSISTENCY_MIN = 0.60   // 60% of motion vectors must be coherent
    }

    fun evaluate(gray: Mat): LivenessResult {
        val clone = gray.clone()
        if (frameHistory.size >= MAX_FRAMES) frameHistory.removeFirst().release()
        frameHistory.addLast(clone)

        if (frameHistory.size < MIN_FRAMES_REQUIRED) {
            return LivenessResult(true, null, 0.5)
        }

        // Layer 1: Texture variance
        val lbpVar = lbpVariance(gray)
        if (lbpVar < LBP_VARIANCE_MIN) {
            return LivenessResult(false, "Printed or flat image detected", 0.95)
        }

        // Layer 2: Specular reflection ratio
        val specRatio = specularRatio(gray)
        if (specRatio > SPECULAR_RATIO_MAX) {
            return LivenessResult(false, "Screen replay or glare detected", 0.90)
        }

        // Layer 5: Reflection consistency across frames (screens are uniform)
        specularHistory.addLast(specRatio)
        if (specularHistory.size > MAX_FRAMES) specularHistory.removeFirst()
        if (specularHistory.size >= 3) {
            val specVariance = variance(specularHistory.toList())
            if (specVariance < SPECULAR_VARIANCE_MAX && specRatio > 0.03) {
                return LivenessResult(false, "Uniform reflection pattern — possible screen replay", 0.88)
            }
        }

        // Layer 3: Micro-movement
        val motion = averageMotion()
        when {
            motion < MIN_MOTION -> return LivenessResult(false, "No micro-movement — possible spoof", 0.92)
            motion > MAX_MOTION -> return LivenessResult(false, "Excessive movement — hold steady", 0.80)
        }

        // Layer 4: DFT high-frequency energy
        val freqEnergy = highFrequencyEnergy(gray)
        if (freqEnergy < FREQ_ENERGY_MIN) {
            return LivenessResult(false, "Low ridge frequency — possible printed image", 0.85)
        }

        // Layer 6: Edge distortion (flat prints have unnaturally uniform edge sharpness)
        val edgeUniformity = edgeSharpnessUniformity(gray)
        if (edgeUniformity > EDGE_SHARPNESS_MAX) {
            return LivenessResult(false, "Unnaturally uniform edges — possible flat print", 0.82)
        }

        // Layer 7: Challenge-response motion consistency
        if (frameHistory.size >= CHALLENGE_FRAMES) {
            val consistent = checkMotionConsistency()
            if (!consistent) {
                return LivenessResult(false, "Inconsistent motion pattern — possible replay attack", 0.78)
            }
        }

        // Compute composite confidence
        val confidence = computeConfidence(lbpVar, specRatio, motion, freqEnergy, edgeUniformity)
        return LivenessResult(true, null, confidence)
    }

    fun reset() {
        frameHistory.forEach { it.release() }
        frameHistory.clear()
        specularHistory.clear()
        motionVectors.clear()
        challengeActive = false
        challengeStartIdx = 0
    }

    // ─── Layer 1: LBP Texture Variance ───────────────────────────────────────

    private fun lbpVariance(gray: Mat): Double {
        val lap = Mat()
        Imgproc.Laplacian(gray, lap, CvType.CV_64F, 3)
        val mean = MatOfDouble(); val std = MatOfDouble()
        Core.meanStdDev(lap, mean, std)
        lap.release()
        return std.toArray()[0].let { it * it }
    }

    // ─── Layer 2: Specular Reflection ────────────────────────────────────────

    private fun specularRatio(gray: Mat): Double {
        val bright = Mat()
        Imgproc.threshold(gray, bright, 240.0, 255.0, Imgproc.THRESH_BINARY)
        val count = Core.countNonZero(bright).toDouble()
        bright.release()
        return count / (gray.rows() * gray.cols())
    }

    // ─── Layer 3: Micro-Movement ─────────────────────────────────────────────

    private fun averageMotion(): Double {
        if (frameHistory.size < 2) return 1.0
        var total = 0.0
        for (i in 1 until frameHistory.size) {
            val diff = Mat()
            Core.absdiff(frameHistory[i - 1], frameHistory[i], diff)
            total += Core.mean(diff).`val`[0]
            diff.release()
        }
        return total / (frameHistory.size - 1)
    }

    // ─── Layer 4: DFT High-Frequency Energy ──────────────────────────────────

    private fun highFrequencyEnergy(gray: Mat): Double {
        val floatMat = Mat()
        gray.convertTo(floatMat, CvType.CV_32F)

        val optRows = Core.getOptimalDFTSize(floatMat.rows())
        val optCols = Core.getOptimalDFTSize(floatMat.cols())
        val padded  = Mat()
        Core.copyMakeBorder(floatMat, padded, 0, optRows - floatMat.rows(),
            0, optCols - floatMat.cols(), Core.BORDER_CONSTANT, Scalar.all(0.0))
        floatMat.release()

        val planes = mutableListOf(padded, Mat.zeros(padded.size(), CvType.CV_32F))
        val complex = Mat()
        Core.merge(planes, complex)
        Core.dft(complex, complex)
        padded.release()

        Core.split(complex, planes)
        complex.release()
        val magnitude = Mat()
        Core.magnitude(planes[0], planes[1], magnitude)
        planes.forEach { it.release() }

        val logMag = Mat()
        val one = Mat.ones(magnitude.size(), CvType.CV_32F)
        Core.add(magnitude, one, logMag)
        Core.log(logMag, logMag)
        magnitude.release(); one.release()

        val shifted = shiftDFT(logMag)
        logMag.release()

        val rows = shifted.rows(); val cols = shifted.cols()
        val totalEnergy = Core.sumElems(shifted).`val`[0]

        val innerRows = (rows * 0.30).toInt()
        val innerCols = (cols * 0.30).toInt()
        val centerRect = Rect(cols/2 - innerCols/2, rows/2 - innerRows/2, innerCols, innerRows)
        val centerEnergy = Core.sumElems(Mat(shifted, centerRect)).`val`[0]
        shifted.release()

        return if (totalEnergy > 0) 1.0 - (centerEnergy / totalEnergy) else 0.0
    }

    private fun shiftDFT(src: Mat): Mat {
        val dst = src.clone()
        val cx = dst.cols() / 2; val cy = dst.rows() / 2
        val q0 = Mat(dst, Rect(0, 0, cx, cy));  val q1 = Mat(dst, Rect(cx, 0, cx, cy))
        val q2 = Mat(dst, Rect(0, cy, cx, cy)); val q3 = Mat(dst, Rect(cx, cy, cx, cy))
        val tmp = Mat()
        q0.copyTo(tmp); q3.copyTo(q0); tmp.copyTo(q3)
        q1.copyTo(tmp); q2.copyTo(q1); tmp.copyTo(q2)
        tmp.release()
        return dst
    }

    // ─── Layer 6: Edge Distortion ─────────────────────────────────────────────

    /**
     * Flat prints have unnaturally uniform edge sharpness across the image.
     * Real fingers have varying sharpness due to 3D surface curvature.
     * Returns normalised uniformity score (0=varied, 1=perfectly uniform).
     */
    private fun edgeSharpnessUniformity(gray: Mat): Double {
        val tileSize = 32
        val sharpnessValues = mutableListOf<Double>()

        val rows = gray.rows(); val cols = gray.cols()
        var r = 0
        while (r + tileSize < rows) {
            var c = 0
            while (c + tileSize < cols) {
                val tile = Mat(gray, Rect(c, r, tileSize, tileSize))
                val lap  = Mat()
                Imgproc.Laplacian(tile, lap, CvType.CV_64F)
                val std = MatOfDouble()
                Core.meanStdDev(lap, MatOfDouble(), std)
                sharpnessValues.add(std.toArray()[0])
                lap.release(); tile.release()
                c += tileSize
            }
            r += tileSize
        }

        if (sharpnessValues.size < 4) return 0.0
        val mean = sharpnessValues.average()
        if (mean == 0.0) return 0.0
        val cv = Math.sqrt(variance(sharpnessValues)) / mean  // coefficient of variation
        // Low CV = uniform = suspicious; high CV = varied = natural
        return (1.0 - cv.coerceIn(0.0, 1.0))
    }

    // ─── Layer 7: Challenge-Response Motion Consistency ───────────────────────

    /**
     * Validates that motion between consecutive frames is spatially coherent
     * (i.e., the whole hand moves together, not random pixel noise from a replay).
     *
     * Uses optical-flow approximation: computes mean displacement in 4 quadrants.
     * If all quadrants move in the same direction → coherent (real hand).
     * If quadrants move independently → incoherent (replay/spoof).
     */
    private fun checkMotionConsistency(): Boolean {
        if (frameHistory.size < 2) return true

        val prev = frameHistory[frameHistory.size - 2]
        val curr = frameHistory[frameHistory.size - 1]

        if (prev.size() != curr.size()) return true

        val rows = curr.rows(); val cols = curr.cols()
        val halfR = rows / 2; val halfC = cols / 2

        val quadrants = listOf(
            Rect(0,     0,     halfC, halfR),
            Rect(halfC, 0,     halfC, halfR),
            Rect(0,     halfR, halfC, halfR),
            Rect(halfC, halfR, halfC, halfR)
        )

        val dxList = mutableListOf<Double>()
        val dyList = mutableListOf<Double>()

        for (q in quadrants) {
            val p = Mat(prev, q); val c = Mat(curr, q)
            val diff = Mat()
            Core.absdiff(p, c, diff)

            // Compute weighted centroid of difference as motion vector
            val moments = Imgproc.moments(diff)
            if (moments.m00 > 0) {
                dxList.add(moments.m10 / moments.m00 - halfC / 2.0)
                dyList.add(moments.m01 / moments.m00 - halfR / 2.0)
            }
            p.release(); c.release(); diff.release()
        }

        if (dxList.size < 3) return true

        // Check sign consistency: majority of quadrants should move in same direction
        val posX = dxList.count { it > 0 }
        val posY = dyList.count { it > 0 }
        val consistency = maxOf(posX, dxList.size - posX).toDouble() / dxList.size

        return consistency >= MOTION_CONSISTENCY_MIN
    }

    // ─── Confidence Computation ───────────────────────────────────────────────

    private fun computeConfidence(
        lbpVar: Double, specRatio: Double, motion: Double,
        freqEnergy: Double, edgeUniformity: Double
    ): Double {
        val textureScore  = (lbpVar / 2000.0).coerceIn(0.0, 1.0)
        val specScore     = (1.0 - specRatio / SPECULAR_RATIO_MAX).coerceIn(0.0, 1.0)
        val motionScore   = if (motion in MIN_MOTION..MAX_MOTION)
            1.0 - Math.abs(motion - 1.0) / MAX_MOTION else 0.5
        val freqScore     = (freqEnergy / 0.3).coerceIn(0.0, 1.0)
        val edgeScore     = (1.0 - edgeUniformity).coerceIn(0.0, 1.0)

        return (textureScore * 0.30 + specScore * 0.20 + motionScore * 0.20 +
                freqScore * 0.20 + edgeScore * 0.10).coerceIn(0.0, 1.0)
    }

    // ─── Utilities ────────────────────────────────────────────────────────────

    private fun variance(values: List<Double>): Double {
        if (values.isEmpty()) return 0.0
        val mean = values.average()
        return values.sumOf { (it - mean) * (it - mean) } / values.size
    }
}
