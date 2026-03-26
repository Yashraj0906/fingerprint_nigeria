/// SDK error codes
enum SdkErrorCode {
  cameraPermissionDenied,
  cameraInitFailed,
  lowQuality,
  livenessFailed,
  timeout,
  deviceUnsupported,
  processingError,
  captureAborted,
  unknown,
}

class SdkException implements Exception {
  final SdkErrorCode code;
  final String message;

  const SdkException(this.code, this.message);

  factory SdkException.fromMap(Map<dynamic, dynamic> m) {
    final code = _parseCode(m['errorCode'] as String? ?? 'UNKNOWN');
    return SdkException(code, m['errorMessage'] as String? ?? 'Unknown error');
  }

  static SdkErrorCode _parseCode(String c) => switch (c) {
        'CAMERA_PERMISSION_DENIED' => SdkErrorCode.cameraPermissionDenied,
        'CAMERA_INIT_FAILED'       => SdkErrorCode.cameraInitFailed,
        'LOW_QUALITY'              => SdkErrorCode.lowQuality,
        'LIVENESS_FAILED'          => SdkErrorCode.livenessFailed,
        'TIMEOUT'                  => SdkErrorCode.timeout,
        'DEVICE_UNSUPPORTED'       => SdkErrorCode.deviceUnsupported,
        'PROCESSING_ERROR'         => SdkErrorCode.processingError,
        'CAPTURE_ABORTED'          => SdkErrorCode.captureAborted,
        _                          => SdkErrorCode.unknown,
      };

  @override
  String toString() => 'SdkException(${code.name}): $message';
}
