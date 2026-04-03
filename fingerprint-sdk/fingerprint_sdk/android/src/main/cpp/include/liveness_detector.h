#pragma once
#include <opencv2/opencv.hpp>
#include <string>
#include <vector>

namespace fingerprint {

struct LivenessResult {
    bool passed;
    std::string reason;     // Nullable equivalent (empty if passed)
    float confidence;       // 0.0 - 1.0
    bool isAiGenerated;
};

class LivenessDetector {
public:
    // Core 12-layer evaluation check translated from Python backend.
    // 'gray_sm' and 'bgr_sm' should be a tight crop around the finger.
    // 'full_bgr' is the uncropped camera frame (used for bezel check).
    static LivenessResult evaluate(const cv::Mat& gray_sm, 
                                   const cv::Mat& bgr_sm, 
                                   const cv::Mat& full_bgr, 
                                   const std::string& hand_mode);

private:
    static bool detectPhoneBezel(const cv::Mat& bgr_full);
    static bool detectScreenReplay(const cv::Mat& gray, const cv::Mat& bgr, std::string& reason);
    static bool detectSpectralDecayAnomaly(const cv::Mat& gray);
};

} // namespace fingerprint
