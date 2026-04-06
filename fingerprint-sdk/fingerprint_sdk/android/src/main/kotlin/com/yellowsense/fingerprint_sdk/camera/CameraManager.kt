package com.yellowsense.fingerprint_sdk.camera

import android.annotation.SuppressLint
import android.content.Context
import android.util.Log
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/**
 * CameraX wrapper optimised for close-up fingerprint capture.
 *
 * - 1280×720 resolution (sufficient for 500 dpi equivalent at ~10 cm)
 * - STRATEGY_KEEP_ONLY_LATEST backpressure (drops stale frames)
 * - YUV_420_888 output for efficient OpenCV conversion
 * - Continuous auto-focus + auto-exposure
 * - Torch control for low-light environments
 */
class CameraManager(private val context: Context) {

    companion object {
        private const val TAG = "CameraManager"
    }

    private var cameraProvider: ProcessCameraProvider? = null
    private var camera: Camera? = null
    private var imageAnalysis: ImageAnalysis? = null
    private var preview: Preview? = null
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()

    /** Called on every new frame from the background executor thread. */
    var onFrame: ((ImageProxy) -> Unit)? = null

    @SuppressLint("UnsafeOptInUsageError")
    fun start(lifecycleOwner: LifecycleOwner, surfaceProvider: androidx.camera.core.Preview.SurfaceProvider? = null) {
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            try {
                cameraProvider = future.get()

                // 1. ANALYSIS (For Fingerprint Processing)
                imageAnalysis = ImageAnalysis.Builder()
                    .setTargetResolution(android.util.Size(1280, 720))
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
                    .build()
                    .also { analysis ->
                        analysis.setAnalyzer(executor) { frame ->
                            onFrame?.invoke(frame)
                        }
                    }

                // 2. PREVIEW (For Flutter UI)
                preview = if (surfaceProvider != null) {
                    Preview.Builder()
                        .setTargetResolution(android.util.Size(1280, 720))
                        .build()
                        .also { it.setSurfaceProvider(surfaceProvider) }
                } else null

                val selector = CameraSelector.DEFAULT_BACK_CAMERA

                cameraProvider?.unbindAll()
                
                val useCases = mutableListOf<UseCase>(imageAnalysis!!)
                preview?.let { useCases.add(it) }

                camera = cameraProvider?.bindToLifecycle(
                    lifecycleOwner, selector, *useCases.toTypedArray()
                )

                // Configure camera for macro/close-up fingerprint capture
                camera?.cameraControl?.let { control ->
                    // Set focus to near distance (0.0 = near, 1.0 = far)
                    control.setLinearZoom(0.0f)
                }

                Log.d(TAG, "Camera started successfully")
            } catch (e: Exception) {
                Log.e(TAG, "Camera start failed: ${e.message}", e)
            }
        }, ContextCompat.getMainExecutor(context))
    }

    /** Enable/disable torch for low-light capture assistance. */
    fun setTorch(enabled: Boolean) {
        camera?.cameraControl?.enableTorch(enabled)
    }

    fun stop() {
        try {
            cameraProvider?.unbindAll()
            camera = null
            Log.d(TAG, "Camera stopped safely")
        } catch (e: Exception) {
            Log.w(TAG, "Error during camera shutdown: ${e.message}")
        }
    }

    fun destroy() {
        stop()
        if (!executor.isShutdown) {
            executor.shutdownNow()
        }
    }
}
