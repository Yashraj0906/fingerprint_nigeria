import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:fingerprint_sdk/fingerprint_sdk.dart';
import 'package:permission_handler/permission_handler.dart';

void main() => runApp(const FingerprintApp());

class FingerprintApp extends StatelessWidget {
  const FingerprintApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'YellowSense Biometric SDK',
        theme: ThemeData(
          colorSchemeSeed: const Color(0xFFFFC107),
          useMaterial3: true,
          fontFamily: 'Roboto',
        ),
        home: const SelectionScreen(),
        debugShowCheckedModeBanner: false,
      );
}

// ─── 1. MODE SELECTION SCREEN ──────────────────────────────────────────────────

class SelectionScreen extends StatefulWidget {
  const SelectionScreen({super.key});

  @override
  State<SelectionScreen> createState() => _SelectionScreenState();
}

class _SelectionScreenState extends State<SelectionScreen> {
  final _sdk = FingerprintSdk.instance;
  bool _initialized = false;
  bool _isCapturing = false;
  String? _error;

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
      await _sdk.initialize(debugMode: false);
      setState(() => _initialized = true);
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  void _onSelect(CaptureMode mode) {
    if (_isCapturing || !_initialized) return;

    final txnId = "TXN-${DateTime.now().millisecondsSinceEpoch}";
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => LiveCaptureScreen(mode: mode, transactionId: txnId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: const Color(0xFFFFC107),
        centerTitle: true,
        title: const Text('YellowSense Biometric SDK',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 18)),
      ),
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 30),
          child: Column(
            children: [
              const Text('Select Capture Mode',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Color(0xFFFFC107))),
              const SizedBox(height: 8),
              const Text('Select the fingers you want to capture',
                  style: TextStyle(color: Colors.grey, fontSize: 13)),
              const SizedBox(height: 32),
              
              Row(
                children: [
                  Expanded(child: _HandCard(label: 'Left Hand', mode: CaptureMode.leftFour, onSelect: _onSelect)),
                  const SizedBox(width: 20),
                  Expanded(child: _HandCard(label: 'Right Hand', mode: CaptureMode.rightFour, onSelect: _onSelect)),
                ],
              ),
              
              const SizedBox(height: 40),
              const Divider(color: Colors.grey, thickness: 0.2),
              const SizedBox(height: 24),
              const Text('Quick Capture',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.black87)),
              const SizedBox(height: 20),
              
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  _QuickButton(label: 'Left Thumb', icon: Icons.thumb_up, mode: CaptureMode.leftThumb, onSelect: _onSelect),
                  _QuickButton(label: 'Right Thumb', icon: Icons.thumb_up, mode: CaptureMode.rightThumb, onSelect: _onSelect),
                  _QuickButton(label: 'Single Finger', icon: Icons.touch_app, mode: CaptureMode.singleFinger, onSelect: _onSelect),
                ],
              ),
              
              if (_error != null) ...[
                const SizedBox(height: 20),
                Text(_error!, style: const TextStyle(color: Colors.red)),
              ]
            ],
          ),
        ),
      ),
    );
  }
}

class _HandCard extends StatelessWidget {
  final String label;
  final CaptureMode mode;
  final Function(CaptureMode) onSelect;

  const _HandCard({required this.label, required this.mode, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => onSelect(mode),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFFF1F8E9),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFFFC107), width: 1.5),
        ),
        child: Column(
          children: [
             Text(label, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
             const SizedBox(height: 12),
             const Icon(Icons.back_hand, size: 64, color: Color(0xFF1B5E20)),
             const SizedBox(height: 12),
             const Text('Tap to Capture', style: TextStyle(fontSize: 11, color: Color(0xFFFFC107))),
          ],
        ),
      ),
    );
  }
}

