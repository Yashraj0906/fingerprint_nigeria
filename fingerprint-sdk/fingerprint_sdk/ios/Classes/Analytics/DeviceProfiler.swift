import Foundation
import os.log

/// Profiles device capability and returns an adaptive performance tier.
enum DeviceProfiler {

    enum Tier { case high, mid, low }

    struct DeviceProfile {
        let tier: Tier
        let targetWidth: Int
        let targetHeight: Int
        let framesPerFinger: Int
        let enableDFTLiveness: Bool
        let enableSkeletonize: Bool
    }

    static func profile() -> DeviceProfile {
        let ramGb   = Double(ProcessInfo.processInfo.physicalMemory) / 1_073_741_824.0
        let cores   = ProcessInfo.processInfo.processorCount
        let iosVer  = ProcessInfo.processInfo.operatingSystemVersion.majorVersion

        let tier: Tier
        if ramGb >= 3.0 && cores >= 6 { tier = .high }
        else if ramGb >= 1.5 && cores >= 4 { tier = .mid }
        else { tier = .low }

        os_log("DeviceProfiler: RAM=%.1fGB cores=%d iOS=%d → tier=%{public}s",
               log: OSLog(subsystem: "com.yellowsense.fingerprint_sdk", category: "Device"),
               type: .debug, ramGb, cores, iosVer, "\(tier)")

        switch tier {
        case .high:
            return DeviceProfile(tier: .high, targetWidth: 1280, targetHeight: 720,
                                 framesPerFinger: 5, enableDFTLiveness: true, enableSkeletonize: true)
        case .mid:
            return DeviceProfile(tier: .mid, targetWidth: 960, targetHeight: 540,
                                 framesPerFinger: 3, enableDFTLiveness: true, enableSkeletonize: true)
        case .low:
            return DeviceProfile(tier: .low, targetWidth: 640, targetHeight: 480,
                                 framesPerFinger: 3, enableDFTLiveness: false, enableSkeletonize: false)
        }
    }
}
