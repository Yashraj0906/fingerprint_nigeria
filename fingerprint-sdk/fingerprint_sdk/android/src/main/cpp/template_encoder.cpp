#include "template_encoder.h"
#include "fingerprint_core.h"
#include "quality_analyzer.h"
#include "liveness_detector.h"
#include <cmath>
#include <algorithm>
#include <map>

// ---------------------------------------------------------------------------
// Base64 helpers (self-contained, no external dependency)
// ---------------------------------------------------------------------------
static const std::string B64_CHARS =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static std::string b64Encode(const std::vector<uint8_t>& data) {
    std::string out;
    out.reserve(((data.size() + 2) / 3) * 4);
    int val = 0, valb = -6;
    for (uint8_t c : data) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            out.push_back(B64_CHARS[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6)
        out.push_back(B64_CHARS[((val << 8) >> (valb + 8)) & 0x3F]);
    while (out.size() % 4) out.push_back('=');
    return out;
}

static std::vector<uint8_t> b64Decode(const std::string& s) {
    std::vector<uint8_t> out;
    std::vector<int> T(256, -1);
    for (int i = 0; i < 64; i++) T[(unsigned char)B64_CHARS[i]] = i;
    int val = 0, valb = -8;
    for (unsigned char c : s) {
        if (T[c] == -1) break;
        val = (val << 6) + T[c];
        valb += 6;
        if (valb >= 0) {
            out.push_back((val >> valb) & 0xFF);
            valb -= 8;
        }
    }
    return out;
}

// ---------------------------------------------------------------------------

namespace fingerprint {

int TemplateEncoder::crossingNumber(const cv::Mat& skel, int x, int y) {
    // 8-neighbour crossing number; CN=1 → ending, CN=3 → bifurcation
    uint8_t nb[9];
    nb[1] = skel.at<uint8_t>(y-1, x  ) > 0 ? 1 : 0;
    nb[2] = skel.at<uint8_t>(y-1, x+1) > 0 ? 1 : 0;
    nb[3] = skel.at<uint8_t>(y,   x+1) > 0 ? 1 : 0;
    nb[4] = skel.at<uint8_t>(y+1, x+1) > 0 ? 1 : 0;
    nb[5] = skel.at<uint8_t>(y+1, x  ) > 0 ? 1 : 0;
    nb[6] = skel.at<uint8_t>(y+1, x-1) > 0 ? 1 : 0;
    nb[7] = skel.at<uint8_t>(y,   x-1) > 0 ? 1 : 0;
    nb[8] = skel.at<uint8_t>(y-1, x-1) > 0 ? 1 : 0;

    int cn = 0;
    for (int k = 1; k <= 8; k++)
        cn += std::abs((int)nb[k] - (int)nb[k % 8 + 1]);
    return cn / 2;
}

float TemplateEncoder::followRidge(const cv::Mat& skel,
                                   int sx, int sy,
                                   int px, int py,
                                   int steps) {
    static const int dx8[8] = {0, 1, 1, 1, 0,-1,-1,-1};
    static const int dy8[8] = {-1,-1,0, 1, 1, 1, 0,-1};

    int x = sx, y = sy, ppx = px, ppy = py;
    float totalAngle = 0.0f;

    for (int s = 0; s < steps; s++) {
        int nx = -1, ny = -1;
        for (int d = 0; d < 8; d++) {
            int cx = x + dx8[d];
            int cy = y + dy8[d];
            if (cx == ppx && cy == ppy) continue;
            if (cx < 0 || cy < 0 || cx >= skel.cols || cy >= skel.rows) continue;
            if (skel.at<uint8_t>(cy, cx) > 0) { nx = cx; ny = cy; break; }
        }
        if (nx == -1) break;
        totalAngle += std::atan2((float)(ny - y), (float)(nx - x));
        ppx = x; ppy = y;
        x = nx; y = ny;
    }
    return totalAngle;
}

std::vector<Minutia>
TemplateEncoder::extractMinutiae(const cv::Mat& skel) {
    std::vector<Minutia> result;
    const int margin = 15;

    for (int y = margin; y < skel.rows - margin; y++) {
        for (int x = margin; x < skel.cols - margin; x++) {
            if (skel.at<uint8_t>(y, x) == 0) continue;

            int cn = crossingNumber(skel, x, y);
            if (cn != 1 && cn != 3) continue;

            // Ridge support: need >=12 skeleton pixels in 16×16 neighbourhood
            int x0 = std::max(0, x - 8), y0 = std::max(0, y - 8);
            cv::Rect roi16(x0, y0,
                           std::min(16, skel.cols - x0),
                           std::min(16, skel.rows - y0));
            if (cv::countNonZero(skel(roi16)) < 12) continue;

            // Follow ridge 7 steps to get stable angle
            float rawAngle = followRidge(skel, x, y, x - 1, y, 7);
            float angle = (float)std::fmod(rawAngle + 2.0 * CV_PI, 2.0 * CV_PI);

            // Local density in 24×24 window → quality
            int qx = std::max(0, x - 12), qy = std::max(0, y - 12);
            cv::Rect roi24(qx, qy,
                           std::min(24, skel.cols - qx),
                           std::min(24, skel.rows - qy));
            int density = cv::countNonZero(skel(roi24));
            uint8_t quality = (uint8_t)std::min(100, density * 2);

            Minutia m;
            m.x       = x;
            m.y       = y;
            m.angle   = angle;
            m.quality = quality;
            m.type    = (cn == 1) ? MinutiaeType::ENDING : MinutiaeType::BIFURCATION;
            result.push_back(m);
        }
    }
    return result;
}

std::vector<Minutia>
TemplateEncoder::filterMinutiae(const std::vector<Minutia>& raw,
                                int width, int height) {
    // 1. Non-maximum suppression within 12 px radius
    std::vector<bool> suppressed(raw.size(), false);
    for (size_t i = 0; i < raw.size(); i++) {
        if (suppressed[i]) continue;
        for (size_t j = i + 1; j < raw.size(); j++) {
            if (suppressed[j]) continue;
            float dx = (float)(raw[i].x - raw[j].x);
            float dy = (float)(raw[i].y - raw[j].y);
            if (dx * dx + dy * dy < 144.0f) {
                size_t worst = (raw[i].quality < raw[j].quality) ? i : j;
                suppressed[worst] = true;
            }
        }
    }

    std::vector<Minutia> filtered;
    for (size_t i = 0; i < raw.size(); i++)
        if (!suppressed[i]) filtered.push_back(raw[i]);

    // 2. Spatial distribution: max 5 per grid cell (4×4 grid)
    int cellW = std::max(1, width  / 4);
    int cellH = std::max(1, height / 4);

    std::sort(filtered.begin(), filtered.end(),
              [](const Minutia& a, const Minutia& b){
                  return a.quality > b.quality;
              });

    std::map<std::pair<int,int>, int> cellCount;
    std::vector<Minutia> spatial;
    for (const auto& m : filtered) {
        auto cell = std::make_pair(m.x / cellW, m.y / cellH);
        if (cellCount[cell] < 5) {
            spatial.push_back(m);
            cellCount[cell]++;
        }
    }

    // 3. Hard cap at 80 minutiae (ISO limit)
    if (spatial.size() > 80) spatial.resize(80);
    return spatial;
}

std::string
TemplateEncoder::encodeISO19794(const std::vector<Minutia>& minutiae,
                                int width, int height) {
    // ISO 19794-2:2005  — simplified FMR binary layout
    // 30-byte header + 6 bytes per minutia
    int totalBytes = 30 + 6 * (int)minutiae.size();
    std::vector<uint8_t> buf(totalBytes, 0);

    // Magic "FMR\0" + version " 20\0"
    buf[0]='F'; buf[1]='M'; buf[2]='R'; buf[3]=0;
    buf[4]=' '; buf[5]='2'; buf[6]='0'; buf[7]=0;

    // Total record length (4 bytes big-endian)
    buf[8]  = (totalBytes >> 24) & 0xFF;
    buf[9]  = (totalBytes >> 16) & 0xFF;
    buf[10] = (totalBytes >>  8) & 0xFF;
    buf[11] =  totalBytes        & 0xFF;

    // Reserved 2 bytes
    buf[12] = buf[13] = 0;

    // Image dimensions
    buf[14] = (width  >> 8) & 0xFF;  buf[15] = width  & 0xFF;
    buf[16] = (height >> 8) & 0xFF;  buf[17] = height & 0xFF;

    // Resolution: 197 ppi
    buf[18] = 0; buf[19] = 197;
    buf[20] = 0; buf[21] = 197;

    buf[22] = 1;    // number of finger views
    buf[23] = 0;    // view number
    buf[24] = 0;    // impression type (live plain)
    buf[25] = 80;   // finger quality
    buf[26] = (uint8_t)minutiae.size();
    buf[27] = buf[28] = buf[29] = 0; // reserved

    // Minutiae records (6 bytes each)
    int offset = 30;
    for (const auto& m : minutiae) {
        uint8_t typeCode = (m.type == MinutiaeType::ENDING) ? 1 : 3;

        // Bytes 0-1: type[2] | x[14]
        uint16_t xt = ((uint16_t)typeCode << 14) | (uint16_t)(m.x & 0x3FFF);
        buf[offset]   = (xt >> 8) & 0xFF;
        buf[offset+1] = xt        & 0xFF;

        // Bytes 2-3: y[14] (2 reserved bits = 0)
        uint16_t yt = (uint16_t)(m.y & 0x3FFF);
        buf[offset+2] = (yt >> 8) & 0xFF;
        buf[offset+3] = yt        & 0xFF;

        // Byte 4: angle mapped 0-255
        buf[offset+4] = (uint8_t)(m.angle / (2.0f * (float)CV_PI) * 255.0f);

        // Byte 5: quality
        buf[offset+5] = m.quality;
        offset += 6;
    }

    return b64Encode(buf);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

TemplateResult TemplateEncoder::extractTemplate(const cv::Mat& image,
                                                int w, int h) {
    TemplateResult result{};
    result.success = false;

    int width  = (w > 0) ? w : image.cols;
    int height = (h > 0) ? h : image.rows;

    cv::Mat skeleton = ImageProcessor::enhanceForEncoding(image);
    if (skeleton.empty()) {
        result.errorMessage = "Skeletonization failed";
        return result;
    }

    auto rawMinutiae = extractMinutiae(skeleton);
    if ((int)rawMinutiae.size() < 10) {
        result.errorMessage = "Insufficient minutiae: " +
                               std::to_string(rawMinutiae.size());
        return result;
    }

    result.minutiae = filterMinutiae(rawMinutiae, width, height);
    if ((int)result.minutiae.size() < 10) {
        result.errorMessage = "Insufficient minutiae after filtering: " +
                               std::to_string(result.minutiae.size());
        return result;
    }

    result.base64Template = encodeISO19794(result.minutiae, width, height);
    result.minutiaeCount  = (int)result.minutiae.size();
    result.success        = true;
    return result;
}

std::vector<Minutia>
TemplateEncoder::decodeTemplate(const std::string& base64Template) {
    std::vector<Minutia> out;
    auto buf = b64Decode(base64Template);
    if ((int)buf.size() < 30) return out;

    int numMinutiae   = buf[26];
    int expectedBytes = 30 + 6 * numMinutiae;
    if ((int)buf.size() < expectedBytes) return out;

    for (int i = 0; i < numMinutiae; i++) {
        int offset = 30 + i * 6;
        Minutia m;

        uint16_t xt      = ((uint16_t)buf[offset] << 8) | buf[offset+1];
        uint8_t  typeCode = (uint8_t)((xt >> 14) & 0x3);
        m.x    = xt & 0x3FFF;
        m.type = (typeCode == 1) ? MinutiaeType::ENDING : MinutiaeType::BIFURCATION;

        uint16_t yt = ((uint16_t)buf[offset+2] << 8) | buf[offset+3];
        m.y = yt & 0x3FFF;

        m.angle   = buf[offset+4] / 255.0f * 2.0f * (float)CV_PI;
        m.quality = buf[offset+5];

        out.push_back(m);
    }
    return out;
}

} // namespace fingerprint
