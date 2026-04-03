#pragma once
#include <opencv2/opencv.hpp>

namespace fingerprint {

struct LivenessResult {
    float confidence;       // 0.0 - 1.0
    bool  isLive;           // confidence >= 0.6
    bool  glareDetected;
    float textureScore;     // 0.0 - 1.0  (LBP proxy)
    float skinScore;        // 0.0 - 1.0  (HSV skin mask)
};

class LivenessDetector {
public:
    // image can be BGR or grayscale
    static LivenessResult detect(const cv::Mat& image);

private:
    // Returns normalised score: 1.0 = no glare, <=0 = fail
    static float checkGlare(const cv::Mat& gray);

    // Local texture variance via box filter E[x²]-E[x]²
    static float computeTextureScore(const cv::Mat& gray);

    // Fraction of pixels matching skin HSV envelope
    static float computeSkinScore(const cv::Mat& bgr);
};

} // namespace fingerprint
