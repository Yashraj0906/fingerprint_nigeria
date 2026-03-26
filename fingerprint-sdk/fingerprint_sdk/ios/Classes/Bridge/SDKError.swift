import Foundation

enum SDKError: Error {
    case cameraPermissionDenied(String)
    case deviceUnsupported(String)
    case timeout(String)
    case lowQuality(String)
    case livenessFailed(String)
    case captureAborted(String)
    case unknown(String)

    var code: String {
        switch self {
        case .cameraPermissionDenied: return "CAMERA_PERMISSION_DENIED"
        case .deviceUnsupported: return "DEVICE_UNSUPPORTED"
        case .timeout: return "TIMEOUT"
        case .lowQuality: return "LOW_QUALITY"
        case .livenessFailed: return "LIVENESS_FAILED"
        case .captureAborted: return "CAPTURE_ABORTED"
        case .unknown: return "UNKNOWN"
        }
    }

    var message: String {
        switch self {
        case .cameraPermissionDenied(let m), .deviceUnsupported(let m),
             .timeout(let m), .lowQuality(let m), .livenessFailed(let m),
             .captureAborted(let m), .unknown(let m): return m
        }
    }
}
