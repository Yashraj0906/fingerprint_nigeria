enum FeedbackType { alignment, lighting, motion, distance, ready, processing }

class FeedbackEvent {
  final FeedbackType type;
  final String message;
  final double confidence; // 0.0 – 1.0

  const FeedbackEvent({
    required this.type,
    required this.message,
    required this.confidence,
  });

  factory FeedbackEvent.fromMap(Map<dynamic, dynamic> m) => FeedbackEvent(
        type: _parseType(m['type'] as String),
        message: m['message'] as String,
        confidence: (m['confidence'] as num).toDouble(),
      );

  static FeedbackType _parseType(String t) => switch (t) {
        'ALIGNMENT'  => FeedbackType.alignment,
        'LIGHTING'   => FeedbackType.lighting,
        'MOTION'     => FeedbackType.motion,
        'DISTANCE'   => FeedbackType.distance,
        'READY'      => FeedbackType.ready,
        'PROCESSING' => FeedbackType.processing,
        _            => FeedbackType.alignment,
      };
}
