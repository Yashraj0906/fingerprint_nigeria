#pragma once
#include "template_encoder.h"
#include <vector>
#include <string>

namespace fingerprint {

struct MatchResult {
    float score;            // 0.0 - 1.0
    bool  isMatch;          // score >= 0.35
    int   matchedPairs;
    int   totalMinutiaeA;
    int   totalMinutiaeB;
};

class Matcher {
public:
    // Match two ISO 19794-2 base64 templates (1:1)
    static MatchResult match(const std::string& templateA,
                             const std::string& templateB);

    // Average score across finger pairs (1:N multi-finger)
    static MatchResult matchMulti(const std::vector<std::string>& templatesA,
                                  const std::vector<std::string>& templatesB);

private:
    static MatchResult matchMinutiae(const std::vector<Minutia>& a,
                                     const std::vector<Minutia>& b);
    static float angleDiff(float a, float b);
};

} // namespace fingerprint
