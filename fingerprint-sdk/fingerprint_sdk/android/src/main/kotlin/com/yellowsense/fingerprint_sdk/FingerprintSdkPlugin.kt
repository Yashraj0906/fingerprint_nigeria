package com.yellowsense.fingerprint_sdk

import android.content.Context
import android.util.Log
import androidx.lifecycle.LifecycleOwner
import com.yellowsense.fingerprint_sdk.analytics.DeviceProfiler
import com.yellowsense.fingerprint_sdk.bridge.CaptureEngine
import com.yellowsense.fingerprint_sdk.camera.CameraManager
import io.flutter.embedding.engine.plugins.FlutterPlugin
import io.flutter.embedding.engine.plugins.activity.ActivityAware
import io.flutter.embedding.engine.plugins.activity.ActivityPluginBinding
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.MethodChannel.MethodCallHandler
import io.flutter.plugin.common.MethodChannel.Result
import org.opencv.android.OpenCVLoader

import io.flutter.view.TextureRegistry
import androidx.camera.core.Preview.SurfaceProvider
import androidx.core.content.ContextCompat

class FingerprintSdkPlugin : FlutterPlugin, MethodCallHandler, ActivityAware {

    private lateinit var methodChannel: MethodChannel
    private lateinit var eventChannel: EventChannel
    private var feedbackSink: EventChannel.EventSink? = null

    private var context: Context? = null
    private var lifecycleOwner: LifecycleOwner? = null
    private var cameraManager: CameraManager? = null
    private var captureEngine: CaptureEngine? = null
    private var debugMode = false

    private var textureRegistry: TextureRegistry? = null
    private var textureEntry: TextureRegistry.SurfaceTextureEntry? = null

    companion object {
        const val METHOD_CHANNEL = "com.yellowsense.fingerprint_sdk/method"
        const val EVENT_CHANNEL  = "com.yellowsense.fingerprint_sdk/feedback"
        const val SDK_VERSION    = "3.0.0"
        const val TAG            = "FingerprintSDK"
    }

    override fun onAttachedToEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        context = binding.applicationContext
        textureRegistry = binding.textureRegistry
        methodChannel = MethodChannel(binding.binaryMessenger, METHOD_CHANNEL)
        methodChannel.setMethodCallHandler(this)
        eventChannel = EventChannel(binding.binaryMessenger, EVENT_CHANNEL)
        eventChannel.setStreamHandler(object : EventChannel.StreamHandler {
            override fun onListen(args: Any?, sink: EventChannel.EventSink?) {
                feedbackSink = sink
                captureEngine?.updateFeedbackSink(sink)
            }
            override fun onCancel(args: Any?) { feedbackSink = null }
        })
    }

    override fun onDetachedFromEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        methodChannel.setMethodCallHandler(null)
        context = null
        textureRegistry = null
    }

    override fun onAttachedToActivity(binding: ActivityPluginBinding) {
        lifecycleOwner = binding.activity as? LifecycleOwner
    }
    override fun onDetachedFromActivity() { lifecycleOwner = null }
    override fun onReattachedToActivityForConfigChanges(b: ActivityPluginBinding) = onAttachedToActivity(b)
    override fun onDetachedFromActivityForConfigChanges() = onDetachedFromActivity()

    override fun onMethodCall(call: MethodCall, result: Result) {
        when (call.method) {
            "initialize"    -> handleInitialize(call, result)
            "startCapture"  -> handleStartCapture(call, result)
            "stopCapture"   -> handleStopCapture(result)
            "dispose"       -> handleDispose(result)
            "getVersion"    -> result.success(SDK_VERSION)
            "getMetrics"    -> handleGetMetrics(result)
            else            -> result.notImplemented()
        }
    }

    private fun handleInitialize(call: MethodCall, result: Result) {
        try {
            val ctx = context ?: return result.error("DEVICE_UNSUPPORTED", "No application context", null)
            val lo  = lifecycleOwner ?: return result.error("DEVICE_UNSUPPORTED", "Activity not attached", null)

            val args = call.arguments as? Map<*, *>
            debugMode = args?.get("debugMode") as? Boolean ?: false

            @Suppress("DEPRECATION")
            if (!OpenCVLoader.initDebug()) {
                Log.e(TAG, "OpenCV init failed — ensure opencv-android-4.8.x.aar is in android/libs/")
                return result.error("DEVICE_UNSUPPORTED", "OpenCV init failed", null)
            }
            
            cameraManager = CameraManager(ctx)
            captureEngine = CaptureEngine(
                cameraManager  = cameraManager!!,
                feedbackSink   = feedbackSink,
                lifecycleOwner = lo,
                debugMode      = debugMode,
                deviceProfile  = DeviceProfiler.profile(ctx)
            )

            // Create texture for preview
            textureEntry = textureRegistry?.createSurfaceTexture()
            val textureId = textureEntry?.id() ?: -1L
            
            result.success(textureId)
        } catch (e: Throwable) {
            Log.e(TAG, "Initialize FATAL: ${e.javaClass.simpleName}: ${e.message}", e)
            result.error("INIT_FAILED", "SDK init failed: ${e.message}", null)
        }
    }

    private fun handleStartCapture(call: MethodCall, result: Result) {
        val engine = captureEngine ?: return result.error("DEVICE_UNSUPPORTED", "SDK not initialised", null)
        val params = call.arguments as? Map<*, *> ?: return result.error("UNKNOWN", "Invalid arguments", null)

        val surfaceProvider = textureEntry?.let { entry ->
            SurfaceProvider { request ->
                val surfaceTexture = entry.surfaceTexture()
                surfaceTexture.setDefaultBufferSize(request.resolution.width, request.resolution.height)
                val surface = android.view.Surface(surfaceTexture)
                request.provideSurface(surface, ContextCompat.getMainExecutor(context!!)) {
                    surface.release()
                }
            }
        }

        engine.configure(params)
        engine.start(
            surfaceProvider = surfaceProvider,
            onComplete = { response -> result.success(response) },
            onError    = { code, msg ->
                if (debugMode) Log.e(TAG, "Capture error [$code]: $msg")
                result.error(code, msg, null)
            }
        )
    }

    private fun handleStopCapture(result: Result) {
        captureEngine?.stop()
        result.success(null)
    }

    private fun handleDispose(result: Result) {
        captureEngine?.stop()
        cameraManager?.stop()
        textureEntry?.release()
        textureEntry = null
        captureEngine = null
        cameraManager = null
        result.success(null)
    }

    private fun handleGetMetrics(result: Result) {
        val metrics = captureEngine?.validationManager?.toResponseMap() ?: emptyMap<String, Any>()
        result.success(metrics)
    }
}
