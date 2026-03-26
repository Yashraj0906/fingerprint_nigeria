import 'finger_result.dart';

enum CaptureStatus { success, failed }

class CaptureResponse {
  final String transactionId;
  final CaptureStatus overallStatus;
  final List<FingerResult> results;

  const CaptureResponse({
    required this.transactionId,
    required this.overallStatus,
    required this.results,
  });

  factory CaptureResponse.fromMap(Map<dynamic, dynamic> m) => CaptureResponse(
        transactionId: m['transactionId'] as String,
        overallStatus: m['overallStatus'] == 'success'
            ? CaptureStatus.success
            : CaptureStatus.failed,
        results: (m['results'] as List)
            .map((r) => FingerResult.fromMap(r as Map))
            .toList(),
      );
}
