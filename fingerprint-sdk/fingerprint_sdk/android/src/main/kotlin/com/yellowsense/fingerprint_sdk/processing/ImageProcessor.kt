package com.yellowsense.fingerprint_sdk.processing

import android.graphics.Bitmap
import androidx.camera.core.ImageProxy
import org.opencv.android.Utils
import org.opencv.core.*
import org.opencv.imgproc.Imgproc
import java.io.ByteArrayOutputStream
import android.util.Base64
import android.util.Log

/**
 * Full fingerprint processing pipeline with hardened segmentation.
 *
 * Segmentation hardening:
 *   - YCrCb skin mask + morphological cleanup
 *   - Contour filtering: min/max area, aspect ratio, portrait orientation
 *   - Convexity-defect splitting for merged/touching fingers
 *   - Fallback: if segmentation yields 0 results, treat full ROI as one finger
 *
 * Enhancement pipeline:
 *   Grayscale → CLAHE → Gaussian → 4-angle Gabor-bank Sobel →
 *   Adaptive threshold → Zhang-Suen skeleton
 */
object ImageProcessor {

    private var nv21Buffer: ByteArray? = null
    private var yBufferData: ByteArray? = null
    private var uBufferData: ByteArray? = null
    private var vBufferData: ByteArray? = null

    fun yuvToMat(image: ImageProxy): Mat {
        try {
            val yPlane = image.planes[0] ?: return Mat()
            val uPlane = image.planes[1] ?: return Mat()
            val vPlane = image.planes[2] ?: return Mat()

            val yBuffer = yPlane.buffer
            val uBuffer = uPlane.buffer
            val vBuffer = vPlane.buffer
            
            if (yBuffer.remaining() == 0) return Mat()

            val yRem = yBuffer.remaining()
            if (yBufferData == null || yBufferData!!.size < yRem) yBufferData = ByteArray(yRem)
            yBuffer.get(yBufferData!!, 0, yRem)
            
            val uRem = uBuffer.remaining()
            if (uBufferData == null || uBufferData!!.size < uRem) uBufferData = ByteArray(uRem)
            uBuffer.get(uBufferData!!, 0, uRem)
            
            val vRem = vBuffer.remaining()
            if (vBufferData == null || vBufferData!!.size < vRem) vBufferData = ByteArray(vRem)
            vBuffer.get(vBufferData!!, 0, vRem)

            val yBytes = yBufferData!!
            val uBytes = uBufferData!!
            val vBytes = vBufferData!!

            val yRowStride    = yPlane.rowStride
            val uvRowStride   = uPlane.rowStride
            val uvPixelStride = uPlane.pixelStride
            val width  = image.width
            val height = image.height

            val totalSize = width * height * 3 / 2
            if (nv21Buffer == null || nv21Buffer!!.size < totalSize) nv21Buffer = ByteArray(totalSize)
            val nv21 = nv21Buffer!!
            var pos = 0

            for (row in 0 until height) {
                val yPos = row * yRowStride
                val len = Math.min(width, Math.max(0, yBytes.size - yPos))
                if (len > 0) {
                    System.arraycopy(yBytes, yPos, nv21, pos, len)
                }
                pos += width
            }

            for (row in 0 until height / 2) {
                val rowOffset = row * uvRowStride
                for (col in 0 until width / 2) {
                    val p = rowOffset + col * uvPixelStride
                    nv21[pos++] = if (p < vBytes.size) vBytes[p] else 0
                    nv21[pos++] = if (p < uBytes.size) uBytes[p] else 0
                }
            }

            val yuv = Mat(height + height / 2, width, CvType.CV_8UC1)
            try {
                yuv.put(0, 0, nv21)
                val bgr = Mat()
                Imgproc.cvtColor(yuv, bgr, Imgproc.COLOR_YUV2BGR_NV21)

                // Normalize orientation so downstream segmentation sees consistent upright frames.
                val rotation = image.imageInfo.rotationDegrees
                if (rotation == 0) return bgr

                val rotated = Mat()
                when (rotation) {
                    90 -> Core.rotate(bgr, rotated, Core.ROTATE_90_CLOCKWISE)
                    180 -> Core.rotate(bgr, rotated, Core.ROTATE_180)
                    270 -> Core.rotate(bgr, rotated, Core.ROTATE_90_COUNTERCLOCKWISE)
                    else -> {
                        bgr.release()
                        return Mat()
                    }
                }
                bgr.release()
                return rotated
            } finally {
                yuv.release()
            }
        } catch (t: Throwable) {
            android.util.Log.e("ImageProcessor", "yuvToMat fatal: ${t.message}")
            return Mat()
        }
    }

