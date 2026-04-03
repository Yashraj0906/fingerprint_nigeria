#import <Foundation/Foundation.h>
#import <CoreVideo/CoreVideo.h>

@interface FingerprintCoreWrapper : NSObject

+ (nonnull NSDictionary *)evaluateLivenessWithGray:(nonnull NSData *)grayData
                                               bgr:(nonnull NSData *)bgrData
                                           fullBgr:(nonnull NSData *)fullBgrData
                                             width:(int)w
                                            height:(int)h
                                          fullWidth:(int)fw
                                         fullHeight:(int)fh
                                          handMode:(nonnull NSString *)handMode;

+ (nonnull NSDictionary *)analyzeQualityWithImage:(nonnull NSData *)imageData
                                            width:(int)w
                                           height:(int)h;

+ (nullable NSString *)extractTemplateWithImage:(nonnull NSData *)imageData
                                           width:(int)w
                                          height:(int)h;

@end
