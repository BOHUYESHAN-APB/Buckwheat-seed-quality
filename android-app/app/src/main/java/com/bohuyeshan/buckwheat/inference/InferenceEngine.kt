package com.bohuyeshan.buckwheat.inference

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ai.onnxruntime.TensorInfo
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.RectF
import android.os.Build
import android.util.Log
import androidx.camera.core.ImageProxy
import com.bohuyeshan.buckwheat.model.BoundingBox
import com.bohuyeshan.buckwheat.model.Detection
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.FloatBuffer
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.util.Arrays
import java.util.HashMap
import java.util.Locale
import com.bohuyeshan.buckwheat.util.Logger

class InferenceEngine(private val context: Context) {

    private enum class ExecutionProviderPreference {
        AUTO,
        CPU_ONLY,
        NNAPI,
        QNN,
        VULKAN,
        XNNPACK;

        companion object {
            fun fromStored(value: String?): ExecutionProviderPreference {
                return when (value?.uppercase(Locale.US)) {
                    "CPU", "CPU_ONLY" -> CPU_ONLY
                    "NNAPI" -> NNAPI
                    "QNN" -> QNN
                    "VULKAN" -> VULKAN
                    "XNNPACK" -> XNNPACK
                    else -> AUTO
                }
            }

            fun toStored(pref: ExecutionProviderPreference): String = when (pref) {
                AUTO -> "AUTO"
                CPU_ONLY -> "CPU"
                NNAPI -> "NNAPI"
                QNN -> "QNN"
                VULKAN -> "VULKAN"
                XNNPACK -> "XNNPACK"
            }
        }
    }

    private enum class SocFamily {
        QUALCOMM,
        MEDIATEK,
        HISILICON,
        SAMSUNG,
        GOOGLE,
        UNKNOWN
    }

    private sealed class ProviderRequest(val label: String) {
        object Cpu : ProviderRequest("CPU")
        data class Nnapi(
            val disableCpuFallback: Boolean,
            val enableFp16: Boolean,
            val executionMode: String?,
            val cacheKey: String
        ) : ProviderRequest("NNAPI")

        data class Qnn(
            val backendPath: String?,
            val enableCaching: Boolean,
            val cacheKey: String
        ) : ProviderRequest("QNN")

        data class Vulkan(val deviceId: Int) : ProviderRequest("VULKAN")
        data class Xnnpack(val threads: Int) : ProviderRequest("XNNPACK")
    }

    // Expose whether the model/session was successfully created
    @Volatile
    var modelLoaded: Boolean = false

    private var environment: OrtEnvironment? = null
    private var session: OrtSession? = null
    private var labels: List<String> = emptyList()
    private var inputName: String? = null

    private val sessionMutex = Mutex()

    @Volatile
    private var shuttingDown: Boolean = false

    private var prefExecutionProvider: ExecutionProviderPreference = ExecutionProviderPreference.AUTO

    private val nnapiCacheDir: File = File(context.codeCacheDir, "nnapi_cache")
    private val qnnCacheDir: File = File(context.codeCacheDir, "qnn_cache")

    data class ProviderReport(
        val preferenceRaw: String,
        val preferenceLabel: String,
        val deviceLabel: String,
        val plannedProviders: List<String>,
        val enabledProviders: List<String>
    ) {
        fun enabledSummary(): String = if (enabledProviders.isEmpty()) {
            "CPU"
        } else {
            enabledProviders.joinToString(separator = " → ")
        }
    }

    @Volatile
    private var lastProviderReport: ProviderReport = ProviderReport(
        preferenceRaw = "AUTO",
        preferenceLabel = "Auto",
        deviceLabel = "Generic",
        plannedProviders = emptyList(),
        enabledProviders = emptyList()
    )

    @Volatile
    private var lastDetectedSoc: SocFamily = SocFamily.UNKNOWN

    private fun ExecutionProviderPreference.displayLabel(): String = when (this) {
        ExecutionProviderPreference.AUTO -> "Auto"
        ExecutionProviderPreference.CPU_ONLY -> "CPU"
        ExecutionProviderPreference.NNAPI -> "NNAPI"
        ExecutionProviderPreference.QNN -> "Qualcomm QNN"
        ExecutionProviderPreference.VULKAN -> "Vulkan"
        ExecutionProviderPreference.XNNPACK -> "XNNPACK"
    }

    private fun SocFamily.displayLabel(): String = when (this) {
        SocFamily.QUALCOMM -> "Qualcomm / Snapdragon"
        SocFamily.MEDIATEK -> "MediaTek Dimensity"
        SocFamily.HISILICON -> "HiSilicon / Kirin"
        SocFamily.SAMSUNG -> "Samsung Exynos"
        SocFamily.GOOGLE -> "Google Tensor"
        SocFamily.UNKNOWN -> "Generic"
    }

    private fun resetSessionLocked(closeEnvironment: Boolean = true) {
        try {
            session?.close()
        } catch (_: Exception) {
        } finally {
            session = null
        }
        if (closeEnvironment) {
            try {
                environment?.close()
            } catch (_: Exception) {
            } finally {
                environment = null
            }
        }
        inputName = null
        modelLoaded = false
        labels = emptyList()
    }

    private suspend fun createSessionLocked(): Result<Unit> {
        return try {
            val modelFile = exportModelToCache()
            val env = OrtEnvironment.getEnvironment()
            val options = OrtSession.SessionOptions().apply {
                setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
                setIntraOpNumThreads(Runtime.getRuntime().availableProcessors().coerceAtMost(4))
            }
            val enabledProviders = configureExecutionProviders(options)
            val ortSession = env.createSession(modelFile.absolutePath, options)
            environment = env
            session = ortSession
            inputName = ortSession.inputNames.firstOrNull()

            try {
                val sb = StringBuilder()
                sb.append("Session inputs:\n")
                for (name in ortSession.inputNames) {
                    val info = ortSession.inputInfo[name]?.info
                    sb.append("name=${name} info=${info}\n")
                }
                Logger.i(TAG, sb.toString())
            } catch (_: Exception) {}

            val tensorInfo = inputName?.let { name ->
                (ortSession.inputInfo[name]?.info as? TensorInfo)
            }
            configureInputShape(tensorInfo)
            labels = loadLabels()
            if (labels.isNotEmpty()) {
                Logger.i(TAG, "Loaded labels: ${labels.joinToString()}")
            } else {
                Logger.i(TAG, "Loaded 0 labels (using fallback)")
            }
            if (enabledProviders.isNotEmpty()) {
                Logger.i(TAG, "Enabled execution providers: ${enabledProviders.joinToString()}")
            } else {
                Logger.i(TAG, "Using default CPU execution provider")
            }
            loadPrefs()
            shuttingDown = false
            modelLoaded = true
            Result.success(Unit)
        } catch (ex: IOException) {
            Logger.e(TAG, "Failed to load model file", ex)
            Result.failure(ex)
        } catch (ex: Exception) {
            Logger.e(TAG, "Failed to create ONNX session", ex)
            Result.failure(ex)
        }
    }

    private fun configureExecutionProviders(options: OrtSession.SessionOptions): List<String> {
        val enabled = mutableListOf<String>()
        val plan = buildProviderPlan()
        val planLabels = plan.map { it.label }
        try {
            Logger.i(TAG, "Execution provider preference=${prefExecutionProvider} plan=${planLabels.joinToString()}")
        } catch (_: Exception) {
        }
        for (request in plan) {
            val success = when (request) {
                ProviderRequest.Cpu -> true
                is ProviderRequest.Nnapi -> tryEnableNnapi(options, request)
                is ProviderRequest.Qnn -> tryEnableQnn(options, request)
                is ProviderRequest.Vulkan -> tryEnableVulkan(options, request)
                is ProviderRequest.Xnnpack -> tryEnableXnnpack(options, request)
            }
            if (success) {
                enabled += request.label
            }
        }
        lastProviderReport = ProviderReport(
            preferenceRaw = ExecutionProviderPreference.toStored(prefExecutionProvider),
            preferenceLabel = prefExecutionProvider.displayLabel(),
            deviceLabel = lastDetectedSoc.displayLabel(),
            plannedProviders = planLabels,
            enabledProviders = enabled.toList()
        )
        return enabled
    }

