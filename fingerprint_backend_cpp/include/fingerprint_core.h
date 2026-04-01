#pragma once
#include "image_processor.h"
#include "quality_analyzer.h"
#include "liveness_detector.h"
#include "template_encoder.h"
#include "matcher.h"
#include <vector>
#include <cstdint>

namespace fingerprint {

// Full single-finger pipeline result
struct CaptureResult {
    QualityResult  quality;
    LivenessResult liveness;
    TemplateResult templ;
    bool           accepted;  // quality ACCEPT + liveness pass + template success
};

// Run full pipeline: decode JPEG → quality → liveness → template
CaptureResult processFingerImage(const std::vector<uint8_t>& jpegBytes);

// Helpers
cv::Mat              decodeImage(const std::vector<uint8_t>& jpegBytes);
std::vector<uint8_t> encodeImage(const cv::Mat& image, int quality = 90);

} // namespace fingerprint