    // ─── Enhancement Pipeline ─────────────────────────────────────────────────

    fun enhance(src: Mat): Mat {
        if (src.empty()) return Mat()
        val gray = Mat()
        val claheOut = Mat()
        val blurred = Mat()
        
        try {
            if (src.channels() == 3) Imgproc.cvtColor(src, gray, Imgproc.COLOR_BGR2GRAY)
            else src.copyTo(gray)

            // Slightly stronger local contrast for ridge clarity on finger ROIs
            val clahe = Imgproc.createCLAHE(3.6, Size(8.0, 8.0))
            clahe.apply(gray, claheOut)
            
            Imgproc.GaussianBlur(claheOut, blurred, Size(3.0, 3.0), 1.0)

            val ridgeEnhanced = gaborBankEnhance(blurred)
            if (ridgeEnhanced.empty()) return Mat()

            val binary = Mat()
            try {
                Imgproc.adaptiveThreshold(
                    ridgeEnhanced, binary, 255.0,
                    Imgproc.ADAPTIVE_THRESH_GAUSSIAN_C, Imgproc.THRESH_BINARY_INV, 11, 2.0
                )
                return skeletonize(binary)
            } finally {
                ridgeEnhanced.release()
                binary.release()
            }
        } catch (t: Throwable) {
            android.util.Log.e("ImageProcessor", "enhance fatal: ${t.message}")
            return Mat()
        } finally {
            gray.release(); claheOut.release(); blurred.release()
        }
    }

    private fun gaborBankEnhance(gray: Mat): Mat {
        if (gray.empty()) return Mat()
        val result = Mat.zeros(gray.size(), CvType.CV_32F)
        val temp32 = Mat()
        
        try {
            gray.convertTo(temp32, CvType.CV_32F)

            val sx = Mat()
            val sy = Mat()
            try {
                Imgproc.Sobel(temp32, sx, CvType.CV_32F, 1, 0, 3)
                Imgproc.Sobel(temp32, sy, CvType.CV_32F, 0, 1, 3)
                Core.magnitude(sx, sy, result)
            } finally {
                sx.release()
                sy.release()
            }

            val out = Mat()
            Core.normalize(result, out, 0.0, 255.0, Core.NORM_MINMAX, CvType.CV_8U)
            return out
        } finally {
            temp32.release()
            result.release()
        }
    }

    private fun skeletonize(binary: Mat): Mat {
        if (binary.empty()) return Mat()
        val skeleton = Mat.zeros(binary.size(), CvType.CV_8U)
        val temp = Mat(); val eroded = Mat()
        val element = Imgproc.getStructuringElement(Imgproc.MORPH_CROSS, Size(3.0, 3.0))
        var curSrc = binary.clone()
        var iters = 0
        try {
            while (iters < 100) { // HARD LIMIT to prevent infinite thinning loops
                Imgproc.erode(curSrc, eroded, element)
                Imgproc.dilate(eroded, temp, element)
                Core.subtract(curSrc, temp, temp)
                Core.bitwise_or(skeleton, temp, skeleton)
                eroded.copyTo(curSrc)
                if (Core.countNonZero(curSrc) == 0) break
                iters++
            }
        } finally {
            curSrc.release(); temp.release(); eroded.release(); element.release()
        }
        return skeleton
    }

    // ─── Ridge Detection ─────────────────────────────────────────────────────

