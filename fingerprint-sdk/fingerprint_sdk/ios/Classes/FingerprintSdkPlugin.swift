import AVFoundation
import Flutter
import UIKit

public class FingerprintSdkPlugin: NSObject, FlutterPlugin {

    private var methodChannel: FlutterMethodChannel?
    private var eventChannel: FlutterEventChannel?
    private var feedbackSink: FlutterEventSink?
    private var captureEngine: CaptureEngine?
    private var debugMode = false

    static let methodChannelName = "com.yellowsense.fingerprint_sdk/method"
    static let eventChannelName  = "com.yellowsense.fingerprint_sdk/feedback"
    static let sdkVersion        = "2.0.0"

    public static func register(with registrar: FlutterPluginRegistrar) {
        let instance = FingerprintSdkPlugin()
        let mc = FlutterMethodChannel(name: methodChannelName, binaryMessenger: registrar.messenger())
        let ec = FlutterEventChannel(name: eventChannelName, binaryMessenger: registrar.messenger())
        registrar.addMethodCallDelegate(instance, channel: mc)
        ec.setStreamHandler(instance)
        instance.methodChannel = mc
        instance.eventChannel  = ec
    }

    public func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        switch call.method {
        case "initialize":   handleInitialize(call, result)
        case "startCapture": handleStartCapture(call, result)
        case "stopCapture":  handleStopCapture(result)
        case "dispose":      handleDispose(result)
        case "getVersion":   result(Self.sdkVersion)
        default:             result(FlutterMethodNotImplemented)
        }
    }

    // MARK: - Handlers

    private func handleInitialize(_ call: FlutterMethodCall, _ result: @escaping FlutterResult) {
        let args = call.arguments as? [String: Any]
        debugMode = args?["debugMode"] as? Bool ?? false

        AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
            DispatchQueue.main.async {
                guard let self else { return }
                guard granted else {
                    result(FlutterError(code: "CAMERA_PERMISSION_DENIED",
                                        message: "Camera permission denied by user", details: nil))
                    return
                }
                self.captureEngine = CaptureEngine(feedbackSink: self.feedbackSink,
                                                    debugMode: self.debugMode)
                result(nil)
            }
        }
    }

    private func handleStartCapture(_ call: FlutterMethodCall, _ result: @escaping FlutterResult) {
        guard let engine = captureEngine else {
            return result(FlutterError(code: "DEVICE_UNSUPPORTED",
                                        message: "SDK not initialised — call initialize() first", details: nil))
        }
        guard let params = call.arguments as? [String: Any] else {
            return result(FlutterError(code: "UNKNOWN", message: "Invalid arguments", details: nil))
        }

        engine.configure(params)
        do {
            try engine.start(
                onComplete: { response in DispatchQueue.main.async { result(response) } },
                onError: { code, msg in
                    DispatchQueue.main.async {
                        result(FlutterError(code: code, message: msg, details: nil))
                    }
                }
            )
        } catch let e as SDKError {
            result(FlutterError(code: e.code, message: e.message, details: nil))
        } catch {
            result(FlutterError(code: "CAMERA_INIT_FAILED", message: error.localizedDescription, details: nil))
        }
    }

    private func handleStopCapture(_ result: @escaping FlutterResult) {
        captureEngine?.stop()
        result(nil)
    }

    private func handleDispose(_ result: @escaping FlutterResult) {
        captureEngine?.stop()
        captureEngine = nil
        result(nil)
    }
}

// MARK: - FlutterStreamHandler

extension FingerprintSdkPlugin: FlutterStreamHandler {
    public func onListen(withArguments arguments: Any?,
                         eventSink events: @escaping FlutterEventSink) -> FlutterError? {
        feedbackSink = events
        captureEngine?.updateFeedbackSink(events)
        return nil
    }

    public func onCancel(withArguments arguments: Any?) -> FlutterError? {
        feedbackSink = nil
        captureEngine?.updateFeedbackSink(nil)
        return nil
    }
}
