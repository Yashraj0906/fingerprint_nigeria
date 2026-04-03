import 'dart:typed_data';
import 'fingerprint_liveness_platform_interface.dart';

/// Main entry point for the Fingerprint Liveness SDK.
class FingerprintLiveness {
  /// Analyze a single camera frame for liveness and quality.
  ///
  /// [imageBytes] — JPEG or PNG image as raw bytes (from camera stream).
  /// [hand]       — 'RIGHT' or 'LEFT'
  /// [mode]       — 'RIGHT_FOUR', 'LEFT_FOUR', 'RIGHT_THUMB', 'LEFT_THUMB', 'SINGLE_FINGER'
  ///
  /// Returns a [FingerprintResult] with per-finger liveness and quality data.
  static Future<FingerprintResult> analyzeFrame({
    required Uint8List imageBytes,
    required String hand,
    required String mode,
  }) {
    return FingerprintLivenessPlatform.instance.analyzeFrame(
      imageBytes: imageBytes,
      hand: hand,
      mode: mode,
    );
  }
}

// ── Result Models ─────────────────────────────────────────────────────────────

/// Top-level result from a single frame analysis.
class FingerprintResult {
  final bool handDetected;
  final String hand;
  final String? guidance;
  final List<FingerResult> fingers;

  FingerprintResult({
    required this.handDetected,
    required this.hand,
    this.guidance,
    required this.fingers,
  });

  factory FingerprintResult.fromMap(Map<dynamic, dynamic> map) {
    return FingerprintResult(
      handDetected: map['hand_detected'] as bool? ?? false,
      hand: map['hand'] as String? ?? '',
      guidance: map['guidance'] as String?,
      fingers: (map['fingers'] as List<dynamic>? ?? [])
          .map((f) => FingerResult.fromMap(f as Map<dynamic, dynamic>))
          .toList(),
    );
  }
}

/// Per-finger result containing liveness and quality data.
class FingerResult {
  /// e.g. 'RIGHT_INDEX', 'LEFT_THUMB'
  final String fingerId;

  /// Was this finger visible in the frame?
  final bool detected;

  /// Composite quality score 0–100. Accept if >= 60.
  final double qualityScore;

  /// Sharpness score 0–100.
  final double? blurScore;

  /// Illumination / contrast score 0–100.
  final double? illumScore;

  /// true = real finger, false = spoof/fake detected.
  final bool liveness;

  /// Confidence of the liveness decision (0.0–1.0).
  final double? livenessConf;

  /// true if the fake is specifically an AI-generated deepfake.
  final bool isAiGenerated;

  /// Human-readable failure reason (null if liveness passed).
  /// Use this as your errorMessage to show to users.
  final String? guidance;

  /// Finger bounding box as percentage of image dimensions.
  final BboxPct? bboxPct;

  FingerResult({
    required this.fingerId,
    required this.detected,
    required this.qualityScore,
    this.blurScore,
    this.illumScore,
    required this.liveness,
    this.livenessConf,
    this.isAiGenerated = false,
    this.guidance,
    this.bboxPct,
  });

  factory FingerResult.fromMap(Map<dynamic, dynamic> map) {
    return FingerResult(
      fingerId: map['finger_id'] as String? ?? '',
      detected: map['detected'] as bool? ?? false,
      qualityScore: (map['quality_score'] as num?)?.toDouble() ?? 0.0,
      blurScore: (map['blur_score'] as num?)?.toDouble(),
      illumScore: (map['illum_score'] as num?)?.toDouble(),
      liveness: map['liveness'] as bool? ?? false,
      livenessConf: (map['liveness_conf'] as num?)?.toDouble(),
      isAiGenerated: map['is_ai_generated'] as bool? ?? false,
      guidance: map['guidance'] as String?,
      bboxPct: map['bbox_pct'] != null
          ? BboxPct.fromMap(map['bbox_pct'] as Map<dynamic, dynamic>)
          : null,
    );
  }

  /// Returns true if this finger is ready to accept (live + quality >= 60).
  bool get isAccepted => liveness && qualityScore >= 60;
}

/// Finger bounding box as fractions of image width/height (0.0–1.0).
class BboxPct {
  final double x;
  final double y;
  final double w;
  final double h;

  BboxPct({
    required this.x,
    required this.y,
    required this.w,
    required this.h,
  });

  factory BboxPct.fromMap(Map<dynamic, dynamic> map) {
    return BboxPct(
      x: (map['x'] as num).toDouble(),
      y: (map['y'] as num).toDouble(),
      w: (map['w'] as num).toDouble(),
      h: (map['h'] as num).toDouble(),
    );
  }
}
