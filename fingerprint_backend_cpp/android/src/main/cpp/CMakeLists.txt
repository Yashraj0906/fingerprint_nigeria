cmake_minimum_required(VERSION 3.18)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# OpenCV Android SDK path injected by build.gradle via OPENCV_ANDROID_SDK env var
set(OPENCV_ANDROID_SDK_PATH $ENV{OPENCV_ANDROID_SDK})
if(NOT OPENCV_ANDROID_SDK_PATH)
    message(FATAL_ERROR "OPENCV_ANDROID_SDK env var not set. "
            "Set it to the root of the OpenCV Android SDK (e.g. ~/opencv-android/OpenCV-android-sdk)")
endif()

include(${OPENCV_ANDROID_SDK_PATH}/sdk/native/jni/OpenCV.cmake)

# Core sources: CMakeLists is at android/src/main/cpp/ → 4 levels up = fingerprint_backend_cpp/
set(CORE_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../)

set(CORE_SOURCES
    ${CORE_ROOT}/src/image_processor.cpp
    ${CORE_ROOT}/src/quality_analyzer.cpp
    ${CORE_ROOT}/src/liveness_detector.cpp
    ${CORE_ROOT}/src/template_encoder.cpp
    ${CORE_ROOT}/src/matcher.cpp
    ${CORE_ROOT}/src/fingerprint_core.cpp
    jni_bridge.cpp
)

add_library(fingerprint_sdk SHARED ${CORE_SOURCES})

target_include_directories(fingerprint_sdk PRIVATE
    ${CORE_ROOT}/include
    ${OpenCV_INCLUDE_DIRS}
)

target_link_libraries(fingerprint_sdk
    ${OpenCV_LIBS}
    android
    log
    jnigraphics
)
