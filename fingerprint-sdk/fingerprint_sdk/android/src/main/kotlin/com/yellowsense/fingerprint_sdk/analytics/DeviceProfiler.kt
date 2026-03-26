package com.yellowsense.fingerprint_sdk.analytics

import android.app.ActivityManager
import android.content.Context
import android.os.Build
import android.util.Log

/**
 * Profiles device capability at SDK init time and returns a performance tier.
 * Low-end devices get reduced resolution and simplified processing.
 */
object DeviceProfiler {

    enum class Tier { HIGH, MID, LOW }

    data class DeviceProfile(
        val tier: Tier,
        val targetResolutionWidth: Int,
        val targetResolutionHeight: Int,
        val framesPerFinger: Int,       // how many frames to accumulate before picking best
        val enableDFTLiveness: Boolean, // DFT is expensive; skip on LOW tier
        val enableSkeletonize: Boolean  // skeletonisation is expensive; skip on LOW tier
    )

    fun profile(context: Context): DeviceProfile {
        val ramMb   = totalRamMb(context)
        val cores   = Runtime.getRuntime().availableProcessors()
        val apiLevel = Build.VERSION.SDK_INT

        val tier = when {
            ramMb >= 3000 && cores >= 6 -> Tier.HIGH
            ramMb >= 1500 && cores >= 4 -> Tier.MID
            else                        -> Tier.LOW
        }

        Log.d("DeviceProfiler", "RAM=${ramMb}MB cores=$cores api=$apiLevel → tier=$tier")

        return when (tier) {
            Tier.HIGH -> DeviceProfile(
                tier                  = Tier.HIGH,
                targetResolutionWidth  = 1280,
                targetResolutionHeight = 720,
                framesPerFinger        = 5,
                enableDFTLiveness      = true,
                enableSkeletonize      = true
            )
            Tier.MID -> DeviceProfile(
                tier                  = Tier.MID,
                targetResolutionWidth  = 960,
                targetResolutionHeight = 540,
                framesPerFinger        = 3,
                enableDFTLiveness      = true,
                enableSkeletonize      = true
            )
            Tier.LOW -> DeviceProfile(
                tier                  = Tier.LOW,
                targetResolutionWidth  = 640,
                targetResolutionHeight = 480,
                framesPerFinger        = 3,
                enableDFTLiveness      = false,  // skip expensive DFT
                enableSkeletonize      = false   // use Canny ridges directly
            )
        }
    }

    private fun totalRamMb(context: Context): Long {
        val am   = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val info = ActivityManager.MemoryInfo()
        am.getMemoryInfo(info)
        return info.totalMem / (1024 * 1024)
    }
}