    private fun buildProviderPlan(): List<ProviderRequest> {
        val deviceFamily = detectSocFamily().also { lastDetectedSoc = it }
        return when (prefExecutionProvider) {
            ExecutionProviderPreference.CPU_ONLY -> listOf(ProviderRequest.Cpu)
            ExecutionProviderPreference.NNAPI -> listOf(
                ProviderRequest.Nnapi(disableCpuFallback = true, enableFp16 = true, executionMode = "burst", cacheKey = "forced_nnapi")
            )
            ExecutionProviderPreference.QNN -> listOf(
                ProviderRequest.Qnn(detectQnnBackendPath(), enableCaching = true, cacheKey = "forced_qnn"),
                ProviderRequest.Nnapi(disableCpuFallback = true, enableFp16 = true, executionMode = "burst", cacheKey = "forced_nnapi_fallback")
            )
            ExecutionProviderPreference.VULKAN -> listOf(
                ProviderRequest.Vulkan(deviceId = 0),
                ProviderRequest.Xnnpack(availableCpuThreads())
            )
            ExecutionProviderPreference.XNNPACK -> listOf(
                ProviderRequest.Xnnpack(availableCpuThreads())
            )
            ExecutionProviderPreference.AUTO -> when (deviceFamily) {
                SocFamily.QUALCOMM -> listOf(
                    ProviderRequest.Qnn(detectQnnBackendPath(), enableCaching = true, cacheKey = "snapdragon_qnn"),
                    ProviderRequest.Nnapi(disableCpuFallback = true, enableFp16 = true, executionMode = "burst", cacheKey = "snapdragon_nnapi"),
                    ProviderRequest.Xnnpack(availableCpuThreads())
                )
                SocFamily.MEDIATEK -> listOf(
                    ProviderRequest.Nnapi(disableCpuFallback = true, enableFp16 = true, executionMode = "async", cacheKey = "mediatek_nnapi"),
                    ProviderRequest.Vulkan(deviceId = 0),
                    ProviderRequest.Xnnpack(availableCpuThreads())
                )
                SocFamily.HISILICON, SocFamily.SAMSUNG -> listOf(
                    ProviderRequest.Nnapi(disableCpuFallback = false, enableFp16 = true, executionMode = "burst", cacheKey = "generic_nnapi"),
                    ProviderRequest.Vulkan(deviceId = 0),
                    ProviderRequest.Xnnpack(availableCpuThreads())
                )
                SocFamily.GOOGLE -> listOf(
                    ProviderRequest.Nnapi(disableCpuFallback = false, enableFp16 = true, executionMode = "burst", cacheKey = "tensor_nnapi"),
                    ProviderRequest.Vulkan(deviceId = 0),
                    ProviderRequest.Xnnpack(availableCpuThreads())
                )
                SocFamily.UNKNOWN -> listOf(
                    ProviderRequest.Nnapi(disableCpuFallback = false, enableFp16 = true, executionMode = null, cacheKey = "auto_nnapi"),
                    ProviderRequest.Vulkan(deviceId = 0),
                    ProviderRequest.Xnnpack(availableCpuThreads())
                )
            }
        }.filterNot { it is ProviderRequest.Nnapi && !supportsNnapi() }
    }

    private fun detectSocFamily(): SocFamily {
        val identifiers = mutableListOf(
            Build.MANUFACTURER.orEmpty(),
            Build.BRAND.orEmpty(),
            Build.HARDWARE.orEmpty(),
            Build.BOARD.orEmpty(),
            Build.MODEL.orEmpty()
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            identifiers += Build.SOC_MANUFACTURER.orEmpty()
            identifiers += Build.SOC_MODEL.orEmpty()
        }
        val lowered = identifiers.filter { it.isNotBlank() }.map { it.lowercase(Locale.US) }

        fun containsAny(predicate: (String) -> Boolean): Boolean = lowered.any(predicate)

        return when {
            containsAny { it.contains("qcom") || it.contains("qualcomm") || it.contains("snapdragon") || it.contains("sm-" ) } -> SocFamily.QUALCOMM
            containsAny { it.contains("mediatek") || it.contains("dimensity") || it.startsWith("mt") } -> SocFamily.MEDIATEK
            containsAny { it.contains("hisilicon") || it.contains("kirin") } -> SocFamily.HISILICON
            containsAny { it.contains("exynos") || it.contains("slsi") } -> SocFamily.SAMSUNG
            containsAny { it.contains("google") || it.contains("tensor") } -> SocFamily.GOOGLE
            else -> SocFamily.UNKNOWN
        }
    }

    private fun supportsNnapi(): Boolean = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P

    private fun tryEnableNnapi(options: OrtSession.SessionOptions, request: ProviderRequest.Nnapi): Boolean {
        if (!supportsNnapi()) {
            Logger.w(TAG, "NNAPI not available below Android 9 (API 28)")
            return false
        }
        return try {
            val dir = ensureDirectory(nnapiCacheDir)
            addSessionConfigEntrySafely(options, "session.nnapi.cache_dir", dir.absolutePath)
            addSessionConfigEntrySafely(options, "session.nnapi.cache_key", request.cacheKey)
            addSessionConfigEntrySafely(options, "session.nnapi.disable_cpu", if (request.disableCpuFallback) "1" else "0")
            addSessionConfigEntrySafely(options, "session.nnapi.enable_fp16", if (request.enableFp16) "1" else "0")
            request.executionMode?.let { mode ->
                addSessionConfigEntrySafely(options, "session.nnapi.execution_mode", mode)
            }
            options.addNnapi()
            true
        } catch (ex: Exception) {
            Logger.w(TAG, "NNAPI execution provider unavailable, continuing with fallback", ex)
            false
        }
    }

    private fun tryEnableQnn(options: OrtSession.SessionOptions, request: ProviderRequest.Qnn): Boolean {
        val backendPath = request.backendPath
        if (backendPath == null) {
            Logger.w(TAG, "QNN backend libraries not detected on this device; skipping QNN provider")
            return false
        }
        return try {
            val method = options.javaClass.getMethod("addExecutionProvider", String::class.java, java.util.Map::class.java)
            val config = HashMap<String, String>().apply {
                put("backend_path", backendPath)
                if (request.enableCaching) {
                    val cacheDir = ensureDirectory(qnnCacheDir)
                    put("context_cache_enable", "1")
                    put("context_cache_path", File(cacheDir, request.cacheKey).absolutePath)
                }
            }
            method.invoke(options, "QNN", config)
            true
        } catch (nsme: NoSuchMethodException) {
            Logger.w(TAG, "ONNX Runtime build does not expose QNN execution provider APIs", nsme)
            false
        } catch (ex: Exception) {
            Logger.w(TAG, "Failed to enable QNN provider; will fall back", ex)
            false
        }
    }

    private fun tryEnableVulkan(options: OrtSession.SessionOptions, request: ProviderRequest.Vulkan): Boolean {
        return try {
            val method = options.javaClass.getMethod("addExecutionProvider", String::class.java, java.util.Map::class.java)
            val config = HashMap<String, String>().apply {
                put("device_id", request.deviceId.toString())
            }
            method.invoke(options, "VULKAN", config)
            true
        } catch (nsme: NoSuchMethodException) {
            Logger.w(TAG, "Vulkan execution provider not bundled; skipping")
            false
        } catch (ex: Exception) {
            Logger.w(TAG, "Failed to enable Vulkan provider; continuing with fallback", ex)
            false
        }
    }

    private fun tryEnableXnnpack(options: OrtSession.SessionOptions, request: ProviderRequest.Xnnpack): Boolean {
        return try {
            val method = options.javaClass.getMethod("addXnnpack", Int::class.javaPrimitiveType)
            method.invoke(options, request.threads)
            true
        } catch (nsme: NoSuchMethodException) {
            Logger.w(TAG, "XNNPACK provider not available in this runtime")
            false
        } catch (ex: Exception) {
            Logger.w(TAG, "Failed to enable XNNPACK provider", ex)
            false
        }
    }

    private fun addSessionConfigEntrySafely(options: OrtSession.SessionOptions, key: String, value: String) {
        try {
            val method = options.javaClass.getMethod("addSessionConfigEntry", String::class.java, String::class.java)
            method.invoke(options, key, value)
        } catch (_: NoSuchMethodException) {
            // Older runtimes may not expose session config entries; ignore silently.
        } catch (ex: Exception) {
            Logger.w(TAG, "Failed to set session config entry $key", ex)
        }
    }

    private fun ensureDirectory(dir: File): File {
        if (!dir.exists()) {
            try {
                dir.mkdirs()
            } catch (_: Exception) {
            }
        }
        return dir
    }

    private fun detectQnnBackendPath(): String? {
        val searchPaths = mutableListOf<String>()
        context.applicationInfo?.nativeLibraryDir?.let { searchPaths += it }
        searchPaths += listOf(
            "/vendor/lib64",
            "/vendor/lib",
            "/system/lib64",
            "/system/lib",
            "/system_ext/lib64"
        )
        val candidateNames = listOf("libQnnHtp.so", "libQnnHtpNetRun.so", "libQnnHtpV69.so")
        for (path in searchPaths) {
            val dir = File(path)
            if (!dir.exists()) continue
            for (name in candidateNames) {
                val candidate = File(dir, name)
                if (candidate.exists()) {
                    return candidate.absolutePath
                }
            }
        }
        return null
    }

    private fun availableCpuThreads(): Int = Runtime.getRuntime().availableProcessors().coerceIn(1, 4)

