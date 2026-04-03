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

    init {
        System.loadLibrary("fingerprint_core")
    }

    private external fun nativeEncode(imageAddr: Long): String?

    /**
     * Returns null if minutiae count < MIN_MINUTIAE (caller should mark LOW_QUALITY).
     */
    fun encode(image: Mat, fingerPosition: Int = 0, qualityScore: Double = 80.0): String? {
        return nativeEncode(image.nativeObjAddr)
    }
}
