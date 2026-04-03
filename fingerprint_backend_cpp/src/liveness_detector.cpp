#include "liveness_detector.h"
#include <cmath>
#include <algorithm>

namespace fingerprint {

float LivenessDetector::checkGlare(const cv::Mat& gray) {
    // Bright pixels > 245 must stay under 12 % of frame
    cv::Mat bright;
    cv::threshold(gray, bright, 245, 255, cv::THRESH_BINARY);
    double ratio = (double)cv::countNonZero(bright) / (double)bright.total();
    // Returns 1.0 when no glare; goes negative when ratio >= 12 %
    return (float)(1.0 - ratio / 0.12);
}

float LivenessDetector::computeTextureScore(const cv::Mat& gray) {
    // Local texture variance via box filter: Var = E[x²] - E[x]²
    cv::Mat gF;
    gray.convertTo(gF, CV_32F);

    cv::Mat gF2 = gF.mul(gF);
    cv::Mat Ex, Ex2;
    cv::boxFilter(gF,  Ex,  CV_32F, cv::Size(5, 5));
    cv::boxFilter(gF2, Ex2, CV_32F, cv::Size(5, 5));

    cv::Mat variance = Ex2 - Ex.mul(Ex);
    cv::Scalar meanVar = cv::mean(variance);
    double localStd = std::sqrt(std::abs(meanVar[0]));

    // Real skin: localStd 20-60 → 1.0
    // Printed / screen: localStd 3-15 → 0.3
    if (localStd < 3  || localStd > 80) return 0.3f;
    if (localStd >= 20 && localStd <= 60) return 1.0f;
    if (localStd < 20) return (float)(localStd / 20.0);
    return std::max(0.3f, (float)(1.0 - (localStd - 60.0) / 80.0));
}

float LivenessDetector::computeSkinScore(const cv::Mat& bgr) {
    cv::Mat hsv;
    cv::cvtColor(bgr, hsv, cv::COLOR_BGR2HSV);

    // OpenCV HSV: H 0-180, S 0-255, V 0-255
    // Skin hue: 0-25 and 165-180 (wraps), S 20-170, V 50-255
    cv::Mat mask1, mask2, skinMask;
    cv::inRange(hsv, cv::Scalar(0,   20,  50), cv::Scalar(25,  170, 255), mask1);
    cv::inRange(hsv, cv::Scalar(165, 20,  50), cv::Scalar(180, 170, 255), mask2);
    cv::bitwise_or(mask1, mask2, skinMask);

    double skinRatio = (double)cv::countNonZero(skinMask) / (double)skinMask.total();
    // At least 15 % of crop should be skin-coloured
    return std::clamp((float)(skinRatio / 0.15), 0.0f, 1.0f);
}

LivenessResult LivenessDetector::detect(const cv::Mat& image) {
    LivenessResult result{};

    cv::Mat gray, bgr;
    if (image.channels() == 1) {
        gray = image.clone();
        cv::cvtColor(image, bgr, cv::COLOR_GRAY2BGR);
    } else {
        bgr = image.clone();
        cv::cvtColor(image, gray, cv::COLOR_BGR2GRAY);
    }

    // Layer 2 (hard gate): glare
    float glareScore = checkGlare(gray);
    result.glareDetected = (glareScore <= 0.0f);
    if (result.glareDetected) {
        result.confidence = 0.1f;
        result.isLive     = false;
        return result;
    }

    // Layer 3: texture
    result.textureScore = computeTextureScore(gray);

    // Layer 4: skin colour
    result.skinScore = computeSkinScore(bgr);

    // Combine scores (mediapipe base = 0.9 assumed present)
    float confidence = 0.9f;
    if (result.textureScore < 0.5f) confidence *= 0.6f;
    if (result.skinScore    < 0.5f) confidence *= 0.7f;

    result.confidence = std::clamp(confidence, 0.0f, 1.0f);
    result.isLive     = result.confidence >= 0.6f;
    return result;
}

} // namespace fingerprint
