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
  bool _isDiagnosticMode = false;
  
  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    final tid = await _sdk.initialize(debugMode: false);
    _sdk.feedbackStream.listen((e) { 
        if (mounted) setState(() { _feedback = e; }); 
    });
    setState(() { _textureId = tid; _initialized = true; });
    
    try {
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
          MaterialPageRoute(builder: (_) => ResultSummaryScreen(response: response)),
        );
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
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
    return Scaffold(
      backgroundColor: Colors.black,
      body: GestureDetector(
        onDoubleTap: () => setState(() => _isDiagnosticMode = !_isDiagnosticMode),
        child: Stack(
          children: [
            if (_textureId != null)
               Positioned.fill(
                 child: Center(
                   child: AspectRatio(
                     aspectRatio: 9 / 16,
                     child: Texture(textureId: _textureId!),
                   ),
                 ),
                ),
            
            // Header
            Positioned(
              top: 50, left: 0, right: 0,
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      IconButton(icon: const Icon(Icons.arrow_back, color: Colors.white), onPressed: () => Navigator.pop(context)),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                        decoration: BoxDecoration(color: const Color(0xFFFFC107), borderRadius: BorderRadius.circular(20)),
                        child: Text(widget.mode.name.toUpperCase().replaceAll('_', ' '),
                            style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                      ),
                      const SizedBox(width: 48),
                    ],
                  ),
                  const SizedBox(height: 20),
                  if (_feedback != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      decoration: BoxDecoration(color: Colors.orange, borderRadius: BorderRadius.circular(20)),
                      child: Text('Quality: ${(_feedback!.confidence * 100).toStringAsFixed(0)}%',
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                    ),
                ],
              ),
            ),

            // Scanner ROI Box Overlay
            Positioned.fill(
              child: CustomPaint(
                painter: ScannerOverlayPainter(mode: widget.mode),
              ),
            ),
            
            // Bottom Instruction Bar
            Positioned(
              bottom: 0, left: 0, right: 0,
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 18),
                decoration: const BoxDecoration(color: Color(0xFFFFC107)),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.info_outline, color: Colors.white, size: 20),
                    SizedBox(width: 10),
                    Text("Place your finger in front of camera",
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15)),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DiagRow extends StatelessWidget {
  final String label;
  final String value;
  const _DiagRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text('$label: $value', style: const TextStyle(color: Colors.white, fontSize: 11, fontFamily: 'monospace')),
    );
  }
}

// ─── 3. RESULT SUMMARY SCREEN ─────────────────────────────────────────────────

class ResultSummaryScreen extends StatefulWidget {
  final CaptureResponse response;
  const ResultSummaryScreen({super.key, required this.response});

  @override
  State<ResultSummaryScreen> createState() => _ResultSummaryScreenState();
}

