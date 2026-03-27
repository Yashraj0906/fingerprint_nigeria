Pod::Spec.new do |s|
  s.name             = 'fingerprint_sdk'
  s.version          = '2.0.0'
  s.summary          = 'YellowSense Contactless Fingerprint Capture SDK'
  s.homepage         = 'https://yellowsense.in'
  s.license          = { :type => 'Proprietary' }
  s.author           = { 'YellowSense' => 'dev@yellowsense.in' }
  s.source           = { :path => '.' }
  s.source_files        = 'Classes/**/*.swift', 'Classes/**/*.h', 'Classes/**/*.mm'
  s.public_header_files = 'Classes/Bridging/OpenCVWrapper.h'
  s.dependency 'Flutter'
  s.dependency 'OpenCV2'
  s.platform         = :ios, '13.0'
  s.swift_version    = '5.9'
  s.pod_target_xcconfig = {
    'DEFINES_MODULE'                                        => 'YES',
    'CLANG_ALLOW_NON_MODULAR_INCLUDES_IN_FRAMEWORK_MODULES' => 'YES'
  }
end
