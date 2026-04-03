cmake_minimum_required(VERSION 3.18)
project(fingerprint_core VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CORE_SOURCES
    image_processor.cpp
    quality_analyzer.cpp
    liveness_detector.cpp
    template_encoder.cpp
    matcher.cpp
    fingerprint_core.cpp
    fingerprint_jni.cpp
)

add_library(fingerprint_core SHARED ${CORE_SOURCES})

# Always include our own headers
target_include_directories(fingerprint_core PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# OpenCV: CI passes -DOPENCV_INCLUDE_DIR=<path/to/sdk/native/jni/include>
# Local builds can use find_package if OpenCV is installed.
if(DEFINED OPENCV_INCLUDE_DIR AND NOT OPENCV_INCLUDE_DIR STREQUAL "")
    message(STATUS "Using OpenCV headers from: ${OPENCV_INCLUDE_DIR}")
    target_include_directories(fingerprint_core PRIVATE ${OPENCV_INCLUDE_DIR})
else()
    # Fallback for local development
    find_package(OpenCV QUIET)
    if(OpenCV_FOUND)
        target_include_directories(fingerprint_core PRIVATE ${OpenCV_INCLUDE_DIRS})
        message(STATUS "Found local OpenCV: ${OpenCV_INCLUDE_DIRS}")
    else()
        message(WARNING "OpenCV not found. Build may fail if OpenCV headers are required.")
    endif()
endif()

target_link_libraries(fingerprint_core
    PUBLIC
    log
    android
    jnigraphics
)