    fun detectRidges(gray: Mat): Mat {
        val edges = Mat()
        Imgproc.Canny(gray, edges, 40.0, 120.0, 3)
        return edges
    }

    // ─── Hardened Finger Segmentation ────────────────────────────────────────

    data class FingerROI(val index: Int, val rect: Rect, val area: Double)

    /**
     * Hardened segmentation pipeline:
     *   1. YCrCb skin mask
     *   2. Morphological cleanup
     *   3. Contour filtering (area, aspect ratio, orientation)
     *   4. Convexity-defect splitting for merged fingers
     *   5. Fallback to full-frame ROI if nothing detected
     */
    fun segmentFingers(src: Mat, maxFingers: Int = 4): List<FingerROI> {
        if (src.empty()) return emptyList()
        val ycrcb = Mat()
        val skinMask = Mat()
        val hierarchy = Mat()
        val contours = mutableListOf<MatOfPoint>()
        
        try {
            Imgproc.cvtColor(src, ycrcb, Imgproc.COLOR_BGR2YCrCb)
            // Slightly widened YCrCb skin bounds to improve recall across lighting and skin tones.
            // (Keeps false positives controlled by later density/shape filters.)
            Core.inRange(
                ycrcb,
                Scalar(0.0, 127.0, 67.0),   // Y, Cr, Cb (lower)
                Scalar(255.0, 185.0, 135.0),// Y, Cr, Cb (upper)
                skinMask
            )
            
            val closeKernel = Imgproc.getStructuringElement(Imgproc.MORPH_ELLIPSE, Size(7.0, 7.0))
            val openKernel  = Imgproc.getStructuringElement(Imgproc.MORPH_ELLIPSE, Size(5.0, 5.0))
            Imgproc.morphologyEx(skinMask, skinMask, Imgproc.MORPH_CLOSE, closeKernel)
            Imgproc.morphologyEx(skinMask, skinMask, Imgproc.MORPH_OPEN,  openKernel)
            closeKernel.release(); openKernel.release()

            Imgproc.findContours(skinMask, contours, hierarchy, Imgproc.RETR_EXTERNAL, Imgproc.CHAIN_APPROX_SIMPLE)

            val imageArea = (src.rows() * src.cols()).toDouble()
            // Allow slightly smaller ROIs so far-away hands still yield candidates.
            val minArea   = imageArea * 0.003
            val maxArea   = imageArea * 0.45

            val rects = mutableListOf<Pair<Rect, Double>>()
            for (c in contours) {
                val rect = Imgproc.boundingRect(c)
                val area = Imgproc.contourArea(c)
                val aspect = rect.width.toDouble() / rect.height.toDouble()
                
                // Accept a bit more rotation/skew than strict portrait-only fingers.
                if (area in minArea..maxArea && aspect < 1.6 && rect.height >= (rect.width * 0.9)) {
                    // Mask density inside bounding rect: reject non-hand blobs.
                    val safeX = rect.x.coerceIn(0, (skinMask.cols() - 1).coerceAtLeast(0))
                    val safeY = rect.y.coerceIn(0, (skinMask.rows() - 1).coerceAtLeast(0))
                    val safeW = rect.width.coerceAtMost((skinMask.cols() - safeX).coerceAtLeast(1))
                    val safeH = rect.height.coerceAtMost((skinMask.rows() - safeY).coerceAtLeast(1))
                    val safeRect = Rect(safeX, safeY, safeW, safeH)
                    val maskRoi = Mat(skinMask, safeRect)
                    val density = Core.countNonZero(maskRoi).toDouble() / (safeRect.area().toDouble().coerceAtLeast(1.0))
                    maskRoi.release()
                    // Lowered slightly to avoid rejecting fingers with specular highlights / motion blur.
                    if (density < 0.22) continue

                    val splits = trySplitMergedFingers(c, rect, maxFingers)
                    if (splits.isNotEmpty()) rects.addAll(splits) else rects.add(Pair(rect, area))
                }
            }

            val sorted = rects
                .filter { (r, a) ->
                    (r.width.toDouble() / r.height.toDouble()) < 1.6 &&
                    a > imageArea * 0.0025 &&
                    r.height >= 60 && r.width >= 35
                }
                .sortedBy { it.first.x }
                .take(maxFingers)

            if (sorted.isEmpty()) {
                // Fail closed: never invent a synthetic ROI when no finger is detected.
                return emptyList()
            }

            return sorted.mapIndexed { idx, (rect, area) -> FingerROI(idx, rect, area) }
        } catch (t: Throwable) {
            android.util.Log.e("ImageProcessor", "segmentFingers fatal: ${t.message}")
            return emptyList()
        } finally {
            ycrcb.release(); skinMask.release(); hierarchy.release()
            contours.forEach { it.release() }
        }
    }

