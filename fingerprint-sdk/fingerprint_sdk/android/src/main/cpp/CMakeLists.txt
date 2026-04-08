cmake_minimum_required(VERSION 3.18)
project(fingerprint_core VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Pull in the C++ standard library (libc++_shared.so) so that operator
# new/delete and STL types in our own code are resolved at link time.
find_library(CPP_SHARED_LIB c++_shared)
if(NOT CPP_SHARED_LIB)
    message(STATUS "c++_shared not found via find_library; the NDK toolchain will handle it")
endif()

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

# ── OpenCV linkage ────────────────────────────────────────────────────────────
# We link against the prebuilt SHARED libopencv_java4.so that ships with the
# OpenCV Android SDK. This is the only correct approach for Android – the
# static .a files cause "undefined symbol: operator new" because they drag in
# the full C++ runtime which conflicts with Android's STL.
# ─────────────────────────────────────────────────────────────────────────────
if(DEFINED OpenCV_DIR AND NOT OpenCV_DIR STREQUAL "")
    # OpenCV_DIR points to  sdk/native/jni  (contains OpenCVConfig.cmake)
    # The shared .so lives one level up at  sdk/native/libs/<ABI>/
    get_filename_component(OPENCV_NATIVE_DIR "${OpenCV_DIR}" DIRECTORY)
    set(OPENCV_LIB_DIR  "${OPENCV_NATIVE_DIR}/libs/${ANDROID_ABI}")
    set(OPENCV_INCLUDE  "${OpenCV_DIR}/include")

    message(STATUS "OpenCV include : ${OPENCV_INCLUDE}")
    message(STATUS "OpenCV lib dir : ${OPENCV_LIB_DIR}")

    add_library(opencv_java4 SHARED IMPORTED)
    set_target_properties(opencv_java4 PROPERTIES
        IMPORTED_LOCATION "${OPENCV_LIB_DIR}/libopencv_java4.so")

    target_include_directories(fingerprint_core PRIVATE "${OPENCV_INCLUDE}")
    target_link_libraries(fingerprint_core PUBLIC opencv_java4 log android jnigraphics
        $<$<BOOL:${CPP_SHARED_LIB}>:${CPP_SHARED_LIB}>)
else()
    # No local SDK – try to find the .so extracted from the Gradle AAR
    message(STATUS "OpenCV_DIR not set – trying find_library(opencv_java4)")
    find_library(OPENCV_java4_LIB opencv_java4)
    if(NOT OPENCV_java4_LIB)
        message(FATAL_ERROR
            "Cannot find libopencv_java4.so. "
            "Set OpenCV_DIR to <sdk>/native/jni or add the opencv AAR to Gradle.")
    endif()
    add_library(opencv_java4 SHARED IMPORTED)
    set_target_properties(opencv_java4 PROPERTIES IMPORTED_LOCATION ${OPENCV_java4_LIB})
    target_link_libraries(fingerprint_core PUBLIC opencv_java4 log android jnigraphics
        $<$<BOOL:${CPP_SHARED_LIB}>:${CPP_SHARED_LIB}>)
endif()
