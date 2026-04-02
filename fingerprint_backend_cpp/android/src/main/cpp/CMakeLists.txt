cmake_minimum_required(VERSION 3.18)
project(fingerprint_sdk)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── OpenCV ──────────────────────────────────────────────────────────────────
# Read the SDK root that the CI sets via $GITHUB_ENV (or local build env).
# We do NOT use OpenCV.cmake — we configure include/lib paths directly so the
# build works regardless of whether that helper script exists.
set(OPENCV_SDK "$ENV{OPENCV_ANDROID_SDK}")
if(NOT OPENCV_SDK OR OPENCV_SDK STREQUAL "")
    message(FATAL_ERROR
        "OPENCV_ANDROID_SDK environment variable is not set.\n"
        "Export it before running Gradle, e.g.:\n"
        "  export OPENCV_ANDROID_SDK=/path/to/OpenCV-android-sdk")
endif()

set(OPENCV_INCLUDE "${OPENCV_SDK}/sdk/native/jni/include")
set(OPENCV_LIB_DIR "${OPENCV_SDK}/sdk/native/libs/${ANDROID_ABI}")

if(NOT EXISTS "${OPENCV_INCLUDE}")
    message(FATAL_ERROR "OpenCV include dir not found: ${OPENCV_INCLUDE}")
endif()

# Import the pre-built OpenCV shared library for the current ABI.
# OpenCV 4.x ships libopencv_java4.so; older versions used opencv_java3.
find_library(OPENCV_LIB
    NAMES opencv_java4 opencv_java3
    PATHS "${OPENCV_LIB_DIR}"
    NO_DEFAULT_PATH
    NO_CMAKE_FIND_ROOT_PATH
)
if(NOT OPENCV_LIB)
    # Fallback: pick the first .so in that dir
    file(GLOB _opencv_libs "${OPENCV_LIB_DIR}/libopencv_java*.so")
    if(_opencv_libs)
        list(GET _opencv_libs 0 OPENCV_LIB)
    else()
        message(FATAL_ERROR "No OpenCV .so found in ${OPENCV_LIB_DIR}")
    endif()
endif()
message(STATUS "Using OpenCV library: ${OPENCV_LIB}")

add_library(opencv_imported SHARED IMPORTED)
set_target_properties(opencv_imported PROPERTIES IMPORTED_LOCATION "${OPENCV_LIB}")

# ── Core sources ─────────────────────────────────────────────────────────────
# CMakeLists lives at:  android/src/main/cpp/
# Core sources live at: fingerprint_backend_cpp/src/
# → 4 levels up = fingerprint_backend_cpp/
set(CORE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../")

add_library(fingerprint_sdk SHARED
    "${CORE_ROOT}/src/image_processor.cpp"
    "${CORE_ROOT}/src/quality_analyzer.cpp"
    "${CORE_ROOT}/src/liveness_detector.cpp"
    "${CORE_ROOT}/src/template_encoder.cpp"
    "${CORE_ROOT}/src/matcher.cpp"
    "${CORE_ROOT}/src/fingerprint_core.cpp"
    jni_bridge.cpp
)

target_include_directories(fingerprint_sdk PRIVATE
    "${CORE_ROOT}/include"
    "${OPENCV_INCLUDE}"
)

target_link_libraries(fingerprint_sdk
    opencv_imported
    android
    log
    jnigraphics
)
