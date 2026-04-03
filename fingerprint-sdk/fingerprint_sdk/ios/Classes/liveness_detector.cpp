#include "liveness_detector.h"
#include <cmath>
#include <iostream>
#include <algorithm>

namespace fingerprint {

bool LivenessDetector::detectPhoneBezel(const cv::Mat& bgr_full) {
    if (bgr_full.empty()) return false;
    
    cv::Mat gray, blurred, edges;
    cv::cvtColor(bgr_full, gray, cv::COLOR_BGR2GRAY);
    cv::GaussianBlur(gray, blurred, cv::Size(5, 5), 0);
    cv::Canny(blurred, edges, 50, 150);

    std::vector<std::vector<cv::Point>> contours;
    cv::findContours(edges, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);

    double img_area = bgr_full.rows * bgr_full.cols;
    
    for (const auto& c : contours) {
        double peri = cv::arcLength(c, true);
        std::vector<cv::Point> approx;
        cv::approxPolyDP(c, approx, 0.04 * peri, true);
        
        if (approx.size() == 4) {
            double area = cv::contourArea(approx);
            if (area > (img_area * 0.15)) {
                return true; // Large rectangular border found
            }
        }
    }
    return false;
}

bool LivenessDetector::detectScreenReplay(const cv::Mat& gray, const cv::Mat& bgr, std::string& reason) {
    if (gray.rows < 64 || gray.cols < 64) return false;

    // Crop to center 100x100 to avoid edges and isolate sub-surface
    int crop_size = std::min({100, gray.rows, gray.cols});
    int cy = gray.rows / 2;
    int cx = gray.cols / 2;
    int r_half = crop_size / 2;

    cv::Rect roi(cx - r_half, cy - r_half, crop_size, crop_size);
    cv::Mat gray_sm = gray(roi);
    cv::Mat bgr_sm = bgr(roi);

    // Gradient kurtosis (screens lack 3D depth, uniform flat surface)
    cv::Mat lap;
    cv::Laplacian(gray_sm, lap, CV_64F);
    cv::Scalar mean, stddev;
    cv::meanStdDev(lap, mean, stddev);
    double lap_var = stddev[0] * stddev[0];

    if (lap_var < 50.0) {
        reason = "Screen replay detected - missing 3D surface detail";
        return true;
    }

    // High-Frequency Cross Energy (Detect OLED/LCD pixel grid)
    cv::Mat f;
    gray_sm.convertTo(f, CV_32F);
    cv::Mat planes[] = {cv::Mat_<float>(f), cv::Mat::zeros(f.size(), CV_32F)};
    cv::Mat complexI;
    cv::merge(planes, 2, complexI);
    cv::dft(complexI, complexI);

    cv::split(complexI, planes);
    cv::Mat mag;
    cv::magnitude(planes[0], planes[1], mag);
    
    // Shift DFT quadrants
    int cxff = mag.cols / 2;
    int cyff = mag.rows / 2;
    cv::Mat q0(mag, cv::Rect(0, 0, cxff, cyff));
    cv::Mat q1(mag, cv::Rect(cxff, 0, cxff, cyff));
    cv::Mat q2(mag, cv::Rect(0, cyff, cxff, cyff));
    cv::Mat q3(mag, cv::Rect(cxff, cyff, cxff, cyff));
    cv::Mat tmp;
    q0.copyTo(tmp); q3.copyTo(q0); tmp.copyTo(q3);
    q1.copyTo(tmp); q2.copyTo(q1); tmp.copyTo(q2);

    // Mask DC component
    cv::circle(mag, cv::Point(cxff, cyff), 15, cv::Scalar(0), -1);

    double cross_energy = cv::sum(mag(cv::Rect(0, cyff - 2, mag.cols, 5)))[0] + 
                          cv::sum(mag(cv::Rect(cxff - 2, 0, 5, mag.rows)))[0];
    double total_energy = cv::sum(mag)[0];

    if (total_energy > 1e-6) {
        double grid_ratio = cross_energy / total_energy;
        if (grid_ratio > 0.40) {
            reason = "Screen replay detected - pixel grid harmonics";
            return true;
        }
    }

    // RGB structural similarity check (Color noise correlation)
    std::vector<cv::Mat> bgr_channels;
    cv::split(bgr_sm, bgr_channels);
    
    cv::Mat b_lap, num_mat, denom_mat;
    cv::Laplacian(bgr_channels[0], b_lap, CV_32F);
    cv::multiply(b_lap, b_lap, num_mat);
    double b_energy = cv::sum(num_mat)[0];
    
    if (b_energy > 0) {
        cv::Mat g_lap, r_lap;
        cv::Laplacian(bgr_channels[1], g_lap, CV_32F);
        cv::Laplacian(bgr_channels[2], r_lap, CV_32F);
        
        cv::Mat g_num; cv::multiply(g_lap, g_lap, g_num);
        cv::Mat r_num; cv::multiply(r_lap, r_lap, r_num);
        
        double g_energy = cv::sum(g_num)[0];
        double r_energy = cv::sum(r_num)[0];
        
        // Unusually high blue energy is typical of RGB OLED pentiles under macro
        if (b_energy > (r_energy * 1.5) && b_energy > (g_energy * 1.5)) {
            reason = "Screen replay detected - RGB matrix anomaly";
            return true;
        }
    }

    return false;
}

bool LivenessDetector::detectSpectralDecayAnomaly(const cv::Mat& gray) {
    if (gray.rows < 64 || gray.cols < 64) return false;
    
    cv::Mat f;
    gray.convertTo(f, CV_32F);
    cv::Mat planes[] = {f, cv::Mat::zeros(f.size(), CV_32F)};
    cv::Mat complexI;
    cv::merge(planes, 2, complexI);
    cv::dft(complexI, complexI);
    
    cv::split(complexI, planes);
    cv::Mat mag;
    cv::magnitude(planes[0], planes[1], mag);
    
    int cx = mag.cols / 2;
    int cy = mag.rows / 2;
    
    // Simple 1D PSD proxy: compare annular ring energies
    double e_low = 0, e_high = 0;
    for (int y = 0; y < mag.rows; y++) {
        for (int x = 0; x < mag.cols; x++) {
            double r = std::sqrt(std::pow(x - cx, 2) + std::pow(y - cy, 2));
            float val = mag.at<float>(y, x);
            if (r > 10 && r <= 30) e_low += val;
            if (r > 30 && r <= 60) e_high += val;
        }
    }
    
    if (e_low > 1e-6) {
        double decay = e_high / e_low;
        if (decay < 0.1 || decay > 0.9) return true; // Unnatural frequency distribution
    }
    return false;
}

LivenessResult LivenessDetector::evaluate(const cv::Mat& gray_sm, 
                                          const cv::Mat& bgr_sm, 
                                          const cv::Mat& full_bgr, 
                                          const std::string& hand_mode) {
    LivenessResult res{};
    res.passed = true;
    res.confidence = 0.95f;
    res.isAiGenerated = false;

    // 1. Phone Bezel Detection Check
    if (detectPhoneBezel(full_bgr)) {
        res.passed = false;
        res.reason = "Screen replay detected - phone border found";
        res.confidence = 0.05f;
        return res;
    }

    // 2. High-Frequency Screen Pixel Grid Check
    std::string screen_reason;
    if (detectScreenReplay(gray_sm, bgr_sm, screen_reason)) {
        res.passed = false;
        res.reason = screen_reason;
        res.confidence = 0.10f;
        return res;
    }

    // 3. AI Generated Texture / Deepfake check (Spectral Decay)
    if (detectSpectralDecayAnomaly(gray_sm)) {
        res.passed = false;
        res.reason = "Deepfake detected - unnatural spectral signature";
        res.confidence = 0.15f;
        res.isAiGenerated = true;
        return res;
    }

    // 4. Basic Skin HSV (from previous version, simplified)
    cv::Mat hsv;
    cv::cvtColor(bgr_sm, hsv, cv::COLOR_BGR2HSV);
    cv::Mat mask1, mask2, skinMask;
    cv::inRange(hsv, cv::Scalar(0, 20, 50), cv::Scalar(25, 170, 255), mask1);
    cv::inRange(hsv, cv::Scalar(165, 20, 50), cv::Scalar(180, 170, 255), mask2);
    cv::bitwise_or(mask1, mask2, skinMask);
    
    double skinRatio = (double)cv::countNonZero(skinMask) / (double)skinMask.total();
    if (skinRatio < 0.15) {
        res.passed = false;
        res.reason = "Spoof detected - non-skin material";
        res.confidence = 0.30f;
        return res;
    }

    return res;
}

} // namespace fingerprint
