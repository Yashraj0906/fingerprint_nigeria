enum FeedbackType { alignment, lighting, motion, distance, ready, processing, stability, warning }

class FeedbackEvent {
  final FeedbackType type;
  final String message;
  final double confidence; // 0.0 – 1.0
  /// Native finger target during capture, e.g. LEFT_INDEX (see SDK events).
  final String? fingerId;

  const FeedbackEvent({
    required this.type,
    required this.message,
    required this.confidence,
    this.fingerId,
  });

  factory FeedbackEvent.fromMap(Map<dynamic, dynamic> m) => FeedbackEvent(
        type: _parseType(m['type'] as String),
        message: m['message'] as String,
        confidence: (m['confidence'] as num).toDouble(),
        fingerId: m['fingerId'] as String?,
      );

  static FeedbackType _parseType(String t) => switch (t) {
        'ALIGNMENT'  => FeedbackType.alignment,
        'LIGHTING'   => FeedbackType.lighting,
        'MOTION'     => FeedbackType.motion,
        'DISTANCE'   => FeedbackType.distance,
        'READY'      => FeedbackType.ready,
        'PROCESSING' => FeedbackType.processing,
        'STABILITY'  => FeedbackType.stability,
        'WARNING'    => FeedbackType.warning,
        _            => FeedbackType.alignment,
      };
}
