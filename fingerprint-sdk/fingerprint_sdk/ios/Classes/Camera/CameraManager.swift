import AVFoundation
import UIKit

/// Manages AVCaptureSession lifecycle.
/// Delivers CMSampleBuffer frames to the processing layer.
final class CameraManager: NSObject {

    private var session: AVCaptureSession?
    private let queue = DispatchQueue(label: "com.yellowsense.camera", qos: .userInteractive)

    var onFrame: ((CMSampleBuffer) -> Void)?

    func start() throws {
        let session = AVCaptureSession()
        session.sessionPreset = .hd1280x720

        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input = try? AVCaptureDeviceInput(device: device) else {
            throw SDKError.deviceUnsupported("Camera unavailable")
        }

        // Auto-focus + auto-exposure for macro fingerprint capture
        try device.lockForConfiguration()
        if device.isFocusModeSupported(.continuousAutoFocus) {
            device.focusMode = .continuousAutoFocus
        }
        if device.isExposureModeSupported(.continuousAutoExposure) {
            device.exposureMode = .continuousAutoExposure
        }
        device.unlockForConfiguration()

        session.addInput(input)

        let output = AVCaptureVideoDataOutput()
        output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        output.alwaysDiscardsLateVideoFrames = true
        output.setSampleBufferDelegate(self, queue: queue)
        session.addOutput(output)

        self.session = session
        queue.async { session.startRunning() }
    }

    func stop() {
        session?.stopRunning()
        session = nil
    }
}

extension CameraManager: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput,
                       didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        onFrame?(sampleBuffer)
    }
}
