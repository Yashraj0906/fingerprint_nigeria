package com.yellowsense.fingerprintsdk;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import java.util.Map;

/**
 * Java entry-point for the Fingerprint C++ SDK.
 *
 * Usage:
 *   Map<String,Object> result = FingerprintSDK.processImage(jpegBytes);
 *   float score = (Float) result.get("qualityScore");
 *   boolean accepted = (Boolean) result.get("accepted");
 *   String template  = (String)  result.get("template");
 *
 *   float matchScore = FingerprintSDK.matchTemplates(templateA, templateB);
 *   boolean isMatch  = FingerprintSDK.isMatch(templateA, templateB);
 */
public final class FingerprintSDK {

    static {
        System.loadLibrary("fingerprint_sdk");
    }

    private FingerprintSDK() {}

    /**
     * Run the full pipeline (quality → liveness → template extraction) on
     * a JPEG-encoded finger image.
     *
     * @param imageBytes JPEG bytes
     * @return Map with keys: qualityScore, blurScore, contrastScore,
     *         ridgeClarityScore, coverageScore, orientationScore, guidance,
     *         livenessScore, isLive, accepted, template, templateSuccess
     */
    @NonNull
    public static native Map<String, Object> processImage(byte[] imageBytes);

    /**
     * Match two ISO 19794-2 base64 templates.
     *
     * @return score 0.0 – 1.0
     */
    public static native float matchTemplates(@NonNull String templateA,
                                              @NonNull String templateB);

    /**
     * Quick quality score only (skips liveness + template encoding).
     *
     * @return composite quality score 0-100
     */
    public static native float getQualityScore(byte[] imageBytes);

    /**
     * Convenience wrapper: returns true when match score >= 0.35.
     */
    public static boolean isMatch(@NonNull String templateA,
                                  @NonNull String templateB) {
        return matchTemplates(templateA, templateB) >= 0.35f;
    }
}
