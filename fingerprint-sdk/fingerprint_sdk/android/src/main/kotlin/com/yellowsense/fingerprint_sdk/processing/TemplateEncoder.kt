package com.yellowsense.fingerprint_sdk.processing

import android.util.Base64
import org.opencv.core.*
import org.opencv.imgproc.Imgproc
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * ISO/IEC 19794-2:2005 Finger Minutiae Record encoder.
 *
 * Improvements over MVP:
 *   - MAX_MINUTIAE capped at 80 (optimal for matching, compact output)
 *   - MIN_MINUTIAE threshold: < 10 → returns null (LOW_QUALITY signal)
 *   - Wider border margin (15px) to remove edge artefacts
 *   - Cluster suppression radius increased to 12px
 *   - Angle normalisation: ridge angle computed over 5×5 neighbourhood
 *   - Quality score written per-minutia from local Laplacian variance
 */
object TemplateEncoder {

    data class Minutia(
        val x: Int,
        val y: Int,
        val angle: Int,    // 0–255 → 0–360°
        val type: Int,     // 1 = ending, 2 = bifurcation
        val quality: Int   // 0–100
    )

    private const val ENDING          = 1
    private const val BIFURCATION     = 2
    private const val BORDER_MARGIN   = 15   // wider border exclusion zone
    private const val CLUSTER_RADIUS  = 12.0 // suppress minutiae closer than this
    private const val MAX_MINUTIAE    = 80   // compact, sufficient for matching
    private const val MIN_MINUTIAE    = 10   // below this → LOW_QUALITY

    /**
     * Returns null if minutiae count < MIN_MINUTIAE (caller should mark LOW_QUALITY).
     */
    fun encode(skeleton: Mat, fingerPosition: Int = 0, qualityScore: Double = 80.0): String? {
        val minutiae = extractMinutiae(skeleton)
        val filtered = filterMinutiae(minutiae, skeleton.cols(), skeleton.rows())

        if (filtered.size < MIN_MINUTIAE) return null  // insufficient ridge detail

        return buildIsoTemplate(filtered, skeleton.cols(), skeleton.rows(),
                                fingerPosition, qualityScore.toInt().coerceIn(0, 100))
    }

    // ─── Minutiae Extraction ─────────────────────────────────────────────────

    private fun extractMinutiae(skeleton: Mat): List<Minutia> {
        val minutiae = mutableListOf<Minutia>()
        val rows = skeleton.rows()
        val cols = skeleton.cols()
        val data = ByteArray((skeleton.total() * skeleton.elemSize()).toInt())
        skeleton.get(0, 0, data)

        fun px(r: Int, c: Int): Int {
            if (r < 0 || r >= rows || c < 0 || c >= cols) return 0
            return if (data[r * cols + c].toInt() and 0xFF > 127) 1 else 0
        }

        for (r in BORDER_MARGIN until rows - BORDER_MARGIN) {
            for (c in BORDER_MARGIN until cols - BORDER_MARGIN) {
                if (px(r, c) == 0) continue

                // Clockwise 8-neighbours
                val n = intArrayOf(
                    px(r-1,c-1), px(r-1,c), px(r-1,c+1),
                    px(r,  c+1),
                    px(r+1,c+1), px(r+1,c), px(r+1,c-1),
                    px(r,  c-1)
                )
                var cn = 0
                for (i in n.indices) cn += Math.abs(n[i] - n[(i+1) % 8])
                cn /= 2

                val type = when (cn) {
                    1 -> ENDING
                    3 -> BIFURCATION
                    else -> continue
                }

                val angle   = estimateRidgeAngle(data, r, c, rows, cols)
                val quality = estimateLocalQuality(data, r, c, rows, cols)
                minutiae.add(Minutia(c, r, angle, type, quality))
            }
        }
        return minutiae
    }

