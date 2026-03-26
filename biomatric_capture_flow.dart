import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:async';

// ─────────────────────────────────────────────────────────────────────────────
// ENTRY POINT
// ─────────────────────────────────────────────────────────────────────────────
void main() {
  runApp(const BiometricApp());
}

class BiometricApp extends StatelessWidget {
  const BiometricApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Biometric Capture',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        fontFamily: 'SF Pro Display',
        scaffoldBackgroundColor: Colors.white,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1A7A3C)),
        useMaterial3: true,
      ),
      home: const FingerprintSetupScreen(),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CONSTANTS & THEME
// ─────────────────────────────────────────────────────────────────────────────
class AppColors {
  static const primary = Color(0xFF1A7A3C);
  static const primaryLight = Color(0xFFE8F5EE);
  static const primaryBright = Color(0xFF2ECC71);
  static const warning = Color(0xFFF59E0B);
  static const warningLight = Color(0xFFFFFBEB);
  static const error = Color(0xFFEF4444);
  static const surface = Color(0xFFF8F9FA);
  static const border = Color(0xFFE5E7EB);
  static const textPrimary = Color(0xFF111827);
  static const textSecondary = Color(0xFF6B7280);
  static const overlayDark = Color(0xFF0D1117);
}

// ─────────────────────────────────────────────────────────────────────────────
// DATA MODELS
// ─────────────────────────────────────────────────────────────────────────────
enum FingerID {
  leftLittle,
  leftRing,
  leftMiddle,
  leftIndex,
  leftThumb,
  rightThumb,
  rightIndex,
  rightMiddle,
  rightRing,
  rightLittle,
}

extension FingerIDExt on FingerID {
  String get label {
    switch (this) {
      case FingerID.leftLittle: return 'Left Little';
      case FingerID.leftRing:   return 'Left Ring';
      case FingerID.leftMiddle: return 'Left Middle';
      case FingerID.leftIndex:  return 'Left Index';
      case FingerID.leftThumb:  return 'Left Thumb';
      case FingerID.rightThumb: return 'Right Thumb';
      case FingerID.rightIndex: return 'Right Index';
      case FingerID.rightMiddle:return 'Right Middle';
      case FingerID.rightRing:  return 'Right Ring';
      case FingerID.rightLittle:return 'Right Little';
    }
  }

  String get shortCode {
    switch (this) {
      case FingerID.leftLittle: return 'L4';
      case FingerID.leftRing:   return 'L3';
      case FingerID.leftMiddle: return 'L2';
      case FingerID.leftIndex:  return 'L1';
      case FingerID.leftThumb:  return 'LT';
      case FingerID.rightThumb: return 'RT';
      case FingerID.rightIndex: return 'R1';
      case FingerID.rightMiddle:return 'R2';
      case FingerID.rightRing:  return 'R3';
      case FingerID.rightLittle:return 'R4';
    }
  }

  bool get isLeft => index < 5;
}

enum CaptureMode { leftFour, rightFour, leftThumb, rightThumb, singleFinger, customSequence, partialCapture }
enum CaptureStatus { idle, searching, aligning, capturing, processing, success, failed }

class CaptureResult {
  final FingerID fingerId;
  final bool isValid;
  final int qualityScore;
  final bool livenessPassed;

