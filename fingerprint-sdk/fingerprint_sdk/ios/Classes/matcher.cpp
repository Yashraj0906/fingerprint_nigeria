#include "matcher.h"
#include <cmath>
#include <algorithm>

namespace fingerprint {

float Matcher::angleDiff(float a, float b) {
    float d = std::abs(a - b);
    if (d > (float)CV_PI) d = 2.0f * (float)CV_PI - d;
    return d;
}

MatchResult Matcher::matchMinutiae(const std::vector<Minutia>& a,
                                   const std::vector<Minutia>& b) {
    MatchResult result{};
    result.totalMinutiaeA = (int)a.size();
    result.totalMinutiaeB = (int)b.size();

    if (a.empty() || b.empty()) {
        result.score   = 0.0f;
        result.isMatch = false;
        return result;
    }

    constexpr float DIST_THRESH  = 20.0f;                        // pixels
    constexpr float ANGLE_THRESH = 30.0f * (float)CV_PI / 180.0f; // radians

    std::vector<bool> usedB(b.size(), false);

    for (const auto& ma : a) {
        float bestDist = 1e9f;
        int   bestIdx  = -1;

        for (int j = 0; j < (int)b.size(); j++) {
            if (usedB[j]) continue;
            float dx = (float)(ma.x - b[j].x);
            float dy = (float)(ma.y - b[j].y);
            float d  = std::sqrt(dx * dx + dy * dy);
            if (d < bestDist) { bestDist = d; bestIdx = j; }
        }

        if (bestIdx >= 0 && bestDist < DIST_THRESH) {
            if (angleDiff(ma.angle, b[bestIdx].angle) < ANGLE_THRESH) {
                result.matchedPairs++;
                usedB[bestIdx] = true;
            }
        }
    }

    int maxCount   = std::max((int)a.size(), (int)b.size());
    result.score   = (maxCount > 0) ? (float)result.matchedPairs / maxCount : 0.0f;
    result.isMatch = result.score >= 0.35f;
    return result;
}

MatchResult Matcher::match(const std::string& templateA,
                           const std::string& templateB) {
    auto a = TemplateEncoder::decodeTemplate(templateA);
    auto b = TemplateEncoder::decodeTemplate(templateB);
    return matchMinutiae(a, b);
}

MatchResult Matcher::matchMulti(const std::vector<std::string>& templatesA,
                                const std::vector<std::string>& templatesB) {
    MatchResult result{};
    if (templatesA.empty() || templatesB.empty()) return result;

    float totalScore = 0.0f;
    int   count      = (int)std::min(templatesA.size(), templatesB.size());

    for (int i = 0; i < count; i++) {
        auto r = match(templatesA[i], templatesB[i]);
        totalScore += r.score;
    }

    result.score   = (count > 0) ? totalScore / count : 0.0f;
    result.isMatch = result.score >= 0.35f;
    return result;
}

} // namespace fingerprint
