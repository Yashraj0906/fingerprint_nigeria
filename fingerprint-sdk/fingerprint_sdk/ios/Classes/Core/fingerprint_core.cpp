#include "fingerprint_core.h"

namespace fingerprint {

cv::Mat decodeImage(const std::vector<uint8_t>& jpegBytes) {
    return cv::imdecode(jpegBytes, cv::IMREAD_COLOR);
}

std::vector<uint8_t> encodeImage(const cv::Mat& image, int quality) {
    std::vector<uint8_t> buf;
    std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, quality};
    cv::imencode(".jpg", image, buf, params);
    return buf;
}

CaptureResult processFingerImage(const std::vector<uint8_t>& jpegBytes) {
    CaptureResult result{};

    cv::Mat image = decodeImage(jpegBytes);
    if (image.empty()) {
        result.accepted = false;
        return result;
    }

    result.quality  = QualityAnalyzer::analyze(image);
    // Note: evaluate requires full image and cropped + hand mode. For simple processFingerImage, pass image to all and "Right" as default.
    result.liveness = LivenessDetector::evaluate(image, image, image, "Right");

    // Only run expensive template extraction when quality + liveness pass
    bool qualityOk  = (result.quality.decision != QualityDecision::REJECT);
    bool livenessOk = result.liveness.passed;

    if (qualityOk && livenessOk) {
        result.templ = TemplateEncoder::extractTemplate(image);
    }

    result.accepted = (result.quality.decision == QualityDecision::ACCEPT)
                      && livenessOk
                      && result.templ.success;
    return result;
}

} // namespace fingerprint
