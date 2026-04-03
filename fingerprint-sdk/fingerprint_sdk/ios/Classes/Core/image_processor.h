#pragma once
// Use targeted includes to avoid ObjC 'NO' macro conflict with stitching headers
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>

namespace fingerprint {

class ImageProcessor {
public:
    // Enhance image for UI display: bilateral filter + CLAHE
    static cv::Mat enhanceForDisplay(const cv::Mat& input);

    // Enhance image and skeletonize for minutiae extraction
    // Returns binary skeleton (0/255)
    static cv::Mat enhanceForEncoding(const cv::Mat& input);

    // Compute per-block ridge orientation field
    // Returns CV_32F mat with one angle per block (radians)
    static cv::Mat computeOrientationField(const cv::Mat& gray, int blockSize = 16);

private:
    static cv::Mat toGrayscale(const cv::Mat& input);
    static cv::Mat applyCLAHE(const cv::Mat& gray);
    static double  estimateRidgeFrequency(const cv::Mat& gray);
    static cv::Mat applyGaborBank(const cv::Mat& gray, double ridgeFreq);
    static cv::Mat skeletonize(const cv::Mat& binary);
};

} // namespace fingerprint
