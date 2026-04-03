cmake_minimum_required(VERSION 3.18)
project(fingerprint_core VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# No find_package(JNI REQUIRED) needed for Android NDK

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

target_include_directories(fingerprint_core
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# OpenCV is linked via the Gradle configuration in build.gradle
target_link_libraries(fingerprint_core 
    PUBLIC 
    log
    android
    jnigraphics
)
