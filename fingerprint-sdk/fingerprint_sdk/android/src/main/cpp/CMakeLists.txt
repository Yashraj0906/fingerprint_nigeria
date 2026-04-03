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

# Try to find OpenCV (works on CI since we passed OpenCV_DIR to CMake, and locally if installed)
find_package(OpenCV REQUIRED)
message(STATUS "Found OpenCV version: ${OpenCV_VERSION}")
target_include_directories(fingerprint_core PRIVATE ${OpenCV_INCLUDE_DIRS})

target_link_libraries(fingerprint_core
    PUBLIC
    ${OpenCV_LIBS}
    log
    android
    jnigraphics
)
