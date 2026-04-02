// FingerprintSDK.mm — Objective-C++ bridge to the fingerprint C++ core
//
// MACRO COLLISION FIX
// -------------------
// OpenCV headers contain C++ identifiers (e.g. enum values named 'NO', 'YES',
// 'nil') that clash with Objective-C runtime macros on Apple platforms.
// We use push_macro/pop_macro to temporarily undefine those macros while the
// C++ headers are included, then restore them for the ObjC bridge code below.
#import "FingerprintSDK.h"   // pulls in Foundation → defines YES, NO, nil, Nil

#pragma push_macro("NO")
#pragma push_macro("YES")
#pragma push_macro("nil")
#pragma push_macro("Nil")
#undef NO
#undef YES
#undef nil
#undef Nil

#include "fingerprint_core.h"   // OpenCV-dependent C++ core

#pragma pop_macro("NO")
#pragma pop_macro("YES")
#pragma pop_macro("nil")
#pragma pop_macro("Nil")

// ---------------------------------------------------------------------------

@implementation FingerprintCaptureResult
@end

@implementation FingerprintSDK

+ (FingerprintCaptureResult*)processImage:(NSData*)jpegData {
    const uint8_t* bytes = reinterpret_cast<const uint8_t*>(jpegData.bytes);
    std::vector<uint8_t> jpeg(bytes, bytes + jpegData.length);

    fingerprint::CaptureResult cpp = fingerprint::processFingerImage(jpeg);

    FingerprintCaptureResult* r = [[FingerprintCaptureResult alloc] init];
    r.qualityScore      = cpp.quality.compositeScore;
    r.blurScore         = cpp.quality.blurScore;
    r.contrastScore     = cpp.quality.contrastScore;
    r.ridgeClarityScore = cpp.quality.ridgeClarityScore;
    r.coverageScore     = cpp.quality.coverageScore;
    r.orientationScore  = cpp.quality.orientationScore;
    r.guidance          = [NSString stringWithUTF8String:cpp.quality.guidance.c_str()];
    r.livenessScore     = cpp.liveness.confidence;
    r.isLive            = (BOOL)cpp.liveness.isLive;
    r.accepted          = (BOOL)cpp.accepted;
    r.templateBase64    = cpp.templ.success
        ? [NSString stringWithUTF8String:cpp.templ.base64Template.c_str()]
        : nil;
    return r;
}

+ (float)matchTemplate:(NSString*)templateA
          withTemplate:(NSString*)templateB {
    fingerprint::MatchResult res = fingerprint::Matcher::match(
        std::string(templateA.UTF8String),
        std::string(templateB.UTF8String));
    return res.score;
}

+ (BOOL)isMatch:(NSString*)templateA
   withTemplate:(NSString*)templateB {
    return [self matchTemplate:templateA withTemplate:templateB] >= 0.35f;
}

+ (float)qualityScoreForImage:(NSData*)jpegData {
    const uint8_t* bytes = reinterpret_cast<const uint8_t*>(jpegData.bytes);
    std::vector<uint8_t> jpeg(bytes, bytes + jpegData.length);

    cv::Mat img = fingerprint::decodeImage(jpeg);
    if (img.empty()) return 0.0f;

    fingerprint::QualityResult q = fingerprint::QualityAnalyzer::analyze(img);
    return q.compositeScore;
}

@end
