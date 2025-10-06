package com.bohuyeshan.buckwheat.storage

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import com.bohuyeshan.buckwheat.inference.InferenceResult
import com.bohuyeshan.buckwheat.model.BoundingBox
import com.bohuyeshan.buckwheat.model.Detection
import com.bohuyeshan.buckwheat.util.Logger
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.util.Locale
import kotlin.math.max
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/**
 * Persistent capture storage that keeps the raw photo, annotated photo and detection metadata
 * for every single-frame capture event.
 */
class CaptureRepository(private val context: Context) {

    private val photosDir: File by lazy {
        File(context.cacheDir, PHOTOS_DIR).apply { if (!exists()) mkdirs() }
    }

    suspend fun persistCapture(rawFile: File, originalBitmap: Bitmap, result: InferenceResult): CaptureRecord {
        return withContext(Dispatchers.IO) {
            val baseName = rawFile.nameWithoutExtension
            val metadata = CaptureMetadata(
                originalWidth = result.metadata.originalWidth,
                originalHeight = result.metadata.originalHeight,
                rotationDegrees = result.metadata.rotationDegrees,
                detections = result.detections.map { detection ->
                    CaptureDetection(
                        label = detection.label,
                        score = detection.score,
                        box = detection.boundingBox
                    )
                }
            )

            val metadataFile = File(photosDir, "$baseName.json")
            metadataFile.writeText(metadata.toJson().toString())

            val annotatedFile = File(photosDir, "${baseName}_marked.jpg")
            createAnnotatedCopy(originalBitmap, result.detections, annotatedFile)

            CaptureRecord(
                baseName = baseName,
                rawFile = rawFile,
                annotatedFile = annotatedFile.takeIf { it.exists() },
                metadataFile = metadataFile,
                metadata = metadata
            )
        }
    }

    fun listCaptures(): List<CaptureRecord> {
        val rawFiles = photosDir.listFiles { file ->
            file.isFile && file.name.lowercase(Locale.US).let { name ->
                name.startsWith(RAW_PREFIX) &&
                    !name.contains(ANNOTATED_SUFFIX) &&
                    (name.endsWith(".jpg") || name.endsWith(".jpeg") || name.endsWith(".png"))
            }
        } ?: return emptyList()

        return rawFiles.mapNotNull { raw ->
            val baseName = raw.nameWithoutExtension
            val metadataFile = File(photosDir, "$baseName.json")
            val metadata = if (metadataFile.exists()) {
                try {
                    CaptureMetadata.fromJson(JSONObject(metadataFile.readText()))
                } catch (ex: JSONException) {
                    Logger.e(TAG, "Failed to parse metadata for $baseName", ex)
                    null
                }
            } else {
                // Fallback metadata for legacy captures – derive dimensions lazily
                val dims = readImageDimensions(raw)
                CaptureMetadata(
                    originalWidth = dims?.first ?: 0,
                    originalHeight = dims?.second ?: 0,
                    rotationDegrees = 0,
                    detections = emptyList()
                ).also {
                    try {
                        metadataFile.writeText(it.toJson().toString())
                    } catch (ignored: IOException) {
                        Logger.w(TAG, "Unable to backfill metadata for legacy capture $baseName", ignored)
                    }
                }
            }

            val annotated = File(photosDir, "${baseName}_marked.jpg")

            // Ensure we have non-null metadata for downstream consumers; backfill using image dims if needed
            val finalMetadata = metadata ?: run {
                val dims = readImageDimensions(raw)
                CaptureMetadata(
                    originalWidth = dims?.first ?: 0,
                    originalHeight = dims?.second ?: 0,
                    rotationDegrees = 0,
                    detections = emptyList()
                ).also {
                    try {
                        metadataFile.writeText(it.toJson().toString())
                    } catch (ignored: IOException) {
                        Logger.w(TAG, "Unable to write backfilled metadata for $baseName", ignored)
                    }
                }
            }

            if (!annotated.exists()) {
                try {
                    regenerateAnnotated(raw, annotated, finalMetadata)
                } catch (ex: Exception) {
                    Logger.w(TAG, "Failed to regenerate annotated capture for $baseName", ex)
                }
            }

            CaptureRecord(
                baseName = baseName,
                rawFile = raw,
                annotatedFile = annotated.takeIf { it.exists() },
                metadataFile = metadataFile,
                metadata = finalMetadata
            )
        }
            .sortedByDescending { it.rawFile.lastModified() }
    }

