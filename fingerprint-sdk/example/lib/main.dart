import 'package:flutter/material.dart';
import 'package:fingerprint_sdk/fingerprint_sdk.dart';
import 'package:permission_handler/permission_handler.dart';

void main() => runApp(const FingerprintApp());

class FingerprintApp extends StatelessWidget {
  const FingerprintApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'YellowSense Fingerprint',
        theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
        home: const CaptureScreen(),
        debugShowCheckedModeBanner: false,
      );
}

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  final _sdk = FingerprintSdk.instance;

  FeedbackEvent? _feedback;
  CaptureResponse? _result;
  bool _capturing = false;
  bool _initialized = false;
  bool _debugMode = false;
  String? _error;
  String _sdkVersion = '';

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final status = await Permission.camera.request();
    if (!status.isGranted) {
      setState(() => _error = 'Camera permission denied');
      return;
    }
    try {
      await _sdk.initialize(debugMode: _debugMode);
      final version = await _sdk.getVersion();
      _sdk.feedbackStream.listen(
        (event) { if (mounted) setState(() => _feedback = event); },
        onError: (e) { if (mounted) setState(() => _error = e.toString()); },
      );
      setState(() { _initialized = true; _sdkVersion = version; });
    } on SdkException catch (e) {
      setState(() => _error = '${e.code.name}: ${e.message}');
    }
  }

  Future<void> _startCapture() async {
    setState(() { _capturing = true; _result = null; _error = null; });

    final request = CaptureRequest(
      transactionId: 'TXN-${DateTime.now().millisecondsSinceEpoch}',
      captureMode: CaptureMode.rightFour,
      fingersRequested: [
        FingerId.rightIndex,
        FingerId.rightMiddle,
        FingerId.rightRing,
        FingerId.rightLittle,
      ],
      options: const CaptureOptions(
        performLivenessCheck: true,
        performQualityCheck: true,
        returnTemplate: true,
        returnProcessedImage: false,
        returnRawImage: false,
        maxRetries: 3,
        timeoutSeconds: 30,
      ),
    );

    try {
      final response = await _sdk.startCapture(request);
      setState(() { _result = response; _capturing = false; });
    } on SdkException catch (e) {
      setState(() { _error = '${e.code.name}: ${e.message}'; _capturing = false; });
    }
  }

  Future<void> _stopCapture() async {
    await _sdk.stopCapture();
    setState(() => _capturing = false);
  }

  @override
  void dispose() {
    _sdk.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('YellowSense Fingerprint'),
        actions: [
          if (_sdkVersion.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
              child: Text('v$_sdkVersion',
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
            ),
          IconButton(
            icon: Icon(_debugMode ? Icons.bug_report : Icons.bug_report_outlined),
            tooltip: 'Toggle debug mode',
            onPressed: () => setState(() => _debugMode = !_debugMode),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _FeedbackCard(feedback: _feedback, debugMode: _debugMode),
            const SizedBox(height: 16),
            if (_error != null) ...[
              _ErrorCard(message: _error!),
              const SizedBox(height: 16),
            ],
            if (_result != null) ...[
              _ResultCard(response: _result!),
              const SizedBox(height: 16),
            ],
            const Spacer(),
            if (_capturing)
              OutlinedButton.icon(
                onPressed: _stopCapture,
                icon: const Icon(Icons.stop, color: Colors.red),
                label: const Text('Stop Capture', style: TextStyle(color: Colors.red)),
              )
            else
              FilledButton.icon(
                onPressed: _initialized ? _startCapture : null,
                icon: const Icon(Icons.fingerprint),
                label: Text(_initialized ? 'Start Capture' : 'Initializing…'),
              ),
          ],
        ),
      ),
    );
  }
}

// ─── Feedback Card ────────────────────────────────────────────────────────────

class _FeedbackCard extends StatelessWidget {
  final FeedbackEvent? feedback;
  final bool debugMode;
  const _FeedbackCard({this.feedback, required this.debugMode});

