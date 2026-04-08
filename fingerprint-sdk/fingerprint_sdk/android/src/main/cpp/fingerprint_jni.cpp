#include <jni.h>
#include <string>
#include <vector>
#include <map>
#include <opencv2/core.hpp>
#include "fingerprint_core.h"
#include "liveness_detector.h"
#include "quality_analyzer.h"
#include "template_encoder.h"

#include <mutex>

using namespace fingerprint;

static std::once_flag g_init_flag;
static jclass g_mapClass = nullptr;
static jmethodID g_mapInit = nullptr;
static jmethodID g_mapPut = nullptr;
static jclass g_boolClass = nullptr;
static jmethodID g_boolValueOf = nullptr;
static jclass g_floatClass = nullptr;
static jmethodID g_floatValueOf = nullptr;

/**
 * Thread-safe JNI cache initialization.
 */
void initializeJniCache(JNIEnv* env) {
    std::call_once(g_init_flag, [env]() {
        jclass localMapClass = env->FindClass("java/util/HashMap");
        g_mapClass = (jclass)env->NewGlobalRef(localMapClass);
        g_mapInit = env->GetMethodID(g_mapClass, "<init>", "()V");
        g_mapPut = env->GetMethodID(g_mapClass, "put", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;");

        jclass localBoolClass = env->FindClass("java/lang/Boolean");
        g_boolClass = (jclass)env->NewGlobalRef(localBoolClass);
        g_boolValueOf = env->GetStaticMethodID(g_boolClass, "valueOf", "(Z)Ljava/lang/Boolean;");

        jclass localFloatClass = env->FindClass("java/lang/Float");
        g_floatClass = (jclass)env->NewGlobalRef(localFloatClass);
        g_floatValueOf = env->GetStaticMethodID(g_floatClass, "valueOf", "(F)Ljava/lang/Float;");
    });
}

extern "C" {

// Helper to create a Java HashMap
jobject createJavaHashMap(JNIEnv* env) {
    initializeJniCache(env);
    return env->NewObject(g_mapClass, g_mapInit);
}

void putInMap(JNIEnv* env, jobject map, const char* key, jobject value) {
    initializeJniCache(env);
    jstring jKey = env->NewStringUTF(key);
    env->CallObjectMethod(map, g_mapPut, jKey, value);
    env->DeleteLocalRef(jKey);
}

jobject toJavaBool(JNIEnv* env, bool value) {
    initializeJniCache(env);
    return env->CallStaticObjectMethod(g_boolClass, g_boolValueOf, value);
}

jobject toJavaFloat(JNIEnv* env, float value) {
    initializeJniCache(env);
    return env->CallStaticObjectMethod(g_floatClass, g_floatValueOf, value);
}

// ---------------------------------------------------------------------------
// LivenessDetector JNI
// ---------------------------------------------------------------------------

JNIEXPORT jobject JNICALL
Java_com_yellowsense_fingerprint_1sdk_validation_LivenessDetector_nativeEvaluate(
        JNIEnv* env, jobject thiz, jlong grayAddr, jlong bgrAddr, jlong fullBgrAddr, jstring handMode) {

    cv::Mat* gray = (cv::Mat*)grayAddr;
    cv::Mat* bgr = (cv::Mat*)bgrAddr;
    cv::Mat* fullBgr = (cv::Mat*)fullBgrAddr;

    const char* nativeHandMode = env->GetStringUTFChars(handMode, nullptr);
    std::string handModeStr(nativeHandMode);
    env->ReleaseStringUTFChars(handMode, nativeHandMode);

    LivenessResult res;
    res.passed = false;
    res.confidence = 0.0;
    try {
        res = LivenessDetector::evaluate(*gray, *bgr, *fullBgr, handModeStr);
    } catch (const cv::Exception& e) {
        res.reason = std::string("JNI_CV_EXCEPTION: ") + e.what();
    } catch (const std::exception& e) {
        res.reason = std::string("JNI_STD_EXCEPTION: ") + e.what();
    } catch (...) {
        res.reason = std::string("JNI_UNKNOWN_EXCEPTION");
    }

    jobject map = createJavaHashMap(env);
    putInMap(env, map, "passed", toJavaBool(env, res.passed));
    putInMap(env, map, "confidence", toJavaFloat(env, res.confidence));
    if (!res.reason.empty()) {
        putInMap(env, map, "reason", env->NewStringUTF(res.reason.c_str()));
    }
    
    return map;
}

// ---------------------------------------------------------------------------
// QualityAnalyzer JNI
// ---------------------------------------------------------------------------

JNIEXPORT jobject JNICALL
Java_com_yellowsense_fingerprint_1sdk_processing_QualityAnalyzer_nativeAnalyze(
        JNIEnv* env, jobject thiz, jlong imageAddr) {

    cv::Mat* image = (cv::Mat*)imageAddr;
    QualityResult res;
    res.decision = QualityDecision::REJECT;
    try {
        res = QualityAnalyzer::analyze(*image);
    } catch (const cv::Exception& e) {
        res.guidance = std::string("JNI_CV_EXCEPTION: ") + e.what();
    } catch (...) {
        res.guidance = std::string("JNI_UNKNOWN_EXCEPTION");
    }

    jobject map = createJavaHashMap(env);
    putInMap(env, map, "blurScore", toJavaFloat(env, res.blurScore));
    putInMap(env, map, "contrastScore", toJavaFloat(env, res.contrastScore));
    putInMap(env, map, "ridgeClarityScore", toJavaFloat(env, res.ridgeClarityScore));
    putInMap(env, map, "coverageScore", toJavaFloat(env, res.coverageScore));
    putInMap(env, map, "orientationScore", toJavaFloat(env, res.orientationScore));
    putInMap(env, map, "compositeScore", toJavaFloat(env, res.compositeScore));
    
    std::string decisionStr = (res.decision == QualityDecision::ACCEPT) ? "ACCEPT" : 
                              (res.decision == QualityDecision::RETRY) ? "RETRY" : "REJECT";
    putInMap(env, map, "decision", env->NewStringUTF(decisionStr.c_str()));
    putInMap(env, map, "guidance", env->NewStringUTF(res.guidance.c_str()));

    return map;
}

// ---------------------------------------------------------------------------
// TemplateEncoder JNI
// ---------------------------------------------------------------------------

JNIEXPORT jstring JNICALL
Java_com_yellowsense_fingerprint_1sdk_processing_TemplateEncoder_nativeEncode(
        JNIEnv* env, jobject thiz, jlong imageAddr) {

    cv::Mat* image = (cv::Mat*)imageAddr;
    
    TemplateResult res;
    res.success = false;
    try {
        res = TemplateEncoder::extractTemplate(*image);
    } catch (...) {
        // Fallback
    }

    if (!res.success) return nullptr;

    return env->NewStringUTF(res.base64Template.c_str());
}

}
