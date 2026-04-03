#pragma once
// Use targeted includes to avoid ObjC 'NO' macro conflict with stitching headers
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <vector>
#include <string>
#include <cstdint>

namespace fingerprint {

enum class MinutiaeType : uint8_t {
    ENDING       = 1,
    BIFURCATION  = 3
};

struct Minutia {
    int   x;
    int   y;
    float angle;        // radians 0 - 2π
    uint8_t quality;    // 0-100
    MinutiaeType type;
};

struct TemplateResult {
    std::string          base64Template;  // ISO 19794-2 encoded as base64
    std::vector<Minutia> minutiae;
    int                  minutiaeCount;
    bool                 success;
    std::string          errorMessage;
};

class TemplateEncoder {
public:
    // Full pipeline: enhance → skeletonize → extract → filter → ISO encode
    static TemplateResult extractTemplate(const cv::Mat& image,
                                          int imageWidth  = 0,
                                          int imageHeight = 0);

    // Decode a base64 ISO 19794-2 template back to minutiae list
    static std::vector<Minutia> decodeTemplate(const std::string& base64Template);

private:
    static std::vector<Minutia> extractMinutiae(const cv::Mat& skeleton);
    static std::vector<Minutia> filterMinutiae(const std::vector<Minutia>& raw,
                                               int width, int height);
    static std::string encodeISO19794(const std::vector<Minutia>& minutiae,
                                      int width, int height);
    static int   crossingNumber(const cv::Mat& skeleton, int x, int y);
    static float followRidge(const cv::Mat& skeleton,
                             int startX, int startY,
                             int prevX,  int prevY,
                             int steps);
};

} // namespace fingerprint