  const CaptureResult({
    required this.fingerId,
    required this.isValid,
    required this.qualityScore,
    required this.livenessPassed,
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SDK BRIDGE (MethodChannel — swap with real SDK channel name)
// ─────────────────────────────────────────────────────────────────────────────
class BiometricSDKBridge {
  static const _channel = MethodChannel('com.yourapp/biometric_sdk');
  static const _eventChannel = EventChannel('com.yourapp/biometric_sdk_events');

  /// Starts a capture session and returns a stream of real-time feedback events.
  static Stream<Map<String, dynamic>> startCapture({
    required CaptureMode mode,
    required List<FingerID> fingers,
    List<FingerID> missingFingers = const [],
  }) {
    // Build the request payload matching the SDK API contract
    final request = {
      'transactionId': DateTime.now().millisecondsSinceEpoch.toString(),
      'captureMode': _modeToString(mode),
      'fingersRequested': fingers.map((f) => f.name.toUpperCase()).toList(),
      'missingFingers': missingFingers.map((f) => f.name.toUpperCase()).toList(),
      'options': {
        'performLivenessCheck': true,
        'performQualityCheck': true,
        'returnTemplate': true,
        'returnProcessedImage': false, // per spec: no raw image display
        'maxRetries': 3,
        'timeoutSeconds': 30,
      },
    };

    // Invoke SDK — in production this triggers native camera + processing
    _channel.invokeMethod('startCapture', request);

    // Listen to real-time feedback events from the SDK
    return _eventChannel
        .receiveBroadcastStream()
        .map((event) => Map<String, dynamic>.from(event as Map));
  }

  static Future<void> cancelCapture() async {
    await _channel.invokeMethod('cancelCapture');
  }

  static String _modeToString(CaptureMode mode) {
    switch (mode) {
      case CaptureMode.leftFour:       return 'LEFT_FOUR';
      case CaptureMode.rightFour:      return 'RIGHT_FOUR';
      case CaptureMode.leftThumb:      return 'LEFT_THUMB';
      case CaptureMode.rightThumb:     return 'RIGHT_THUMB';
      case CaptureMode.singleFinger:   return 'SINGLE_FINGER';
      case CaptureMode.customSequence: return 'CUSTOM_SEQUENCE';
      case CaptureMode.partialCapture: return 'PARTIAL_CAPTURE';
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SCREEN 1: FINGERPRINT SETUP
// ─────────────────────────────────────────────────────────────────────────────
class FingerprintSetupScreen extends StatelessWidget {
  const FingerprintSetupScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          onPressed: () => Navigator.maybePop(context),
        ),
        title: const Text(
          'Fingerprint Setup',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontWeight: FontWeight.w700,
            fontSize: 18,
          ),
        ),
        centerTitle: true,
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            decoration: BoxDecoration(
              color: AppColors.primaryLight,
              shape: BoxShape.circle,
            ),
            child: IconButton(
              icon: const Icon(Icons.volume_up_rounded, color: AppColors.primary),
              onPressed: () {},
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Illustration card
                  Container(
                    width: double.infinity,
                    height: 220,
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFF3E8),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Center(
                      child: _SetupIllustration(),
                    ),
                  ),
                  const SizedBox(height: 28),

                  const Text(
                    'Place your fingers against a plain background',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                      color: AppColors.textPrimary,
                      height: 1.2,
                    ),
                  ),
                  const SizedBox(height: 28),

                  // Steps
                  _SetupStep(
                    number: 1,
                    title: 'Find a flat, plain wall',
                    subtitle: 'Ensure there are no patterns or shadows.',
                  ),
                  const SizedBox(height: 20),
                  _SetupStep(
                    number: 2,
                    title: 'Hold your fingers together',
                    subtitle: 'Keep them straight and close together.',
                  ),
                  const SizedBox(height: 20),
                  _SetupStep(
                    number: 3,
                    title: 'Point camera at fingers',
                    subtitle: 'Hold the phone steady about 5 inches away.',
                  ),
                  const SizedBox(height: 24),

                  // Warning banner
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.warningLight,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFFDE68A)),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: const [
                        Icon(Icons.wb_sunny_rounded, color: AppColors.warning, size: 20),
                        SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Ensure the area is well-lit for the best results. The app will ask for camera permission next.',
                            style: TextStyle(
                              color: AppColors.warning,
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              height: 1.4,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Special registration link
                  Center(
                    child: TextButton(
                      onPressed: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => const SpecialRegistrationScreen(),
                        ),
                      ),
                      child: const Text(
                        'Can\'t provide all fingers? Special Registration',
                        style: TextStyle(
                          color: AppColors.primary,
                          fontWeight: FontWeight.w600,
                          fontSize: 13,
                          decoration: TextDecoration.underline,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          // CTA Button
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
            child: _PrimaryButton(
              label: 'Start Capture',
              icon: Icons.camera_alt_rounded,
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const BiometricCaptureScreen(
                    stepIndex: 0,
                    totalSteps: 3,
                    captureMode: CaptureMode.leftFour,
                    fingers: [
                      FingerID.leftIndex,
                      FingerID.leftMiddle,
                      FingerID.leftRing,
                      FingerID.leftLittle,
                    ],
                    stepLabel: 'Left 4 Fingers',
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SetupStep extends StatelessWidget {
  final int number;
  final String title;
  final String subtitle;

  const _SetupStep({
    required this.number,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: AppColors.primaryLight,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Center(
            child: Text(
              '$number',
              style: const TextStyle(
                color: AppColors.primary,
                fontWeight: FontWeight.w800,
                fontSize: 16,
              ),
            ),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 2),
              Text(subtitle,
                style: const TextStyle(
                  fontSize: 13,
                  color: AppColors.textSecondary,
                  height: 1.4,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SetupIllustration extends StatelessWidget {
  const _SetupIllustration();

  @override
  Widget build(BuildContext context) {
    // Placeholder illustration — replace with actual asset
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(Icons.back_hand_outlined, size: 80, color: Colors.brown.shade300),
        const SizedBox(height: 8),
        Text(
          'Camera → Fingers',
          style: TextStyle(
            color: Colors.brown.shade400,
            fontWeight: FontWeight.w600,
            fontSize: 13,
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SCREEN 2: BIOMETRIC CAPTURE (Live Camera + Real-time Feedback)
// ─────────────────────────────────────────────────────────────────────────────
class BiometricCaptureScreen extends StatefulWidget {
  final int stepIndex;
  final int totalSteps;
  final CaptureMode captureMode;
  final List<FingerID> fingers;
  final String stepLabel;
  final List<FingerID> missingFingers;

  const BiometricCaptureScreen({
    super.key,
    required this.stepIndex,
    required this.totalSteps,
    required this.captureMode,
    required this.fingers,
    required this.stepLabel,
    this.missingFingers = const [],
  });

  @override
  State<BiometricCaptureScreen> createState() => _BiometricCaptureScreenState();
}

class _BiometricCaptureScreenState extends State<BiometricCaptureScreen>
    with TickerProviderStateMixin {

  CaptureStatus _status = CaptureStatus.searching;
  String _statusMessage = 'Searching for hand...';
  String? _feedbackBadge;
  Color _borderColor = AppColors.primary;
  bool _isCapturing = false;
  StreamSubscription<Map<String, dynamic>>? _sdkSubscription;

  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;
  late AnimationController _borderController;

  final List<CaptureResult> _capturedResults = [];

  // Maps SDK event types → user-friendly messages
  static const _feedbackMessages = {
    'HAND_NOT_FOUND':    'Searching for hand...',
    'HAND_DETECTED':     'Hand detected — align fingers',
    'ALIGN_CLOSER':      'Move closer to the camera',
    'ALIGN_FARTHER':     'Move further away',
    'ALIGN_CENTER':      'Center your hand in the frame',
    'LIGHTING_LOW':      'Too dark — find better lighting',
    'LIGHTING_GOOD':     'Good lighting ✓',
    'MOTION_BLUR':       'Hold still — motion detected',
    'FINGER_COVERAGE':   'Spread fingers slightly apart',
    'CAPTURE_READY':     'Hold steady — capturing...',
    'PROCESSING':        'Processing fingerprints...',
    'CAPTURE_SUCCESS':   'Capture successful!',
    'LIVENESS_FAILED':   'Liveness check failed — retry',
    'QUALITY_LOW':       'Quality too low — retry',
    'TIMEOUT':           'Timeout — please try again',
  };

  @override
  void initState() {
    super.initState();

    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    )..repeat(reverse: true);

    _pulseAnimation = Tween<double>(begin: 0.95, end: 1.05)
        .animate(CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut));

    _borderController = AnimationController(
      duration: const Duration(milliseconds: 400),
      vsync: this,
    );

    _startCapture();
  }

  void _startCapture() {
    setState(() => _isCapturing = true);

    // Subscribe to real-time SDK feedback stream
    _sdkSubscription = BiometricSDKBridge.startCapture(
      mode: widget.captureMode,
      fingers: widget.fingers,
      missingFingers: widget.missingFingers,
    ).listen(
      _handleSDKEvent,
      onError: _handleSDKError,
    );
  }

  void _handleSDKEvent(Map<String, dynamic> event) {
    if (!mounted) return;

    final type = event['type'] as String? ?? '';
    final message = _feedbackMessages[type] ?? type;

    setState(() {
      _statusMessage = message;

      switch (type) {
        case 'LIGHTING_GOOD':
          _feedbackBadge = '☀️  Good lighting';
          _borderColor = AppColors.primary;
          break;
        case 'LIGHTING_LOW':
          _feedbackBadge = '🌑  Poor lighting';
          _borderColor = AppColors.warning;
          break;
        case 'MOTION_BLUR':
          _feedbackBadge = '⚡  Motion detected';
          _borderColor = AppColors.warning;
          break;
        case 'CAPTURE_READY':
          _feedbackBadge = '✅  Ready to capture';
          _borderColor = AppColors.primaryBright;
          _status = CaptureStatus.capturing;
          break;
        case 'PROCESSING':
          _feedbackBadge = null;
          _status = CaptureStatus.processing;
          break;
        case 'CAPTURE_SUCCESS':
          _borderColor = AppColors.primaryBright;
          _status = CaptureStatus.success;
          _handleCaptureSuccess(event);
          break;
        case 'LIVENESS_FAILED':
        case 'QUALITY_LOW':
        case 'TIMEOUT':
          _borderColor = AppColors.error;
          _status = CaptureStatus.failed;
          break;
        case 'HAND_DETECTED':
        case 'ALIGN_CLOSER':
        case 'ALIGN_FARTHER':
        case 'ALIGN_CENTER':
        case 'FINGER_COVERAGE':
          _feedbackBadge = null;
          _status = CaptureStatus.aligning;
          _borderColor = AppColors.primary;
          break;
        default:
          _status = CaptureStatus.searching;
          _borderColor = AppColors.primary;
      }
    });
  }

  void _handleCaptureSuccess(Map<String, dynamic> event) {
    final results = (event['results'] as List?)?.cast<Map<String, dynamic>>() ?? [];

    final parsed = results.map((r) {
      final fingerId = widget.fingers.firstWhere(
        (f) => f.name.toUpperCase() == (r['fingerId'] as String? ?? ''),
        orElse: () => widget.fingers.first,
      );
      return CaptureResult(
        fingerId: fingerId,
        isValid: r['status'] == 'success',
        qualityScore: (r['qualityScore'] as num?)?.toInt() ?? 0,
        livenessPassed: r['livenessPassed'] as bool? ?? false,
      );
    }).toList();

    _capturedResults.addAll(parsed);

    // Determine next step or go to review
    Future.delayed(const Duration(milliseconds: 800), () {
      if (!mounted) return;
      _navigateNext();
    });
  }

  void _navigateNext() {
    // Example flow: left4 → right4 → thumbs → review
    // In production, drive this from your workflow orchestrator
    if (widget.stepIndex < widget.totalSteps - 1) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => BiometricCaptureScreen(
            stepIndex: widget.stepIndex + 1,
            totalSteps: widget.totalSteps,
            captureMode: CaptureMode.rightFour,
            fingers: const [
              FingerID.rightIndex,
              FingerID.rightMiddle,
              FingerID.rightRing,
              FingerID.rightLittle,
            ],
            stepLabel: 'Right 4 Fingers',
          ),
        ),
      );
    } else {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => ReviewCaptureScreen(results: _capturedResults),
        ),
      );
    }
  }

  void _handleSDKError(dynamic error) {
    if (!mounted) return;
    setState(() {
      _status = CaptureStatus.failed;
      _statusMessage = 'An error occurred. Please retry.';
      _borderColor = AppColors.error;
    });
  }

  @override
  void dispose() {
    _sdkSubscription?.cancel();
    BiometricSDKBridge.cancelCapture();
    _pulseController.dispose();
    _borderController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.overlayDark,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            _buildProgressBar(),
            Expanded(child: _buildCameraArea()),
            _buildStatusPanel(),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.close, color: Colors.white),
            onPressed: () => Navigator.pop(context),
          ),
          const Expanded(
            child: Text(
              'Biometric Capture',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 17,
              ),
            ),
          ),
          // Step label
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
            decoration: BoxDecoration(
              color: AppColors.primaryLight,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              widget.stepLabel,
              style: const TextStyle(
                color: AppColors.primary,
                fontWeight: FontWeight.w700,
                fontSize: 12,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProgressBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
      child: Row(
        children: [
          Text(
            'Step ${widget.stepIndex + 1} of ${widget.totalSteps}',
            style: const TextStyle(
              color: AppColors.primaryBright,
              fontWeight: FontWeight.w700,
              fontSize: 13,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Row(
              children: List.generate(widget.totalSteps, (i) {
                final isCompleted = i < widget.stepIndex;
                final isCurrent = i == widget.stepIndex;
                return Expanded(
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 2),
                    height: 4,
                    decoration: BoxDecoration(
                      color: isCompleted
                          ? AppColors.primaryBright
                          : isCurrent
                              ? AppColors.primary
                              : Colors.white24,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCameraArea() {
    return Stack(
      alignment: Alignment.center,
      children: [
        // Camera preview placeholder — replace with real camera widget
        Container(
          color: const Color(0xFF0A1A0F),
          child: Center(
            child: Icon(
              Icons.back_hand_outlined,
              size: 140,
              color: Colors.white.withOpacity(0.08),
            ),
          ),
        ),

        // Finger guide lines inside the frame
        Positioned.fill(
          child: Align(
            alignment: const Alignment(0, -0.1),
            child: _FingerGuideOverlay(fingerCount: widget.fingers.length),
          ),
        ),

        // Animated scan frame
        AnimatedBuilder(
          animation: _pulseAnimation,
          builder: (context, child) {
            return Transform.scale(
              scale: _status == CaptureStatus.searching ? _pulseAnimation.value : 1.0,
              child: _ScanFrame(
                borderColor: _borderColor,
                isCapturing: _status == CaptureStatus.capturing,
              ),
            );
          },
        ),

        // Feedback badge pill
        if (_feedbackBadge != null)
          Positioned(
            bottom: 80,
            child: AnimatedOpacity(
              opacity: _feedbackBadge != null ? 1.0 : 0.0,
              duration: const Duration(milliseconds: 300),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
                decoration: BoxDecoration(
                  color: AppColors.overlayDark.withOpacity(0.85),
                  borderRadius: BorderRadius.circular(30),
                ),
                child: Text(
                  _feedbackBadge ?? '',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildStatusPanel() {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            'STATUS',
            style: TextStyle(
              color: AppColors.primary,
              fontWeight: FontWeight.w800,
              fontSize: 11,
              letterSpacing: 1.5,
            ),
          ),
          const SizedBox(height: 6),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 300),
            child: Text(
              _statusMessage,
              key: ValueKey(_statusMessage),
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontWeight: FontWeight.w700,
                fontSize: 20,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _ControlButton(
                icon: Icons.help_outline_rounded,
                onPressed: () => _showHelpDialog(context),
              ),
              _CaptureButton(
                isCapturing: _status == CaptureStatus.capturing,
                isProcessing: _status == CaptureStatus.processing,
              ),
              _ControlButton(
                icon: Icons.flash_off_rounded,
                onPressed: () {},
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _showHelpDialog(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => const _HelpSheet(),
    );
  }
}

class _ScanFrame extends StatelessWidget {
  final Color borderColor;
  final bool isCapturing;

  const _ScanFrame({required this.borderColor, required this.isCapturing});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 260,
      height: 340,
      decoration: BoxDecoration(
        border: Border.all(color: borderColor, width: 2.5),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Stack(
        children: [
          // Corner accents
          ..._buildCorners(borderColor),
          // Center horizontal guide line
          if (isCapturing)
            Positioned(
              top: 0,
              bottom: 0,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  height: 1.5,
                  color: borderColor.withOpacity(0.5),
                ),
              ),
            ),
        ],
      ),
    );
  }

  List<Widget> _buildCorners(Color color) {
    const size = 20.0;
    const thickness = 3.0;
    return [
      Positioned(top: -1, left: -1,
        child: _Corner(color: color, size: size, thickness: thickness,
            top: true, left: true)),
      Positioned(top: -1, right: -1,
        child: _Corner(color: color, size: size, thickness: thickness,
            top: true, left: false)),
      Positioned(bottom: -1, left: -1,
        child: _Corner(color: color, size: size, thickness: thickness,
            top: false, left: true)),
      Positioned(bottom: -1, right: -1,
        child: _Corner(color: color, size: size, thickness: thickness,
            top: false, left: false)),
    ];
  }
}

class _Corner extends StatelessWidget {
  final Color color;
  final double size;
  final double thickness;
  final bool top;
  final bool left;

  const _Corner({
    required this.color,
    required this.size,
    required this.thickness,
    required this.top,
    required this.left,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(painter: _CornerPainter(color, thickness, top, left)),
    );
  }
}

class _CornerPainter extends CustomPainter {
  final Color color;
  final double thickness;
  final bool top;
  final bool left;

  _CornerPainter(this.color, this.thickness, this.top, this.left);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = thickness
      ..style = PaintingStyle.stroke;

    final path = Path();
    if (top && left) {
      path.moveTo(0, size.height);
      path.lineTo(0, 0);
      path.lineTo(size.width, 0);
    } else if (top && !left) {
      path.moveTo(0, 0);
      path.lineTo(size.width, 0);
      path.lineTo(size.width, size.height);
    } else if (!top && left) {
      path.moveTo(0, 0);
      path.lineTo(0, size.height);
      path.lineTo(size.width, size.height);
    } else {
      path.moveTo(0, size.height);
      path.lineTo(size.width, size.height);
      path.lineTo(size.width, 0);
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_CornerPainter old) => false;
}

class _FingerGuideOverlay extends StatelessWidget {
  final int fingerCount;
  const _FingerGuideOverlay({required this.fingerCount});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 260,
      height: 100,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: List.generate(fingerCount, (i) {
          return Container(
            width: 6,
            height: 60 + (i % 2 == 0 ? 0.0 : 15.0),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.15),
              borderRadius: BorderRadius.circular(3),
            ),
          );
        }),
      ),
    );
  }
}

class _ControlButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onPressed;

  const _ControlButton({required this.icon, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return IconButton(
      icon: Icon(icon, color: AppColors.textSecondary, size: 26),
      onPressed: onPressed,
    );
  }
}

class _CaptureButton extends StatelessWidget {
  final bool isCapturing;
  final bool isProcessing;

  const _CaptureButton({required this.isCapturing, required this.isProcessing});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 64,
      height: 64,
      decoration: BoxDecoration(
        color: AppColors.primary,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withOpacity(0.35),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: isProcessing
          ? const Padding(
              padding: EdgeInsets.all(18),
              child: CircularProgressIndicator(
                color: Colors.white,
                strokeWidth: 2.5,
              ),
            )
          : const Icon(Icons.camera_alt_rounded, color: Colors.white, size: 28),
    );
  }
}

class _HelpSheet extends StatelessWidget {
  const _HelpSheet();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Tips for Best Capture',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18)),
          const SizedBox(height: 16),
          ...[
            'Use natural or bright indoor lighting',
            'Keep your hand flat with fingers together',
            'Hold your phone 4–6 inches from your hand',
            'Use a plain white or light wall as background',
            'Stay still during the capture',
          ].map((tip) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(
              children: [
                const Icon(Icons.check_circle_rounded,
                    color: AppColors.primary, size: 18),
                const SizedBox(width: 10),
                Expanded(child: Text(tip,
                  style: const TextStyle(fontSize: 14, color: AppColors.textPrimary))),
              ],
            ),
          )),
          const SizedBox(height: 16),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SCREEN 3: REVIEW CAPTURE
// ─────────────────────────────────────────────────────────────────────────────
class ReviewCaptureScreen extends StatefulWidget {
  final List<CaptureResult> results;

  const ReviewCaptureScreen({super.key, required this.results});

  @override
  State<ReviewCaptureScreen> createState() => _ReviewCaptureScreenState();
}

class _ReviewCaptureScreenState extends State<ReviewCaptureScreen> {
  late Map<String, List<CaptureResult>> _grouped;

  @override
  void initState() {
    super.initState();
    _grouped = {};
    for (final r in widget.results) {
      final group = r.fingerId.isLeft ? 'Left Hand' : 'Right Hand';
      _grouped.putIfAbsent(group, () => []).add(r);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text('Review Capture',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontWeight: FontWeight.w700,
            fontSize: 18,
          ),
        ),
        centerTitle: true,
      ),
      body: Column(
        children: [
          // Step dots
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: List.generate(3, (i) => Container(
                margin: const EdgeInsets.symmetric(horizontal: 4),
                width: i == 2 ? 28 : 8,
                height: 8,
                decoration: BoxDecoration(
                  color: i == 2 ? AppColors.primaryBright : AppColors.border,
                  borderRadius: BorderRadius.circular(4),
                ),
              )),
            ),
          ),

          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Verify Biometrics',
                    style: TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.w800,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Please ensure all captured prints are clear, high-contrast, and free of blur before submitting for verification.',
                    style: TextStyle(
                      fontSize: 14,
                      color: AppColors.textSecondary,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Hand result cards
                  ..._grouped.entries.map((entry) =>
                    _HandResultCard(
                      handLabel: entry.key,
                      results: entry.value,
                      onRetake: () => _retakeHand(entry.key),
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Confirm & Submit
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
            child: _PrimaryButton(
              label: 'Confirm & Submit',
              trailingIcon: Icons.arrow_forward_rounded,
              onPressed: _allValid ? _submit : null,
            ),
          ),
        ],
      ),
    );
  }

  bool get _allValid => widget.results.every((r) => r.isValid);

  void _retakeHand(String handLabel) {
    final isLeft = handLabel == 'Left Hand';
    Navigator.push(context, MaterialPageRoute(
      builder: (_) => BiometricCaptureScreen(
        stepIndex: isLeft ? 0 : 1,
        totalSteps: 3,
        captureMode: isLeft ? CaptureMode.leftFour : CaptureMode.rightFour,
        fingers: isLeft
            ? [FingerID.leftIndex, FingerID.leftMiddle, FingerID.leftRing, FingerID.leftLittle]
            : [FingerID.rightIndex, FingerID.rightMiddle, FingerID.rightRing, FingerID.rightLittle],
        stepLabel: handLabel,
      ),
    ));
  }

  void _submit() {
    // Pass results to your backend/workflow orchestrator
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Submitted!', style: TextStyle(fontWeight: FontWeight.w800)),
        content: const Text('Your biometric data has been submitted successfully.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context)
              ..pop()
              ..pop()
              ..pop(),
            child: const Text('Done', style: TextStyle(color: AppColors.primary, fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
  }
}

class _HandResultCard extends StatelessWidget {
  final String handLabel;
  final List<CaptureResult> results;
  final VoidCallback onRetake;

  const _HandResultCard({
    required this.handLabel,
    required this.results,
    required this.onRetake,
  });

  @override
  Widget build(BuildContext context) {
    final allValid = results.every((r) => r.isValid);
    final avgQuality = results.isEmpty ? 0
        : (results.map((r) => r.qualityScore).reduce((a, b) => a + b) / results.length).round();

    return Container(
      margin: const EdgeInsets.only(bottom: 20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 12,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
            child: Row(
              children: [
                const Icon(Icons.back_hand_outlined, size: 18, color: AppColors.textPrimary),
                const SizedBox(width: 8),
                Text(handLabel,
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: allValid ? AppColors.primaryLight : const Color(0xFFFEF2F2),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: allValid ? AppColors.primary : AppColors.error,
                      width: 1.2,
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        allValid ? Icons.check_circle_rounded : Icons.cancel_rounded,
                        size: 14,
                        color: allValid ? AppColors.primary : AppColors.error,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        allValid ? 'VALID' : 'INVALID',
                        style: TextStyle(
                          color: allValid ? AppColors.primary : AppColors.error,
                          fontWeight: FontWeight.w800,
                          fontSize: 12,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Finger chips — NOT showing actual fingerprint images per requirement
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: results.map((r) => _FingerChip(result: r)).toList(),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Icon(Icons.analytics_outlined, size: 14, color: AppColors.textSecondary),
                    const SizedBox(width: 4),
                    Text(
                      'Average quality score: $avgQuality/100',
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.textSecondary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Retake button
          Container(
            decoration: const BoxDecoration(
              border: Border(top: BorderSide(color: AppColors.border)),
            ),
            child: TextButton.icon(
              onPressed: onRetake,
              icon: const Icon(Icons.refresh_rounded, size: 16),
              label: Text('Retake $handLabel'),
              style: TextButton.styleFrom(
                foregroundColor: AppColors.textPrimary,
                padding: const EdgeInsets.symmetric(vertical: 14),
                minimumSize: const Size(double.infinity, 0),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _FingerChip extends StatelessWidget {
  final CaptureResult result;

  const _FingerChip({required this.result});

  @override
  Widget build(BuildContext context) {
    final isValid = result.isValid && result.livenessPassed;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: isValid ? AppColors.primaryLight : const Color(0xFFFEF2F2),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isValid ? Icons.fingerprint : Icons.warning_amber_rounded,
            size: 14,
            color: isValid ? AppColors.primary : AppColors.error,
          ),
          const SizedBox(width: 5),
          Text(
            result.fingerId.label,
            style: TextStyle(
              color: isValid ? AppColors.primary : AppColors.error,
              fontWeight: FontWeight.w600,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SCREEN 4: SPECIAL REGISTRATION (Missing Fingers)
// ─────────────────────────────────────────────────────────────────────────────
class SpecialRegistrationScreen extends StatefulWidget {
  const SpecialRegistrationScreen({super.key});

  @override
  State<SpecialRegistrationScreen> createState() => _SpecialRegistrationScreenState();
}

class _SpecialRegistrationScreenState extends State<SpecialRegistrationScreen> {
  // Start with all fingers available
  final Set<FingerID> _availableFingers = Set.from(FingerID.values);

  static const _leftFingers = [
    FingerID.leftLittle,
    FingerID.leftRing,
    FingerID.leftMiddle,
    FingerID.leftIndex,
    FingerID.leftThumb,
  ];

  static const _rightFingers = [
    FingerID.rightThumb,
    FingerID.rightIndex,
    FingerID.rightMiddle,
    FingerID.rightRing,
    FingerID.rightLittle,
  ];

  void _toggleFinger(FingerID finger) {
    setState(() {
      if (_availableFingers.contains(finger)) {
        _availableFingers.remove(finger);
      } else {
        _availableFingers.add(finger);
      }
    });
  }

  List<FingerID> get _missingFingers =>
      FingerID.values.where((f) => !_availableFingers.contains(f)).toList();

  String get _selectedFingersText {
    if (_availableFingers.isEmpty) return 'No fingers selected';
    return _availableFingers.map((f) => f.label).join(', ');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Special Registration',
                    style: TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.w800,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text('Tap the fingers you can provide',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Deselect any fingers that are unavailable or difficult to capture.',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppColors.textSecondary,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Hand selector card
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Column(
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Column(
                                children: [
                                  const Text('Left Hand',
                                    style: TextStyle(
                                      fontWeight: FontWeight.w700,
                                      fontSize: 14,
                                      color: AppColors.textPrimary,
                                    ),
                                  ),
                                  const SizedBox(height: 12),
                                  _HandDiagram(
                                    fingers: _leftFingers,
                                    availableFingers: _availableFingers,
                                    onToggle: _toggleFinger,
                                    isLeft: true,
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Column(
                                children: [
                                  const Text('Right Hand',
                                    style: TextStyle(
                                      fontWeight: FontWeight.w700,
                                      fontSize: 14,
                                      color: AppColors.textPrimary,
                                    ),
                                  ),
                                  const SizedBox(height: 12),
                                  _HandDiagram(
                                    fingers: _rightFingers,
                                    availableFingers: _availableFingers,
                                    onToggle: _toggleFinger,
                                    isLeft: false,
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),

                        // Finger code buttons
                        Row(
                          children: [
                            Expanded(
                              child: _FingerButtonRow(
                                fingers: _leftFingers,
                                available: _availableFingers,
                                onToggle: _toggleFinger,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: _FingerButtonRow(
                                fingers: _rightFingers,
                                available: _availableFingers,
                                onToggle: _toggleFinger,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 20),

                  // Selected fingers summary
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.primaryLight,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.info_outline, color: AppColors.primary, size: 18),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('Selected Fingers:',
                                style: TextStyle(
                                  fontWeight: FontWeight.w700,
                                  color: AppColors.primary,
                                  fontSize: 13,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                _selectedFingersText,
                                style: const TextStyle(
                                  color: AppColors.primary,
                                  fontSize: 13,
                                  height: 1.4,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Action buttons
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
            child: _PrimaryButton(
              label: 'Continue with Selected Fingers',
              trailingIcon: Icons.arrow_forward_rounded,
              onPressed: _availableFingers.isEmpty ? null : _continueWithSelected,
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
            child: TextButton(
              onPressed: _captureAll,
              child: const Text(
                'Capture All Fingers Instead',
                style: TextStyle(
                  color: AppColors.primary,
                  fontWeight: FontWeight.w600,
                  decoration: TextDecoration.underline,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _continueWithSelected() {
    final fingers = _availableFingers.toList();
    Navigator.push(context, MaterialPageRoute(
      builder: (_) => BiometricCaptureScreen(
        stepIndex: 0,
        totalSteps: 1,
        captureMode: CaptureMode.partialCapture,
        fingers: fingers,
        missingFingers: _missingFingers,
        stepLabel: 'Partial Capture',
      ),
    ));
  }

  void _captureAll() {
    setState(() => _availableFingers.addAll(FingerID.values));
    Navigator.pop(context);
  }
}

class _HandDiagram extends StatelessWidget {
  final List<FingerID> fingers;
  final Set<FingerID> availableFingers;
  final ValueChanged<FingerID> onToggle;
  final bool isLeft;

  const _HandDiagram({
    required this.fingers,
    required this.availableFingers,
    required this.onToggle,
    required this.isLeft,
  });

  @override
  Widget build(BuildContext context) {
    // Visual finger representation with tap targets
    return SizedBox(
      height: 120,
      child: CustomPaint(
        painter: _HandOutlinePainter(
          fingers: fingers,
          availableFingers: availableFingers,
          isLeft: isLeft,
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: fingers.map((f) {
            final isAvailable = availableFingers.contains(f);
            final isThumb = f == FingerID.leftThumb || f == FingerID.rightThumb;
            return GestureDetector(
              onTap: () => onToggle(f),
              child: Container(
                width: 24,
                height: isThumb ? 40 : 70,
                margin: const EdgeInsets.symmetric(horizontal: 2),
                decoration: BoxDecoration(
                  color: isAvailable
                      ? AppColors.primary.withOpacity(0.15)
                      : Colors.grey.withOpacity(0.1),
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                  border: Border.all(
                    color: isAvailable ? AppColors.primary : Colors.grey.shade300,
                    width: 1.5,
                  ),
                ),
                child: isAvailable
                    ? const Icon(Icons.check_rounded, size: 12, color: AppColors.primary)
                    : null,
              ),
            );
          }).toList(),
        ),
      ),
    );
  }
}

class _HandOutlinePainter extends CustomPainter {
  final List<FingerID> fingers;
  final Set<FingerID> availableFingers;
  final bool isLeft;

  _HandOutlinePainter({
    required this.fingers,
    required this.availableFingers,
    required this.isLeft,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // Minimal palm line
    final paint = Paint()
      ..color = AppColors.border
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(4, size.height - 20, size.width - 8, 18),
        const Radius.circular(8),
      ),
      paint,
    );
  }

  @override
  bool shouldRepaint(_HandOutlinePainter old) =>
      old.availableFingers != availableFingers;
}

class _FingerButtonRow extends StatelessWidget {
  final List<FingerID> fingers;
  final Set<FingerID> available;
  final ValueChanged<FingerID> onToggle;

  const _FingerButtonRow({
    required this.fingers,
    required this.available,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 4,
      runSpacing: 6,
      alignment: WrapAlignment.center,
      children: fingers.map((f) {
        final isAvailable = available.contains(f);
        return GestureDetector(
          onTap: () => onToggle(f),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: isAvailable ? AppColors.primary : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: isAvailable ? AppColors.primary : AppColors.border,
                width: 1.5,
              ),
            ),
            child: Center(
              child: Text(
                f.shortCode,
                style: TextStyle(
                  color: isAvailable ? Colors.white : AppColors.textSecondary,
                  fontWeight: FontWeight.w800,
                  fontSize: 11,
                ),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SHARED WIDGETS
// ─────────────────────────────────────────────────────────────────────────────
class _PrimaryButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final IconData? trailingIcon;
  final VoidCallback? onPressed;

  const _PrimaryButton({
    required this.label,
    this.icon,
    this.trailingIcon,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 56,
      child: ElevatedButton(
        onPressed: onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          disabledBackgroundColor: AppColors.border,
          disabledForegroundColor: AppColors.textSecondary,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          elevation: 0,
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (icon != null) ...[
              Icon(icon, size: 20),
              const SizedBox(width: 8),
            ],
            Text(
              label,
              style: const TextStyle(
                fontWeight: FontWeight.w700,
                fontSize: 16,
              ),
            ),
            if (trailingIcon != null) ...[
              const SizedBox(width: 8),
              Icon(trailingIcon, size: 20),
            ],
          ],
        ),
      ),
    );
  }
}