package com.bohuyeshan.buckwheat

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.Preview
import androidx.camera.core.UseCaseGroup
import androidx.camera.core.ViewPort
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.bohuyeshan.buckwheat.camera.CameraAnalyzer
import com.bohuyeshan.buckwheat.databinding.ActivityMainBinding
import com.bohuyeshan.buckwheat.inference.InferenceEngine
import com.bohuyeshan.buckwheat.inference.InferenceResult
import com.bohuyeshan.buckwheat.util.Logger
import com.bohuyeshan.buckwheat.util.PerformanceMonitor
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import android.util.Rational
import android.view.Surface
import android.util.Size

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var cameraExecutor: ExecutorService
    private lateinit var inferenceEngine: InferenceEngine
    private lateinit var performanceMonitor: PerformanceMonitor
    private var imageAnalyzer: ImageAnalysis? = null
    private var lastErrorShownAt: Long = 0L
    private var errorDialogVisible: Boolean = false
    private var realtimeMode: Boolean = true
    private var imageCapture: ImageCapture? = null
    private var performanceMonitorEnabled: Boolean = false

    private val photoManagerLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { activityResult ->
            if (activityResult.resultCode != Activity.RESULT_OK) return@registerForActivityResult
            val data = activityResult.data ?: return@registerForActivityResult
            val photoPath = data.getStringExtra(ImageManagerActivity.EXTRA_SELECTED_PHOTO_PATH) ?: return@registerForActivityResult

            lifecycleScope.launch {
                try {
                    if (realtimeMode) {
                        realtimeMode = false
                        binding.buttonModeToggle.alpha = 0.6f
                        binding.buttonModeToggle.contentDescription = "Single"
                        binding.modeText.text = "Single"
                        binding.buttonShutter.isEnabled = true
                        try {
                            imageAnalyzer?.clearAnalyzer()
                        } catch (_: Exception) { }
                    }
                    binding.statusText.setText(R.string.status_initializing)
                    val bitmap = BitmapFactory.decodeFile(photoPath)
                    if (bitmap == null) {
                        Toast.makeText(this@MainActivity, "Failed to load photo", Toast.LENGTH_SHORT).show()
                        binding.statusText.setText(R.string.status_ready)
                        return@launch
                    }
                    val inferenceResult = inferenceEngine.runInference(bitmap)
                    inferenceResult.onSuccess {
                        binding.statusText.setText(R.string.status_ready)
                        renderDetections(it)
                        Toast.makeText(this@MainActivity, "Inference complete", Toast.LENGTH_SHORT).show()
                    }.onFailure {
                        handleInferenceError(it)
                    }
                } catch (ex: Exception) {
                    handleInferenceError(ex)
                }
            }
        }

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) {
                startCamera()
            } else {
                binding.statusText.setText(R.string.status_permission_required)
                Toast.makeText(this, R.string.status_permission_required, Toast.LENGTH_SHORT).show()
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Logger.init(this)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

    binding.detectionOverlay.configureInputSize(640, 640)
        cameraExecutor = Executors.newSingleThreadExecutor()
        inferenceEngine = InferenceEngine(this)
        performanceMonitor = PerformanceMonitor(this)

        lifecycleScope.launch {
            binding.statusText.setText(R.string.status_initializing)
            inferenceEngine.initialize()
                .onSuccess {
                    binding.statusText.setText(R.string.status_ready)
                    ensureCameraPermission()
                    // initialize mode label
                    binding.modeText.text = if (realtimeMode) "Realtime" else "Single"
                    binding.buttonModeToggle.alpha = if (realtimeMode) 1f else 0.6f
                    binding.buttonShutter.isEnabled = !realtimeMode
                    refreshProviderSummary()

                    // Start performance monitoring loop
                    startPerformanceMonitoring()
                }
                .onFailure { error ->
                    binding.statusText.setText(R.string.status_inference_error)
                    Toast.makeText(this@MainActivity, error.localizedMessage.orEmpty(), Toast.LENGTH_LONG).show()
                }
        }

        // Long-press status text to open settings/diagnostics
        binding.statusText.setOnLongClickListener {
            SettingsActivity.open(this)
            true
        }

        // Toggle performance monitor on click
        binding.statusText.setOnClickListener {
            performanceMonitorEnabled = !performanceMonitorEnabled
            binding.performancePanel.visibility = if (performanceMonitorEnabled) {
                android.view.View.VISIBLE
            } else {
                android.view.View.GONE
            }
        }

        binding.buttonSettings.setOnClickListener {
            SettingsActivity.open(this)
        }

        // add press-scale animation for tactile feedback
        binding.buttonSettings.enablePressScale(this)
        binding.buttonPhotoManager.enablePressScale(this)
        binding.buttonModeToggle.enablePressScale(this)
        binding.buttonShutter.enablePressScale(this)
        binding.checkboxEmoji.enablePressScale(this)

        // Long-press settings: copy/share latest ONNX input dump for easier retrieval when ADB is limited
        binding.buttonSettings.setOnLongClickListener {
            lifecycleScope.launch {
                try {
                    val json = inferenceEngine.getLatestInputDump()
                    if (json == null) {
                        runOnUiThread { Toast.makeText(this@MainActivity, "No ONNX input dump found", Toast.LENGTH_SHORT).show() }
                        return@launch
                    }
                    // copy to clipboard
                    val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                    val clip = ClipData.newPlainText("onnx_input", json)
                    clipboard.setPrimaryClip(clip)

                    // share via chooser
                    val send = Intent().apply {
                        action = Intent.ACTION_SEND
                        putExtra(Intent.EXTRA_TEXT, json)
                        type = "application/json"
                    }
                    startActivity(Intent.createChooser(send, "Share ONNX input JSON"))
                } catch (ex: Exception) {
                    runOnUiThread { Toast.makeText(this@MainActivity, "Failed to export ONNX input: ${ex.localizedMessage}", Toast.LENGTH_LONG).show() }
                }
            }
            true
        }

        binding.buttonPhotoManager.setOnClickListener {
            val intent = Intent(this, ImageManagerActivity::class.java)
            photoManagerLauncher.launch(intent)
        }

        // Mode toggle: realtime / single-frame
        binding.buttonModeToggle.setOnClickListener {
            realtimeMode = !realtimeMode
            // update visual state: tint/alpha and content description
            binding.buttonModeToggle.alpha = if (realtimeMode) 1f else 0.6f
            binding.buttonModeToggle.contentDescription = if (realtimeMode) "Realtime" else "Single"
            // update textual mode indicator
            binding.modeText.text = if (realtimeMode) "Realtime" else "Single"
            // enable/disable shutter depending on mode
            binding.buttonShutter.isEnabled = !realtimeMode
            if (realtimeMode) {
                // 重新启动实时检测:重新绑定相机用例
                Logger.i("MainActivity", "Switching to Realtime mode, restarting camera...")
                binding.statusText.setText(R.string.status_initializing)
                startCamera()
            } else {
                // 切换到单张模式:停止分析器避免同时运行
                Logger.i("MainActivity", "Switching to Single mode, clearing analyzer...")
                imageAnalyzer?.clearAnalyzer()
                binding.detectionOverlay.updateDetections(emptyList())
                binding.statusText.setText(R.string.status_ready)
            }
        }

        // Shutter button: capture single frame and run inference (high-res ImageCapture)
        binding.buttonShutter.setOnClickListener {
            if (realtimeMode) return@setOnClickListener
            val cap = imageCapture
            if (cap == null) {
                Toast.makeText(this, "Capture not ready", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            binding.statusText.setText(R.string.status_initializing)

            // Save captured JPEG to cache directory, then decode and run inference on the saved file.
            try {
                val photosDir = java.io.File(cacheDir, "photos").apply { mkdirs() }
                val outFile = java.io.File.createTempFile("capture_", ".jpg", photosDir)
                val outputOptions = androidx.camera.core.ImageCapture.OutputFileOptions.Builder(outFile).build()

                cap.takePicture(outputOptions, ContextCompat.getMainExecutor(this), object : androidx.camera.core.ImageCapture.OnImageSavedCallback {
                    override fun onImageSaved(outputFileResults: androidx.camera.core.ImageCapture.OutputFileResults) {
                        // Saved to outFile
                        Logger.i("MainActivity", "Photo saved: ${outFile.absolutePath}")
                        lifecycleScope.launch {
                            try {
                                val bmp = android.graphics.BitmapFactory.decodeFile(outFile.absolutePath)
                                val result = inferenceEngine.runInference(bmp)
                                result.onSuccess { inf ->
                                    binding.statusText.setText(R.string.status_ready)
                                    renderDetections(inf)
                                    
                                    // 保存带检测框的图片到相册
                                    if (inf.detections.isNotEmpty()) {
                                        saveBitmapToGallery(bmp, inf.detections)
                                    }
                                }.onFailure { err ->
                                    handleInferenceError(err)
                                }
                            } catch (ex: Exception) {
                                handleInferenceError(ex)
                            }
                        }
                    }

                    override fun onError(exception: androidx.camera.core.ImageCaptureException) {
                        handleInferenceError(exception)
                    }
                })
            } catch (ex: Exception) {
                handleInferenceError(ex)
            }
        }

        // Emoji ImageButton toggles overlay emoji rendering
        var emojiEnabled = false
        binding.checkboxEmoji.setOnClickListener {
            emojiEnabled = !emojiEnabled
            // simple visual feedback by tint
            binding.checkboxEmoji.alpha = if (emojiEnabled) 1f else 0.5f
            binding.detectionOverlay.setEmojiRenderingEnabled(emojiEnabled)
        }
    }

    override fun onResume() {
        super.onResume()
        if (this::inferenceEngine.isInitialized) {
            refreshProviderSummary()
        }
    }

    private fun ensureCameraPermission() {
        when {
            ActivityCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED -> {
                startCamera()
            }
            ActivityCompat.shouldShowRequestPermissionRationale(this, Manifest.permission.CAMERA) -> {
                binding.statusText.setText(R.string.status_permission_required)
                permissionLauncher.launch(Manifest.permission.CAMERA)
            }
            else -> {
                permissionLauncher.launch(Manifest.permission.CAMERA)
            }
        }
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            try {
                val cameraProvider = cameraProviderFuture.get()
                bindCameraUseCases(cameraProvider)
            } catch (ex: Exception) {
                binding.statusText.setText(R.string.status_camera_error)
                Toast.makeText(this, ex.localizedMessage.orEmpty(), Toast.LENGTH_LONG).show()
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun refreshProviderSummary() {
        if (!this::inferenceEngine.isInitialized) return
        val report = inferenceEngine.getProviderReport()
        val planned = if (report.plannedProviders.isEmpty()) "CPU" else report.plannedProviders.joinToString(" → ")
        val active = report.enabledSummary()
        val description = getString(R.string.provider_dialog_device, report.deviceLabel) + "\n" +
            getString(R.string.provider_dialog_plan, planned)

        binding.providerChip.text = getString(R.string.provider_chip_template, active)
        binding.providerChip.tooltipText = description
        binding.providerChip.setOnClickListener {
            showProviderReportDialog(inferenceEngine.getProviderReport())
        }
        binding.providerChip.setOnLongClickListener {
            showProviderReportDialog(inferenceEngine.getProviderReport())
            true
        }
    }

    private fun showProviderReportDialog(report: InferenceEngine.ProviderReport) {
        val planned = if (report.plannedProviders.isEmpty()) "CPU" else report.plannedProviders.joinToString(" → ")
        val message = buildString {
            appendLine(getString(R.string.provider_dialog_device, report.deviceLabel))
            appendLine(getString(R.string.provider_dialog_preference, report.preferenceLabel))
            appendLine(getString(R.string.provider_dialog_plan, planned))
            append(getString(R.string.provider_dialog_active, report.enabledSummary()))
        }

        AlertDialog.Builder(this)
            .setTitle(R.string.provider_dialog_title)
            .setMessage(message)
            .setPositiveButton(android.R.string.ok, null)
            .show()
    }

    private fun bindCameraUseCases(cameraProvider: ProcessCameraProvider) {
        cameraProvider.unbindAll()

        val displayRotation = binding.previewView.display?.rotation ?: Surface.ROTATION_0
        val targetResolution = Size(1280, 720)
        val aspectRatio = Rational(targetResolution.width, targetResolution.height)

        val preview = Preview.Builder()
            .setTargetRotation(displayRotation)
            .setTargetResolution(targetResolution)
            .build()
            .also { it.setSurfaceProvider(binding.previewView.surfaceProvider) }

        imageCapture = ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .setTargetRotation(displayRotation)
            .setTargetResolution(targetResolution)
            .build()

        val analyzer = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
            .setTargetRotation(displayRotation)
            .setTargetResolution(targetResolution)
            .build()

        val cameraAnalyzer = CameraAnalyzer(
            scope = lifecycleScope,
            inferenceEngine = inferenceEngine,
            onDetections = ::renderDetections,
            onError = ::handleInferenceError
        )
        analyzer.setAnalyzer(cameraExecutor, cameraAnalyzer)
        imageAnalyzer = analyzer

        val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA
        val useCaseGroupBuilder = UseCaseGroup.Builder()
            .addUseCase(preview)
            .addUseCase(analyzer)
        imageCapture?.let { useCaseGroupBuilder.addUseCase(it) }

        val viewPort = ViewPort.Builder(aspectRatio, displayRotation).build()
        val useCaseGroup = useCaseGroupBuilder.setViewPort(viewPort).build()

        cameraProvider.bindToLifecycle(this, cameraSelector, useCaseGroup)
    }

    private fun renderDetections(result: InferenceResult) {
        // Record frame for FPS calculation
        performanceMonitor.recordFrame()
        
        // 传入原始相机尺寸和旋转角度,让DetectionOverlay处理坐标转换
        binding.detectionOverlay.configureInputSize(
            result.metadata.originalWidth, 
            result.metadata.originalHeight,
            result.metadata.rotationDegrees
        )
        binding.detectionOverlay.updateDetections(result.detections)
    }

    // 保存带检测框的图片到相册
    private fun saveBitmapToGallery(bitmap: android.graphics.Bitmap, detections: List<com.bohuyeshan.buckwheat.model.Detection>) {
        try {
            // 创建带检测框的新图片
            val annotatedBitmap = android.graphics.Bitmap.createBitmap(
                bitmap.width,
                bitmap.height,
                android.graphics.Bitmap.Config.ARGB_8888
            )
            val canvas = android.graphics.Canvas(annotatedBitmap)
            canvas.drawBitmap(bitmap, 0f, 0f, null)

            // 定义颜色
            val classColors = listOf(
                android.graphics.Color.rgb(0, 255, 0),     // 绿色 - seeda
                android.graphics.Color.rgb(255, 165, 0),   // 橙色 - seedb
                android.graphics.Color.rgb(255, 0, 255),   // 品红 - seedc
                android.graphics.Color.rgb(0, 255, 255)    // 青色 - seedd
            )

            val boxPaint = android.graphics.Paint().apply {
                strokeWidth = 8f
                style = android.graphics.Paint.Style.STROKE
                isAntiAlias = true
            }

            val textBackgroundPaint = android.graphics.Paint().apply {
                color = android.graphics.Color.argb(200, 0, 0, 0)
                style = android.graphics.Paint.Style.FILL
                isAntiAlias = true
            }

            val textPaint = android.graphics.Paint().apply {
                color = android.graphics.Color.WHITE
                textSize = 60f
                isAntiAlias = true
                isFakeBoldText = true
            }

            // 绘制每个检测框
            detections.forEach { detection ->
                // 根据标签选择颜色
                boxPaint.color = when {
                    detection.label.contains("seeda", ignoreCase = true) -> classColors[0]
                    detection.label.contains("seedb", ignoreCase = true) -> classColors[1]
                    detection.label.contains("seedc", ignoreCase = true) -> classColors[2]
                    detection.label.contains("seedd", ignoreCase = true) -> classColors[3]
                    else -> {
                        val classIndex = detection.label.substringAfter("Class ", "").toIntOrNull() ?: 0
                        classColors[classIndex % classColors.size]
                    }
                }

                val rect = android.graphics.RectF(
                    detection.boundingBox.left,
                    detection.boundingBox.top,
                    detection.boundingBox.right,
                    detection.boundingBox.bottom
                )
                canvas.drawRect(rect, boxPaint)

                // 绘制标签
                val labelText = "${detection.label} ${(detection.score * 100).toInt()}%"
                val textWidth = textPaint.measureText(labelText)
                val textHeight = textPaint.textSize

                canvas.drawRect(
                    rect.left,
                    rect.top - textHeight - 16,
                    rect.left + textWidth + 32,
                    rect.top,
                    textBackgroundPaint
                )
                canvas.drawText(labelText, rect.left + 16, rect.top - 24, textPaint)
            }

            // 保存到相册
            val timestamp = java.text.SimpleDateFormat("yyyyMMdd_HHmmss", java.util.Locale.getDefault()).format(java.util.Date())
            val displayName = "buckwheat_$timestamp.jpg"

            val values = android.content.ContentValues().apply {
                put(android.provider.MediaStore.Images.Media.DISPLAY_NAME, displayName)
                put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
                put(android.provider.MediaStore.Images.Media.RELATIVE_PATH, "Pictures/BuckwheatDetections")
            }

            val resolver = contentResolver
            val uri = resolver.insert(android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)

            uri?.let {
                resolver.openOutputStream(it).use { outputStream ->
                    if (outputStream != null) {
                        annotatedBitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG, 95, outputStream)
                    }
                }
                runOnUiThread {
                    Toast.makeText(this, "已保存到相册: BuckwheatDetections/$displayName", Toast.LENGTH_LONG).show()
                }
                Logger.i("MainActivity", "Saved annotated photo to gallery: $displayName")
            } ?: run {
                runOnUiThread {
                    Toast.makeText(this, "保存失败", Toast.LENGTH_SHORT).show()
                }
            }

            annotatedBitmap.recycle()
        } catch (ex: Exception) {
            Logger.e("MainActivity", "Failed to save annotated photo", ex)
            runOnUiThread {
                Toast.makeText(this, "保存失败: ${ex.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun handleInferenceError(throwable: Throwable) {
        binding.statusText.setText(R.string.status_inference_error)
        Logger.e("MainActivity", "Inference error", throwable)

        val now = System.currentTimeMillis()
        // Debounce: only show dialog if >8s since last shown, and ensure only one dialog visible
        if (errorDialogVisible || now - lastErrorShownAt < 8000L) {
            // show a brief toast instead to avoid spam
            runOnUiThread {
                Toast.makeText(this, throwable.localizedMessage.orEmpty(), Toast.LENGTH_SHORT).show()
            }
            return
        }

        lastErrorShownAt = now
        errorDialogVisible = true

        // Stop analyzer to prevent continuous exceptions and UI freeze
        try {
            imageAnalyzer?.clearAnalyzer()
        } catch (_: Exception) {
        }

        val logPath = Logger.getLogFilePath() ?: "(unknown)"
        runOnUiThread {
            val dlg = AlertDialog.Builder(this)
                .setTitle("Inference error")
                .setMessage("${throwable.localizedMessage}\n\nLog file: $logPath")
                .setPositiveButton("Share Logs") { _, _ ->
                    val content = Logger.readAll() ?: ""
                    val send = Intent().apply {
                        action = Intent.ACTION_SEND
                        putExtra(Intent.EXTRA_TEXT, content)
                        type = "text/plain"
                    }
                    startActivity(Intent.createChooser(send, "Share logs"))
                }
                .setNeutralButton("Restart Inference") { _, _ ->
                    // attempt to re-init engine and restart camera
                    lifecycleScope.launch {
                        binding.statusText.setText(R.string.status_initializing)
                        inferenceEngine.initialize()
                            .onSuccess {
                                binding.statusText.setText(R.string.status_ready)
                                // restart camera binder
                                startCamera()
                            }
                            .onFailure { err ->
                                binding.statusText.setText(R.string.status_inference_error)
                                Logger.e("MainActivity", "Restart failed", err)
                            }
                    }
                }
                .setNegativeButton("Dismiss") { _, _ -> }
                .create()

            dlg.setOnDismissListener {
                errorDialogVisible = false
            }
            dlg.show()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        imageAnalyzer?.clearAnalyzer()
        cameraExecutor.shutdown()
        inferenceEngine.close()
    }

    /**
     * 启动性能监控后台循环，每500ms更新一次UI
     */
    private fun startPerformanceMonitoring() {
        lifecycleScope.launch {
            while (true) {
                delay(500)
                if (!performanceMonitorEnabled) {
                    delay(500) // 如果关闭了监控，降低检查频率
                    continue
                }
                
                try {
                    val snapshot = performanceMonitor.getSnapshot()
                    runOnUiThread {
                        binding.perfFps.text = "FPS: ${snapshot.fps.toInt()}"
                        binding.perfCpu.text = "CPU: ${snapshot.cpuUsage.toInt()}%"
                        binding.perfMemory.text = "MEM: ${snapshot.memoryMB.toInt()} MB"
                        binding.perfGpu.text = "GPU: ${snapshot.gpuInfo}"
                        binding.perfNpu.text = "NPU: ${snapshot.npuInfo}"
                    }
                } catch (e: Exception) {
                    Logger.e("MainActivity", "Performance monitoring error", e)
                }
            }
        }
    }
}