class _QuickButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final CaptureMode mode;
  final Function(CaptureMode) onSelect;

  const _QuickButton({required this.label, required this.icon, required this.mode, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => onSelect(mode),
      child: Container(
        width: 100,
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: const Color(0xFFF1F8E9),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFFFC107), width: 0.5),
        ),
        child: Column(
          children: [
            Icon(icon, color: const Color(0xFFFFC107), size: 24),
            const SizedBox(height: 8),
            Text(label, textAlign: TextAlign.center, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}

// ─── 2. LIVE CAPTURE SCREEN ───────────────────────────────────────────────────

class LiveCaptureScreen extends StatefulWidget {
  final CaptureMode mode;
  final String? transactionId;
  const LiveCaptureScreen({super.key, required this.mode, this.transactionId});

  @override
  State<LiveCaptureScreen> createState() => _LiveCaptureScreenState();
}

class _LiveCaptureScreenState extends State<LiveCaptureScreen> {
  final _sdk = FingerprintSdk.instance;
  int? _textureId;
  FeedbackEvent? _feedback;
  bool _initialized = false;
  
  @override
  void initState() {
    super.initState();
    _start();
  }

  @override
  void dispose() {
    _sdk.stopCapture();
    _sdk.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    try {
      final tid = await _sdk.initialize(debugMode: false);
      if (!mounted) return;
      if (tid > 0) {
        setState(() { _textureId = tid; _initialized = true; });
      } else {
        setState(() { _initialized = true; });
      }

      await Future.delayed(const Duration(milliseconds: 500));
      if (!mounted) return;

      _sdk.feedbackStream.listen((e) { 
          if (mounted) setState(() { _feedback = e; }); 
      });

      final request = CaptureRequest(
        transactionId: widget.transactionId ?? 'TXN-${DateTime.now().millisecondsSinceEpoch}',
        captureMode: widget.mode,
        fingersRequested: _getFingersForMode(widget.mode),
        options: const CaptureOptions(
          performLivenessCheck: true,
          performQualityCheck: true,
          returnProcessedImage: true,
          timeoutSeconds: 60,
        ),
      );
      final response = await _sdk.startCapture(request);
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => ResultSummaryScreen(response: response, mode: widget.mode)),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Capture error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  List<FingerId> _getFingersForMode(CaptureMode mode) => switch (mode) {
    CaptureMode.leftFour => [FingerId.leftIndex, FingerId.leftMiddle, FingerId.leftRing, FingerId.leftLittle],
    CaptureMode.rightFour => [FingerId.rightIndex, FingerId.rightMiddle, FingerId.rightRing, FingerId.rightLittle],
    CaptureMode.leftThumb => [FingerId.leftThumb],
    CaptureMode.rightThumb => [FingerId.rightThumb],
    _ => [FingerId.rightIndex],
  };

  @override
  Widget build(BuildContext context) {
    final expectedCount = _getFingersForMode(widget.mode).length;
    
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // 1. Camera Preview
          if (_textureId != null && _textureId! > 0)
             Positioned.fill(
               child: Center(
                 child: AspectRatio(
                   aspectRatio: 9 / 16,
                   child: Texture(textureId: _textureId!),
                 ),
               ),
              ),
          
          // 2. Header & Badges
          Positioned(
            top: 50, left: 16, right: 16,
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    InkWell(
                      onTap: () => Navigator.pop(context),
                      child: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(color: const Color(0xFFFFC107), borderRadius: BorderRadius.circular(12)),
                        child: const Icon(Icons.arrow_back, color: Colors.white, size: 24),
                      ),
                    ),
                    Text(widget.mode.name.toUpperCase().replaceAll('_', ' '),
                        style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
                    const SizedBox(width: 40),
                  ],
                ),
                const SizedBox(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _Badge(
                      label: 'Quality: ${(_feedback?.confidence ?? 0 * 100).toStringAsFixed(0)}%',
                      color: Colors.orange,
                    ),
                    _Badge(
                      label: '$expectedCount Fingers',
                      color: const Color(0xFFFFC107),
                      icon: Icons.check_circle,
                    ),
                  ],
                ),
              ],
            ),
          ),

          // 3. Scanner ROI Box Overlay
          Positioned.fill(
            child: CustomPaint(
              painter: ScannerOverlayPainter(mode: widget.mode),
            ),
          ),
          
          // 4. Instruction Bar
          Positioned(
            bottom: 30, left: 24, right: 24,
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
              decoration: BoxDecoration(
                color: const Color(0xFFFFC107),
                borderRadius: BorderRadius.circular(16),
                boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.3), blurRadius: 10, offset: const Offset(0, 5))],
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.check_circle, color: Colors.white, size: 24),
                  const SizedBox(width: 12),
                  Text(_feedback?.message ?? "Place your hand inside the box",
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;
  const _Badge({required this.label, required this.color, this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(20)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[Icon(icon, size: 14, color: Colors.white), const SizedBox(width: 6)],
          Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
        ],
      ),
    );
  }
}