  @override
  Widget build(BuildContext context) {
    final f = feedback;
    if (f == null) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
            const SizedBox(width: 12),
            Text('Waiting for camera…', style: TextStyle(color: Colors.grey.shade600)),
          ]),
        ),
      );
    }

    final (color, icon) = _style(f.type);

    return Card(
      color: color.withOpacity(0.08),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: color.withOpacity(0.3)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(width: 10),
            Expanded(
              child: Text(f.message,
                  style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 15)),
            ),
          ]),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: f.confidence,
              color: color,
              backgroundColor: color.withOpacity(0.15),
              minHeight: 6,
            ),
          ),
          if (debugMode) ...[
            const SizedBox(height: 6),
            Text('type: ${f.type.name}  confidence: ${(f.confidence * 100).toStringAsFixed(0)}%',
                style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),
          ],
        ]),
      ),
    );
  }

  (Color, IconData) _style(FeedbackType t) => switch (t) {
    FeedbackType.ready      => (Colors.green,  Icons.check_circle_outline),
    FeedbackType.lighting   => (Colors.orange, Icons.wb_sunny_outlined),
    FeedbackType.motion     => (Colors.red,    Icons.blur_on),
    FeedbackType.distance   => (Colors.purple, Icons.open_with),
    FeedbackType.alignment  => (Colors.blue,   Icons.center_focus_strong),
    FeedbackType.processing => (Colors.teal,   Icons.hourglass_top),
  };
}

// ─── Error Card ───────────────────────────────────────────────────────────────

class _ErrorCard extends StatelessWidget {
  final String message;
  const _ErrorCard({required this.message});

  @override
  Widget build(BuildContext context) => Card(
    color: Colors.red.shade50,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Row(children: [
        const Icon(Icons.error_outline, color: Colors.red),
        const SizedBox(width: 10),
        Expanded(child: Text(message, style: const TextStyle(color: Colors.red))),
      ]),
    ),
  );
}

// ─── Result Card ──────────────────────────────────────────────────────────────

class _ResultCard extends StatelessWidget {
  final CaptureResponse response;
  const _ResultCard({required this.response});

  @override
  Widget build(BuildContext context) {
    final ok = response.overallStatus == CaptureStatus.success;
    return Card(
      color: ok ? Colors.green.shade50 : Colors.orange.shade50,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(ok ? Icons.verified_outlined : Icons.warning_amber_outlined,
                color: ok ? Colors.green : Colors.orange),
            const SizedBox(width: 8),
            Expanded(
              child: Text(response.transactionId,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                  overflow: TextOverflow.ellipsis),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: ok ? Colors.green : Colors.orange,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(ok ? 'SUCCESS' : 'FAILED',
                  style: const TextStyle(color: Colors.white, fontSize: 11,
                      fontWeight: FontWeight.bold)),
            ),
          ]),
          const Divider(height: 20),
          ...response.results.map((r) => _FingerRow(result: r)),
        ]),
      ),
    );
  }
}

class _FingerRow extends StatelessWidget {
  final FingerResult result;
  const _FingerRow({required this.result});

  @override
  Widget build(BuildContext context) {
    final (icon, color) = switch (result.status) {
      FingerStatus.success => (Icons.check_circle, Colors.green),
      FingerStatus.missing => (Icons.remove_circle_outline, Colors.grey),
      _                    => (Icons.cancel_outlined, Colors.red),
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 8),
        Expanded(
          child: Text(result.fingerId,
              style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13)),
        ),
        if (result.status == FingerStatus.success) ...[
          _QualityBadge(score: result.qualityScore),
          const SizedBox(width: 6),
          Icon(
            result.livenessPassed ? Icons.shield_outlined : Icons.shield_outlined,
            size: 16,
            color: result.livenessPassed ? Colors.green : Colors.red,
          ),
        ],
        if (result.errorCode != null)
          Text(result.errorCode!,
              style: const TextStyle(color: Colors.red, fontSize: 11)),
      ]),
    );
  }
}

class _QualityBadge extends StatelessWidget {
  final double score;
  const _QualityBadge({required this.score});

  @override
  Widget build(BuildContext context) {
    final color = score > 70 ? Colors.green : score >= 40 ? Colors.orange : Colors.red;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Text('Q: ${score.toStringAsFixed(0)}',
          style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600)),
    );
  }
}