class _ResultSummaryScreenState extends State<ResultSummaryScreen> {
  int _selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    _selectedIndex = widget.response.results.indexWhere((r) => r.status == FingerStatus.success);
    if (_selectedIndex < 0) _selectedIndex = 0;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Capture Result'),
        backgroundColor: Colors.black,
        leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst)),
      ),
      backgroundColor: Colors.black,
      body: SingleChildScrollView(
        child: Column(
          children: [
            if (widget.response.results.isNotEmpty && _selectedIndex < widget.response.results.length)
              Container(
                height: 280, width: double.infinity,
                color: Colors.black,
                child: widget.response.results[_selectedIndex].processedImage != null
                    ? Image.memory(
                        base64Decode(widget.response.results[_selectedIndex].processedImage!),
                        fit: BoxFit.cover,
                      )
                    : const Center(child: Icon(Icons.fingerprint, color: Colors.white24, size: 80)),
              ),
              
            Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _MetricCard(
                    label: 'Overall Quality Score', 
                    value: widget.response.results.isEmpty ? 0 : widget.response.results.fold(0.0, (sum, e) => sum + e.qualityScore) / (widget.response.results.length * 100),
                    results: widget.response.results,
                  ),
                  const SizedBox(height: 12),
                  _ResultBadge(passed: widget.response.results.every((r) => r.livenessPassed)),
                  const SizedBox(height: 16),
                  
                  ...List.generate(widget.response.results.length, (index) {
                    final finger = widget.response.results[index];
                    return GestureDetector(
                       onTap: () => setState(() => _selectedIndex = index),
                       child: Container(
                         margin: const EdgeInsets.only(bottom: 8),
                         decoration: BoxDecoration(
                           border: Border.all(color: _selectedIndex == index ? const Color(0xFFFFC107) : Colors.transparent, width: 2),
                           borderRadius: BorderRadius.circular(14),
                         ),
                         child: _FingerDetailItem(finger: finger),
                       ),
                    );
                  }),
                  
                  const SizedBox(height: 16),
                  _TransactionTable(response: widget.response),
                  const SizedBox(height: 24),
                  
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFFFC107),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
                    icon: const Icon(Icons.home),
                    label: const Text('Done', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFFFFC107),
                      side: const BorderSide(color: Color(0xFFFFC107)),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.refresh),
                    label: const Text('Capture Again'),
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

class _FingerDetailItem extends StatelessWidget {
  final FingerResult finger;
  const _FingerDetailItem({required this.finger});

  @override
  Widget build(BuildContext context) {
    var name = finger.fingerId.toUpperCase().replaceAll('_', ' ');
    if (name == 'RIGHT INDEX' && finger.fingerId == 'RIGHT_INDEX') {
        name = 'FINGER SCANNED'; 
    }
    return Card(
      elevation: 0, color: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: Colors.grey.shade200)),
      child: ExpansionTile(
        leading: Icon(
          finger.status == FingerStatus.success ? Icons.check_circle : Icons.error_outline,
          color: finger.status == FingerStatus.success ? Colors.green : Colors.red,
        ),
        title: Text(name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
        trailing: Text('Q: ${finger.qualityScore.toInt()}', style: const TextStyle(color: Color(0xFFFFC107), fontWeight: FontWeight.bold)),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: _DetailedQualityCard(finger: finger),
          )
        ],
      ),
    );
  }
}

class _DetailedQualityCard extends StatelessWidget {
  final FingerResult finger;
  const _DetailedQualityCard({super.key, required this.finger});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
          const Text('Quality Details', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
          const SizedBox(height: 16),
          _DetailRow(icon: Icons.grid_on, label: 'Sharpness Score', value: finger.sharpnessScore),
          _DetailRow(icon: Icons.flare, label: 'Texture Score (Liveness)', value: finger.livenessConfidence * 100),
          _DetailRow(icon: Icons.shield, label: 'Liveness Verdict', value: finger.livenessPassed ? 100 : 0, isVerdict: true),
      ],
    );
  }
}

class _ResultBadge extends StatelessWidget {
  final bool passed;
  const _ResultBadge({required this.passed});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
      decoration: BoxDecoration(
        color: passed ? Colors.green.shade600 : Colors.red.shade600,
        borderRadius: BorderRadius.circular(8),
        boxShadow: [
            BoxShadow(color: (passed ? Colors.green : Colors.red).withOpacity(0.3), blurRadius: 8, offset: const Offset(0, 4)),
        ],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(passed ? Icons.verified_user : Icons.gpp_bad, color: Colors.white, size: 24),
          const SizedBox(width: 12),
          Text(
            passed ? "AUTHENTIC BIOMETRIC VERIFIED" : "SECURITY ALERT: SPOOF DETECTED",
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
          ),
        ],
      ),
    );
  }
}

class _MetricCard extends StatefulWidget {
  final String label;
  final double value;
  final List<FingerResult> results;
  const _MetricCard({required this.label, required this.value, required this.results});

  @override
  State<_MetricCard> createState() => _MetricCardState();
}