// ─── 3. RESULT SUMMARY SCREEN ─────────────────────────────────────────────────

class ResultSummaryScreen extends StatelessWidget {
  final CaptureResponse response;
  final CaptureMode mode;
  const ResultSummaryScreen({super.key, required this.response, required this.mode});

  @override
  Widget build(BuildContext context) {
    final successFingers = response.results.where((r) => r.status == FingerStatus.success).toList();
    final avgQuality = successFingers.isEmpty ? 0.0 : successFingers.fold(0.0, (sum, e) => sum + e.qualityScore) / successFingers.length;
    final livenessPassed = response.results.every((r) => r.livenessPassed);

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: const Text('Capture Result', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFFFFC107),
        centerTitle: true,
        elevation: 0,
        automaticallyImplyLeading: false,
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            const SizedBox(height: 24),
            // Success Icon
            Container(
              width: 100, height: 100,
              decoration: BoxDecoration(
                color: Colors.white,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.green, width: 3),
              ),
              child: const Icon(Icons.check, color: Colors.green, size: 64),
            ),
            const SizedBox(height: 16),
            const Text('Capture Successful!', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Color(0xFFFFC107))),
            Text(mode.name.toUpperCase().replaceAll('_', ' '), style: TextStyle(fontSize: 14, color: Colors.grey.shade600, letterSpacing: 1.2)),
            
            const SizedBox(height: 24),
            // Captured Image
            if (successFingers.isNotEmpty)
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 24),
                height: 240,
                width: double.infinity,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(20),
                  image: DecorationImage(
                    image: MemoryImage(base64Decode(successFingers.first.processedImage ?? '')),
                    fit: BoxFit.cover,
                  ),
                ),
              ),
            
            Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Quality Score Bar
                  const Text('Quality Score', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: LinearProgressIndicator(
                          value: avgQuality / 100,
                          minHeight: 12,
                          backgroundColor: Colors.grey.shade200,
                          color: const Color(0xFFFFC107),
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Text('${avgQuality.toInt()}%', style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFFFFC107), fontSize: 18)),
                    ],
                  ),

                  const SizedBox(height: 32),
                  // Quality Details Section
                  const Text('Quality Details', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                  const SizedBox(height: 16),
                  _MetricDetail(label: 'Sharpness (Blur)', value: successFingers.isEmpty ? 0 : successFingers.map((e) => e.sharpnessScore).reduce((a, b) => a + b) / successFingers.length, icon: Icons.grid_on),
                  _MetricDetail(label: 'Brightness', value: successFingers.isEmpty ? 0 : successFingers.map((e) => e.brightnessScore).reduce((a, b) => a + b) / successFingers.length, icon: Icons.light_mode),
                  _MetricDetail(label: 'Centering', value: successFingers.isEmpty ? 0 : successFingers.map((e) => e.centeringScore).reduce((a, b) => a + b) / successFingers.length, icon: Icons.center_focus_strong),
                  
                  const SizedBox(height: 24),
                  const Divider(),
                  const SizedBox(height: 24),
                  
                  // Transaction Info
                  _InfoRow(label: 'Transaction ID', value: response.transactionId.substring(0, 12) + '...'),
                  _InfoRow(label: 'Fingers Captured', value: successFingers.length.toString()),
                  _InfoRow(
                    label: 'Liveness Check', 
                    value: livenessPassed ? 'Passed ✓' : 'Failed ❌',
                    valueColor: livenessPassed ? Colors.green : Colors.red,
                  ),
                  
                  const SizedBox(height: 32),
                  // Finger Details List
                  const Text('Finger Details', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                  const SizedBox(height: 12),
                  ...response.results.map((r) => _FingerScoreItem(finger: r)),
                  
                  const SizedBox(height: 40),
                  // Buttons
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(color: Color(0xFFFFC107)),
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                          onPressed: () => Navigator.pop(context),
                          child: const Text('Capture Again', style: TextStyle(color: Color(0xFFFFC107), fontWeight: FontWeight.bold)),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFFFC107),
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                          onPressed: () => Navigator.of(context).popUntil((r) => r.isFirst),
                          child: const Text('Done', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricDetail extends StatelessWidget {
  final String label;
  final double value;
  final IconData icon;
  const _MetricDetail({required this.label, required this.value, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        children: [
          Icon(icon, size: 20, color: Colors.grey),
          const SizedBox(width: 12),
          Expanded(child: Text(label, style: const TextStyle(color: Colors.grey, fontSize: 14))),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(color: const Color(0xFFFFF8E1), borderRadius: BorderRadius.circular(20)),
            child: Text('${value.toInt()}%', style: const TextStyle(color: Color(0xFFFFC107), fontWeight: FontWeight.bold, fontSize: 12)),
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;
  const _InfoRow({required this.label, required this.value, this.valueColor});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Text(label, style: const TextStyle(color: Colors.grey, fontSize: 14)),
          const Spacer(),
          Text(value, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: valueColor ?? Colors.black87)),
        ],
      ),
    );
  }
}

