package com.fingerprintsdk.liveness

import android.util.Base64
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Fingerprint Liveness SDK v2.0
 * Contactless multi-finger liveness detection and quality scoring.
 *
 * Usage:
 *   val sdk = FingerprintSDK("http://YOUR_SERVER:8000")
 *   sdk.analyzeFrame(jpegBytes, "RIGHT", "RIGHT_FOUR") { result ->
 *       if (result.handDetected) {
 *           result.fingers.forEach { finger ->
 *               if (finger.liveness) { /* real */ } else { showAlert(finger.guidance) }
 *           }
 *       }
 *   }
 */
class FingerprintSDK(private val serverUrl: String) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()

    /**
     * Analyze a camera frame asynchronously.
     *
     * @param imageBytes  Raw JPEG bytes from camera
     * @param hand        "RIGHT" or "LEFT"
     * @param mode        "RIGHT_FOUR", "LEFT_FOUR", "RIGHT_THUMB", "LEFT_THUMB", "SINGLE_FINGER"
     * @param callback    Called on completion with FingerprintResult
     */
    fun analyzeFrame(
        imageBytes: ByteArray,
        hand: String,
        mode: String,
        callback: (FingerprintResult) -> Unit
    ) {
        val b64 = Base64.encodeToString(imageBytes, Base64.NO_WRAP)
        val body = JSONObject().apply {
            put("image_base64", b64)
            put("hand", hand)
            put("mode", mode)
        }.toString()

        val request = Request.Builder()
            .url("$serverUrl/api/capture/analyze")
            .post(body.toRequestBody(JSON_MEDIA))
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: java.io.IOException) {
                callback(FingerprintResult(
                    handDetected = false,
                    hand = hand,
                    guidance = "Connection error: ${e.message}",
                    fingers = emptyList()
                ))
            }

            override fun onResponse(call: Call, response: Response) {
                val json = JSONObject(response.body?.string() ?: "{}")
                callback(FingerprintResult.fromJson(json))
            }
        })
    }

    /**
     * Synchronous version — call from background thread only.
     */
    fun analyzeFrameSync(imageBytes: ByteArray, hand: String, mode: String): FingerprintResult {
        val b64 = Base64.encodeToString(imageBytes, Base64.NO_WRAP)
        val body = JSONObject().apply {
            put("image_base64", b64)
            put("hand", hand)
            put("mode", mode)
        }.toString()

        val request = Request.Builder()
            .url("$serverUrl/api/capture/analyze")
            .post(body.toRequestBody(JSON_MEDIA))
            .build()

        return try {
            val response = client.newCall(request).execute()
            val json = JSONObject(response.body?.string() ?: "{}")
            FingerprintResult.fromJson(json)
        } catch (e: Exception) {
            FingerprintResult(
                handDetected = false,
                hand = hand,
                guidance = "Error: ${e.message}",
                fingers = emptyList()
            )
        }
    }
}

// ── Data Models ───────────────────────────────────────────────────────────────

data class FingerprintResult(
    val handDetected: Boolean,
    val hand: String,
    val guidance: String?,
    val fingers: List<FingerResult>
) {
    companion object {
        fun fromJson(json: JSONObject) = FingerprintResult(
            handDetected = json.optBoolean("hand_detected", false),
            hand = json.optString("hand", ""),
            guidance = json.optString("guidance", null),
            fingers = json.optJSONArray("fingers")?.let { arr ->
                (0 until arr.length()).map { FingerResult.fromJson(arr.getJSONObject(it)) }
            } ?: emptyList()
        )
    }
}

data class FingerResult(
    /** e.g. RIGHT_INDEX, LEFT_THUMB */
    val fingerId: String,
    val detected: Boolean,
    /** Quality 0-100. Accept if >= 60. */
    val qualityScore: Double,
    val blurScore: Double?,
    val illumScore: Double?,
    /** true = real, false = spoof detected */
    val liveness: Boolean,
    /** Confidence 0.0-1.0 */
    val livenessConf: Double?,
    val isAiGenerated: Boolean,
    /** Human-readable failure reason — use as errorMessage */
    val guidance: String?,
    val bboxPct: BboxPct?
) {
    /** true if finger is ready to enroll (live + quality >= 60) */
    val isAccepted: Boolean get() = liveness && qualityScore >= 60

    companion object {
        fun fromJson(json: JSONObject) = FingerResult(
            fingerId     = json.optString("finger_id", ""),
            detected     = json.optBoolean("detected", false),
            qualityScore = json.optDouble("quality_score", 0.0),
            blurScore    = if (json.has("blur_score")) json.getDouble("blur_score") else null,
            illumScore   = if (json.has("illum_score")) json.getDouble("illum_score") else null,
            liveness     = json.optBoolean("liveness", false),
            livenessConf = if (json.has("liveness_conf")) json.getDouble("liveness_conf") else null,
            isAiGenerated = json.optBoolean("is_ai_generated", false),
            guidance     = json.optString("guidance", null),
            bboxPct      = json.optJSONObject("bbox_pct")?.let { BboxPct.fromJson(it) }
        )
    }
}

data class BboxPct(val x: Double, val y: Double, val w: Double, val h: Double) {
    companion object {
        fun fromJson(json: JSONObject) = BboxPct(
            x = json.optDouble("x", 0.0),
            y = json.optDouble("y", 0.0),
            w = json.optDouble("w", 0.0),
            h = json.optDouble("h", 0.0)
        )
    }
}