    private suspend fun handleInferenceFailureLocked(ex: Exception): Result<InferenceResult>? {
        val message = ex.message.orEmpty()
        return if (ex is IllegalStateException && message.contains("closed OrtSession", ignoreCase = true)) {
            Logger.e(TAG, "OrtSession closed during inference; attempting to rebuild session", ex)
            resetSessionLocked()
            val rebuild = createSessionLocked()
            if (rebuild.isSuccess) {
                null
            } else {
                Result.failure(rebuild.exceptionOrNull() ?: CancellationException("Session rebuild failed"))
            }
        } else {
            Logger.e(TAG, "ONNX inference failed", ex)
            Result.failure(ex)
        }
    }

    // runtime prefs controlled from SettingsActivity
    private var prefChannelSwap: Boolean = false
    private var prefDebugMode: Boolean = false
    private var prefConfidenceThreshold: Float = 0.25f
    // preprocessing params (mean/std per channel, and overall scale multiplier)
    private var prefMean: FloatArray = floatArrayOf(0f, 0f, 0f)
    private var prefStd: FloatArray = floatArrayOf(1f, 1f, 1f)
    private var prefScale: Float = 1.0f

    private var inputWidth: Int = DEFAULT_INPUT_SIZE
    private var inputHeight: Int = DEFAULT_INPUT_SIZE
    private var inputChannels: Int = DEFAULT_INPUT_CHANNELS

    private var tensorArray: FloatArray = FloatArray(inputChannels * inputWidth * inputHeight)
    private var tensorBuffer: FloatBuffer = FloatBuffer.wrap(tensorArray)
    private var letterboxPixels: IntArray = IntArray(inputWidth * inputHeight)

    private var rgbBitmap: Bitmap? = null
    private var yuvPixels: IntArray = IntArray(0)
    private var letterboxBitmap: Bitmap = Bitmap.createBitmap(inputWidth, inputHeight, Bitmap.Config.ARGB_8888)
    private val letterboxCanvas = Canvas(letterboxBitmap)
    private val letterboxPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { isFilterBitmap = true }
    private val destRect = RectF()

    suspend fun initialize(): Result<Unit> {
        return withContext(Dispatchers.IO) {
            sessionMutex.withLock {
                resetSessionLocked()
                createSessionLocked()
            }
        }
    }

    // Run a simple self-test using an asset image (if present) to validate model inference works.
    suspend fun runSelfTest(): Result<Boolean> {
        return withContext(Dispatchers.Default) {
            try {
                if (environment == null || session == null) return@withContext Result.failure(IllegalStateException("Session not initialized"))
                // Try to load a small test image from assets if provided
                val assetNames = context.assets.list("")?.toList() ?: emptyList()
                val candidate = if (assetNames.contains("test.jpg")) "test.jpg" else null
                if (candidate == null) {
                    // No bundled test image; just return modelLoaded flag
                    return@withContext Result.success(modelLoaded)
                }
                val bmp = withContext(Dispatchers.IO) {
                    android.graphics.BitmapFactory.decodeStream(context.assets.open(candidate))
                } ?: return@withContext Result.failure(IllegalStateException("Failed to decode test asset"))

                val res = runInference(bmp)
                if (res.isFailure) return@withContext Result.failure(res.exceptionOrNull()!!)
                val detections = res.getOrNull()?.detections ?: emptyList()
                Result.success(detections.isNotEmpty())
            } catch (ex: Exception) {
                Result.failure(ex)
            }
        }
    }

    suspend fun getLatestInputDump(): String? {
        return withContext(Dispatchers.IO) {
            try {
                val photosDir = File(context.cacheDir, "photos")
                if (!photosDir.exists() || !photosDir.isDirectory) return@withContext null
                val files = photosDir.listFiles { f -> f.isFile && f.name.startsWith("onnx_input_") && f.name.endsWith(".json") } ?: return@withContext null
                if (files.isEmpty()) return@withContext null
                val latest = files.maxByOrNull { it.lastModified() } ?: return@withContext null
                latest.readText()
            } catch (_: Exception) {
                null
            }
        }
    }

    private fun loadPrefs() {
        try {
            val prefs = context.getSharedPreferences("buckwheat_prefs", Context.MODE_PRIVATE)
            prefChannelSwap = prefs.getBoolean("pref_channel_swap", false)
            prefDebugMode = prefs.getBoolean("pref_debug_mode", false)
            prefConfidenceThreshold = prefs.getFloat("pref_confidence_threshold", 0.25f)
            prefExecutionProvider = ExecutionProviderPreference.fromStored(
                prefs.getString("pref_execution_provider", ExecutionProviderPreference.toStored(ExecutionProviderPreference.AUTO))
            )
            // load preprocessing CSVs (expected "x,y,z")
            val defaultMean = "0.0,0.0,0.0"
            val defaultStd = "1.0,1.0,1.0"
            val defaultScale = "1.0"
            val meanStr = prefs.getString("pref_mean", defaultMean) ?: defaultMean
            val stdStr = prefs.getString("pref_std", defaultStd) ?: defaultStd
            val scaleStr = prefs.getString("pref_scale", defaultScale) ?: defaultScale
            prefMean = parseCsvToFloatArray(meanStr, 3, floatArrayOf(0f, 0f, 0f))
            prefStd = parseCsvToFloatArray(stdStr, 3, floatArrayOf(1f, 1f, 1f))
            prefScale = try { scaleStr.toFloat() } catch (_: Exception) { 1.0f }
        } catch (_: Exception) {
        }
    }

    private fun parseCsvToFloatArray(s: String, len: Int, fallback: FloatArray): FloatArray {
        try {
            val parts = s.split(',').map { it.trim() }.filter { it.isNotEmpty() }
            val out = FloatArray(len)
            for (i in 0 until len) {
                out[i] = if (i < parts.size) parts[i].toFloatOrNull() ?: fallback[i] else fallback[i]
            }
            return out
        } catch (_: Exception) {
            return fallback
        }
    }

    fun isReady(): Boolean = !shuttingDown && session != null && inputName != null

    fun getProviderReport(): ProviderReport = lastProviderReport

    suspend fun runInference(image: ImageProxy): Result<InferenceResult> {
        return withContext(Dispatchers.Default) {
            var attempt = 0
            while (attempt < 2) {
                if (shuttingDown) {
                    return@withContext Result.failure(CancellationException("Inference engine shutting down"))
                }
                val result = sessionMutex.withLock<Result<InferenceResult>?> {
                    if (shuttingDown) {
                        return@withLock Result.failure(CancellationException("Inference engine shutting down"))
                    }

                    val env = environment ?: return@withLock Result.failure(IllegalStateException("Environment not initialized"))
                    val sess = session ?: return@withLock Result.failure(IllegalStateException("Session not initialized"))
                    val inputKey = inputName ?: return@withLock Result.failure(IllegalStateException("Input name missing"))

                    try {
                        loadPrefs()
                        val bitmap = imageProxyToBitmap(image)
                        val metadata = renderLetterboxed(bitmap, image.imageInfo.rotationDegrees)
                        tensorBuffer.rewind()
                        val inputTensor = OnnxTensor.createTensor(env, tensorBuffer, longArrayOf(1, inputChannels.toLong(), inputHeight.toLong(), inputWidth.toLong()))

                        if (prefDebugMode) {
                            try {
                                val inputDumpFile = File(context.cacheDir, "photos/onnx_input_${System.currentTimeMillis()}.json").apply { parentFile?.mkdirs() }
                                val snapshot = tensorArray.copyOf()
                                val root = JSONObject()
                                root.put("shape", JSONArray(listOf(1, inputChannels, inputHeight, inputWidth)))
                                val arr = JSONArray()
                                for (v in snapshot) arr.put(v.toDouble())
                                root.put("data", arr)
                                inputDumpFile.writeText(root.toString())
                                Logger.i(TAG, "Dumped input tensor to ${inputDumpFile.absolutePath}")
                            } catch (_: Exception) {}
                        }

                        val feed = mutableMapOf<String, OnnxTensor>()
                        val extraTensors = mutableListOf<OnnxTensor>()
                        try {
                            feed[inputKey] = inputTensor

                            for (name in sess.inputNames) {
                                if (name == inputKey) continue
                                val tensor = createAuxiliaryTensor(env, sess, name, metadata)
                                if (tensor != null) {
                                    feed[name] = tensor
                                    extraTensors += tensor
                                }
                            }

                            if (prefDebugMode) {
                                try {
                                    val sb = StringBuilder()
                                    sb.append("Auxiliary inputs provided:\n")
                                    for ((k, v) in feed) {
                                        val info = try { v.info } catch (_: Exception) { null }
                                        sb.append("name=${k} info=${info}\n")
                                    }
                                    Logger.i(TAG, sb.toString())
                                } catch (_: Exception) {}
                            }

                            val detections = inputTensor.use {
                                sess.run(feed).use { result ->
                                    if (result == null || result.size() == 0) {
                                        Logger.i(TAG, "ONNX run returned no outputs: size=${result?.size()}")
                                        return@use emptyList<Detection>()
                                    }

                                    try {
                                        val outInfoSb = StringBuilder()
                                        for (i in 0 until result.size()) {
                                            val r = result[i]
                                            val info = try { (r as? OnnxTensor)?.info } catch (_: Exception) { null }
                                            outInfoSb.append("out[$i]=class=${r?.javaClass?.name} info=${info}\n")
                                        }
                                        Logger.i(TAG, "ONNX outputs metadata:\n${outInfoSb}")
                                    } catch (_: Exception) {}

                                    parseVariousOnnxOutputs(result, metadata)
                                }
                            }

                            Result.success(InferenceResult(detections = detections, metadata = metadata))
                        } finally {
                            for (t in extraTensors) {
                                try { t.close() } catch (_: Exception) {}
                            }
                        }
                    } catch (ex: Exception) {
                        val handled = handleInferenceFailureLocked(ex)
                        if (handled == null) {
                            null
                        } else {
                            handled
                        }
                    }
                }
                if (result != null) {
                    return@withContext result
                }
                attempt++
            }
            Result.failure(IllegalStateException("Inference failed after session rebuild"))
        }
    }

