Pod::Spec.new do |s|
  s.name             = 'fingerprint_sdk'
  s.version          = '2.0.0'
  s.summary          = 'YellowSense Contactless Fingerprint Capture SDK'
  s.homepage         = 'https://yellowsense.in'
  s.license          = { :type => 'Proprietary' }
  s.author           = { 'YellowSense' => 'dev@yellowsense.in' }
  s.source           = { :path => '.' }
  s.source_files     = 'Classes/**/*.swift'
  s.dependency 'Flutter'
  s.dependency 'OpenCV2', '~> 4.8.0'
  s.platform         = :ios, '13.0'
  s.swift_version    = '5.9'
  s.pod_target_xcconfig = {
    'DEFINES_MODULE'              => 'YES',
    'SWIFT_OBJC_BRIDGING_HEADER'  => '${PODS_TARGET_SRCROOT}/Classes/Bridging/FingerprintSDK-Bridging-Header.h'
  }
end