    /**
     * Ridge angle via 5×5 gradient neighbourhood for better accuracy.
     * Returns ISO 19794-2 angle units (0–255 = 0–360°).
     */
    private fun estimateRidgeAngle(data: ByteArray, r: Int, c: Int, rows: Int, cols: Int): Int {
        fun px(dr: Int, dc: Int): Double {
            val nr = (r + dr).coerceIn(0, rows - 1)
            val nc = (c + dc).coerceIn(0, cols - 1)
            return (data[nr * cols + nc].toInt() and 0xFF).toDouble()
        }
        // Sobel-like 5×5 gradient
        val gx = (-px(-2,-2) - 2*px(-1,-2) - px(0,-2) + px(0,2) + 2*px(1,2) + px(2,2)) +
                 (-px(-2,-1) - 2*px(-1,-1)             + px(0,1) + 2*px(1,1) + px(2,1))
        val gy = (-px(-2,-2) - 2*px(-2,-1) - px(-2,0) + px(2,0) + 2*px(2,1) + px(2,2)) +
                 (-px(-1,-2) - 2*px(-1,-1)             + px(1,0) + 2*px(1,1) + px(1,2))

        val angleDeg = Math.toDegrees(Math.atan2(gy, gx))
        return (((angleDeg + 360.0) % 360.0) / 360.0 * 255.0).toInt().coerceIn(0, 255)
    }

    /** Local Laplacian variance as per-minutia quality estimate (0–100). */
    private fun estimateLocalQuality(data: ByteArray, r: Int, c: Int, rows: Int, cols: Int): Int {
        fun px(dr: Int, dc: Int): Double {
            val nr = (r + dr).coerceIn(0, rows - 1)
            val nc = (c + dc).coerceIn(0, cols - 1)
            return (data[nr * cols + nc].toInt() and 0xFF).toDouble()
        }
        val lap = px(-1,0) + px(1,0) + px(0,-1) + px(0,1) - 4 * px(0,0)
        return (Math.abs(lap) / 4.0 * 100.0).toInt().coerceIn(0, 100)
    }

    // ─── Minutiae Filtering ───────────────────────────────────────────────────

    private fun filterMinutiae(raw: List<Minutia>, width: Int, height: Int): List<Minutia> {
        // Sort by quality descending so we keep the best minutiae when clustering
        val sorted = raw.sortedByDescending { it.quality }
        val accepted = mutableListOf<Minutia>()

        for (m in sorted) {
            if (m.x < BORDER_MARGIN || m.x > width  - BORDER_MARGIN) continue
            if (m.y < BORDER_MARGIN || m.y > height - BORDER_MARGIN) continue

            val tooClose = accepted.any { e ->
                val dx = (m.x - e.x).toDouble()
                val dy = (m.y - e.y).toDouble()
                Math.sqrt(dx * dx + dy * dy) < CLUSTER_RADIUS
            }
            if (!tooClose) accepted.add(m)
            if (accepted.size >= MAX_MINUTIAE) break
        }
        return accepted
    }

    // ─── ISO 19794-2 Binary Encoding ─────────────────────────────────────────

    private fun buildIsoTemplate(
        minutiae: List<Minutia>,
        width: Int, height: Int,
        fingerPosition: Int,
        fingerQuality: Int
    ): String {
        val count       = minutiae.size.coerceAtMost(MAX_MINUTIAE)
        val recordLength = 28 + count * 6 + 2

        val buf = ByteBuffer.allocate(recordLength).order(ByteOrder.BIG_ENDIAN)

        buf.put("FMR\u0000".toByteArray(Charsets.US_ASCII))
        buf.put(" 20\u0000".toByteArray(Charsets.US_ASCII))
        buf.putInt(recordLength)
        buf.putShort(0)                        // CBEFF product ID
        buf.putShort(0)                        // capture equipment
        buf.putShort(width.toShort())
        buf.putShort(height.toShort())
        buf.putShort(197)                      // X resolution (≈500 dpi)
        buf.putShort(197)                      // Y resolution
        buf.put(1)                             // number of views
        buf.put(0)                             // reserved
        buf.put(fingerPosition.toByte())
        buf.put(0x00)                          // view 0, live-scan plain
        buf.put(fingerQuality.toByte())
        buf.put(count.toByte())

        for (m in minutiae.take(count)) {
            val typeAndXHigh = ((m.type and 0x03) shl 6) or ((m.x shr 8) and 0x3F)
            buf.put(typeAndXHigh.toByte())
            buf.put((m.x and 0xFF).toByte())
            buf.put(((m.y shr 8) and 0x3F).toByte())
            buf.put((m.y and 0xFF).toByte())
            buf.put(m.angle.toByte())
            buf.put(m.quality.toByte())
        }
        buf.putShort(0)  // no extended data

        return Base64.encodeToString(buf.array(), Base64.NO_WRAP)
    }
}
