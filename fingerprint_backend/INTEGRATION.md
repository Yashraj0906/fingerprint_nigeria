# Flutter Integration Guide
## Connecting the Biometric Capture App to the Python Backend

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  PHONE — Flutter Native SDK (your colleague's side)              │
│                                                                  │
│  Phase 1 (on-device, real-time):                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ MediaPipe Hand Detection → finger crops (4 fingers)      │   │
│  │ Liveness CNN → blocks fake fingers / screen replays      │   │
│  │ Quality check → blur, contrast, ridge clarity            │   │
│  │ Minutiae extraction → ISO 19794-2 template               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                 │  MethodChannel / EventChannel                  │
│                 ▼                                                │
│  Flutter Dart layer assembles results, calls backend             │
└─────────────────────────┬────────────────────────────────────────┘
                          │  HTTPS
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  PYTHON BACKEND (your side)                                      │
│                                                                  │
│  GET  /api/session         → generate transactionId             │
│  POST /api/capture/process → fallback processing (single finger) │
│  POST /api/capture/multi   → 4-finger slap capture              │
│  POST /api/enroll          → store templates in DB              │
│  POST /api/verify          → match against stored templates      │
│  POST /api/audit/log       → record security events             │
│  GET  /api/audit/logs      → retrieve logs                      │
└──────────────────────────────────────────────────────────────────┘
```

### Hybrid AI Strategy
| Layer | What runs there | Why |
|---|---|---|
| On-device (SDK) | Hand detection, liveness, quality, template | Speed, offline capability, <5s capture |
| Backend | Matching engine, storage, audit logging | Security, server-grade 1:N comparison |

The backend also runs the **full processing pipeline** independently (for testing and web UI). In production the Flutter SDK does processing on-device and only sends the final template.

---

## Step 1 — Add dependencies

In `pubspec.yaml`:

```yaml
dependencies:
  http: ^1.2.0
```

```bash
flutter pub get
```

---

## Step 2 — Fix the SDK channel name

In `biomatric_capture_flow.dart`, find the `BiometricSDKBridge` class.

**Change:**
```dart
static const _channel      = MethodChannel('com.yourapp/biometric_sdk');
static const _eventChannel = EventChannel('com.yourapp/biometric_sdk_events');
```

**To:**
```dart
static const _channel      = MethodChannel('com.yellowsense.fingerprint_sdk/method');
static const _eventChannel = EventChannel('com.yellowsense.fingerprint_sdk/feedback');
```

---

## Step 3 — Create the backend service file

Create `lib/services/backend_service.dart`:

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class BackendService {
  // Android emulator → 10.0.2.2
  // iOS simulator    → 127.0.0.1
  // Real device      → your PC's WiFi IP (run `ipconfig` to find it)
  static const String _baseUrl = 'http://10.0.2.2:8000';

  // ── Step A: Get a transaction ID before every capture session ─────────────
  static Future<String> getTransactionId() async {
    final response = await http.get(Uri.parse('$_baseUrl/api/session'));
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return data['transaction_id'] as String;
    }
    throw Exception('Session creation failed: ${response.body}');
  }

  // ── Step B: 4-finger slap capture (single image → 4 results) ─────────────
  // Preferred method. Send one frame with all 4 fingers visible.
  static Future<Map<String, dynamic>> processMultiCapture({
    required String transactionId,
    required String imageBase64,   // full frame, all 4 fingers in view
    required String hand,          // 'RIGHT' or 'LEFT'
  }) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/api/capture/multi'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'transaction_id': transactionId,
        'image_base64':   imageBase64,
        'hand':           hand,
      }),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Multi-capture failed: ${response.body}');
  }

  // ── Step B (alt): Single-finger capture ───────────────────────────────────
  // Use when capturing fingers one at a time.
  static Future<Map<String, dynamic>> processSingleCapture({
    required String transactionId,
    required List<Map<String, String>> fingers,
    // fingers = [{ 'finger_id': 'RIGHT_INDEX', 'image_base64': '...' }]
  }) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/api/capture/process'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'transaction_id': transactionId,
        'fingers':        fingers,
      }),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Capture processing failed: ${response.body}');
  }

  // ── Step C: Enroll a new user ─────────────────────────────────────────────
  static Future<Map<String, dynamic>> enrollUser({
    required String userId,
    required String transactionId,
    required List<Map<String, dynamic>> fingers,
    // fingers = [{ 'finger_id': 'RIGHT_INDEX', 'template': '...', 'quality_score': 87.0 }]
  }) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/api/enroll'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'user_id':        userId,
        'transaction_id': transactionId,
        'fingers':        fingers,
      }),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Enrollment failed: ${response.body}');
  }

  // ── Step C (alt): Verify a returning user ─────────────────────────────────
  static Future<Map<String, dynamic>> verifyUser({
    required String userId,
    required String transactionId,
    required List<Map<String, String>> fingers,
    // fingers = [{ 'finger_id': 'RIGHT_INDEX', 'image_base64': '...' }]
  }) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/api/verify'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'user_id':        userId,
        'transaction_id': transactionId,
        'fingers':        fingers,
      }),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Verification failed: ${response.body}');
  }

  // ── Audit logging (call after every SDK event) ────────────────────────────
  static Future<void> logEvent({
    required String transactionId,
    required String eventType,   // CAPTURE | ENROLL | VERIFY | LIVENESS_FAIL | ERROR
    required String status,      // success | failed
    String?  userId,
    String?  fingerId,
    String?  errorCode,
    double?  qualityScore,
    Map<String, dynamic>? deviceInfo,
  }) async {
    try {
      await http.post(
        Uri.parse('$_baseUrl/api/audit/log'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'transaction_id': transactionId,
          'event_type':     eventType,
          'status':         status,
          if (userId       != null) 'user_id':       userId,
          if (fingerId     != null) 'finger_id':     fingerId,
          if (errorCode    != null) 'error_code':    errorCode,
          if (qualityScore != null) 'quality_score': qualityScore,
          if (deviceInfo   != null) 'device_info':   deviceInfo,
        }),
      );
    } catch (_) {
      // Audit logging failures must never crash the app
    }
  }
}
```

---

## Step 4 — Update the CaptureResult model

In `biomatric_capture_flow.dart`, find the `CaptureResult` class.

**Add `template` and `guidanceMessage` fields:**
```dart
class CaptureResult {
  final FingerID fingerId;
  final bool     isValid;
  final int      qualityScore;
  final bool     livenessPassed;
  final String?  template;          // ← add: base64 ISO 19794-2 template
  final String?  guidanceMessage;   // ← add: "Hold still", "Improve lighting", etc.

  const CaptureResult({
    required this.fingerId,
    required this.isValid,
    required this.qualityScore,
    required this.livenessPassed,
    this.template,
    this.guidanceMessage,
  });
}
```

---

## Step 5 — Wire up the complete capture flow

In `biomatric_capture_flow.dart`, replace `_handleCaptureSuccess()`:

```dart
void _handleCaptureSuccess(Map<String, dynamic> event) async {
  // 1. Get a transaction ID
  final transactionId = await BackendService.getTransactionId();

  final rawResults = (event['results'] as List?)?.cast<Map<String, dynamic>>() ?? [];

  // 2. Determine hand side from captured fingers
  final hand = rawResults.isNotEmpty
      ? ((rawResults.first['fingerId'] as String).startsWith('RIGHT') ? 'RIGHT' : 'LEFT')
      : 'RIGHT';

  // 3. Get the full frame image from the SDK event
  final frameBase64 = event['frameBase64'] as String?;

  if (frameBase64 != null) {
    try {
      // 4. Send to 4-finger multi-capture endpoint
      final backendResult = await BackendService.processMultiCapture(
        transactionId: transactionId,
        imageBase64:   frameBase64,
        hand:          hand,
      );

      // 5. Log audit event
      await BackendService.logEvent(
        transactionId: transactionId,
        eventType:     'CAPTURE',
        status:        backendResult['overall_status'] == 'success' ? 'success' : 'failed',
      );

      // 6. Parse results — show guidance message if any finger failed
      final backendFingers =
          (backendResult['results'] as List?)?.cast<Map<String, dynamic>>() ?? [];

      final guidance = backendResult['guidance'] as String?;
      if (guidance != null) {
        // Show guidance to user (e.g. "Raise: Ring, Little")
        _showGuidanceBanner(guidance);
      }

      final parsed = backendFingers.map((r) {
        final fingerId = widget.fingers.firstWhere(
          (f) => f.name.toUpperCase() == (r['finger_id'] as String? ?? ''),
          orElse: () => widget.fingers.first,
        );
        return CaptureResult(
          fingerId:        fingerId,
          isValid:         r['status'] == 'success',
          qualityScore:    (r['quality_score'] as num?)?.toInt() ?? 0,
          livenessPassed:  r['liveness_passed'] as bool? ?? false,
          template:        r['template'] as String?,
          guidanceMessage: r['guidance_message'] as String?,
        );
      }).toList();

      _capturedResults.addAll(parsed);

    } catch (e) {
      // Backend unreachable — use on-device SDK results as fallback
      await BackendService.logEvent(
        transactionId: transactionId,
        eventType:     'ERROR',
        status:        'failed',
        errorCode:     'BACKEND_UNREACHABLE',
      );
      _capturedResults.addAll(_parseLocalResults(rawResults));
    }
  } else {
    _capturedResults.addAll(_parseLocalResults(rawResults));
  }

  Future.delayed(const Duration(milliseconds: 800), () {
    if (!mounted) return;
    _navigateNext();
  });
}

List<CaptureResult> _parseLocalResults(List<Map<String, dynamic>> results) {
  return results.map((r) {
    final fingerId = widget.fingers.firstWhere(
      (f) => f.name.toUpperCase() == (r['fingerId'] as String? ?? ''),
      orElse: () => widget.fingers.first,
    );
    return CaptureResult(
      fingerId:       fingerId,
      isValid:        r['status'] == 'success',
      qualityScore:   (r['qualityScore'] as num?)?.toInt() ?? 0,
      livenessPassed: r['livenessPassed'] as bool? ?? false,
    );
  }).toList();
}
```

---

## Step 6 — Wire up the Submit button

In `ReviewCaptureScreen`, replace `_submit()`:

```dart
void _submit() async {
  const String userId     = 'user_123'; // TODO: pass real user ID from auth
  final String transactionId = await BackendService.getTransactionId();

  final fingersWithTemplates = widget.results
      .where((r) => r.template != null)
      .map((r) => {
            'finger_id':    r.fingerId.name.toUpperCase(),
            'template':     r.template!,
            'quality_score': r.qualityScore.toDouble(),
          })
      .toList();

  if (fingersWithTemplates.isEmpty) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('No valid fingerprint templates to submit.')),
    );
    return;
  }

  showDialog(
    context: context,
    barrierDismissible: false,
    builder: (_) => const Center(child: CircularProgressIndicator()),
  );

  try {
    final result = await BackendService.enrollUser(
      userId:        userId,
      transactionId: transactionId,
      fingers:       fingersWithTemplates,
    );

    await BackendService.logEvent(
      transactionId: transactionId,
      eventType:     'ENROLL',
      status:        'success',
      userId:        userId,
    );

    Navigator.of(context).pop();
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Enrolled!'),
        content: Text(
          'Fingers enrolled: ${(result['fingers_enrolled'] as List).join(', ')}\n'
          'Enrollment ID: ${result['enrollment_id']}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context)..pop()..pop()..pop(),
            child: const Text('Done'),
          ),
        ],
      ),
    );
  } catch (e) {
    await BackendService.logEvent(
      transactionId: transactionId,
      eventType:     'ENROLL',
      status:        'failed',
      errorCode:     'SUBMIT_ERROR',
      userId:        userId,
    );
    Navigator.of(context).pop();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Submission failed: $e')),
    );
  }
}
```

---

## Step 7 — Android permissions

In `android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.CAMERA"/>

<application
    android:usesCleartextTraffic="true"
    ... >
```

> Remove `usesCleartextTraffic` in production and use HTTPS.

---

## API Reference

### GET `/api/session`
Call this before every capture session to get a `transactionId`.

**Response:**
```json
{
  "transaction_id": "833d164c-7301-452d-9eb1-ee9ea9a96886",
  "issued_at": "2026-03-26T07:55:24+00:00",
  "expires_in": 300
}
```

---

### POST `/api/capture/multi`
**Preferred.** Send one camera frame with all 4 fingers visible. Backend uses MediaPipe to detect which fingers are extended, crops each individually, and processes them.

**Request:**
```json
{
  "transaction_id": "833d164c...",
  "image_base64": "<base64 JPEG of full hand frame>",
  "hand": "RIGHT"
}
```

**Response:**
```json
{
  "transaction_id": "833d164c...",
  "overall_status": "partial",
  "hand": "RIGHT",
  "guidance": "Raise: Ring, Little",
  "results": [
    {
      "finger_id": "RIGHT_INDEX",
      "status": "success",
      "quality_score": 83.4,
      "blur_score": 91.2,
      "contrast_score": 78.5,
      "ridge_score": 80.1,
      "coverage_score": 84.0,
      "liveness_passed": true,
      "liveness_confidence": 0.88,
      "template": "<base64 ISO 19794-2>",
      "error_code": null,
      "error_message": null,
      "guidance_message": null
    },
    {
      "finger_id": "RIGHT_RING",
      "status": "failed",
      "quality_score": 0.0,
      "liveness_passed": false,
      "template": null,
      "error_code": "FINGER_NOT_DETECTED",
      "error_message": "Finger not visible — spread hand wider",
      "guidance_message": "Show all 4 fingers clearly"
    }
  ]
}
```

**Error codes in results:**
| Code | Meaning | User action |
|---|---|---|
| `NO_HAND_DETECTED` | No hand in frame | Place hand in camera view |
| `FINGER_NOT_DETECTED` | Finger not extended | Raise that finger |
| `QUALITY_LOW` | Blur/contrast below threshold | Improve lighting, hold still |
| `LIVENESS_FAILED` | Screen replay or glare detected | Use real finger |
| `LOW_RIDGE_DETAIL` | Template extraction failed | Flatten finger slightly |
| `DECODE_ERROR` | Bad image data | Check base64 encoding |

---

### POST `/api/capture/process`
Single-finger capture (fallback / one at a time).

**Request:**
```json
{
  "transaction_id": "833d164c...",
  "fingers": [
    { "finger_id": "RIGHT_INDEX", "image_base64": "<base64 JPEG>" }
  ]
}
```

**Response:** Same `FingerResult` structure as above, wrapped in `results` array.

---

### POST `/api/enroll`
Store fingerprint templates for a new user.

**Request:**
```json
{
  "user_id": "user_123",
  "transaction_id": "833d164c...",
  "fingers": [
    { "finger_id": "RIGHT_INDEX",  "template": "<base64>", "quality_score": 83.4 },
    { "finger_id": "RIGHT_MIDDLE", "template": "<base64>", "quality_score": 79.1 }
  ]
}
```

**Response:**
```json
{
  "enrollment_id": "uuid-...",
  "user_id": "user_123",
  "status": "enrolled",
  "fingers_enrolled": ["RIGHT_INDEX", "RIGHT_MIDDLE"]
}
```

---

### POST `/api/verify`
Match a live finger against the stored enrollment.

**Request:**
```json
{
  "user_id": "user_123",
  "transaction_id": "833d164c...",
  "fingers": [
    { "finger_id": "RIGHT_INDEX", "image_base64": "<base64 JPEG>" }
  ]
}
```

**Response:**
```json
{
  "transaction_id": "833d164c...",
  "user_id": "user_123",
  "match": true,
  "confidence": 0.824,
  "message": "Identity verified"
}
```

---

### POST `/api/audit/log`
Record a security or operational event. Call after every SDK event.

**Request:**
```json
{
  "transaction_id": "833d164c...",
  "event_type": "LIVENESS_FAIL",
  "status": "failed",
  "user_id": "user_123",
  "finger_id": "RIGHT_INDEX",
  "error_code": "LIVENESS_FAILED",
  "quality_score": 62.1,
  "device_info": {
    "sdk_version": "1.0.0",
    "os": "Android 14",
    "model": "Pixel 7"
  }
}
```

**Event types:** `CAPTURE` | `ENROLL` | `VERIFY` | `LIVENESS_FAIL` | `ERROR`

**Response:**
```json
{
  "log_id": "uuid-...",
  "recorded_at": "2026-03-26T08:00:00+00:00"
}
```

---

### GET `/api/audit/logs`
Retrieve logs for monitoring. Optional query params: `transaction_id`, `event_type`, `limit`.

```
GET /api/audit/logs?event_type=LIVENESS_FAIL&limit=20
```

---

## Finger IDs

```
RIGHT_THUMB   RIGHT_INDEX   RIGHT_MIDDLE   RIGHT_RING   RIGHT_LITTLE
LEFT_THUMB    LEFT_INDEX    LEFT_MIDDLE    LEFT_RING    LEFT_LITTLE
```

The 4-finger slap capture uses: `INDEX`, `MIDDLE`, `RING`, `LITTLE` of the chosen hand.

---

## Environment URLs

| Environment | Base URL |
|---|---|
| Android Emulator | `http://10.0.2.2:8000` |
| iOS Simulator | `http://127.0.0.1:8000` |
| Real device (WiFi) | `http://<PC-WiFi-IP>:8000` |
| Production | `https://your-domain.com` |

Find your PC WiFi IP on Windows: run `ipconfig`, look for **IPv4 Address** under your WiFi adapter.

---

## Running the backend

```bash
cd fingerprint_backend
pip install -r requirements.txt

# For local testing (emulator only):
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# For real device on same WiFi:
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Live test UI: `http://127.0.0.1:8000/ui`
- Interactive API docs: `http://127.0.0.1:8000/docs`