    // One-shot inference entry for a captured Bitmap (single-frame / shutter use-case)
    suspend fun runInference(bitmap: Bitmap): Result<InferenceResult> {
        return withContext(Dispatchers.Default) {
            var attempt = 0
            while (attempt < 2) {
                if (shuttingDown) {
                    return@withContext Result.failure(CancellationException("Inference engine shutting down"))
                }
                val result = sessionMutex.withLock<Result<InferenceResult>?> {
                    if (shuttingDown) {
                        return@withLock Result.failure(CancellationException("Inference engine shutting down"))
                    }

                    val env = environment ?: return@withLock Result.failure(IllegalStateException("Environment not initialized"))
                    val sess = session ?: return@withLock Result.failure(IllegalStateException("Session not initialized"))
                    val inputKey = inputName ?: return@withLock Result.failure(IllegalStateException("Input name missing"))

                    try {
                        loadPrefs()
                        val metadata = renderLetterboxed(bitmap, 0)
                        tensorBuffer.rewind()
                        val inputTensor = OnnxTensor.createTensor(env, tensorBuffer, longArrayOf(1, inputChannels.toLong(), inputHeight.toLong(), inputWidth.toLong()))

                        if (prefDebugMode) {
                            try {
                                val inputDumpFile = File(context.cacheDir, "photos/onnx_input_${System.currentTimeMillis()}.json").apply { parentFile?.mkdirs() }
                                val snapshot = tensorArray.copyOf()
                                val root = JSONObject()
                                root.put("shape", JSONArray(listOf(1, inputChannels, inputHeight, inputWidth)))
                                val arr = JSONArray()
                                for (v in snapshot) arr.put(v.toDouble())
                                root.put("data", arr)
                                inputDumpFile.writeText(root.toString())
                                Logger.i(TAG, "Dumped input tensor to ${inputDumpFile.absolutePath}")
                            } catch (_: Exception) {}
                        }

                        val feed = mutableMapOf<String, OnnxTensor>()
                        val extraTensors = mutableListOf<OnnxTensor>()
                        try {
                            feed[inputKey] = inputTensor
                            for (name in sess.inputNames) {
                                if (name == inputKey) continue
                                val tensor = createAuxiliaryTensor(env, sess, name, metadata)
                                if (tensor != null) {
                                    feed[name] = tensor
                                    extraTensors += tensor
                                }
                            }

                            val detections = inputTensor.use {
                                sess.run(feed).use { result ->
                                    if (result == null || result.size() < 2) {
                                        Logger.e(TAG, "Unexpected ONNX result: size=${result?.size()}")
                                        throw IllegalStateException("Unexpected ONNX result size: ${result?.size()}")
                                    }
                                    val out0 = result[0]
                                    val out1 = result[1]
                                    if (out0 !is OnnxTensor || out1 !is OnnxTensor) {
                                        Logger.e(TAG, "ONNX outputs are not tensors: out0=${out0?.javaClass?.name}, out1=${out1?.javaClass?.name}")
                                        throw IllegalStateException("ONNX outputs are not tensors")
                                    }
                                    val boxesTensor = out0 as OnnxTensor
                                    val scoresTensor = out1 as OnnxTensor

                                    try {
                                        val bInfo = boxesTensor.info as? TensorInfo
                                        val bShape = bInfo?.shape
                                        if (bShape != null && bShape.isNotEmpty() && bShape[0] == 0L) {
                                            Logger.i(TAG, "ONNX model returned zero boxes (shape=${bShape.toList()}) - no detections")
                                            return@use emptyList<Detection>()
                                        }
                                    } catch (t: Throwable) {}

                                    val boxesBuf = try { boxesTensor.floatBuffer } catch (t: Throwable) { null }
                                    val scoresBuf = try { scoresTensor.floatBuffer } catch (t: Throwable) { null }

                                    if (boxesBuf != null && scoresBuf != null) {
                                        val boxesArray = FloatArray(boxesBuf.remaining())
                                        boxesBuf.get(boxesArray)
                                        boxesBuf.rewind()

                                        val scoresArray = FloatArray(scoresBuf.remaining())
                                        scoresBuf.get(scoresArray)
                                        scoresBuf.rewind()

                                        if (prefDebugMode) {
                                            try {
                                                val dumpFile = File(context.cacheDir, "onnx_dump_${System.currentTimeMillis()}.json")
                                                dumpOnnxOutputs(boxesArray, scoresArray, dumpFile)
                                            } catch (_: Exception) {}
                                        }

                                        parseDetectionsFromFloatArrays(boxesArray, scoresArray, metadata)
                                    } else {
                                        try {
                                            val boxesVal = boxesTensor.value
                                            val scoresVal = scoresTensor.value
                                            val boxesArray = flattenToFloatArray(boxesVal)
                                            val scoresArray = flattenToFloatArray(scoresVal)
                                            if (boxesArray.isEmpty() || scoresArray.isEmpty()) {
                                                Logger.e(TAG, "Converted ONNX outputs are empty. boxesInfo=${boxesTensor.info}, scoresInfo=${scoresTensor.info}")
                                                throw IllegalStateException("ONNX outputs empty after conversion")
                                            }
                                            if (prefDebugMode) {
                                                try {
                                                    val dumpFile = File(context.cacheDir, "onnx_dump_${System.currentTimeMillis()}.json")
                                                    dumpOnnxOutputs(boxesArray, scoresArray, dumpFile)
                                                } catch (_: Exception) {}
                                            }

                                            parseDetectionsFromFloatArrays(boxesArray, scoresArray, metadata)
                                        } catch (convEx: Exception) {
                                            Logger.e(TAG, "Failed to convert ONNX output to float arrays", convEx)
                                            throw IllegalStateException("ONNX tensor floatBuffer is null and conversion failed", convEx)
                                        }
                                    }
                                }
                            }
                            Result.success(InferenceResult(detections = detections, metadata = metadata))
                        } finally {
                            for (t in extraTensors) {
                                try { t.close() } catch (_: Exception) {}
                            }
                        }
                    } catch (ex: Exception) {
                        val handled = handleInferenceFailureLocked(ex)
                        if (handled == null) {
                            null
                        } else {
                            handled
                        }
                    }
                }
                if (result != null) {
                    return@withContext result
                }
                attempt++
            }
            Result.failure(IllegalStateException("Inference failed after session rebuild"))
        }
    }

    fun close() {
        shuttingDown = true
        runBlocking {
            sessionMutex.withLock {
                resetSessionLocked()
            }
        }
    }

    private fun configureInputShape(info: TensorInfo?) {
        if (info == null) {
            resizeInputBuffers(DEFAULT_INPUT_SIZE, DEFAULT_INPUT_SIZE, DEFAULT_INPUT_CHANNELS)
            return
        }
        val shape = info.shape
        if (shape.size < 4) {
            resizeInputBuffers(DEFAULT_INPUT_SIZE, DEFAULT_INPUT_SIZE, DEFAULT_INPUT_CHANNELS)
            return
        }
        val channels = shape[shape.size - 3].toDimension(DEFAULT_INPUT_CHANNELS)
        val height = shape[shape.size - 2].toDimension(DEFAULT_INPUT_SIZE)
        val width = shape[shape.size - 1].toDimension(DEFAULT_INPUT_SIZE)
        resizeInputBuffers(width, height, channels)
    }

    private fun resizeInputBuffers(width: Int, height: Int, channels: Int) {
        val safeWidth = width.coerceAtLeast(1)
        val safeHeight = height.coerceAtLeast(1)
        val safeChannels = channels.coerceAtLeast(1)
        if (safeWidth == inputWidth && safeHeight == inputHeight && safeChannels == inputChannels) {
            return
        }
        inputWidth = safeWidth
        inputHeight = safeHeight
        inputChannels = safeChannels

        tensorArray = FloatArray(inputChannels * inputWidth * inputHeight)
        tensorBuffer = FloatBuffer.wrap(tensorArray)
        letterboxPixels = IntArray(inputWidth * inputHeight)

        letterboxBitmap.recycle()
        letterboxBitmap = Bitmap.createBitmap(inputWidth, inputHeight, Bitmap.Config.ARGB_8888)
        letterboxCanvas.setBitmap(letterboxBitmap)
    }

