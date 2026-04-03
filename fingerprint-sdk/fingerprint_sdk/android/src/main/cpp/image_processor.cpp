#include "image_processor.h"
#include <cmath>

namespace fingerprint {

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

cv::Mat ImageProcessor::toGrayscale(const cv::Mat& input) {
    if (input.channels() == 1) return input.clone();
    cv::Mat gray;
    cv::cvtColor(input, gray, cv::COLOR_BGR2GRAY);
    return gray;
}

cv::Mat ImageProcessor::applyCLAHE(const cv::Mat& gray) {
    cv::Ptr<cv::CLAHE> clahe = cv::createCLAHE(3.0, cv::Size(8, 8));
    cv::Mat out;
    clahe->apply(gray, out);
    return out;
}

double ImageProcessor::estimateRidgeFrequency(const cv::Mat& gray) {
    // FFT → find peak spatial frequency in the ridge-spacing band (5-18 px)
    cv::Mat padded;
    int m = cv::getOptimalDFTSize(gray.rows);
    int n = cv::getOptimalDFTSize(gray.cols);
    cv::copyMakeBorder(gray, padded, 0, m - gray.rows, 0, n - gray.cols,
                       cv::BORDER_CONSTANT, cv::Scalar::all(0));

    cv::Mat planes[] = { cv::Mat_<float>(padded),
                         cv::Mat::zeros(padded.size(), CV_32F) };
    cv::Mat complexI;
    cv::merge(planes, 2, complexI);
    cv::dft(complexI, complexI);
    cv::split(complexI, planes);

    cv::Mat magI;
    cv::magnitude(planes[0], planes[1], magI);
    magI += cv::Scalar::all(1);
    cv::log(magI, magI);

    int cx = magI.cols / 2;
    int cy = magI.rows / 2;

    // shift quadrants so DC is at centre
    cv::Mat q0(magI, cv::Rect(0,  0,  cx, cy));
    cv::Mat q1(magI, cv::Rect(cx, 0,  cx, cy));
    cv::Mat q2(magI, cv::Rect(0,  cy, cx, cy));
    cv::Mat q3(magI, cv::Rect(cx, cy, cx, cy));
    cv::Mat tmp;
    q0.copyTo(tmp); q3.copyTo(q0); tmp.copyTo(q3);
    q1.copyTo(tmp); q2.copyTo(q1); tmp.copyTo(q2);

    float bestVal = 0;
    int   bestR   = 10;
    int   rMin    = std::max(1, magI.rows / 18);
    int   rMax    = magI.rows / 5;

    for (int r = rMin; r <= rMax; r++) {
        float ring  = 0;
        int   count = 0;
        for (int y = cy - r - 1; y <= cy + r + 1; y++) {
            for (int x = cx - r - 1; x <= cx + r + 1; x++) {
                if (y < 0 || y >= magI.rows || x < 0 || x >= magI.cols) continue;
                float dr = std::sqrt((float)((y - cy) * (y - cy) +
                                             (x - cx) * (x - cx)));
                if (std::abs(dr - r) < 0.5f) { ring += magI.at<float>(y, x); count++; }
            }
        }
        if (count > 0 && ring / count > bestVal) {
            bestVal = ring / count;
            bestR   = r;
        }
    }

    double freq = (bestR > 0) ? (double)magI.rows / bestR : 10.0;
    return std::max(5.0, std::min(18.0, freq));
}

cv::Mat ImageProcessor::applyGaborBank(const cv::Mat& gray, double ridgeFreq) {
    cv::Mat grayF;
    gray.convertTo(grayF, CV_32F, 1.0 / 255.0);

    cv::Mat result = cv::Mat::zeros(gray.size(), CV_32F);

    double sigma = 0.56 * ridgeFreq;
    int    ksize = (int)(6 * sigma + 1) | 1;   // force odd
    ksize = (ksize < 3) ? 3 : (ksize > 31) ? 31 : ksize;

    for (int i = 0; i < 8; i++) {
        double theta = i * CV_PI / 8.0;
        cv::Mat kernel = cv::getGaborKernel(cv::Size(ksize, ksize),
                                            sigma, theta,
                                            ridgeFreq, 1.0, 0, CV_32F);
        cv::Mat filtered;
        cv::filter2D(grayF, filtered, CV_32F, kernel);
        result = cv::max(result, filtered);
    }

    cv::Mat out;
    cv::normalize(result, out, 0, 255, cv::NORM_MINMAX, CV_8U);
    return out;
}

cv::Mat ImageProcessor::skeletonize(const cv::Mat& binary) {
    // Zhang-Suen thinning
    cv::Mat img;
    binary.copyTo(img);
    img /= 255; // values 0 or 1

    cv::Mat prev = cv::Mat::zeros(img.size(), CV_8U);
    cv::Mat diff;

    do {
        for (int pass = 0; pass < 2; pass++) {
            cv::Mat marker = cv::Mat::zeros(img.size(), CV_8U);
            for (int i = 1; i < img.rows - 1; i++) {
                for (int j = 1; j < img.cols - 1; j++) {
                    if (!img.at<uint8_t>(i, j)) continue;

                    uint8_t p2 = img.at<uint8_t>(i-1, j  );
                    uint8_t p3 = img.at<uint8_t>(i-1, j+1);
                    uint8_t p4 = img.at<uint8_t>(i,   j+1);
                    uint8_t p5 = img.at<uint8_t>(i+1, j+1);
                    uint8_t p6 = img.at<uint8_t>(i+1, j  );
                    uint8_t p7 = img.at<uint8_t>(i+1, j-1);
                    uint8_t p8 = img.at<uint8_t>(i,   j-1);
                    uint8_t p9 = img.at<uint8_t>(i-1, j-1);

                    uint8_t nb[9] = {0, p2, p3, p4, p5, p6, p7, p8, p9};
                    int B = p2+p3+p4+p5+p6+p7+p8+p9;
                    int A = 0;
                    for (int k = 1; k <= 8; k++)
                        A += (nb[k] == 0 && nb[k % 8 + 1] == 1) ? 1 : 0;

                    bool cond1 = (A == 1);
                    bool cond2 = (B >= 2 && B <= 6);
                    bool cond3, cond4;
                    if (pass == 0) {
                        cond3 = (p2 * p4 * p6) == 0;
                        cond4 = (p4 * p6 * p8) == 0;
                    } else {
                        cond3 = (p2 * p4 * p8) == 0;
                        cond4 = (p2 * p6 * p8) == 0;
                    }

                    if (cond1 && cond2 && cond3 && cond4)
                        marker.at<uint8_t>(i, j) = 1;
                }
            }
            img &= ~marker;
        }
        cv::absdiff(img, prev, diff);
        img.copyTo(prev);
    } while (cv::countNonZero(diff) > 0);

    return img * 255;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

cv::Mat ImageProcessor::enhanceForDisplay(const cv::Mat& input) {
    cv::Mat gray = toGrayscale(input);
    cv::Mat bilateral;
    cv::bilateralFilter(gray, bilateral, 9, 50, 50);
    return applyCLAHE(bilateral);
}

cv::Mat ImageProcessor::enhanceForEncoding(const cv::Mat& input) {
    cv::Mat gray = toGrayscale(input);

    cv::Mat bilateral;
    cv::bilateralFilter(gray, bilateral, 9, 50, 50);

    cv::Mat clahe = applyCLAHE(bilateral);

    double  ridgeFreq = estimateRidgeFrequency(clahe);
    cv::Mat gabor     = applyGaborBank(clahe, ridgeFreq);

    cv::Mat binary;
    cv::adaptiveThreshold(gabor, binary, 255,
                          cv::ADAPTIVE_THRESH_GAUSSIAN_C,
                          cv::THRESH_BINARY, 11, 2);

    // Ridges should be white; invert if background is brighter
    if (cv::mean(binary)[0] > 128)
        cv::bitwise_not(binary, binary);

    cv::Mat kernel = cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(3, 3));
    cv::Mat opened;
    cv::morphologyEx(binary, opened, cv::MORPH_OPEN, kernel);

    return skeletonize(opened);
}

cv::Mat ImageProcessor::computeOrientationField(const cv::Mat& gray, int blockSize) {
    cv::Mat gx, gy;
    cv::Sobel(gray, gx, CV_32F, 1, 0, 3);
    cv::Sobel(gray, gy, CV_32F, 0, 1, 3);

    int rows = (gray.rows + blockSize - 1) / blockSize;
    int cols = (gray.cols + blockSize - 1) / blockSize;
    cv::Mat field(rows, cols, CV_32F, cv::Scalar(0));

    for (int i = 0; i < rows; i++) {
        for (int j = 0; j < cols; j++) {
            int y0 = i * blockSize;
            int x0 = j * blockSize;
            int y1 = std::min(y0 + blockSize, gray.rows);
            int x1 = std::min(x0 + blockSize, gray.cols);

            float Gxy = 0, Gxx_yy = 0;
            for (int y = y0; y < y1; y++) {
                for (int x = x0; x < x1; x++) {
                    float dx = gx.at<float>(y, x);
                    float dy = gy.at<float>(y, x);
                    Gxy    += 2 * dx * dy;
                    Gxx_yy += dx * dx - dy * dy;
                }
            }
            field.at<float>(i, j) =
                0.5f * std::atan2(Gxy, Gxx_yy) + (float)CV_PI / 2.0f;
        }
    }
    return field;
}

} // namespace fingerprint
