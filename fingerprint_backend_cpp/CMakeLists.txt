cmake_minimum_required(VERSION 3.18)
project(fingerprint_core VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(JNI REQUIRED)

set(CORE_SOURCES
    src/image_processor.cpp
    src/quality_analyzer.cpp
    src/liveness_detector.cpp
    src/template_encoder.cpp
    src/matcher.cpp
    src/fingerprint_core.cpp
    src/fingerprint_jni.cpp
)

add_library(fingerprint_core SHARED ${CORE_SOURCES})

target_include_directories(fingerprint_core
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${OpenCV_INCLUDE_DIRS}
)

target_link_libraries(fingerprint_core PUBLIC ${OpenCV_LIBS})

install(TARGETS fingerprint_core
    LIBRARY  DESTINATION lib
    ARCHIVE  DESTINATION lib
    RUNTIME  DESTINATION bin
)
install(DIRECTORY include/ DESTINATION include)
