#import "FingerprintCoreWrapper.h"

// Include only what we actually use. Full opencv.hpp pulls in stitching headers
// that conflict with ObjC's '#define NO __objc_no' macro.
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>

#import "liveness_detector.h"
#import "quality_analyzer.h"
#import "template_encoder.h"

using namespace fingerprint;

@implementation FingerprintCoreWrapper

+ (nonnull NSDictionary *)evaluateLivenessWithGray:(nonnull NSData *)grayData
                                               bgr:(nonnull NSData *)bgrData
                                           fullBgr:(nonnull NSData *)fullBgrData
                                             width:(int)w
                                            height:(int)h
                                          fullWidth:(int)fw
                                         fullHeight:(int)fh
                                          handMode:(nonnull NSString *)handMode {
    
    cv::Mat gray(h, w, CV_8UC1, (void *)grayData.bytes);
    cv::Mat bgr(h, w, CV_8UC3, (void *)bgrData.bytes);
    cv::Mat fullBgr(fh, fw, CV_8UC3, (void *)fullBgrData.bytes);
    
    LivenessDetector detector;
    LivenessResult res = detector.evaluate(gray, bgr, fullBgr, [handMode UTF8String]);
    
    return @{
        @"passed": @(res.passed),
        @"score": @(res.confidence),
        @"reason": res.reason.empty() ? @"" : [NSString stringWithUTF8String:res.reason.c_str()]
    };
}

+ (nonnull NSDictionary *)analyzeQualityWithImage:(nonnull NSData *)imageData
                                            width:(int)w
                                           height:(int)h {
    
    cv::Mat image(h, w, CV_8UC3, (void *)imageData.bytes);
    
    QualityAnalyzer analyzer;
    QualityResult res = analyzer.analyze(image);
    
    NSString *decisionStr = (res.decision == QualityDecision::ACCEPT) ? @"ACCEPT" : 
                             (res.decision == QualityDecision::RETRY) ? @"RETRY" : @"REJECT";
    
    return @{
        @"blurScore": @(res.blurScore),
        @"contrastScore": @(res.contrastScore),
        @"ridgeClarityScore": @(res.ridgeClarityScore),
        @"coverageScore": @(res.coverageScore),
        @"orientationScore": @(res.orientationScore),
        @"compositeScore": @(res.compositeScore),
        @"decision": decisionStr,
        @"guidance": [NSString stringWithUTF8String:res.guidance.c_str()]
    };
}

+ (nullable NSString *)extractTemplateWithImage:(nonnull NSData *)imageData
                                           width:(int)w
                                          height:(int)h {
    
    cv::Mat image(h, w, CV_8UC3, (void *)imageData.bytes);
    
    TemplateEncoder encoder;
    TemplateResult res = encoder.extractTemplate(image);
    
    if (!res.success) return nil;
    
    return [NSString stringWithUTF8String:res.base64Template.c_str()];
}

@end
