#include "LivenessDetector.hpp"
#include <cmath>
#include <iostream>

using namespace cv;
using namespace std;

bool LivenessDetector::_screen_replay_detection(const Mat& gray, const Mat& bgr, string& reason) {
    int h = gray.rows;
    int w = gray.cols;
    if (h < 64 || w < 64) return false;

    int crop_size = min({100, h, w});
    int cy = h / 2, cx = w / 2;
    int r_half = crop_size / 2;

    Rect roi(cx - r_half, cy - r_half, crop_size, crop_size);
    Mat gray_sm = gray(roi);
    Mat bgr_sm = bgr(roi);

    // Check 1: Blur uniformity (Laplacian variance)
    Mat lap;
    Laplacian(gray_sm, lap, CV_64F);
    Scalar mean, stddev;
    meanStdDev(lap, mean, stddev);
    double lap_var = stddev[0] * stddev[0];
    
    if (lap_var < 50.0) {
        reason = "Screen replay detected - missing 3D surface detail";
        return true;
    }

    // Check 2: High-Frequency Cross Energy (Phone Pixel Grid)
    Mat f;
    gray_sm.convertTo(f, CV_32F);
    Mat planes[] = {Mat_<float>(f), Mat::zeros(f.size(), CV_32F)};
    Mat complexI;
    merge(planes, 2, complexI);
    dft(complexI, complexI);

    // Compute magnitude
    split(complexI, planes);
    Mat mag;
    magnitude(planes[0], planes[1], mag);
    
    // Shift DFT
    int cxff = mag.cols / 2;
    int cyff = mag.rows / 2;
    Mat q0(mag, Rect(0, 0, cxff, cyff));
    Mat q1(mag, Rect(cxff, 0, cxff, cyff));
    Mat q2(mag, Rect(0, cyff, cxff, cyff));
    Mat q3(mag, Rect(cxff, cyff, cxff, cyff));
    Mat tmp;
    q0.copyTo(tmp); q3.copyTo(q0); tmp.copyTo(q3);
    q1.copyTo(tmp); q2.copyTo(q1); tmp.copyTo(q2);

    // Mask DC component
    circle(mag, Point(cxff, cyff), 15, Scalar(0), -1);

    double cross_energy = sum(mag(Rect(0, cyff - 2, mag.cols, 5)))[0] + 
                          sum(mag(Rect(cxff - 2, 0, 5, mag.rows)))[0];
    double total_energy = sum(mag)[0];

    if (total_energy > 1e-6) {
        double grid_ratio = cross_energy / total_energy;
        if (grid_ratio > 0.40) {
            reason = "Screen replay detected - pixel grid harmonics";
            return true;
        }
    }

    return false;
}

FingerprintResult LivenessDetector::analyzeFrame(const Mat& bgrImage, const string& hand, const string& mode) {
    FingerprintResult result;
    result.hand_detected = true;
    result.hand = hand;

    // ── HARD SCREEN BLOCK: Detect physical rectangular phone ───────────────
    Mat gray_full, blurred, edges;
    cvtColor(bgrImage, gray_full, COLOR_BGR2GRAY);
    GaussianBlur(gray_full, blurred, Size(5, 5), 0);
    Canny(blurred, edges, 50, 150);

    vector<vector<Point>> contours;
    findContours(edges, contours, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE);

    double img_area = bgrImage.rows * bgrImage.cols;
    bool screen_bezel_detected = false;

    for (const auto& c : contours) {
        double peri = arcLength(c, true);
        vector<Point> approx;
        approxPolyDP(c, approx, 0.04 * peri, true);
        if (approx.size() == 4 && contourArea(approx) > (img_area * 0.15)) {
            screen_bezel_detected = true;
            break;
        }
    }

    if (screen_bezel_detected) {
        result.guidance = "Screen replay detected - phone border found";
        return result;
    }

    // TODO: MediaPipe C++ Hands implementation goes here.
    // For now, returning the skeleton structure.
    
    return result;
}
