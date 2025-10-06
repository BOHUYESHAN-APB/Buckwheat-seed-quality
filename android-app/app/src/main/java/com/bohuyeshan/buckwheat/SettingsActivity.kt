package com.bohuyeshan.buckwheat

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.content.ContentValues
import android.provider.MediaStore
import android.os.Build
import android.os.Bundle
import android.widget.Button
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.button.MaterialButtonToggleGroup
import com.google.android.material.chip.Chip
import com.google.android.material.switchmaterial.SwitchMaterial
import com.google.android.material.textfield.TextInputEditText
import java.util.Locale
import android.widget.TextView
import android.widget.Toast
import androidx.annotation.RequiresApi
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import com.bohuyeshan.buckwheat.util.Logger
import java.io.File

class SettingsActivity : AppCompatActivity() {

    private lateinit var copyBtn: Button
    private lateinit var clearBtn: Button
    private lateinit var verboseSwitch: SwitchMaterial
    private lateinit var channelSwapSwitch: SwitchMaterial
    private lateinit var debugModeSwitch: SwitchMaterial
    private var etMean: TextInputEditText? = null
    private var etStd: TextInputEditText? = null
    private var etScale: TextInputEditText? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        val toolbar: MaterialToolbar = findViewById(R.id.settings_toolbar)
        toolbar.setNavigationOnClickListener { finish() }

        val providerToggleGroup: MaterialButtonToggleGroup = findViewById(R.id.provider_toggle_group)
        val deviceChip: Chip = findViewById(R.id.device_chip)

        copyBtn = findViewById(R.id.copy_log_path)
        clearBtn = findViewById(R.id.clear_logs)
        val viewLogsBtn: Button = findViewById(R.id.btn_view_logs)
        val selfTestBtn: Button = findViewById(R.id.btn_self_test)
        verboseSwitch = findViewById(R.id.switch_verbose)
        channelSwapSwitch = findViewById(R.id.switch_channel_swap)
        debugModeSwitch = findViewById(R.id.switch_debug_mode)
        val shareBtn: Button = findViewById(R.id.share_logs)
        val shareInputBtn: Button = findViewById(R.id.btn_share_input_json)
        val clearCacheBtn: Button = findViewById(R.id.btn_clear_cache)

        Logger.init(this)

        deviceChip.text = getString(R.string.settings_device_unknown, detectDeviceLabel())