class _FingerScoreItem extends StatelessWidget {
  final FingerResult finger;
  const _FingerScoreItem({required this.finger});

  @override
  Widget build(BuildContext context) {
    final name = finger.fingerId.toUpperCase().replaceAll('_', ' ');
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        children: [
          Icon(finger.status == FingerStatus.success ? Icons.check_circle : Icons.error, color: finger.status == FingerStatus.success ? Colors.green : Colors.red, size: 20),
          const SizedBox(width: 12),
          Text(name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
            decoration: BoxDecoration(color: const Color(0xFFE8F5E9), borderRadius: BorderRadius.circular(8)),
            child: Text('Q: ${finger.qualityScore.toInt()}', style: const TextStyle(color: Colors.green, fontWeight: FontWeight.bold, fontSize: 12)),
          ),
        ],
      ),
    );
  }
}

// ─── 4. UI COMPONENTS ────────────────────────────────────────────────────────

class ScannerOverlayPainter extends CustomPainter {
  final CaptureMode mode;
  ScannerOverlayPainter({required this.mode});

  @override
  void paint(Canvas canvas, Size size) {
    final centerX = size.width / 2;
    final centerY = size.height / 2;
    
    // Main Scanning Box (65% width, proportional height)
    final boxWidth = size.width * 0.75;
    final boxHeight = boxWidth * 0.85;
    final rect = Rect.fromCenter(center: Offset(centerX, centerY), width: boxWidth, height: boxHeight);
    
    final paint = Paint()
      ..color = const Color(0xFFFFC107)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.0;

    // Outer Rounded Box
    canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(24)), paint);

    // If capturing 4 fingers, draw 4 vertical slots
    if (mode == CaptureMode.leftFour || mode == CaptureMode.rightFour) {
        final slotWidth = boxWidth / 4;
        final slotPaint = Paint()
          ..color = Colors.white.withOpacity(0.3)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.2;
        
        for (int i = 1; i < 4; i++) {
            final x = rect.left + (slotWidth * i);
            canvas.drawLine(Offset(x, rect.top + 30), Offset(x, rect.bottom - 30), slotPaint);
        }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
