// OpenCVWrapper.h
// Objective-C interface that wraps OpenCV C++ calls for Swift consumption.

#import <Foundation/Foundation.h>
#import <CoreVideo/CoreVideo.h>
#import <CoreGraphics/CoreGraphics.h>
#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface OpenCVWrapper : NSObject

/// Multi-angle Sobel ridge enhancement. Returns enhanced grayscale CGImage.
+ (nullable CGImageRef)enhanceRidges:(CGImageRef)grayImage CF_RETURNS_RETAINED;

/// Adaptive Gaussian threshold → binary image (white ridges on black).
+ (nullable CGImageRef)adaptiveThreshold:(CGImageRef)grayImage CF_RETURNS_RETAINED;

/// Zhang-Suen skeletonisation on binary image.
+ (nullable CGImageRef)skeletonize:(CGImageRef)binaryImage CF_RETURNS_RETAINED;

/// Canny edge detection for ridge map.
+ (nullable CGImageRef)detectEdges:(CGImageRef)grayImage CF_RETURNS_RETAINED;

/// YCrCb skin segmentation → array of {x,y,w,h,area} dicts, sorted left→right.
+ (NSArray<NSDictionary *> *)segmentFingers:(CVPixelBufferRef)pixelBuffer
                                 maxFingers:(int)maxFingers;

@end

NS_ASSUME_NONNULL_END