        val prefs = getSharedPreferences("buckwheat_prefs", Context.MODE_PRIVATE)
        val storedProvider = prefs.getString("pref_execution_provider", "AUTO")?.uppercase(Locale.US) ?: "AUTO"
        val providerIdMap = mapOf(
            R.id.provider_auto to "AUTO",
            R.id.provider_nnapi to "NNAPI",
            R.id.provider_qnn to "QNN",
            R.id.provider_vulkan to "VULKAN",
            R.id.provider_xnnpack to "XNNPACK",
            R.id.provider_cpu to "CPU"
        )
        val initialSelection = providerIdMap.entries.firstOrNull { it.value == storedProvider }?.key ?: R.id.provider_auto
        providerToggleGroup.check(initialSelection)
        providerToggleGroup.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (isChecked) {
                val value = providerIdMap[checkedId] ?: "AUTO"
                prefs.edit().putString("pref_execution_provider", value).apply()
                Toast.makeText(this, getString(R.string.provider_saved_toast, value), Toast.LENGTH_SHORT).show()
            }
        }

        copyBtn.setOnClickListener {
            val path = Logger.getLogFilePath() ?: ""
            val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.setPrimaryClip(ClipData.newPlainText("log-path", path))
            Toast.makeText(this, "Log path copied", Toast.LENGTH_SHORT).show()
        }

        clearCacheBtn.setOnClickListener {
            lifecycleScope.launch(Dispatchers.IO) {
                try {
                    val photosDir = File(cacheDir, "photos")
                    var deletedCount = 0
                    var freedBytes = 0L
                    
                    if (photosDir.exists() && photosDir.isDirectory) {
                        photosDir.listFiles()?.forEach { file ->
                            if (file.isFile && (file.name.startsWith("onnx_") || file.name.startsWith("capture_"))) {
                                freedBytes += file.length()
                                if (file.delete()) {
                                    deletedCount++
                                }
                            }
                        }
                    }
                    
                    val freedMB = freedBytes / (1024.0 * 1024.0)
                    withContext(Dispatchers.Main) {
                        Toast.makeText(
                            this@SettingsActivity,
                            "Cleared $deletedCount files (${String.format("%.2f", freedMB)} MB)",
                            Toast.LENGTH_LONG
                        ).show()
                    }
                    Logger.i("SettingsActivity", "Cache cleared: $deletedCount files, $freedMB MB")
                } catch (ex: Exception) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(this@SettingsActivity, "Failed to clear cache: ${ex.message}", Toast.LENGTH_SHORT).show()
                    }
                    Logger.e("SettingsActivity", "Cache clear failed", ex)
                }
            }
        }

        viewLogsBtn.setOnClickListener {
            LogActivity.open(this)
        }

        selfTestBtn.setOnClickListener {
            // Run a quick local self-test in background
            lifecycleScope.launch {
                try {
                    val engine = com.bohuyeshan.buckwheat.inference.InferenceEngine(this@SettingsActivity)
                    val initRes = engine.initialize()
                    if (initRes.isFailure) {
                        Toast.makeText(this@SettingsActivity, "Model init failed: ${initRes.exceptionOrNull()?.message}", Toast.LENGTH_LONG).show()
                        return@launch
                    }
                    val res = engine.runSelfTest()
                    if (res.isSuccess) {
                        val ok = res.getOrNull() ?: false
                        Toast.makeText(this@SettingsActivity, if (ok) "Self-test: detections found" else "Self-test: no detections", Toast.LENGTH_LONG).show()
                        Logger.i("SettingsActivity", "Self-test result: $ok")
                    } else {
                        Toast.makeText(this@SettingsActivity, "Self-test failed: ${res.exceptionOrNull()?.message}", Toast.LENGTH_LONG).show()
                        Logger.e("SettingsActivity", "Self-test error", res.exceptionOrNull())
                    }
                } catch (ex: Exception) {
                    Toast.makeText(this@SettingsActivity, "Self-test exception: ${ex.message}", Toast.LENGTH_LONG).show()
                    Logger.e("SettingsActivity", "Self-test exception", ex)
                }
            }
        }

        shareBtn.setOnClickListener { shareLogsViaFileProvider() }

        shareInputBtn.setOnClickListener {
            lifecycleScope.launch {
                val latestFile = withContext(Dispatchers.IO) {
                    try {
                        val photosDir = File(cacheDir, "photos")
                        if (!photosDir.exists() || !photosDir.isDirectory) {
                            null
                        } else {
                            val files = photosDir.listFiles { f ->
                                f.isFile && f.name.startsWith("onnx_input_") && f.name.endsWith(".json")
                            }
                            files?.maxByOrNull { it.lastModified() }
                        }
                    } catch (_: Exception) {
                        null
                    }
                }

                if (latestFile == null) {
                    Toast.makeText(this@SettingsActivity, "No input JSON found yet. Run detection once and try again.", Toast.LENGTH_SHORT).show()
                    return@launch
                }

                val shareUri = try {
                    FileProvider.getUriForFile(
                        this@SettingsActivity,
                        "${packageName}.fileprovider",
                        latestFile
                    )
                } catch (ex: Exception) {
                    Logger.e("SettingsActivity", "Failed to create URI for input JSON", ex)
                    null
                }

                if (shareUri == null) {
                    Toast.makeText(this@SettingsActivity, "Couldn't prepare input JSON for sharing", Toast.LENGTH_SHORT).show()
                    return@launch
                }

                val shareIntent = Intent(Intent.ACTION_SEND).apply {
                    type = "application/json"
                    putExtra(Intent.EXTRA_STREAM, shareUri)
                    putExtra(Intent.EXTRA_SUBJECT, "Latest ONNX input JSON")
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    clipData = ClipData.newUri(contentResolver, "onnx_input", shareUri)
                }

                try {
                    val targets = packageManager.queryIntentActivities(shareIntent, 0)
                    targets?.forEach { resolveInfo ->
                        grantUriPermission(resolveInfo.activityInfo.packageName, shareUri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }
                    Logger.i("SettingsActivity", "Launching input share chooser with ${targets?.size ?: 0} targets")
                    startActivity(Intent.createChooser(shareIntent, "Share latest input JSON"))
                } catch (ex: Exception) {
                    Logger.e("SettingsActivity", "Failed to launch input share chooser", ex)
                    Toast.makeText(this@SettingsActivity, "No app available to share input JSON", Toast.LENGTH_SHORT).show()
                }
            }
        }

        clearBtn.setOnClickListener {
            Logger.clear()
            Toast.makeText(this, "Logs cleared", Toast.LENGTH_SHORT).show()
        }

        verboseSwitch.isChecked = prefs.getBoolean("pref_verbose_logging", false)
        verboseSwitch.setOnCheckedChangeListener { _, isChecked ->
            prefs.edit().putBoolean("pref_verbose_logging", isChecked).apply()
            Toast.makeText(this, "Verbose logging: $isChecked", Toast.LENGTH_SHORT).show()
        }

        channelSwapSwitch.isChecked = prefs.getBoolean("pref_channel_swap", false)
        channelSwapSwitch.setOnCheckedChangeListener { _, isChecked ->
            prefs.edit().putBoolean("pref_channel_swap", isChecked).apply()
            Toast.makeText(this, "Channel swap: $isChecked", Toast.LENGTH_SHORT).show()
        }

        debugModeSwitch.isChecked = prefs.getBoolean("pref_debug_mode", false)
        debugModeSwitch.setOnCheckedChangeListener { _, isChecked ->
            prefs.edit().putBoolean("pref_debug_mode", isChecked).apply()
            Toast.makeText(this, "Debug mode: $isChecked", Toast.LENGTH_SHORT).show()
        }

        // Confidence threshold seekbar (5% - 95%, stored as 0.05 - 0.95)
        val seekbarConfidence = findViewById<android.widget.SeekBar>(R.id.seekbar_confidence)
        val tvConfidenceValue = findViewById<TextView>(R.id.tv_confidence_value)
        
        val currentConfidence = prefs.getFloat("pref_confidence_threshold", 0.25f)
        val currentProgress = ((currentConfidence - 0.05f) / 0.90f * 90f).toInt().coerceIn(0, 90)
        seekbarConfidence.progress = currentProgress
        tvConfidenceValue.text = "${(currentConfidence * 100).toInt()}%"
        
        seekbarConfidence.setOnSeekBarChangeListener(object : android.widget.SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: android.widget.SeekBar?, progress: Int, fromUser: Boolean) {
                val confidence = 0.05f + (progress / 90f) * 0.90f
                tvConfidenceValue.text = "${(confidence * 100).toInt()}%"
            }
            
            override fun onStartTrackingTouch(seekBar: android.widget.SeekBar?) {}
            
            override fun onStopTrackingTouch(seekBar: android.widget.SeekBar?) {
                val progress = seekBar?.progress ?: 20
                val confidence = 0.05f + (progress / 90f) * 0.90f
                prefs.edit().putFloat("pref_confidence_threshold", confidence).apply()
                Toast.makeText(this@SettingsActivity, "Confidence threshold: ${(confidence * 100).toInt()}%", Toast.LENGTH_SHORT).show()
            }
        })

    // preprocessing fields
    etMean = findViewById(R.id.et_mean)
    etStd = findViewById(R.id.et_std)
    etScale = findViewById(R.id.et_scale)

        // load persisted preprocessing values
        val defaultMean = "0.0,0.0,0.0"
        val defaultStd = "1.0,1.0,1.0"
        val defaultScale = "1.0"

        fun migrateOldDefaults(key: String, oldValue: String, newValue: String) {
            val current = prefs.getString(key, null)
            if (current == null) {
                prefs.edit().putString(key, newValue).apply()
            } else if (current.trim().equals(oldValue, ignoreCase = true)) {
                prefs.edit().putString(key, newValue).apply()
            }
        }

        migrateOldDefaults("pref_mean", "0.5,0.5,0.5", defaultMean)
        migrateOldDefaults("pref_std", "0.5,0.5,0.5", defaultStd)
        migrateOldDefaults("pref_scale", "1.0", defaultScale)

        etMean?.setText(prefs.getString("pref_mean", defaultMean))
        etStd?.setText(prefs.getString("pref_std", defaultStd))
        etScale?.setText(prefs.getString("pref_scale", defaultScale))

        // save when changed (simple: save on focus lost)
        val savePreproc: (String, String) -> Unit = { key, value -> prefs.edit().putString(key, value).apply() }
        etMean?.setOnFocusChangeListener { _, has -> if (!has) savePreproc("pref_mean", etMean?.text?.toString() ?: "") }
        etStd?.setOnFocusChangeListener { _, has -> if (!has) savePreproc("pref_std", etStd?.text?.toString() ?: "") }
        etScale?.setOnFocusChangeListener { _, has -> if (!has) savePreproc("pref_scale", etScale?.text?.toString() ?: "") }
    }

    // logs now accessed via LogActivity

    companion object {
        fun open(context: Context) {
            context.startActivity(Intent(context, SettingsActivity::class.java))
        }
    }

    private fun shareLogsViaFileProvider() {
        val file: File? = Logger.getLogFile()
        if (file == null || !file.exists() || file.length() == 0L) {
            Toast.makeText(this, "No logs available", Toast.LENGTH_SHORT).show()
            return
        }

        // Try sharing via FileProvider first
        try {
            val uri: Uri = FileProvider.getUriForFile(
                this,
                "${packageName}.fileprovider",
                file
            )

            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_STREAM, uri)
                putExtra(Intent.EXTRA_SUBJECT, "Buckwheat logs")
                // Some OEM launchers require ClipData to be present to accept stream URIs
                clipData = ClipData.newUri(contentResolver, "Log", uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }

            // Grant temporary permission to all resolved target activities (helps on MIUI)
            val resInfoList = packageManager.queryIntentActivities(intent, 0)
            if (resInfoList.isNullOrEmpty()) {
                Logger.i("SettingsActivity", "No share targets for FileProvider URI, will fallback to Downloads export")
            } else {
                val chooser = Intent.createChooser(intent, "Share logs")
                for (resolveInfo in resInfoList) {
                    val packageName = resolveInfo.activityInfo.packageName
                    grantUriPermission(packageName, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                Logger.i("SettingsActivity", "Launching share chooser with ${resInfoList.size} targets")
                startActivity(chooser)
                return
            }
        } catch (e: Exception) {
            // Fall through to try export to Downloads
            e.printStackTrace()
        }

        // Fallback: export to Downloads (public) and share that URI
        val exportedUri = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            try {
                exportLogToDownloads(file!!)
            } catch (ex: Exception) {
                Logger.e("SettingsActivity", "Failed to export logs to Downloads", ex)
                null
            }
        } else {
            Logger.w("SettingsActivity", "Downloads export unavailable below Android 10; ensure a share target supports FileProvider URI")
            null
        }

        if (exportedUri != null) {
            val intent2 = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_STREAM, exportedUri)
                putExtra(Intent.EXTRA_SUBJECT, "Buckwheat logs")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            try {
                Logger.i("SettingsActivity", "Launching share chooser for exported Downloads URI")
                startActivity(Intent.createChooser(intent2, "Share logs"))
                Logger.i("SettingsActivity", "Share chooser launched for exported URI")
            } catch (e: Exception) {
                Toast.makeText(this, "No app available to share logs", Toast.LENGTH_SHORT).show()
                Logger.e("SettingsActivity", "No app available to share logs for exported URI", e)
            }
        } else {
            Toast.makeText(this, "Failed to prepare logs for sharing", Toast.LENGTH_SHORT).show()
            Logger.e("SettingsActivity", "Failed to prepare logs for sharing: exportedUri is null")
        }
    }

    @RequiresApi(Build.VERSION_CODES.Q)
    private fun exportLogToDownloads(file: File): Uri? {
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, file.name)
            put(MediaStore.Downloads.MIME_TYPE, "text/plain")
        }

        val resolver = contentResolver
        val collection = MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        val itemUri = resolver.insert(collection, values) ?: return null

        resolver.openOutputStream(itemUri).use { out ->
            file.inputStream().use { input ->
                input.copyTo(out!!)
            }
        }

        return itemUri
    }

    private fun detectDeviceLabel(): String {
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

        return when {
            lowered.any { it.contains("qcom") || it.contains("qualcomm") || it.contains("snapdragon") } -> "Qualcomm / Snapdragon"
            lowered.any { it.contains("mediatek") || it.contains("dimensity") || it.startsWith("mt") } -> "MediaTek Dimensity"
            lowered.any { it.contains("kirin") || it.contains("hisilicon") } -> "HiSilicon / Kirin"
            lowered.any { it.contains("exynos") || it.contains("slsi") } -> "Samsung Exynos"
            lowered.any { it.contains("tensor") || it.contains("google") } -> "Google Tensor"
            else -> "Generic"
        }
    }
}