    fun loadCapture(baseName: String): CaptureRecord? {
        val rawFileCandidates = photosDir.listFiles { file ->
            file.isFile && file.nameWithoutExtension == baseName && !file.name.contains(ANNOTATED_SUFFIX)
        } ?: return null
        val rawFile = rawFileCandidates.firstOrNull() ?: return null
        val metadataFile = File(photosDir, "$baseName.json")
        if (!metadataFile.exists()) return null
        val metadata = try {
            CaptureMetadata.fromJson(JSONObject(metadataFile.readText()))
        } catch (ex: JSONException) {
            Logger.e(TAG, "Failed to parse metadata for $baseName", ex)
            return null
        }
        val annotated = File(photosDir, "${baseName}_marked.jpg")
        if (!annotated.exists()) {
            try {
                regenerateAnnotated(rawFile, annotated, metadata)
            } catch (ex: Exception) {
                Logger.w(TAG, "Unable to regenerate annotated capture for $baseName", ex)
            }
        }
        return CaptureRecord(
            baseName = baseName,
            rawFile = rawFile,
            annotatedFile = annotated.takeIf { it.exists() },
            metadataFile = metadataFile,
            metadata = metadata
        )
    }

    private fun createAnnotatedCopy(original: Bitmap, detections: List<Detection>, output: File) {
        if (detections.isEmpty()) {
            copyBitmapToFile(original, output)
            return
        }
        val annotated = original.copy(Bitmap.Config.ARGB_8888, true)
        val canvas = Canvas(annotated)
        val boxPaint = Paint().apply {
            style = Paint.Style.STROKE
            strokeWidth = 6f
            isAntiAlias = true
        }
        val textPaint = Paint().apply {
            color = Color.WHITE
            textSize = 48f
            isAntiAlias = true
            isFakeBoldText = true
        }
        val textBackgroundPaint = Paint().apply {
            color = Color.argb(180, 0, 0, 0)
            style = Paint.Style.FILL
            isAntiAlias = true
        }
        val rect = RectF()

        detections.forEach { detection ->
            boxPaint.color = colorForLabel(detection.label)
            rect.set(
                detection.boundingBox.left,
                detection.boundingBox.top,
                detection.boundingBox.right,
                detection.boundingBox.bottom
            )
            canvas.drawRect(rect, boxPaint)

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
            canvas.drawText(labelText, rect.left + 16, rect.top - 20, textPaint)
        }

        saveBitmapJpeg(annotated, output)
        annotated.recycle()
    }

    private fun regenerateAnnotated(rawFile: File, annotated: File, metadata: CaptureMetadata?) {
        if (!rawFile.exists()) return
        val bitmap = BitmapFactoryWrapper.decode(rawFile) ?: return
        try {
            val detections = metadata?.toDetections() ?: emptyList()
            createAnnotatedCopy(bitmap, detections, annotated)
        } finally {
            bitmap.recycle()
        }
    }

    private fun copyBitmapToFile(bitmap: Bitmap, output: File) {
        saveBitmapJpeg(bitmap, output)
    }

    private fun saveBitmapJpeg(bitmap: Bitmap, output: File) {
        output.parentFile?.mkdirs()
        FileOutputStream(output).use { stream ->
            bitmap.compress(Bitmap.CompressFormat.JPEG, 95, stream)
            stream.flush()
        }
    }

    private fun readImageDimensions(file: File): Pair<Int, Int>? {
        return BitmapFactoryWrapper.readDimensions(file)
    }

