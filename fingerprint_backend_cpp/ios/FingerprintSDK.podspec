Pod::Spec.new do |s|
  s.name             = 'FingerprintSDK'
  s.version          = '1.0.0'
  s.summary          = 'On-device fingerprint capture, quality, liveness & matching SDK'
  s.description      = <<-DESC
    C++ core wrapped in Objective-C++ providing:
    - Gabor-based ridge enhancement
    - 5-metric quality scoring
    - 4-layer liveness detection
    - ISO 19794-2 minutiae template extraction
    - 1:1 and 1:N template matching
  DESC
  s.homepage         = 'https://github.com/yellowsense/fingerprint-sdk'
  s.license          = { :type => 'Proprietary' }
  s.author           = { 'YellowSense' => 'dev@yellowsense.in' }
  s.source           = { :git => '', :tag => s.version.to_s }

  s.ios.deployment_target = '13.0'

  # Objective-C++ bridge + shared C++ core
  s.source_files = [
    'Classes/**/*.{h,mm}',
    '../../src/**/*.cpp',
    '../../include/**/*.h'
  ]

  s.public_header_files = 'Classes/**/*.h'

  s.pod_target_xcconfig = {
    'CLANG_CXX_LANGUAGE_STANDARD'    => 'c++17',
    'CLANG_CXX_LIBRARY'              => 'libc++',
    'HEADER_SEARCH_PATHS'            => '$(PODS_TARGET_SRCROOT)/../../include',
    'GCC_PREPROCESSOR_DEFINITIONS'  => '$(inherited) OPENCV_DISABLE_EIGEN_TENSOR_SUPPORT=1',
    'ENABLE_BITCODE'                 => 'NO'
  }

  # opencv2.framework must be placed alongside the podspec before `pod install`
  s.vendored_frameworks = 'opencv2.framework'
  s.frameworks          = 'Foundation', 'UIKit', 'AVFoundation', 'Accelerate'
end
