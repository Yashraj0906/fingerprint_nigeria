#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

/** Result of a full fingerprint capture pipeline run. */
@interface FingerprintCaptureResult : NSObject

@property (nonatomic) float qualityScore;        ///< 0-100 composite
@property (nonatomic) float blurScore;
@property (nonatomic) float contrastScore;
@property (nonatomic) float ridgeClarityScore;
@property (nonatomic) float coverageScore;
@property (nonatomic) float orientationScore;
@property (nonatomic, strong) NSString* guidance; ///< user-facing message
@property (nonatomic) float livenessScore;        ///< 0.0-1.0
@property (nonatomic) BOOL  isLive;
@property (nonatomic) BOOL  accepted;
/// ISO 19794-2 template as base64 string, or nil if extraction failed.
@property (nonatomic, strong, nullable) NSString* templateBase64;

@end


/** Main SDK entry point. All methods are thread-safe. */
@interface FingerprintSDK : NSObject

/**
 * Run the full pipeline on a JPEG-encoded finger crop.
 *
 * @param jpegData  Raw JPEG bytes (e.g. from AVCaptureOutput or UIImageJPEGRepresentation)
 * @return          FingerprintCaptureResult with all scores and template
 */
+ (FingerprintCaptureResult*)processImage:(NSData*)jpegData;

/**
 * Match two ISO 19794-2 base64-encoded templates.
 *
 * @return  Score 0.0 – 1.0
 */
+ (float)matchTemplate:(NSString*)templateA
          withTemplate:(NSString*)templateB;

/**
 * Convenience: returns YES when score >= 0.35.
 */
+ (BOOL)isMatch:(NSString*)templateA
   withTemplate:(NSString*)templateB;

/**
 * Quick quality score only (skips liveness + template encoding).
 *
 * @return  Composite quality score 0-100
 */
+ (float)qualityScoreForImage:(NSData*)jpegData;

@end

NS_ASSUME_NONNULL_END
