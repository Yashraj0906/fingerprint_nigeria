// OpenCVWrapper.mm
// Objective-C++ implementation — bridges OpenCV C++ to Swift.

#import "OpenCVWrapper.h"

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdocumentation"
#import <opencv2/opencv.hpp>
#pragma clang diagnostic pop

// ─── CGImage ↔ cv::Mat Helpers ────────────────────────────────────────────────

static cv::Mat cgImageToMat(CGImageRef image) {
    size_t width  = CGImageGetWidth(image);
    size_t height = CGImageGetHeight(image);

    cv::Mat mat((int)height, (int)width, CV_8UC1);

    CGColorSpaceRef space = CGColorSpaceCreateDeviceGray();
    CGContextRef ctx = CGBitmapContextCreate(
        mat.data, width, height, 8, width, space, kCGImageAlphaNone
    );
    CGContextDrawImage(ctx, CGRectMake(0, 0, width, height), image);
    CGContextRelease(ctx);
    CGColorSpaceRelease(space);
    return mat;
}

static CGImageRef matToCGImage(const cv::Mat& mat) {
    cv::Mat display;
    if (mat.channels() == 1) {
        display = mat;
    } else {
        cv::cvtColor(mat, display, cv::COLOR_BGR2GRAY);
    }

    CGColorSpaceRef space = CGColorSpaceCreateDeviceGray();
    CGDataProviderRef provider = CGDataProviderCreateWithData(
        nullptr, display.data, display.total() * display.elemSize(),
        [](void*, const void*, size_t) {}
    );
    CGImageRef image = CGImageCreate(
        display.cols, display.rows, 8, 8, display.cols,
        space, kCGBitmapByteOrderDefault, provider,
        nullptr, false, kCGRenderingIntentDefault
    );
    CGDataProviderRelease(provider);
    CGColorSpaceRelease(space);
    return image;
}

// ─── OpenCVWrapper Implementation ─────────────────────────────────────────────

@implementation OpenCVWrapper

+ (CGImageRef)enhanceRidges:(CGImageRef)grayImage {
    cv::Mat gray = cgImageToMat(grayImage);
    cv::Mat gray32;
    gray.convertTo(gray32, CV_32F);

    // 4-angle Sobel bank (0°, 45°, 90°, 135°)
    cv::Mat result = cv::Mat::zeros(gray.size(), CV_32F);
    int dxDy[4][2] = {{1,0},{1,1},{0,1},{-1,1}};

    for (auto& d : dxDy) {
        cv::Mat sx, sy, mag;
        cv::Sobel(gray32, sx, CV_32F, abs(d[0]), 0, 3);
        cv::Sobel(gray32, sy, CV_32F, 0, abs(d[1]), 3);
        cv::magnitude(sx, sy, mag);
        cv::max(result, mag, result);
    }

    cv::Mat out;
    cv::normalize(result, out, 0, 255, cv::NORM_MINMAX, CV_8U);
    return matToCGImage(out);
}

+ (CGImageRef)adaptiveThreshold:(CGImageRef)grayImage {
    cv::Mat gray = cgImageToMat(grayImage);
    cv::Mat binary;
    cv::adaptiveThreshold(gray, binary, 255,
        cv::ADAPTIVE_THRESH_GAUSSIAN_C, cv::THRESH_BINARY_INV, 11, 2);
    return matToCGImage(binary);
}

+ (CGImageRef)skeletonize:(CGImageRef)binaryImage {
    cv::Mat src = cgImageToMat(binaryImage);
    cv::Mat skeleton = cv::Mat::zeros(src.size(), CV_8U);
    cv::Mat temp, eroded;
    cv::Mat element = cv::getStructuringElement(cv::MORPH_CROSS, cv::Size(3, 3));
    cv::Mat current = src.clone();

    bool done = false;
    while (!done) {
        cv::erode(current, eroded, element);
        cv::dilate(eroded, temp, element);
        cv::subtract(current, temp, temp);
        cv::bitwise_or(skeleton, temp, skeleton);
        eroded.copyTo(current);
        done = (cv::countNonZero(current) == 0);
    }
    return matToCGImage(skeleton);
}

+ (CGImageRef)detectEdges:(CGImageRef)grayImage {
    cv::Mat gray = cgImageToMat(grayImage);
    cv::Mat edges;
    cv::Canny(gray, edges, 40, 120, 3);
    return matToCGImage(edges);
}

+ (NSArray<NSDictionary *> *)segmentFingers:(CVPixelBufferRef)pixelBuffer
                                 maxFingers:(int)maxFingers {
    CVPixelBufferLockBaseAddress(pixelBuffer, kCVPixelBufferLock_ReadOnly);

    size_t width      = CVPixelBufferGetWidth(pixelBuffer);
    size_t height     = CVPixelBufferGetHeight(pixelBuffer);
    size_t bytesPerRow = CVPixelBufferGetBytesPerRow(pixelBuffer);
    uint8_t* base     = (uint8_t*)CVPixelBufferGetBaseAddress(pixelBuffer);

    // Build BGR Mat from BGRA pixel buffer
    cv::Mat bgra((int)height, (int)width, CV_8UC4, base, bytesPerRow);
    cv::Mat bgr;
    cv::cvtColor(bgra, bgr, cv::COLOR_BGRA2BGR);
    CVPixelBufferUnlockBaseAddress(pixelBuffer, kCVPixelBufferLock_ReadOnly);

    // YCrCb skin segmentation
    cv::Mat ycrcb;
    cv::cvtColor(bgr, ycrcb, cv::COLOR_BGR2YCrCb);
    cv::Mat skinMask;
    cv::inRange(ycrcb, cv::Scalar(0, 133, 77), cv::Scalar(255, 173, 127), skinMask);

    // Morphological cleanup
    cv::Mat closeKernel = cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(7, 7));
    cv::Mat openKernel  = cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(5, 5));
    cv::morphologyEx(skinMask, skinMask, cv::MORPH_CLOSE, closeKernel);
    cv::morphologyEx(skinMask, skinMask, cv::MORPH_OPEN,  openKernel);

    std::vector<std::vector<cv::Point>> contours;
    cv::findContours(skinMask, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);

    double imageArea = (double)(width * height);
    double minArea   = imageArea * 0.005;
    double maxArea   = imageArea * 0.40;

    // Filter and sort
    std::vector<std::pair<cv::Rect, double>> valid;
    for (auto& c : contours) {
        cv::Rect rect = cv::boundingRect(c);
        double area   = cv::contourArea(c);
        double aspect = (double)rect.width / rect.height;
        if (area >= minArea && area <= maxArea && aspect < 1.2 && rect.height > rect.width) {
            valid.push_back({rect, area});
        }
    }
    std::sort(valid.begin(), valid.end(), [](auto& a, auto& b) { return a.first.x < b.first.x; });

    NSMutableArray* result = [NSMutableArray array];
    int count = MIN((int)valid.size(), maxFingers);
    for (int i = 0; i < count; i++) {
        cv::Rect r = valid[i].first;
        [result addObject:@{
            @"x": @((double)r.x),
            @"y": @((double)r.y),
            @"w": @((double)r.width),
            @"h": @((double)r.height),
            @"area": @(valid[i].second)
        }];
    }
    return result;
}

@end
