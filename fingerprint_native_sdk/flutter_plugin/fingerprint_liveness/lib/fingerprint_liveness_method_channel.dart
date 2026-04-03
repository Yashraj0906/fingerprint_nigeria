import 'dart:typed_data';
import 'package:flutter/services.dart';
import 'fingerprint_liveness.dart';
import 'fingerprint_liveness_platform_interface.dart';

/// Method channel implementation — bridges Flutter Dart to native Android/iOS.
class MethodChannelFingerprintLiveness extends FingerprintLivenessPlatform {
  static const MethodChannel _channel =
      MethodChannel('com.fingerprintsdk.liveness/analyze');

  @override
  Future<FingerprintResult> analyzeFrame({
    required Uint8List imageBytes,
    required String hand,
    required String mode,
  }) async {
    final Map<dynamic, dynamic> result =
        await _channel.invokeMethod('analyzeFrame', {
      'imageBytes': imageBytes,
      'hand': hand,
      'mode': mode,
    });

    return FingerprintResult.fromMap(result);
  }
}
