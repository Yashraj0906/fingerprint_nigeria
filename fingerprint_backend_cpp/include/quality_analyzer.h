#pragma once
// Use targeted includes to avoid ObjC 'NO' macro conflict with stitching headers
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <string>

namespace fingerprint {

enum class QualityDecision {
    ACCEPT,   // composite score >= 70
    RETRY,    // composite score 40-69
    REJECT    // composite score < 40
};

struct QualityResult {
    float compositeScore;       // 0-100 weighted average
    float blurScore;            // 0-100  weight 25%
    float contrastScore;        // 0-100  weight 15%
    float ridgeClarityScore;    // 0-100  weight 25%
    float coverageScore;        // 0-100  weight 15%
    float orientationScore;     // 0-100  weight 20%
    QualityDecision decision;
    std::string guidance;       // user-facing message
};

class QualityAnalyzer {
public:
    static QualityResult analyze(const cv::Mat& image);

private:
    static float computeBlurScore(const cv::Mat& gray);
    static float computeContrastScore(const cv::Mat& gray);
    static float computeRidgeClarityScore(const cv::Mat& gray);
    static float computeCoverageScore(const cv::Mat& gray);
    static float computeOrientationScore(const cv::Mat& gray);
    static std::string generateGuidance(const QualityResult& r);
};

} // namespace fingerprint
