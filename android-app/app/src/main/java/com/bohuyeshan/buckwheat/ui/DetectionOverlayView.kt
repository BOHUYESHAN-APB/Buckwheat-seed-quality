package com.bohuyeshan.buckwheat.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View
import com.bohuyeshan.buckwheat.model.Detection
import com.bohuyeshan.buckwheat.util.Logger
import kotlin.math.max

class DetectionOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    // 为不同类别定义不同颜色
    private val classColors = listOf(
        Color.rgb(0, 255, 0),     // 绿色 - seeda
        Color.rgb(255, 165, 0),   // 橙色 - seedb
        Color.rgb(255, 0, 255),   // 品红 - seedc
        Color.rgb(0, 255, 255)    // 青色 - seedd
    )

    private val boxPaint = Paint().apply {
        color = Color.GREEN
        strokeWidth = 5f
        style = Paint.Style.STROKE
        isAntiAlias = true
    }

    private val textBackgroundPaint = Paint().apply {
        color = Color.argb(200, 0, 0, 0)  // 更不透明的背景
        style = Paint.Style.FILL
        isAntiAlias = true
    }

    private val textPaint = Paint().apply {
        color = Color.WHITE
        textSize = 40f  // 更大的文字
        isAntiAlias = true
        isFakeBoldText = true  // 加粗
    }

    private val rect = RectF()
    private var detections: List<Detection> = emptyList()
    private var inferenceInputWidth: Int = 640
    private var inferenceInputHeight: Int = 640
    private var rotationDegrees: Int = 0  // 图像旋转角度
    private var horizontalPadding: Float = 0f
    private var verticalPadding: Float = 0f
    private var emojiEnabled: Boolean = false

    private fun getColorForLabel(label: String): Int {
        // 根据标签名获取颜色
        return when {
            label.contains("seeda", ignoreCase = true) -> classColors[0]
            label.contains("seedb", ignoreCase = true) -> classColors[1]
            label.contains("seedc", ignoreCase = true) -> classColors[2]
            label.contains("seedd", ignoreCase = true) -> classColors[3]
            else -> {
                // 如果是 "Class N" 格式，使用索引
                val classIndex = label.substringAfter("Class ", "").toIntOrNull() ?: 0
                classColors[classIndex % classColors.size]
            }
        }
    }

    fun configureInputSize(width: Int, height: Int, rotation: Int = 0) {
        inferenceInputWidth = max(1, width)
        inferenceInputHeight = max(1, height)
        rotationDegrees = rotation
        invalidate()
    }

    fun updateDetections(items: List<Detection>, hPadding: Float = 0f, vPadding: Float = 0f) {
        detections = items
        horizontalPadding = hPadding
        verticalPadding = vPadding
        postInvalidateOnAnimation()
    }

    fun setEmojiRenderingEnabled(enabled: Boolean) {
        emojiEnabled = enabled
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (detections.isEmpty()) return

        val inputWidth = inferenceInputWidth.toFloat()
        val inputHeight = inferenceInputHeight.toFloat()
        if (inputWidth <= 0f || inputHeight <= 0f) return

    val viewWidth = width.toFloat()
    val viewHeight = height.toFloat()

        // PreviewView会自动旋转显示图像,我们需要匹配这个旋转
        // 当旋转90或270度时,PreviewView显示的是旋转后的图像(宽高交换)
        val displayWidth: Float
        val displayHeight: Float
        when (rotationDegrees) {
            90, 270 -> {
                // 旋转90或270度:PreviewView显示时宽高交换
                displayWidth = inputHeight  // 640x480 -> 显示为480宽
                displayHeight = inputWidth  // 640x480 -> 显示为640高
            }
            else -> {
                // 0或180度:宽高不变
                displayWidth = inputWidth
                displayHeight = inputHeight
            }
        }

        // PreviewView使用fitCenter,计算实际显示区域(可能有黑边)
        val imageAspect = displayWidth / displayHeight
        val viewAspect = viewWidth / viewHeight
        
        val scale: Float
        val offsetX: Float
        val offsetY: Float
        
        if (viewAspect > imageAspect) {
            // View更宽,图像会垂直填充,左右有黑边
            scale = viewHeight / displayHeight
            offsetX = (viewWidth - displayWidth * scale) / 2f
            offsetY = 0f
        } else {
            // View更高,图像会水平填充,上下有黑边
            scale = viewWidth / displayWidth
            offsetX = 0f
            offsetY = (viewHeight - displayHeight * scale) / 2f
        }
        
        // 调试日志
        if (detections.isNotEmpty()) {
            Logger.i("DetectionOverlay", "View=${viewWidth.toInt()}x${viewHeight.toInt()}, Input=${inputWidth.toInt()}x${inputHeight.toInt()}, rotation=${rotationDegrees}°, Display=${displayWidth.toInt()}x${displayHeight.toInt()}, scale=${"%.3f".format(scale)}, offset=(${"%.1f".format(offsetX)}, ${"%.1f".format(offsetY)}), detections=${detections.size}")
        }

        detections.forEach { detection ->
            // 根据旋转角度转换坐标
            val left: Float
            val top: Float
            val right: Float
            val bottom: Float
            
            when (rotationDegrees) {
                90 -> {
                    // 顺时针旋转90度: (x,y) -> (height-y, x)
                    // 原图坐标系: 640x480, 新坐标系: 480x640
                    left = (inputHeight - detection.boundingBox.bottom) * scale + offsetX
                    top = detection.boundingBox.left * scale + offsetY
                    right = (inputHeight - detection.boundingBox.top) * scale + offsetX
                    bottom = detection.boundingBox.right * scale + offsetY
                }
                270 -> {
                    // 逆时针旋转90度(或顺时针270度): (x,y) -> (y, width-x)
                    left = detection.boundingBox.top * scale + offsetX
                    top = (inputWidth - detection.boundingBox.right) * scale + offsetY
                    right = detection.boundingBox.bottom * scale + offsetX
                    bottom = (inputWidth - detection.boundingBox.left) * scale + offsetY
                }
                180 -> {
                    // 旋转180度: (x,y) -> (width-x, height-y)
                    left = (inputWidth - detection.boundingBox.right) * scale + offsetX
                    top = (inputHeight - detection.boundingBox.bottom) * scale + offsetY
                    right = (inputWidth - detection.boundingBox.left) * scale + offsetX
                    bottom = (inputHeight - detection.boundingBox.top) * scale + offsetY
                }
                else -> {
                    // 0度:不旋转
                    left = detection.boundingBox.left * scale + offsetX
                    top = detection.boundingBox.top * scale + offsetY
                    right = detection.boundingBox.right * scale + offsetX
                    bottom = detection.boundingBox.bottom * scale + offsetY
                }
            }
            
            rect.left = left
            rect.top = top
            rect.right = right
            rect.bottom = bottom

            // 根据标签选择颜色
            boxPaint.color = getColorForLabel(detection.label)
            canvas.drawRect(rect, boxPaint)

            // 格式化标签文本
            val labelText = "${detection.label} ${(detection.score * 100).toInt()}%"
            val textWidth = textPaint.measureText(labelText)
            val textHeight = textPaint.textSize
            var xText = rect.left + 8

            // 如果启用emoji，在标签前绘制emoji
            if (emojiEnabled) {
                val emoji = selectEmojiForLabel(detection.label)
                canvas.drawText(emoji, xText, rect.top - 8, textPaint)
                val emojiWidth = textPaint.measureText(emoji) + 8
                xText += emojiWidth
            }

            // 绘制文本背景
            canvas.drawRect(
                rect.left,
                rect.top - textHeight - 8,
                rect.left + textWidth + 16,
                rect.top,
                textBackgroundPaint
            )
            // 绘制文本
            canvas.drawText(labelText, xText, rect.top - 12, textPaint)
        }
    }

    private fun selectEmojiForLabel(label: String): String {
        // simple deterministic mapping: pick one from list by label hash
        val pool = listOf("🌾", "✅", "❌", "🍂", "🔍", "📸")
        val idx = (kotlin.math.abs(label.hashCode())) % pool.size
        return pool[idx]
    }
}
