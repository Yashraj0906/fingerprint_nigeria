#include <jni.h>
#include <android/log.h>
#include <string>
#include <vector>
#include "fingerprint_core.h"

#define LOG_TAG "FingerprintSDK"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// ---------------------------------------------------------------------------
// Helper: put a Float into a Java HashMap
// ---------------------------------------------------------------------------
static void putFloat(JNIEnv* env, jobject map,
                     jmethodID mapPut,
                     jclass floatClass, jmethodID floatInit,
                     const char* key, float val) {
    env->CallObjectMethod(map, mapPut,
        env->NewStringUTF(key),
        env->NewObject(floatClass, floatInit, val));
}

static void putBool(JNIEnv* env, jobject map,
                    jmethodID mapPut,
                    jclass boolClass, jmethodID boolInit,
                    const char* key, bool val) {
    env->CallObjectMethod(map, mapPut,
        env->NewStringUTF(key),
        env->NewObject(boolClass, boolInit, (jboolean)val));
}

static void putStr(JNIEnv* env, jobject map,
                   jmethodID mapPut,
                   const char* key, const std::string& val) {
    env->CallObjectMethod(map, mapPut,
        env->NewStringUTF(key),
        env->NewStringUTF(val.c_str()));
}

// ---------------------------------------------------------------------------
// JNI exports
// ---------------------------------------------------------------------------
extern "C" {

/**
 * Runs the full fingerprint pipeline on a JPEG byte array.
 * Returns a HashMap<String,Object> with keys:
 *   qualityScore, blurScore, contrastScore, ridgeClarityScore,
 *   coverageScore, orientationScore, guidance,
 *   livenessScore, isLive, accepted, template, templateSuccess
 */
JNIEXPORT jobject JNICALL
Java_com_yellowsense_fingerprintsdk_FingerprintSDK_processImage(
        JNIEnv* env, jclass /*cls*/, jbyteArray imageBytes) {

    jsize  len   = env->GetArrayLength(imageBytes);
    jbyte* bytes = env->GetByteArrayElements(imageBytes, nullptr);
    std::vector<uint8_t> jpeg(reinterpret_cast<uint8_t*>(bytes),
                              reinterpret_cast<uint8_t*>(bytes) + len);
    env->ReleaseByteArrayElements(imageBytes, bytes, JNI_ABORT);

    fingerprint::CaptureResult r = fingerprint::processFingerImage(jpeg);

    // Build result HashMap
    jclass    mapClass = env->FindClass("java/util/HashMap");
    jmethodID mapInit  = env->GetMethodID(mapClass, "<init>", "()V");
    jmethodID mapPut   = env->GetMethodID(mapClass, "put",
                             "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;");
    jobject map = env->NewObject(mapClass, mapInit);

    jclass    fClass = env->FindClass("java/lang/Float");
    jmethodID fInit  = env->GetMethodID(fClass, "<init>", "(F)V");
    jclass    bClass = env->FindClass("java/lang/Boolean");
    jmethodID bInit  = env->GetMethodID(bClass, "<init>", "(Z)V");

    putFloat(env, map, mapPut, fClass, fInit, "qualityScore",      r.quality.compositeScore);
    putFloat(env, map, mapPut, fClass, fInit, "blurScore",         r.quality.blurScore);
    putFloat(env, map, mapPut, fClass, fInit, "contrastScore",     r.quality.contrastScore);
    putFloat(env, map, mapPut, fClass, fInit, "ridgeClarityScore", r.quality.ridgeClarityScore);
    putFloat(env, map, mapPut, fClass, fInit, "coverageScore",     r.quality.coverageScore);
    putFloat(env, map, mapPut, fClass, fInit, "orientationScore",  r.quality.orientationScore);
    putStr  (env, map, mapPut,               "guidance",           r.quality.guidance);
    putFloat(env, map, mapPut, fClass, fInit, "livenessScore",     r.liveness.confidence);
    putBool (env, map, mapPut, bClass, bInit, "isLive",            r.liveness.isLive);
    putBool (env, map, mapPut, bClass, bInit, "accepted",          r.accepted);
    putStr  (env, map, mapPut,               "template",
             r.templ.success ? r.templ.base64Template : "");
    putBool (env, map, mapPut, bClass, bInit, "templateSuccess",   r.templ.success);

    return map;
}

/**
 * Match two ISO 19794-2 base64 templates.
 * Returns a float score 0.0 – 1.0.
 */
JNIEXPORT jfloat JNICALL
Java_com_yellowsense_fingerprintsdk_FingerprintSDK_matchTemplates(
        JNIEnv* env, jclass /*cls*/,
        jstring templateA, jstring templateB) {

    const char* tA = env->GetStringUTFChars(templateA, nullptr);
    const char* tB = env->GetStringUTFChars(templateB, nullptr);

    fingerprint::MatchResult result =
        fingerprint::Matcher::match(std::string(tA), std::string(tB));

    env->ReleaseStringUTFChars(templateA, tA);
    env->ReleaseStringUTFChars(templateB, tB);

    return (jfloat)result.score;
}

/**
 * Extract quality score only (fast path, no template encoding).
 */
JNIEXPORT jfloat JNICALL
Java_com_yellowsense_fingerprintsdk_FingerprintSDK_getQualityScore(
        JNIEnv* env, jclass /*cls*/, jbyteArray imageBytes) {

    jsize  len   = env->GetArrayLength(imageBytes);
    jbyte* bytes = env->GetByteArrayElements(imageBytes, nullptr);
    std::vector<uint8_t> jpeg(reinterpret_cast<uint8_t*>(bytes),
                              reinterpret_cast<uint8_t*>(bytes) + len);
    env->ReleaseByteArrayElements(imageBytes, bytes, JNI_ABORT);

    cv::Mat img = fingerprint::decodeImage(jpeg);
    if (img.empty()) return 0.0f;

    fingerprint::QualityResult q = fingerprint::QualityAnalyzer::analyze(img);
    return (jfloat)q.compositeScore;
}

} // extern "C"