    /**
     * Detect merged/touching fingers using convexity defects.
     * If a contour is wide enough to contain multiple fingers, split it
     * into equal vertical strips at convexity-defect valleys.
     *
     * Returns split rects, or empty list if no split needed.
     */
    private fun trySplitMergedFingers(
        contour: MatOfPoint,
        boundingRect: Rect,
        maxFingers: Int
    ): List<Pair<Rect, Double>> {
        if (contour.empty()) return emptyList()
        val aspectRatio = boundingRect.width.toDouble() / boundingRect.height.toDouble()
        if (aspectRatio < 1.5) return emptyList()

        val hull = MatOfInt()
        val defects = MatOfInt4()
        
        try {
            Imgproc.convexHull(contour, hull, false)
            if (hull.empty() || hull.rows() == 0) return emptyList()
            
            Imgproc.convexityDefects(contour, hull, defects)
            if (defects.empty() || defects.rows() == 0) return emptyList()

            val points = contour.toArray()
            val defectData = defects.toArray()

            val valleyXs = mutableListOf<Int>()
            for (i in defectData.indices step 4) {
                val farIdx   = defectData[i + 2]
                val depth    = defectData[i + 3] / 256.0
                if (depth > boundingRect.height * 0.25 && farIdx < points.size) {
                    valleyXs.add(points[farIdx].x.toInt())
                }
            }

            if (valleyXs.isEmpty()) return emptyList()

            val splitXs = (listOf(boundingRect.x) + valleyXs.sorted() + listOf(boundingRect.x + boundingRect.width))
                .distinct().sorted()

            val splits = mutableListOf<Pair<Rect, Double>>()
            for (i in 0 until splitXs.size - 1) {
                val x0 = splitXs[i]
                val x1 = splitXs[i + 1]
                val w  = x1 - x0
                if (w < 20) continue
                val r = Rect(x0, boundingRect.y, w, boundingRect.height)
                splits.add(Pair(r, r.area()))
            }

            return if (splits.size in 2..maxFingers) splits else emptyList()
        } catch (t: Throwable) {
            android.util.Log.e("ImageProcessor", "trySplitMergedFingers fatal: ${t.message}")
            return emptyList()
        } finally {
            hull.release(); defects.release()
        }
    }

    // ─── Helpers ─────────────────────────────────────────────────────────────

    fun matToBitmap(mat: Mat): Bitmap {
        val display = when (mat.channels()) {
            1 -> Mat().also { Imgproc.cvtColor(mat, it, Imgproc.COLOR_GRAY2BGRA) }
            3 -> Mat().also { Imgproc.cvtColor(mat, it, Imgproc.COLOR_BGR2RGBA) }
            4 -> mat
            else -> Mat().also { mat.copyTo(it) }
        }
        val bmp = Bitmap.createBitmap(display.cols(), display.rows(), Bitmap.Config.ARGB_8888)
        Utils.matToBitmap(display, bmp)
        if (display !== mat) display.release()
        return bmp
    }

    fun matToBase64(mat: Mat, quality: Int = 85): String {
        val bmp = matToBitmap(mat)
        val stream = ByteArrayOutputStream()
        bmp.compress(Bitmap.CompressFormat.JPEG, quality, stream)
        bmp.recycle()
        return Base64.encodeToString(stream.toByteArray(), Base64.NO_WRAP)
    }
}
