Pod::Spec.new do |s|
  s.name             = 'fingerprint_sdk'
  s.version          = '2.0.0'
  s.summary          = 'YellowSense Contactless Fingerprint Capture SDK'
  s.homepage         = 'https://yellowsense.in'
  s.license          = { :type => 'Proprietary' }
  s.author           = { 'YellowSense' => 'dev@yellowsense.in' }
  s.source           = { :path => '.' }
  # Swift/ObjC sources from all subdirectories; C++ files ONLY from Classes/Core/
  s.source_files        = 'Classes/**/*.{h,m,mm,swift}', 'Classes/Core/**/*.{h,cpp}'
  s.public_header_files = 'Classes/Bridging/OpenCVWrapper.h', 'Classes/Bridge/FingerprintCoreWrapper.h'
  s.dependency 'Flutter'
  s.dependency 'OpenCV2'
  s.platform         = :ios, '13.0'
  s.swift_version    = '5.9'

  s.pod_target_xcconfig = {
    'DEFINES_MODULE'                                        => 'YES',
    'CLANG_ALLOW_NON_MODULAR_INCLUDES_IN_FRAMEWORK_MODULES' => 'YES',
    'FRAMEWORK_SEARCH_PATHS'                                => '$(inherited) "${PODS_ROOT}/OpenCV2"',
    'HEADER_SEARCH_PATHS'                                   => '$(inherited) "${PODS_ROOT}/OpenCV2/opencv2.framework/Headers" "${PODS_TARGET_SRCROOT}/Classes/**" "${PODS_TARGET_SRCROOT}/Classes/Core/include"',
    'CLANG_CXX_LANGUAGE_STANDARD'                           => 'c++17',
    'CLANG_CXX_LIBRARY'                                     => 'libc++',
    'OTHER_CPLUSPLUSFLAGS'                                  => '$(inherited) -std=c++17'
  }
end
