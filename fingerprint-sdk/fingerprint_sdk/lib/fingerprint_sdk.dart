/// YellowSense Contactless Fingerprint Capture SDK
///
/// Usage:
/// ```dart
/// final sdk = FingerprintSdk.instance;
/// await sdk.initialize();
/// sdk.feedbackStream.listen((feedback) { ... });
/// final result = await sdk.startCapture(request);
/// ```
library fingerprint_sdk;

export 'src/fingerprint_sdk.dart';
export 'src/models/capture_request.dart';
export 'src/models/capture_response.dart';
export 'src/models/feedback_event.dart';
export 'src/models/finger_result.dart';
export 'src/models/sdk_error.dart';
export 'src/models/capture_mode.dart';