class _MetricCardState extends State<_MetricCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final totalSharpness = widget.results.fold(0.0, (sum, e) => sum + e.sharpnessScore);
    final totalLiveness  = widget.results.fold(0.0, (sum, e) => sum + e.livenessConfidence);
    final avgSharpness   = widget.results.isEmpty ? 0.0 : totalSharpness / widget.results.length;
    final avgLiveness    = widget.results.isEmpty ? 0.0 : totalLiveness / widget.results.length;

    return InkWell(
      onTap: () => setState(() => _expanded = !_expanded),
      child: Card(
        elevation: 0, color: Colors.grey.shade50,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: Colors.grey.shade200)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(widget.label, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                Icon(_expanded ? Icons.expand_less : Icons.expand_more, size: 16, color: Colors.grey),
              ],
            ),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: LinearProgressIndicator(value: widget.value, color: const Color(0xFFFFC107), backgroundColor: Colors.grey.shade200, minHeight: 8)),
              const SizedBox(width: 12),
              Text('${(widget.value * 100).toStringAsFixed(0)}%', style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFFFFC107))),
            ]),
            if (_expanded) ...[
              const SizedBox(height: 20),
              const Divider(height: 1),
              const SizedBox(height: 16),
              _DetailRow(icon: Icons.grid_on, label: 'Average Sharpness', value: avgSharpness),
              _DetailRow(icon: Icons.flare, label: 'Average Liveness (Texture)', value: avgLiveness * 100),
            ]
          ]),
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final double value;
  final bool isVerdict;
  const _DetailRow({required this.icon, required this.label, required this.value, this.isVerdict = false});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(children: [
        Icon(icon, size: 14, color: Colors.grey),
        const SizedBox(width: 8),
        Expanded(child: Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey))),
        if (isVerdict)
          Text(value > 50 ? 'REAL' : 'FAKE', style: TextStyle(color: value > 50 ? Colors.green : Colors.red, fontSize: 11, fontWeight: FontWeight.bold))
        else
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(color: const Color(0xFFFFF8E1), borderRadius: BorderRadius.circular(20)),
            child: Text('${value.toStringAsFixed(0)}%', style: const TextStyle(color: Color(0xFFFFC107), fontSize: 10, fontWeight: FontWeight.bold)),
          ),
      ]),
    );
  }
}

class _TransactionTable extends StatelessWidget {
  final CaptureResponse response;
  const _TransactionTable({required this.response});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0, color: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: Colors.grey.shade200)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          _TableRow(icon: Icons.tag, label: 'Transaction ID', value: response.transactionId),
          const Divider(height: 24),
          _TableRow(icon: Icons.fingerprint, label: 'Fingers Captured', value: response.results.length.toString()),
          const Divider(height: 24),
          _TableRow(icon: Icons.security, label: 'Liveness Check', value: response.results.every((r) => r.livenessPassed) ? 'Passed ✓' : 'Failed ❌', isStatus: true),
        ]),
      ),
    );
  }
}

class _TableRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final bool isStatus;
  const _TableRow({required this.icon, required this.label, required this.value, this.isStatus = false});

  @override
  Widget build(BuildContext context) {
     return Row(children: [
        Icon(icon, size: 16, color: Colors.grey),
        const SizedBox(width: 12),
        Text(label, style: const TextStyle(color: Colors.grey, fontSize: 12)),
        const Spacer(),
        Text(value, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: isStatus ? (value.contains('Passed') ? Colors.green : Colors.red) : Colors.black87)),
     ]);
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
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;

    // Outer Rounded Box
    canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(20)), paint);

    // If capturing 4 fingers, draw 4 vertical slots
    if (mode == CaptureMode.leftFour || mode == CaptureMode.rightFour) {
        final slotWidth = boxWidth / 4;
        final slotPaint = Paint()
          ..color = Colors.white.withOpacity(0.3)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.0;
        
        for (int i = 1; i < 4; i++) {
            final x = rect.left + (slotWidth * i);
            canvas.drawLine(Offset(x, rect.top + 20), Offset(x, rect.bottom - 20), slotPaint);
        }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