    private suspend fun exportModelToCache(): File {
        return withContext(Dispatchers.IO) {
            val cacheDir = File(context.filesDir, MODEL_CACHE_DIR).apply { mkdirs() }
            val destination = File(cacheDir, MODEL_FILE_NAME)
            if (destination.exists()) {
                return@withContext destination
            }
            context.assets.open(MODEL_ASSET_PATH).use { input ->
                FileOutputStream(destination).use { output ->
                    input.copyTo(output)
                }
            }
            destination
        }
    }

    private suspend fun loadLabels(): List<String> {
        return withContext(Dispatchers.IO) {
            try {
                context.assets.open(LABELS_ASSET_PATH).bufferedReader().use { reader ->
                    parseLabelFile(reader.readText())
                }
            } catch (ex: IOException) {
                Log.w(TAG, "Label file not found, using fallback labels", ex)
                emptyList()
            }
        }
    }

    fun imageProxyToBitmap(image: ImageProxy): Bitmap {
        val width = image.width
        val height = image.height

        val bitmap = rgbBitmap?.takeIf { it.width == width && it.height == height }
            ?: Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888).also { rgbBitmap = it }

        val yPlane = image.planes[0]
        val uPlane = image.planes[1]
        val vPlane = image.planes[2]

        val yBuffer = yPlane.buffer
        val uBuffer = uPlane.buffer
        val vBuffer = vPlane.buffer

        val yRowStride = yPlane.rowStride
        val uvRowStride = uPlane.rowStride
        val uvPixelStride = uPlane.pixelStride

    val pixels = ensureYuvPixels(width * height)

        var pixelIndex = 0
        for (row in 0 until height) {
            val yRow = yRowStride * row
            val uvRow = uvRowStride * (row / 2)
            for (col in 0 until width) {
                val yIndex = yRow + col
                val uvIndex = uvRow + (col / 2) * uvPixelStride
                val y = yBuffer.get(yIndex).toInt() and 0xFF
                val u = uBuffer.get(uvIndex).toInt() and 0xFF
                val v = vBuffer.get(uvIndex).toInt() and 0xFF
                pixels[pixelIndex++] = yuvToArgb(y, u, v)
            }
        }

