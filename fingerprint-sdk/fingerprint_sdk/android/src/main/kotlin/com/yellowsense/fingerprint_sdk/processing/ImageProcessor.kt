package com.yellowsense.fingerprint_sdk.processing

import android.graphics.Bitmap
import androidx.camera.core.ImageProxy
import org.opencv.android.Utils
import org.opencv.core.*
import org.opencv.imgproc.Imgproc
import java.io.ByteArrayOutputStream
import android.util.Base64

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
        val yPlane = image.planes[0]
        val uPlane = image.planes[1]
        val vPlane = image.planes[2]

        val yBuffer = yPlane.buffer
        val uBuffer = uPlane.buffer
        val vBuffer = vPlane.buffer

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
        yuv.put(0, 0, nv21)
        val bgr = Mat()
        Imgproc.cvtColor(yuv, bgr, Imgproc.COLOR_YUV2BGR_NV21)
        yuv.release()
        return bgr
    }

    // ─── Enhancement Pipeline ─────────────────────────────────────────────────

    fun enhance(src: Mat): Mat {
        val gray = Mat()
        if (src.channels() == 3) Imgproc.cvtColor(src, gray, Imgproc.COLOR_BGR2GRAY)
        else src.copyTo(gray)

        val clahe = Imgproc.createCLAHE(3.0, Size(8.0, 8.0))
        val claheOut = Mat()
        clahe.apply(gray, claheOut)
        gray.release()

        val blurred = Mat()
        Imgproc.GaussianBlur(claheOut, blurred, Size(3.0, 3.0), 1.0)
        claheOut.release()

        val ridgeEnhanced = gaborBankEnhance(blurred)
        blurred.release()

        val binary = Mat()
        Imgproc.adaptiveThreshold(
            ridgeEnhanced, binary, 255.0,
            Imgproc.ADAPTIVE_THRESH_GAUSSIAN_C, Imgproc.THRESH_BINARY_INV, 11, 2.0
        )
        ridgeEnhanced.release()

        val skeleton = skeletonize(binary)
        binary.release()
        return skeleton
    }

    private fun gaborBankEnhance(gray: Mat): Mat {
        val result = Mat.zeros(gray.size(), CvType.CV_32F)
        val temp32 = Mat()
        gray.convertTo(temp32, CvType.CV_32F)

        for ((dx, dy) in listOf(Pair(1,0), Pair(1,1), Pair(0,1), Pair(-1,1))) {
            val sx = Mat(); val sy = Mat(); val mag = Mat()
            Imgproc.Sobel(temp32, sx, CvType.CV_32F, dx.coerceIn(0,1), 0, 3)
            Imgproc.Sobel(temp32, sy, CvType.CV_32F, 0, dy.coerceIn(0,1), 3)
            Core.magnitude(sx, sy, mag)
            Core.max(result, mag, result)
            sx.release(); sy.release(); mag.release()
        }
        temp32.release()

        val out = Mat()
        Core.normalize(result, out, 0.0, 255.0, Core.NORM_MINMAX, CvType.CV_8U)
        result.release()
        return out
    }

    private fun skeletonize(binary: Mat): Mat {
        val skeleton = Mat.zeros(binary.size(), CvType.CV_8U)
        val temp = Mat(); val eroded = Mat()
        val element = Imgproc.getStructuringElement(Imgproc.MORPH_CROSS, Size(3.0, 3.0))
        var src = binary.clone()
        while (true) {
            Imgproc.erode(src, eroded, element)
            Imgproc.dilate(eroded, temp, element)
            Core.subtract(src, temp, temp)
            Core.bitwise_or(skeleton, temp, skeleton)
            eroded.copyTo(src)
            if (Core.countNonZero(src) == 0) break
        }
        src.release(); temp.release(); eroded.release(); element.release()
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
        val ycrcb = Mat()
        Imgproc.cvtColor(src, ycrcb, Imgproc.COLOR_BGR2YCrCb)
        val skinMask = Mat()
        Core.inRange(ycrcb, Scalar(0.0, 133.0, 77.0), Scalar(255.0, 173.0, 127.0), skinMask)
        ycrcb.release()

        val closeKernel = Imgproc.getStructuringElement(Imgproc.MORPH_ELLIPSE, Size(7.0, 7.0))
        val openKernel  = Imgproc.getStructuringElement(Imgproc.MORPH_ELLIPSE, Size(5.0, 5.0))
        Imgproc.morphologyEx(skinMask, skinMask, Imgproc.MORPH_CLOSE, closeKernel)
        Imgproc.morphologyEx(skinMask, skinMask, Imgproc.MORPH_OPEN,  openKernel)
        closeKernel.release(); openKernel.release()

        val contours  = mutableListOf<MatOfPoint>()
        val hierarchy = Mat()
        Imgproc.findContours(skinMask, contours, hierarchy, Imgproc.RETR_EXTERNAL, Imgproc.CHAIN_APPROX_SIMPLE)
        skinMask.release(); hierarchy.release()

        val imageArea = (src.rows() * src.cols()).toDouble()
        val minArea   = imageArea * 0.005
        val maxArea   = imageArea * 0.45

        // Primary filter: area + aspect ratio + portrait orientation
        val validContours = contours.filter { c ->
            val rect   = Imgproc.boundingRect(c)
            val area   = Imgproc.contourArea(c)
            val aspect = rect.width.toDouble() / rect.height.toDouble()
            area in minArea..maxArea && aspect < 1.3 && rect.height >= rect.width
        }

        // Try to split merged fingers via convexity defects
        val rects = mutableListOf<Pair<Rect, Double>>()
        for (c in validContours) {
            val rect = Imgproc.boundingRect(c)
            val area = Imgproc.contourArea(c)
            val splits = trySplitMergedFingers(c, rect, maxFingers)
            if (splits.isNotEmpty()) {
                rects.addAll(splits)
            } else {
                rects.add(Pair(rect, area))
            }
        }

        // Sort left→right, take up to maxFingers
        val sorted = rects
            .filter { (r, a) ->
                val aspect = r.width.toDouble() / r.height.toDouble()
                a > imageArea * 0.003 && aspect < 1.4
            }
            .sortedBy { (r, _) -> r.x }
            .take(maxFingers)

        // Fallback: if nothing detected, use centre 60% of frame as single ROI
        if (sorted.isEmpty()) {
            val fallbackRect = Rect(
                (src.cols() * 0.20).toInt(), (src.rows() * 0.10).toInt(),
                (src.cols() * 0.60).toInt(), (src.rows() * 0.80).toInt()
            )
            return listOf(FingerROI(0, fallbackRect, fallbackRect.area()))
        }

        val result = sorted.mapIndexed { idx, (rect, area) -> FingerROI(idx, rect, area) }
        contours.forEach { it.release() }
        return result
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
        val aspectRatio = boundingRect.width.toDouble() / boundingRect.height.toDouble()
        // Only attempt split if contour is wider than tall (likely merged fingers)
        if (aspectRatio < 1.5) return emptyList()

        val hull = MatOfInt()
        Imgproc.convexHull(contour, hull, false)

        val defects = MatOfInt4()
        try {
            Imgproc.convexityDefects(contour, hull, defects)
        } catch (e: Exception) {
            hull.release(); defects.release()
            return emptyList()
        }

        if (defects.rows() == 0) {
            hull.release(); defects.release()
            return emptyList()
        }

        val points = contour.toArray()
        val defectData = defects.toArray()

        // Collect valley x-coordinates from significant defects
        val valleyXs = mutableListOf<Int>()
        for (i in defectData.indices step 4) {
            val farIdx   = defectData[i + 2]
            val depth    = defectData[i + 3] / 256.0  // depth in pixels
            if (depth > boundingRect.height * 0.25 && farIdx < points.size) {
                valleyXs.add(points[farIdx].x.toInt())
            }
        }
        hull.release(); defects.release()

        if (valleyXs.isEmpty()) return emptyList()

        // Build split rects between valleys
        val splitXs = (listOf(boundingRect.x) + valleyXs.sorted() + listOf(boundingRect.x + boundingRect.width))
            .distinct().sorted()

        val splits = mutableListOf<Pair<Rect, Double>>()
        for (i in 0 until splitXs.size - 1) {
            val x0 = splitXs[i]
            val x1 = splitXs[i + 1]
            val w  = x1 - x0
            if (w < 20) continue  // too narrow
            val r = Rect(x0, boundingRect.y, w, boundingRect.height)
            splits.add(Pair(r, r.area()))
        }

        return if (splits.size in 2..maxFingers) splits else emptyList()
    }

    // ─── Helpers ─────────────────────────────────────────────────────────────

    fun matToBitmap(mat: Mat): Bitmap {
        val display = if (mat.channels() == 1) {
            val rgb = Mat(); Imgproc.cvtColor(mat, rgb, Imgproc.COLOR_GRAY2BGRA); rgb
        } else mat
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
