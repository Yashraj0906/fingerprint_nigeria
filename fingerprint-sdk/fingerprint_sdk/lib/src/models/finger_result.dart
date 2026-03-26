enum FingerStatus { success, failed, missing }

class FingerResult {
  final String fingerId;
  final FingerStatus status;
  final double qualityScore;
  final bool livenessPassed;
  final String? template;       // base64 ISO template
  final String? rawImage;       // base64, only if returnRawImage=true
  final String? processedImage; // base64, only if returnProcessedImage=true
  final String? errorCode;
  final String? errorMessage;

  const FingerResult({
    required this.fingerId,
    required this.status,
    required this.qualityScore,
    required this.livenessPassed,
    this.template,
    this.rawImage,
    this.processedImage,
    this.errorCode,
    this.errorMessage,
  });

  factory FingerResult.fromMap(Map<dynamic, dynamic> m) => FingerResult(
        fingerId: m['fingerId'] as String,
        status: _parseStatus(m['status'] as String),
        qualityScore: (m['qualityScore'] as num).toDouble(),
        livenessPassed: m['livenessPassed'] as bool,
        template: m['template'] as String?,
        rawImage: m['rawImage'] as String?,
        processedImage: m['processedImage'] as String?,
        errorCode: m['errorCode'] as String?,
        errorMessage: m['errorMessage'] as String?,
      );

  static FingerStatus _parseStatus(String s) => switch (s) {
        'success' => FingerStatus.success,
        'missing' => FingerStatus.missing,
        _ => FingerStatus.failed,
      };
}
