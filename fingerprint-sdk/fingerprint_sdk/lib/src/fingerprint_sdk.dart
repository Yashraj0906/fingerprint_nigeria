import 'dart:async';
import 'package:flutter/services.dart';

import 'models/capture_request.dart';
import 'models/capture_response.dart';
import 'models/feedback_event.dart';
import 'models/sdk_error.dart';

/// Primary SDK entry point. Use [FingerprintSdk.instance].
class FingerprintSdk {
  FingerprintSdk._();
  static final FingerprintSdk instance = FingerprintSdk._();

  static const _method = MethodChannel('com.yellowsense.fingerprint_sdk/method');
  static const _event  = EventChannel('com.yellowsense.fingerprint_sdk/feedback');

  Stream<FeedbackEvent>? _feedbackStream;

  /// Live feedback stream — subscribe before calling [startCapture].
  Stream<FeedbackEvent> get feedbackStream {
    _feedbackStream ??= _event
        .receiveBroadcastStream()
        .map((e) => FeedbackEvent.fromMap(e as Map));
    return _feedbackStream!;
  }

  /// Initialize camera and ML models.
  /// Pass [debugMode: true] to enable verbose native logging.
  Future<void> initialize({bool debugMode = false}) async {
    try {
      await _method.invokeMethod<void>('initialize', {'debugMode': debugMode});
    } on PlatformException catch (e) {
      throw SdkException.fromMap({'errorCode': e.code, 'errorMessage': e.message});
    }
  }

  /// Start a capture session. Returns structured [CaptureResponse].
  /// Throws [SdkException] on failure.
  Future<CaptureResponse> startCapture(CaptureRequest request) async {
    try {
      final result = await _method.invokeMapMethod<dynamic, dynamic>(
        'startCapture',
        request.toMap(),
      );
      return CaptureResponse.fromMap(result!);
    } on PlatformException catch (e) {
      throw SdkException.fromMap({'errorCode': e.code, 'errorMessage': e.message});
    }
  }

  /// Abort an in-progress capture session.
  Future<void> stopCapture() async {
    try {
      await _method.invokeMethod<void>('stopCapture');
    } on PlatformException catch (e) {
      throw SdkException.fromMap({'errorCode': e.code, 'errorMessage': e.message});
    }
  }

  /// Release camera and free all resources. Call in widget dispose().
  Future<void> dispose() async {
    try {
      await _method.invokeMethod<void>('dispose');
    } on PlatformException catch (_) {
      // Ignore dispose errors
    } finally {
      _feedbackStream = null;
    }
  }

  /// Returns SDK version string.
  Future<String> getVersion() async {
    final v = await _method.invokeMethod<String>('getVersion');
    return v ?? '2.0.0';
  }
}
