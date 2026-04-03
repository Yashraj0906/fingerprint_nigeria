#include "quality_analyzer.h"
#include "liveness_detector.h"
#include "image_processor.h"
#include <cmath>
#include <algorithm>

namespace fingerprint {

// ---------------------------------------------------------------------------
// Private metrics
// ---------------------------------------------------------------------------

float QualityAnalyzer::computeBlurScore(const cv::Mat& gray) {
    // Laplacian variance
    cv::Mat lap;
    cv::Laplacian(gray, lap, CV_64F);
    cv::Scalar mean, stddev;
    cv::meanStdDev(lap, mean, stddev);
    double lapVar = stddev[0] * stddev[0];

    // Tenengrad (Sobel energy)
    cv::Mat gx, gy;
    cv::Sobel(gray, gx, CV_64F, 1, 0, 3);
    cv::Sobel(gray, gy, CV_64F, 0, 1, 3);
    cv::Mat mag;
    cv::sqrt(gx.mul(gx) + gy.mul(gy), mag);
    double tenenMean = cv::mean(mag)[0];

    // Blend: Laplacian variance dominates
    double combined = 0.6 * (lapVar / 100.0) + 0.4 * (tenenMean / 20.0);
    float score = (float)(combined * 100.0);
    return (score < 0.0f) ? 0.0f : (score > 100.0f) ? 100.0f : score;
}

float QualityAnalyzer::computeContrastScore(const cv::Mat& gray) {
    cv::Scalar mean, stddev;
    cv::meanStdDev(gray, mean, stddev);
    double rms = stddev[0];

    // Histogram entropy
    cv::Mat hist;
    float range[] = {0, 256};
    const float* histRange = range;
    int histSize = 256;
    cv::calcHist(&gray, 1, nullptr, cv::Mat(), hist, 1, &histSize, &histRange);
    hist /= (float)gray.total();
    float entropy = 0;
    for (int i = 0; i < 256; i++) {
        float p = hist.at<float>(i);
        if (p > 1e-7f) entropy -= p * std::log2(p);
    }
    float entNorm = std::min(8.0f, entropy) / 8.0f * 100.0f;

    // Penalty for extreme brightness (dark < 55, glare > 215)
    float brightnessPenalty = (mean[0] < 55 || mean[0] > 215) ? 0.5f : 1.0f;

    float score = (float)(rms / 60.0 * 50.0) + entNorm * 0.5f;
    float finalScore = score * brightnessPenalty;
    return (finalScore < 0.0f) ? 0.0f : (finalScore > 100.0f) ? 100.0f : finalScore;
}

float QualityAnalyzer::computeRidgeClarityScore(const cv::Mat& gray) {
    cv::Mat edges;
    cv::Canny(gray, edges, 50, 150);
    double density = (double)cv::countNonZero(edges) / (double)edges.total();

    // Ideal density ~15 %
    double deviation = std::abs(density - 0.15);
    float score = (float)(100.0 * (1.0 - deviation / 0.15));
    return (score < 0.0f) ? 0.0f : (score > 100.0f) ? 100.0f : score;
}

float QualityAnalyzer::computeCoverageScore(const cv::Mat& gray) {
    cv::Mat binary;
    cv::threshold(gray, binary, 0, 255, cv::THRESH_BINARY | cv::THRESH_OTSU);
    double coverage = (double)cv::countNonZero(binary) / (double)binary.total();

    // Ideal 30-80 %; penalise outside that band
    if (coverage >= 0.30 && coverage <= 0.80) {
        float centreDist = (float)std::abs(coverage - 0.55);
        return std::clamp(100.0f - centreDist * 200.0f, 0.0f, 100.0f);
    }
    float dist = (float)std::min(std::abs(coverage - 0.30), std::abs(coverage - 0.80));
    float score = 100.0f - dist * 500.0f;
    return (score < 0.0f) ? 0.0f : (score > 100.0f) ? 100.0f : score;
}

float QualityAnalyzer::computeOrientationScore(const cv::Mat& gray) {
    cv::Mat gx, gy;
    cv::Sobel(gray, gx, CV_32F, 1, 0, 3);
    cv::Sobel(gray, gy, CV_32F, 0, 1, 3);

    const int blockSize = 16;
    float sinSum = 0, cosSum = 0;
    int   count  = 0;

    for (int i = 0; i + blockSize <= gray.rows; i += blockSize) {
        for (int j = 0; j + blockSize <= gray.cols; j += blockSize) {
            float Gxy = 0, Gxx_yy = 0;
            for (int y = i; y < i + blockSize; y++) {
                for (int x = j; x < j + blockSize; x++) {
                    float dx = gx.at<float>(y, x);
                    float dy = gy.at<float>(y, x);
                    Gxy    += 2.0f * dx * dy;
                    Gxx_yy += dx * dx - dy * dy;
                }
            }
            float angle = 0.5f * std::atan2(Gxy, Gxx_yy);
            sinSum += std::sin(2.0f * angle);
            cosSum += std::cos(2.0f * angle);
            count++;
        }
    }

    if (count == 0) return 50.0f;

    float coherence = std::sqrt(sinSum * sinSum + cosSum * cosSum) / count;
    float score = coherence * 111.0f;
    return (score < 0.0f) ? 0.0f : (score > 100.0f) ? 100.0f : score;
}

std::string QualityAnalyzer::generateGuidance(const QualityResult& r) {
    // Priority: lighting > blur > coverage > ridges > orientation
    if (r.contrastScore < 40.0f) {
        return r.contrastScore < 25.0f
            ? "Poor lighting - adjust brightness"
            : "Adjust lighting for better contrast";
    }
    if (r.blurScore        < 40.0f) return "Hold still - image is blurry";
    if (r.coverageScore    < 40.0f) return "Center your finger on the sensor";
    if (r.ridgeClarityScore < 40.0f) return "Press finger more firmly";
    if (r.orientationScore < 40.0f) return "Straighten your finger";
    if (r.compositeScore   >= 70.0f) return "Good - capture ready";
    return "Adjust position slightly";
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

QualityResult QualityAnalyzer::analyze(const cv::Mat& image) {
    cv::Mat gray;
    if (image.channels() > 1)
        cv::cvtColor(image, gray, cv::COLOR_BGR2GRAY);
    else
        gray = image.clone();

    QualityResult r;
    r.blurScore         = computeBlurScore(gray);
    r.contrastScore     = computeContrastScore(gray);
    r.ridgeClarityScore = computeRidgeClarityScore(gray);
    r.coverageScore     = computeCoverageScore(gray);
    r.orientationScore  = computeOrientationScore(gray);

    r.compositeScore =
        r.blurScore         * 0.25f +
        r.contrastScore     * 0.15f +
        r.ridgeClarityScore * 0.25f +
        r.coverageScore     * 0.15f +
        r.orientationScore  * 0.20f;

    r.compositeScore = (r.compositeScore < 0.0f) ? 0.0f : (r.compositeScore > 100.0f) ? 100.0f : r.compositeScore;

    if      (r.compositeScore >= 70.0f) r.decision = QualityDecision::ACCEPT;
    else if (r.compositeScore >= 40.0f) r.decision = QualityDecision::RETRY;
    else                                r.decision = QualityDecision::REJECT;

    r.guidance = generateGuidance(r);
    return r;
}

} // namespace fingerprint
