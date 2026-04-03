#ifndef LIVENESS_DETECTOR_HPP
#define LIVENESS_DETECTOR_HPP

#include <opencv2/opencv.hpp>
#include <string>
#include <vector>

struct BboxPct {
    double x, y, w, h;
};

struct FingerResult {
    std::string finger_id;
    bool detected;
    double quality_score;
    double blur_score;
    double illum_score;
    bool liveness;
    double liveness_conf;
    bool is_ai_generated;
    std::string guidance;
    BboxPct bbox_pct;
};

struct FingerprintResult {
    bool hand_detected;
    std::string hand;
    std::string guidance;
    std::vector<FingerResult> fingers;
};

class LivenessDetector {
public:
    static FingerprintResult analyzeFrame(const cv::Mat& bgrImage, const std::string& hand, const std::string& mode);

private:
    static bool _screen_replay_detection(const cv::Mat& gray, const cv::Mat& bgr, std::string& reason);
    static bool _spectral_decay_anomaly(const cv::Mat& gray);
    static double _blur_score_raw(const cv::Mat& gray);
    static double _illumination_score_raw(const cv::Mat& gray);
};

#endif // LIVENESS_DETECTOR_HPP
