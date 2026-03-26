/// Supported capture modes
enum CaptureMode {
  leftFour,
  rightFour,
  leftThumb,
  rightThumb,
  singleFinger,
  customSequence,
  partialCapture,
}

extension CaptureModeX on CaptureMode {
  String get value => switch (this) {
        CaptureMode.leftFour => 'LEFT_FOUR',
        CaptureMode.rightFour => 'RIGHT_FOUR',
        CaptureMode.leftThumb => 'LEFT_THUMB',
        CaptureMode.rightThumb => 'RIGHT_THUMB',
        CaptureMode.singleFinger => 'SINGLE_FINGER',
        CaptureMode.customSequence => 'CUSTOM_SEQUENCE',
        CaptureMode.partialCapture => 'PARTIAL_CAPTURE',
      };

  static CaptureMode fromString(String v) => CaptureMode.values.firstWhere(
        (e) => e.value == v,
        orElse: () => CaptureMode.singleFinger,
      );
}

/// Finger identifiers
enum FingerId {
  rightThumb,
  rightIndex,
  rightMiddle,
  rightRing,
  rightLittle,
  leftThumb,
  leftIndex,
  leftMiddle,
  leftRing,
  leftLittle,
}

extension FingerIdX on FingerId {
  String get value => switch (this) {
        FingerId.rightThumb => 'RIGHT_THUMB',
        FingerId.rightIndex => 'RIGHT_INDEX',
        FingerId.rightMiddle => 'RIGHT_MIDDLE',
        FingerId.rightRing => 'RIGHT_RING',
        FingerId.rightLittle => 'RIGHT_LITTLE',
        FingerId.leftThumb => 'LEFT_THUMB',
        FingerId.leftIndex => 'LEFT_INDEX',
        FingerId.leftMiddle => 'LEFT_MIDDLE',
        FingerId.leftRing => 'LEFT_RING',
        FingerId.leftLittle => 'LEFT_LITTLE',
      };
}
