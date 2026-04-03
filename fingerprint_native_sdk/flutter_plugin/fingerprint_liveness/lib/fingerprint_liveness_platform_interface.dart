import 'dart:typed_data';
import 'package:plugin_platform_interface/plugin_platform_interface.dart';
import 'fingerprint_liveness.dart';
import 'fingerprint_liveness_method_channel.dart';

/// Platform interface for the Fingerprint Liveness SDK.
/// Allows swapping native implementations (Android/iOS).
abstract class FingerprintLivenessPlatform extends PlatformInterface {
  FingerprintLivenessPlatform() : super(token: _token);

  static final Object _token = Object();
  static FingerprintLivenessPlatform _instance = MethodChannelFingerprintLiveness();

  static FingerprintLivenessPlatform get instance => _instance;

  static set instance(FingerprintLivenessPlatform instance) {
    PlatformInterface.verifyToken(instance, _token);
    _instance = instance;
  }

  Future<FingerprintResult> analyzeFrame({
    required Uint8List imageBytes,
    required String hand,
    required String mode,
  }) {
    throw UnimplementedError('analyzeFrame() has not been implemented.');
  }
}