        bitmap.setPixels(pixels, 0, width, 0, 0, width, height)
        return bitmap
    }

    private fun renderLetterboxed(source: Bitmap, rotationDegrees: Int): LetterboxMetadata {
        letterboxCanvas.drawColor(LETTERBOX_COLOR)

        // 记录原始尺寸
        val originalWidth = source.width
        val originalHeight = source.height

        // ===== 关键修改: 不旋转图像,保持原始方向 =====
        // PreviewView会自动处理显示旋转,我们的坐标应该在原始图像空间
        val rotatedBitmap = source  // 直接使用原图,不做任何旋转
        // ==========================================


        val scale = min(inputWidth.toFloat() / rotatedBitmap.width, inputHeight.toFloat() / rotatedBitmap.height)
        val scaledWidth = rotatedBitmap.width * scale
        val scaledHeight = rotatedBitmap.height * scale
        val padX = (inputWidth - scaledWidth) / 2f
        val padY = (inputHeight - scaledHeight) / 2f

        destRect.set(padX, padY, padX + scaledWidth, padY + scaledHeight)
        letterboxCanvas.drawBitmap(rotatedBitmap, null, destRect, letterboxPaint)

        val rotatedWidth = rotatedBitmap.width
        val rotatedHeight = rotatedBitmap.height
        if (rotatedBitmap !== source) {
            rotatedBitmap.recycle()
        }

        letterboxBitmap.getPixels(letterboxPixels, 0, inputWidth, 0, 0, inputWidth, inputHeight)
        val area = inputWidth * inputHeight
        val meanR = prefMean.getOrElse(0) { 0f }
        val meanG = prefMean.getOrElse(1) { 0f }
        val meanB = prefMean.getOrElse(2) { 0f }
        val stdR = prefStd.getOrElse(0) { 1f }.let { if (abs(it) < 1e-6f) 1f else it }
        val stdG = prefStd.getOrElse(1) { 1f }.let { if (abs(it) < 1e-6f) 1f else it }
        val stdB = prefStd.getOrElse(2) { 1f }.let { if (abs(it) < 1e-6f) 1f else it }
        val scaleMultiplier = prefScale
        for (i in 0 until area) {
            val color = letterboxPixels[i]
            val rRaw = ((color shr 16) and 0xFF) / 255f
            val gRaw = ((color shr 8) and 0xFF) / 255f
            val bRaw = (color and 0xFF) / 255f

            // apply normalization ((channel - mean) / std) * scale
            val r = ((rRaw - meanR) / stdR) * scaleMultiplier
            val g = ((gRaw - meanG) / stdG) * scaleMultiplier
            val b = ((bRaw - meanB) / stdB) * scaleMultiplier

            if (prefChannelSwap) {
                // write B,G,R order
                if (inputChannels > 0) tensorArray[i] = b
                if (inputChannels > 1) tensorArray[area + i] = g
                if (inputChannels > 2) tensorArray[2 * area + i] = r
            } else {
                // default R,G,B
                if (inputChannels > 0) tensorArray[i] = r
                if (inputChannels > 1) tensorArray[area + i] = g
                if (inputChannels > 2) tensorArray[2 * area + i] = b
            }
        }

        if (inputChannels > 3) {
            val remaining = inputChannels - 3
            val offsetStart = 3 * area
            java.util.Arrays.fill(tensorArray, offsetStart, offsetStart + remaining * area, 0f)
        }

        val scaleX = if (rotatedWidth != 0) (scaledWidth / rotatedWidth).toFloat() else scale
        val scaleY = if (rotatedHeight != 0) (scaledHeight / rotatedHeight).toFloat() else scale

        val metadata = LetterboxMetadata(
            scale = scale,
            padX = padX,
            padY = padY,
            sourceWidth = rotatedWidth,
            sourceHeight = rotatedHeight,
            scaleX = scaleX,
            scaleY = scaleY,
            rotationDegrees = rotationDegrees,
            originalWidth = originalWidth,
            originalHeight = originalHeight
        )
        
        // 强制输出letterbox信息用于调试
        Logger.i(TAG, "Letterbox: source=${rotatedWidth}x${rotatedHeight}, letterbox=${inputWidth}x${inputHeight}, scale=$scale, padX=$padX, padY=$padY, scaledSize=${scaledWidth}x${scaledHeight}")
        
        return metadata
    }

    private fun parseDetections(boxesTensor: OnnxTensor, scoresTensor: OnnxTensor, metadata: LetterboxMetadata): List<Detection> {
        val boxesBuffer = boxesTensor.floatBuffer
        val scoresBuffer = scoresTensor.floatBuffer

        val boxesArray = FloatArray(boxesBuffer.remaining())
        boxesBuffer.get(boxesArray)
        boxesBuffer.rewind()

        val scoresArray = FloatArray(scoresBuffer.remaining())
        scoresBuffer.get(scoresArray)
        scoresBuffer.rewind()

        val numDetections = boxesArray.size / 4
        val numClasses = if (numDetections == 0) 0 else scoresArray.size / numDetections

        if (numDetections == 0 || numClasses == 0) {
            return emptyList()
        }

        val candidates = mutableListOf<RawDetection>()
        val invScaleX = if (metadata.scaleX == 0f) 0f else 1f / metadata.scaleX
        val invScaleY = if (metadata.scaleY == 0f) 0f else 1f / metadata.scaleY
        val imageWidth = metadata.sourceWidth.toFloat()
        val imageHeight = metadata.sourceHeight.toFloat()
        for (index in 0 until numDetections) {
            val boxOffset = index * 4
            val scoreOffset = index * numClasses

            var bestScore = 0f
            var bestClass = -1
            for (cls in 0 until numClasses) {
                val score = scoresArray[scoreOffset + cls]
                if (score > bestScore) {
                    bestScore = score
                    bestClass = cls
                }
            }

            if (bestClass >= 0 && bestScore >= prefConfidenceThreshold) {
                val x1 = ((boxesArray[boxOffset] - metadata.padX) * invScaleX).coerceIn(0f, imageWidth)
                val y1 = ((boxesArray[boxOffset + 1] - metadata.padY) * invScaleY).coerceIn(0f, imageHeight)
                val x2 = ((boxesArray[boxOffset + 2] - metadata.padX) * invScaleX).coerceIn(0f, imageWidth)
                val y2 = ((boxesArray[boxOffset + 3] - metadata.padY) * invScaleY).coerceIn(0f, imageHeight)
                candidates += RawDetection(
                    classIndex = bestClass,
                    score = bestScore,
                    box = BoundingBox(
                        left = min(x1, x2),
                        top = min(y1, y2),
                        right = max(x1, x2),
                        bottom = max(y1, y2)
                    )
                )
            }
        }

        if (candidates.isEmpty()) return emptyList()

        val finalDetections = mutableListOf<Detection>()
        candidates.groupBy { it.classIndex }.values.forEach { perClass ->
            val sorted = perClass.sortedByDescending { it.score }
            val kept = mutableListOf<RawDetection>()
            for (candidate in sorted) {
                if (kept.none { iou(it.box, candidate.box) > NMS_THRESHOLD }) {
                    kept += candidate
                }
            }
            kept.forEach { raw ->
                val label = labels.getOrNull(raw.classIndex) ?: "Class ${raw.classIndex}"
                finalDetections += Detection(
                    label = label,
                    score = raw.score,
                    boundingBox = raw.box
                )
            }
        }

        return finalDetections
    }

    private fun iou(a: BoundingBox, b: BoundingBox): Float {
        val x1 = max(a.left, b.left)
        val y1 = max(a.top, b.top)
        val x2 = min(a.right, b.right)
        val y2 = min(a.bottom, b.bottom)

        val intersection = max(0f, x2 - x1).let { width ->
            val height = max(0f, y2 - y1)
            width * height
        }

        if (intersection <= 0f) return 0f

        val areaA = (a.right - a.left).coerceAtLeast(0f) * (a.bottom - a.top).coerceAtLeast(0f)
        val areaB = (b.right - b.left).coerceAtLeast(0f) * (b.bottom - b.top).coerceAtLeast(0f)
        val union = areaA + areaB - intersection
        return if (union <= 0f) 0f else intersection / union
    }

    // Helper: flatten arbitrary multi-dimensional ONNX output value to a float array (best-effort)
    private fun flattenToFloatArray(value: Any?): FloatArray {
        if (value == null) return FloatArray(0)
        return when (value) {
            is FloatArray -> value
            is DoubleArray -> FloatArray(value.size) { i -> value[i].toFloat() }
            is IntArray -> FloatArray(value.size) { i -> value[i].toFloat() }
            is LongArray -> FloatArray(value.size) { i -> value[i].toFloat() }
            is Array<*> -> {
                // recursively flatten
                val list = ArrayList<Float>()
                fun walk(v: Any?) {
                    when (v) {
                        is Float -> list.add(v)
                        is Double -> list.add(v.toFloat())
                        is Int -> list.add(v.toFloat())
                        is Long -> list.add(v.toFloat())
                        is FloatArray -> v.forEach { list.add(it) }
                        is DoubleArray -> v.forEach { list.add(it.toFloat()) }
                        is IntArray -> v.forEach { list.add(it.toFloat()) }
                        is LongArray -> v.forEach { list.add(it.toFloat()) }
                        is Array<*> -> v.forEach { walk(it) }
                        else -> {}
                    }
                }
                walk(value)
                list.toFloatArray()
            }
            else -> FloatArray(0)
        }
    }

    private fun parseDetectionsFromFloatArrays(boxesArray: FloatArray, scoresArray: FloatArray, metadata: LetterboxMetadata): List<Detection> {
        val numDetections = boxesArray.size / 4
        val numClasses = if (numDetections == 0) 0 else scoresArray.size / numDetections

        if (numDetections == 0 || numClasses == 0) {
            return emptyList()
        }

        val candidates = mutableListOf<RawDetection>()
        val invScaleX = if (metadata.scaleX == 0f) 0f else 1f / metadata.scaleX
        val invScaleY = if (metadata.scaleY == 0f) 0f else 1f / metadata.scaleY
        val imageWidth = metadata.sourceWidth.toFloat()
        val imageHeight = metadata.sourceHeight.toFloat()
        
        // 检测坐标是否已经在原图尺度 (由上游手动缩放过)
        var maxCoord = 0f
        for (index in 0 until numDetections) {
            val boxOffset = index * 4
            maxCoord = max(maxCoord, max(
                max(boxesArray[boxOffset], boxesArray[boxOffset + 1]),
                max(boxesArray[boxOffset + 2], boxesArray[boxOffset + 3])
            ))
        }
        val alreadyScaled = (maxCoord > 1000f)
        
        if (prefDebugMode) {
            Logger.i(TAG, "parseDetections: numDet=$numDetections, numCls=$numClasses, maxCoord=$maxCoord, alreadyScaled=$alreadyScaled")
        }
        
        for (index in 0 until numDetections) {
            val boxOffset = index * 4
            val scoreOffset = index * numClasses

            var bestScore = 0f
            var bestClass = -1
            for (cls in 0 until numClasses) {
                val score = scoresArray[scoreOffset + cls]
                if (score > bestScore) {
                    bestScore = score
                    bestClass = cls
                }
            }

            val threshold = if (prefDebugMode) 0f else prefConfidenceThreshold
            if (bestClass >= 0 && bestScore >= threshold) {
                // 如果坐标已经被手动缩放到原图尺寸,则跳过letterbox逆变换
                val x1: Float
                val y1: Float
                val x2: Float
                val y2: Float
                
                if (alreadyScaled) {
                    // 坐标已经在原图尺寸,只需限制范围
                    x1 = boxesArray[boxOffset].coerceIn(0f, imageWidth)
                    y1 = boxesArray[boxOffset + 1].coerceIn(0f, imageHeight)
                    x2 = boxesArray[boxOffset + 2].coerceIn(0f, imageWidth)
                    y2 = boxesArray[boxOffset + 3].coerceIn(0f, imageHeight)
                } else {
                    // 需要letterbox逆变换
                    x1 = ((boxesArray[boxOffset] - metadata.padX) * invScaleX).coerceIn(0f, imageWidth)
                    y1 = ((boxesArray[boxOffset + 1] - metadata.padY) * invScaleY).coerceIn(0f, imageHeight)
                    x2 = ((boxesArray[boxOffset + 2] - metadata.padX) * invScaleX).coerceIn(0f, imageWidth)
                    y2 = ((boxesArray[boxOffset + 3] - metadata.padY) * invScaleY).coerceIn(0f, imageHeight)
                }
                
                candidates += RawDetection(
                    classIndex = bestClass,
                    score = bestScore,
                    box = BoundingBox(
                        left = min(x1, x2),
                        top = min(y1, y2),
                        right = max(x1, x2),
                        bottom = max(y1, y2)
                    )
                )
            }
        }

        if (candidates.isEmpty()) return emptyList()

        val finalDetections = mutableListOf<Detection>()
        candidates.groupBy { it.classIndex }.values.forEach { perClass ->
            val sorted = perClass.sortedByDescending { it.score }
            val kept = mutableListOf<RawDetection>()
            for (candidate in sorted) {
                if (kept.none { iou(it.box, candidate.box) > NMS_THRESHOLD }) {
                    kept += candidate
                }
            }
            kept.forEach { raw ->
                val label = labels.getOrNull(raw.classIndex) ?: "Class ${raw.classIndex}"
                finalDetections += Detection(
                    label = label,
                    score = raw.score,
                    boundingBox = raw.box
                )
            }
        }

        return finalDetections
    }

    // 专门处理PaddleDetection的Nx6格式输出: [class, score, x1, y1, x2, y2]
    private fun parsePaddleDetectionNx6(flatArray: FloatArray, metadata: LetterboxMetadata): List<Detection> {
        if (flatArray.size % 6 != 0) {
            Logger.e(TAG, "Invalid Nx6 array size: ${flatArray.size}")
            return emptyList()
        }
        
        val numRows = flatArray.size / 6
        val invScaleX = if (metadata.scaleX == 0f) 0f else 1f / metadata.scaleX
        val invScaleY = if (metadata.scaleY == 0f) 0f else 1f / metadata.scaleY
        val imageWidth = metadata.sourceWidth.toFloat()
        val imageHeight = metadata.sourceHeight.toFloat()
        val expectedLetterboxWidth = (metadata.scaleX * metadata.sourceWidth).coerceAtLeast(1f)
        val expectedLetterboxHeight = (metadata.scaleY * metadata.sourceHeight).coerceAtLeast(1f)

        // 检测坐标是否在原图尺度还是letterbox尺度
        var maxCoord = 0f
        for (r in 0 until numRows) {
            val base = r * 6
            val score = flatArray[base + 1]
            if (score >= 0.01f) {  // 降低阈值以检查坐标范围
                maxCoord = max(maxCoord, max(
                    max(flatArray[base + 2], flatArray[base + 3]),
                    max(flatArray[base + 4], flatArray[base + 5])
                ))
            }
        }
        
        // 如果最大坐标接近letterbox尺寸(800),需要手动缩放到原图
        val expectedMaxLetterbox = max(expectedLetterboxWidth, expectedLetterboxHeight)
        val coordsLookLikeLetterbox = if (expectedMaxLetterbox <= 1f) {
            maxCoord <= 1000f
        } else {
            maxCoord <= expectedMaxLetterbox * 1.05f
        }
        val applyLetterboxInverse = coordsLookLikeLetterbox

        val manualScaleX = if (applyLetterboxInverse) metadata.scaleX else 1f
        val manualScaleY = if (applyLetterboxInverse) metadata.scaleY else 1f
        
        // 强制输出metadata用于调试(不受prefDebugMode限制)
        Logger.i(TAG, "PaddleNx6 Metadata: source=${metadata.sourceWidth}x${metadata.sourceHeight}, padX=${metadata.padX}, padY=${metadata.padY}, scaleX=${metadata.scaleX}, scaleY=${metadata.scaleY}, invScaleX=$invScaleX, invScaleY=$invScaleY")
    Logger.i(TAG, "PaddleNx6: rows=$numRows, maxCoord=$maxCoord, letterboxExpected=$expectedMaxLetterbox, applyInverse=$applyLetterboxInverse, scale=[$manualScaleX, $manualScaleY]")

        
        val candidates = mutableListOf<RawDetection>()
        val threshold = if (prefDebugMode) 0.05f else prefConfidenceThreshold
        
        for (r in 0 until numRows) {
            val base = r * 6
            val classId = flatArray[base].toInt()
            val score = flatArray[base + 1]
            
            if (score < threshold) continue
            
            // PaddleDetection输出的坐标始终在letterbox尺度(0-800)
            // 需要: 1) 减去padding  2) 除以scale转换到原图尺度  3) 反向旋转到原始相机坐标系
            val rawX1 = flatArray[base + 2]
            val rawY1 = flatArray[base + 3]
            val rawX2 = flatArray[base + 4]
            val rawY2 = flatArray[base + 5]
            
            var x1: Float
            var y1: Float
            var x2: Float
            var y2: Float

            if (applyLetterboxInverse) {
                x1 = (rawX1 - metadata.padX) * invScaleX
                y1 = (rawY1 - metadata.padY) * invScaleY
                x2 = (rawX2 - metadata.padX) * invScaleX
                y2 = (rawY2 - metadata.padY) * invScaleY
            } else {
                x1 = rawX1
                y1 = rawY1
                x2 = rawX2
                y2 = rawY2
            }
            
            // ===== 不需要反向旋转 - 图像未被旋转 =====
            // 坐标已经在原始图像空间,直接限制范围即可
            
            // 限制到原始图像范围
            val finalWidth = metadata.originalWidth.toFloat()
            val finalHeight = metadata.originalHeight.toFloat()
            x1 = x1.coerceIn(0f, finalWidth)
            y1 = y1.coerceIn(0f, finalHeight)
            x2 = x2.coerceIn(0f, finalWidth)
            y2 = y2.coerceIn(0f, finalHeight)
            
            // 输出前3个检测的详细转换过程
            if (r < 3) {
                Logger.i(TAG, "  Detection $r: class=$classId, score=${"%.2f".format(score)}")
                Logger.i(TAG, "    Raw letterbox coords: [${"%.1f".format(rawX1)}, ${"%.1f".format(rawY1)}, ${"%.1f".format(rawX2)}, ${"%.1f".format(rawY2)}]")
                Logger.i(TAG, "    Final image coords: [${"%.1f".format(x1)}, ${"%.1f".format(y1)}, ${"%.1f".format(x2)}, ${"%.1f".format(y2)}]")
                Logger.i(TAG, "    Image size: ${finalWidth.toInt()}x${finalHeight.toInt()}")
            }
            
            candidates += RawDetection(
                classIndex = classId,
                score = score,
                box = BoundingBox(
                    left = min(x1, x2),
                    top = min(y1, y2),
                    right = max(x1, x2),
                    bottom = max(y1, y2)
                )
            )
        }
        
        Logger.i(TAG, "PaddleNx6 candidates: ${candidates.size} (threshold=$threshold)")
        
        if (candidates.isEmpty()) return emptyList()
        
        // NMS处理
        val finalDetections = mutableListOf<Detection>()
        candidates.groupBy { it.classIndex }.values.forEach { perClass ->
            val sorted = perClass.sortedByDescending { it.score }
            val kept = mutableListOf<RawDetection>()
            for (candidate in sorted) {
                if (kept.none { iou(it.box, candidate.box) > NMS_THRESHOLD }) {
                    kept += candidate
                }
            }
            kept.forEach { raw ->
                val label = labels.getOrNull(raw.classIndex) ?: "Class ${raw.classIndex}"
                finalDetections += Detection(
                    label = label,
                    score = raw.score,
                    boundingBox = raw.box
                )
            }
        }
        
        Logger.i(TAG, "PaddleNx6 final detections: ${finalDetections.size}")
        return finalDetections
    }

    // Heuristic parser: accept different ONNX output layouts and return detections.
    private fun parseVariousOnnxOutputs(result: OrtSession.Result, metadata: LetterboxMetadata): List<Detection> {
        return try {
            // PaddleDetection格式: 第一个张量是 [N, 6] (class, score, x1, y1, x2, y2)
            // 第二个张量是 [1] 包含检测数量
            if (result.size() >= 2 && result[0] is OnnxTensor) {
                val out0 = result[0] as OnnxTensor
                val info0 = out0.info as? TensorInfo
                val shape0 = info0?.shape
                
                // 检查第一个张量是否是 [N, 6] 格式
                if (shape0 != null && shape0.size == 2 && shape0[1] == 6L) {
                    val detTensor = tensorToFloatArray(out0)
                    if (detTensor.isNotEmpty()) {
                        Logger.i(TAG, "Detected PaddleDetection Nx6 format: ${shape0[0]} rows")
                        return parsePaddleDetectionNx6(detTensor, metadata)
                    }
                }
                
                // 传统格式: 两个张量 (boxes, scores)
                val out1 = result[1]
                val boxesArr = tensorToFloatArray(out0)
                val scoresArr = tensorToFloatArray(out1)
                if (boxesArr.isNotEmpty() && scoresArr.isNotEmpty()) {
                    if (prefDebugMode) dumpOnnxOutputs(boxesArr, scoresArr, File("onnx_dump_${System.currentTimeMillis()}.json"))
                    return parseDetectionsFromFloatArrays(boxesArr, scoresArr, metadata)
                }
            }

            // Single-tensor detection formats: Nx6 (class,score,x1,y1,x2,y2) from PaddleDetection ONNX
            if (result.size() == 1 && result[0] is OnnxTensor) {
                val t = result[0]
                val flat = tensorToFloatArray(t)
                if (flat.isNotEmpty()) {
                    // try interpret as rows of 6 - PaddleDetection format: [class, score, x1, y1, x2, y2]
                    if (flat.size % 6 == 0) {
                        val rows = flat.size / 6
                        
                        // 关键修复: 检测坐标是否需要手动缩放
                        var maxCoord = 0f
                        for (r in 0 until rows) {
                            val base = r * 6
                            val score = flat[base + 1]
                            if (score >= prefConfidenceThreshold) {
                                maxCoord = max(maxCoord, max(
                                    max(flat[base + 2], flat[base + 3]),
                                    max(flat[base + 4], flat[base + 5])
                                ))
                            }
                        }
                        
                        // 如果最大坐标 < 1000, 说明还在800x800尺度,需要手动缩放
                        val needsManualScaling = (maxCoord > 0f && maxCoord < 1000f)
                        val manualScaleX = if (needsManualScaling) metadata.scaleX else 1f
                        val manualScaleY = if (needsManualScaling) metadata.scaleY else 1f
                        
                        Logger.i(TAG, "Nx6 format: rows=$rows, maxCoord=$maxCoord, needsManualScaling=$needsManualScaling, manualScale=[$manualScaleX, $manualScaleY]")
                        
                        val boxes = FloatArray(rows * 4)
                        val scores = FloatArray(rows * labels.size.coerceAtLeast(1))
                        
                        for (r in 0 until rows) {
                            val base = r * 6
                            val classId = flat[base].toInt()
                            val score = flat[base + 1]
                            
                            // 应用手动缩放
                            boxes[r * 4 + 0] = flat[base + 2] * manualScaleX
                            boxes[r * 4 + 1] = flat[base + 3] * manualScaleY
                            boxes[r * 4 + 2] = flat[base + 4] * manualScaleX
                            boxes[r * 4 + 3] = flat[base + 5] * manualScaleY
                            
                            // 构建per-class scores数组
                            if (classId >= 0 && classId < labels.size) {
                                scores[r * labels.size + classId] = score
                            }
                        }
                        
                        if (prefDebugMode) dumpOnnxOutputs(boxes, scores, File("onnx_dump_${System.currentTimeMillis()}.json"))
                        return parseDetectionsFromFloatArrays(boxes, scores, metadata)
                    }
                    // Try Nx5 (x1,y1,x2,y2,score)
                    if (flat.size % 5 == 0) {
                        val rows = flat.size / 5
                        val boxes = FloatArray(rows * 4)
                        val scoresConcat = FloatArray(rows)
                        for (r in 0 until rows) {
                            val base = r * 5
                            boxes[r * 4 + 0] = flat[base]
                            boxes[r * 4 + 1] = flat[base + 1]
                            boxes[r * 4 + 2] = flat[base + 2]
                            boxes[r * 4 + 3] = flat[base + 3]
                            scoresConcat[r] = flat[base + 4]
                        }
                        if (prefDebugMode) dumpOnnxOutputs(boxes, scoresConcat, File("onnx_dump_${System.currentTimeMillis()}.json"))
                        return parseDetectionsFromFloatArrays(boxes, scoresConcat, metadata)
                    }
                }
            }

            // Last resort: attempt to flatten all outputs and try interpret
            val allFloats = ArrayList<Float>()
            for (i in 0 until result.size()) {
                try {
                    val r = result[i]
                    val arr = tensorToFloatArray(r)
                    if (arr.isNotEmpty()) allFloats.addAll(arr.toList())
                } catch (_: Exception) {}
            }
            val flatAll = allFloats.toFloatArray()
            if (flatAll.size >= 5 && flatAll.size % 5 == 0) {
                val rows = flatAll.size / 5
                val boxes = FloatArray(rows * 4)
                val scores = FloatArray(rows)
                for (r in 0 until rows) {
                    val base = r * 5
                    boxes[r * 4 + 0] = flatAll[base]
                    boxes[r * 4 + 1] = flatAll[base + 1]
                    boxes[r * 4 + 2] = flatAll[base + 2]
                    boxes[r * 4 + 3] = flatAll[base + 3]
                    scores[r] = flatAll[base + 4]
                }
                if (prefDebugMode) dumpOnnxOutputs(boxes, scores, File("onnx_dump_${System.currentTimeMillis()}.json"))
                return parseDetectionsFromFloatArrays(boxes, scores, metadata)
            }

            emptyList()
        } catch (ex: Exception) {
            Logger.e(TAG, "parseVariousOnnxOutputs failed", ex)
            emptyList()
        }
    }

    private fun tensorToFloatArray(obj: Any?): FloatArray {
        if (obj == null) return FloatArray(0)
        return try {
            if (obj is OnnxTensor) {
                val fb = try { obj.floatBuffer } catch (_: Throwable) { null }
                if (fb != null) {
                    val arr = FloatArray(fb.remaining())
                    fb.get(arr)
                    fb.rewind()
                    arr
                } else {
                    flattenToFloatArray(obj.value)
                }
            } else {
                flattenToFloatArray(obj)
            }
        } catch (ex: Exception) {
            try { flattenToFloatArray((obj as? OnnxTensor)?.value ?: obj) } catch (_: Exception) { FloatArray(0) }
        }
    }

    private fun createAuxiliaryTensor(
        env: OrtEnvironment,
        sess: OrtSession,
        name: String,
        metadata: LetterboxMetadata
    ): OnnxTensor? {
        return try {
            val info = sess.inputInfo[name]?.info as? TensorInfo
            val shapeList = info?.shape?.map { dim -> if (dim <= 0) 1L else dim } ?: emptyList()
            var targetShape = if (shapeList.isEmpty()) null else shapeList.toLongArray()

            val lowerName = name.lowercase(Locale.ROOT)
            val isScaleFactor = lowerName.contains("scale") && lowerName.contains("factor")

            val baseValues: FloatArray = if (isScaleFactor) {
                val scaleVals = floatArrayOf(metadata.scaleY, metadata.scaleX)
                if (targetShape == null || targetShape.isEmpty()) {
                    targetShape = longArrayOf(1, scaleVals.size.toLong())
                }
                scaleVals
            } else {
                val count = if (targetShape == null || targetShape.isEmpty()) 1L else targetShape!!.fold(1L) { acc, v -> acc * v }
                if (targetShape == null || targetShape!!.isEmpty()) {
                    targetShape = longArrayOf(count)
                }
                FloatArray(count.toInt()) { 1.0f }
            }

            if (targetShape == null || targetShape.isEmpty()) {
                targetShape = longArrayOf(baseValues.size.toLong())
            }

            val elementCount = targetShape!!.fold(1L) { acc, v -> acc * v }.toInt().coerceAtLeast(1)
            val values = if (baseValues.size == elementCount) {
                baseValues
            } else {
                FloatArray(elementCount) { idx -> baseValues[idx % baseValues.size] }
            }

            val buffer = FloatBuffer.wrap(values)
            OnnxTensor.createTensor(env, buffer, targetShape!!)
        } catch (ex: Exception) {
            Logger.e(TAG, "Failed to create auxiliary tensor for '$name'", ex)
            null
        }
    }

        // After run, dump raw ONNX outputs (boxes/scores) to JSON when debug mode is enabled.
        private fun dumpOnnxOutputs(boxes: FloatArray, scores: FloatArray, outFile: File) {
            try {
                if (!prefDebugMode) return
                // prefer cache/photos so it's easy to associate with captured photos
                val photosDir = File(context.cacheDir, "photos").apply { mkdirs() }
                val target = File(photosDir, outFile.name)
                val root = JSONObject()
                root.put("boxes_shape", boxes.size)
                root.put("scores_shape", scores.size)
                val boxesArr = JSONArray()
                for (v in boxes) boxesArr.put(v.toDouble())
                val scoresArr = JSONArray()
                for (v in scores) scoresArr.put(v.toDouble())
                root.put("boxes", boxesArr)
                root.put("scores", scoresArr)
                target.writeText(root.toString())

                // Log a short summary (shapes + first up to 10 values) to make quick inspection easier
                fun head(arr: FloatArray): String {
                    val n = minOf(arr.size, 10)
                    return arr.take(n).joinToString(prefix = "[", postfix = if (arr.size > n) ",... ]" else "]")
                }
                Logger.i(TAG, "Dumped ONNX outputs to ${target.absolutePath} boxes_shape=${boxes.size} scores_shape=${scores.size} boxes_head=${head(boxes)} scores_head=${head(scores)}")
            } catch (ex: Exception) {
                Logger.e(TAG, "Failed to dump ONNX outputs", ex)
            }
        }

    private fun parseLabelFile(json: String): List<String> {
        try {
            val root = JSONObject(json)
            val items = root.optJSONArray("labels") ?: return emptyList()
            return buildList {
                for (i in 0 until items.length()) {
                    add(items.getString(i))
                }
            }
        } catch (ex: JSONException) {
            try {
                val array = JSONArray(json)
                return buildList {
                    for (i in 0 until array.length()) {
                        add(array.getString(i))
                    }
                }
            } catch (inner: JSONException) {
                Log.w(TAG, "Unable to parse label json", inner)
                return emptyList()
            }
        }
    }

    private fun ensureYuvPixels(requiredSize: Int): IntArray {
        if (yuvPixels.size < requiredSize) {
            yuvPixels = IntArray(requiredSize)
        }
        return yuvPixels
    }

    private fun Long.toDimension(fallback: Int): Int {
        return if (this > 0 && this <= Int.MAX_VALUE) this.toInt() else fallback
    }

    companion object {
        private const val TAG = "InferenceEngine"
        private const val MODEL_ASSET_PATH = "models/model.onnx"
        private const val MODEL_FILE_NAME = "model.onnx"
        private const val MODEL_CACHE_DIR = "models"
        private const val LABELS_ASSET_PATH = "models/labels.json"

    private const val DEFAULT_INPUT_SIZE = 640
    private const val DEFAULT_INPUT_CHANNELS = 3
        private const val CONFIDENCE_THRESHOLD = 0.25f
        private const val NMS_THRESHOLD = 0.45f
    private val LETTERBOX_COLOR = Color.BLACK

        private fun yuvToArgb(y: Int, u: Int, v: Int): Int {
            val yClamped = (y - 16).coerceAtLeast(0)
            val uShifted = u - 128
            val vShifted = v - 128

            var r = (1.164f * yClamped + 1.596f * vShifted).toInt()
            var g = (1.164f * yClamped - 0.392f * uShifted - 0.813f * vShifted).toInt()
            var b = (1.164f * yClamped + 2.017f * uShifted).toInt()

            r = r.coerceIn(0, 255)
            g = g.coerceIn(0, 255)
            b = b.coerceIn(0, 255)

            return (0xFF shl 24) or (r shl 16) or (g shl 8) or b
        }
    }
}

data class InferenceResult(
    val detections: List<Detection>,
    val metadata: LetterboxMetadata
)

data class LetterboxMetadata(
    val scale: Float,
    val padX: Float,
    val padY: Float,
    val sourceWidth: Int,  // 旋转后的宽度(推理输入使用)
    val sourceHeight: Int,  // 旋转后的高度(推理输入使用)
    val scaleX: Float,
    val scaleY: Float,
    val rotationDegrees: Int,  // 图像旋转角度
    val originalWidth: Int,  // 原始相机图像宽度(未旋转)
    val originalHeight: Int  // 原始相机图像高度(未旋转)
)

private data class RawDetection(
    val classIndex: Int,
    val score: Float,
    val box: BoundingBox
)
