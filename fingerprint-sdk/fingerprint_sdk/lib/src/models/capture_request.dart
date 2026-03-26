import 'capture_mode.dart';

class CaptureOptions {
  final bool performLivenessCheck;
  final bool performQualityCheck;
  final bool returnTemplate;
  final bool returnProcessedImage;
  final bool returnRawImage;
  final int maxRetries;
  final int timeoutSeconds;

  const CaptureOptions({
    this.performLivenessCheck = true,
    this.performQualityCheck = true,
    this.returnTemplate = true,
    this.returnProcessedImage = false,
    this.returnRawImage = false,
    this.maxRetries = 3,
    this.timeoutSeconds = 30,
  });

  Map<String, dynamic> toMap() => {
        'performLivenessCheck': performLivenessCheck,
        'performQualityCheck': performQualityCheck,
        'returnTemplate': returnTemplate,
        'returnProcessedImage': returnProcessedImage,
        'returnRawImage': returnRawImage,
        'maxRetries': maxRetries,
        'timeoutSeconds': timeoutSeconds,
      };
}

class CaptureRequest {
  final String transactionId;
  final CaptureMode captureMode;
  final List<FingerId> fingersRequested;
  final List<FingerId> missingFingers;
  final CaptureOptions options;

  const CaptureRequest({
    required this.transactionId,
    required this.captureMode,
    required this.fingersRequested,
    this.missingFingers = const [],
    this.options = const CaptureOptions(),
  });

  Map<String, dynamic> toMap() => {
        'transactionId': transactionId,
        'captureMode': captureMode.value,
        'fingersRequested': fingersRequested.map((f) => f.value).toList(),
        'missingFingers': missingFingers.map((f) => f.value).toList(),
        'options': options.toMap(),
      };
}
