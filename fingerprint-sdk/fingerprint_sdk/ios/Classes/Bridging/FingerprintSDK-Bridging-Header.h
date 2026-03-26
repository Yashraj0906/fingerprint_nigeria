// FingerprintSDK-Bridging-Header.h
// Exposes OpenCV C++ headers to Swift via Objective-C bridge.
// OpenCV must be imported BEFORE any UIKit/Foundation headers to avoid conflicts.

#ifdef __cplusplus
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdocumentation"
#import <opencv2/opencv.hpp>
#import <opencv2/imgproc/imgproc.hpp>
#import <opencv2/core/core.hpp>
#pragma clang diagnostic pop
#endif
