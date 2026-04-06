#include <jni.h>
#include <string>
#include <vector>
#include <map>
#include <opencv2/core.hpp>
#include "fingerprint_core.h"
#include "liveness_detector.h"
#include "quality_analyzer.h"
#include "template_encoder.h"

using namespace fingerprint;

extern "C" {

// Helper to create a Java HashMap
jobject createJavaHashMap(JNIEnv* env) {
    jclass mapClass = env->FindClass("java/util/HashMap");
    jmethodID init = env->GetMethodID(mapClass, "<init>", "()V");
    return env->NewObject(mapClass, init);
}

void putInMap(JNIEnv* env, jobject map, const char* key, jobject value) {
    static jclass mapClass = nullptr;
    static jmethodID put = nullptr;
    if (mapClass == nullptr) {
        mapClass = (jclass)env->NewGlobalRef(env->FindClass("java/util/HashMap"));
        put = env->GetMethodID(mapClass, "put", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;");
    }
    env->CallObjectMethod(map, put, env->NewStringUTF(key), value);
}

jobject toJavaBool(JNIEnv* env, bool value) {
    jclass boolClass = env->FindClass("java/lang/Boolean");
    jmethodID valueOf = env->GetStaticMethodID(boolClass, "valueOf", "(Z)Ljava/lang/Boolean;");
    return env->CallStaticObjectMethod(boolClass, valueOf, value);
}

jobject toJavaFloat(JNIEnv* env, float value) {
    jclass floatClass = env->FindClass("java/lang/Float");
    jmethodID valueOf = env->GetStaticMethodID(floatClass, "valueOf", "(F)Ljava/lang/Float;");
    return env->CallStaticObjectMethod(floatClass, valueOf, value);
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