    companion object {
        private const val TAG = "CaptureRepository"
        private const val PHOTOS_DIR = "photos"
        private const val RAW_PREFIX = "capture_"
        private const val ANNOTATED_SUFFIX = "_marked"

        private fun colorForLabel(label: String): Int {
            return when {
                label.contains("seeda", ignoreCase = true) -> Color.rgb(0, 255, 0)
                label.contains("seedb", ignoreCase = true) -> Color.rgb(255, 165, 0)
                label.contains("seedc", ignoreCase = true) -> Color.rgb(255, 0, 255)
                label.contains("seedd", ignoreCase = true) -> Color.rgb(0, 255, 255)
                else -> {
                    val idx = max(0, label.hashCode()) % COLOR_POOL.size
                    COLOR_POOL[idx]
                }
            }
        }

        private val COLOR_POOL = listOf(
            Color.rgb(244, 81, 30),
            Color.rgb(66, 133, 244),
            Color.rgb(171, 71, 188),
            Color.rgb(0, 150, 136)
        )
    }
}

data class CaptureDetection(
    val label: String,
    val score: Float,
    val box: BoundingBox
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("label", label)
        put("score", score)
        put("left", box.left)
        put("top", box.top)
        put("right", box.right)
        put("bottom", box.bottom)
    }

    fun toDetection(): Detection = Detection(label, score, box)

    companion object {
        fun fromJson(obj: JSONObject): CaptureDetection {
            val box = BoundingBox(
                left = obj.optDouble("left", 0.0).toFloat(),
                top = obj.optDouble("top", 0.0).toFloat(),
                right = obj.optDouble("right", 0.0).toFloat(),
                bottom = obj.optDouble("bottom", 0.0).toFloat()
            )
            return CaptureDetection(
                label = obj.optString("label"),
                score = obj.optDouble("score", 0.0).toFloat(),
                box = box
            )
        }
    }
}

data class CaptureMetadata(
    val originalWidth: Int,
    val originalHeight: Int,
    val rotationDegrees: Int,
    val detections: List<CaptureDetection>
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("width", originalWidth)
        put("height", originalHeight)
        put("rotation", rotationDegrees)
        put("detections", JSONArray().apply {
            detections.forEach { put(it.toJson()) }
        })
    }

    fun toDetections(): List<Detection> = detections.map { it.toDetection() }

    companion object {
        fun fromJson(obj: JSONObject): CaptureMetadata {
            val width = obj.optInt("width", 0)
            val height = obj.optInt("height", 0)
            val rotation = obj.optInt("rotation", 0)
            val detectionsArray = obj.optJSONArray("detections") ?: JSONArray()
            val detections = mutableListOf<CaptureDetection>()
            for (i in 0 until detectionsArray.length()) {
                val detectionObj = detectionsArray.optJSONObject(i) ?: continue
                detections += CaptureDetection.fromJson(detectionObj)
            }
            return CaptureMetadata(width, height, rotation, detections)
        }
    }
}

data class CaptureRecord(
    val baseName: String,
    val rawFile: File,
    val annotatedFile: File?,
    val metadataFile: File,
    val metadata: CaptureMetadata
)

private object BitmapFactoryWrapper {
    fun decode(file: File): Bitmap? {
        return try {
            android.graphics.BitmapFactory.decodeFile(file.absolutePath)
        } catch (ex: Exception) {
            Logger.e("BitmapFactoryWrapper", "decode failed for ${file.absolutePath}", ex)
            null
        }
    }

    fun readDimensions(file: File): Pair<Int, Int>? {
        return try {
            val options = android.graphics.BitmapFactory.Options().apply { inJustDecodeBounds = true }
            android.graphics.BitmapFactory.decodeFile(file.absolutePath, options)
            if (options.outWidth > 0 && options.outHeight > 0) {
                options.outWidth to options.outHeight
            } else {
                null
            }
        } catch (ex: Exception) {
            Logger.e("BitmapFactoryWrapper", "dimension read failed for ${file.absolutePath}", ex)
            null
        }
    }
}
