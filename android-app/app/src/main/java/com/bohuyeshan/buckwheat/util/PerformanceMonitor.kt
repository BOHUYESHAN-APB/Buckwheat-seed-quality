package com.bohuyeshan.buckwheat.util

import android.app.ActivityManager
import android.content.Context
import android.os.Debug
import android.os.Process
import java.io.File
import java.io.RandomAccessFile
import kotlin.math.roundToInt

/**
 * 性能监控工具，用于采集 CPU、内存、FPS 等指标
 */
class PerformanceMonitor(private val context: Context) {

    private var lastFrameTime = 0L
    private var frameCount = 0
    private var currentFps = 0f
    private var fpsUpdateTime = 0L

    private val activityManager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
    private val pid = Process.myPid()

    // CPU 使用率相关
    private var lastCpuTime = 0L
    private var lastAppCpuTime = 0L
    private var cpuUsagePercent = 0f

    /**
     * 记录一帧，用于 FPS 计算
     */
    fun recordFrame() {
        val now = System.currentTimeMillis()
        frameCount++

        // 每秒更新一次 FPS
        if (now - fpsUpdateTime >= 1000) {
            currentFps = frameCount * 1000f / (now - fpsUpdateTime)
            frameCount = 0
            fpsUpdateTime = now
        }
    }

    /**
     * 获取当前 FPS
     */
    fun getFps(): Float = currentFps

    /**
     * 获取当前进程内存使用情况 (MB)
     */
    fun getMemoryUsage(): MemoryInfo {
        val memInfo = Debug.MemoryInfo()
        Debug.getMemoryInfo(memInfo)

        val nativeHeap = memInfo.nativePss / 1024f // KB to MB
        val dalvikHeap = memInfo.dalvikPss / 1024f
        val other = memInfo.otherPss / 1024f
        val total = memInfo.totalPss / 1024f

        // 获取系统可用内存
        val mi = ActivityManager.MemoryInfo()
        activityManager.getMemoryInfo(mi)
        val availableMem = mi.availMem / 1024f / 1024f // bytes to MB

        return MemoryInfo(
            totalPss = total,
            nativeHeap = nativeHeap,
            dalvikHeap = dalvikHeap,
            other = other,
            availableSystemMem = availableMem
        )
    }

    /**
     * 更新并获取 CPU 使用率 (%)
     * 注意：需要定期调用以获得准确数值
     */
    fun updateAndGetCpuUsage(): Float {
        try {
            val totalCpuTime = getTotalCpuTime()
            val appCpuTime = getAppCpuTime()

            if (lastCpuTime > 0 && lastAppCpuTime > 0) {
                val totalDelta = totalCpuTime - lastCpuTime
                val appDelta = appCpuTime - lastAppCpuTime

                if (totalDelta > 0) {
                    cpuUsagePercent = (appDelta * 100f / totalDelta)
                }
            }

            lastCpuTime = totalCpuTime
            lastAppCpuTime = appCpuTime

            return cpuUsagePercent
        } catch (e: Exception) {
            Logger.e("PerformanceMonitor", "Failed to get CPU usage", e)
            return 0f
        }
    }

    /**
     * 获取系统总 CPU 时间 (来自 /proc/stat)
     */
    private fun getTotalCpuTime(): Long {
        return try {
            RandomAccessFile("/proc/stat", "r").use { reader ->
                val line = reader.readLine() ?: return 0L
                // cpu  user nice system idle iowait irq softirq...
                val parts = line.split("\\s+".toRegex())
                if (parts.size < 5) return 0L
                
                var total = 0L
                for (i in 1..4) {
                    total += parts[i].toLongOrNull() ?: 0L
                }
                total
            }
        } catch (e: Exception) {
            0L
        }
    }

    /**
     * 获取当前应用的 CPU 时间 (来自 /proc/[pid]/stat)
     */
    private fun getAppCpuTime(): Long {
        return try {
            RandomAccessFile("/proc/$pid/stat", "r").use { reader ->
                val line = reader.readLine() ?: return 0L
                val parts = line.split("\\s+".toRegex())
                if (parts.size < 17) return 0L
                
                val utime = parts[13].toLongOrNull() ?: 0L
                val stime = parts[14].toLongOrNull() ?: 0L
                utime + stime
            }
        } catch (e: Exception) {
            0L
        }
    }

    /**
     * 获取 GPU 使用情况（Android 系统限制，无法直接获取，返回占位）
     */
    fun getGpuUsage(): String {
        // Android 不提供直接的 GPU 使用率 API
        // 可以尝试读取厂商特定的节点，但不通用
        return "N/A"
    }

    /**
     * 获取 NPU 使用情况（Android 系统限制，无法直接获取，返回占位）
     */
    fun getNpuUsage(): String {
        // NPU (Neural Processing Unit) 使用率同样没有标准 API
        // 高通、华为等芯片厂商可能有私有接口
        return "N/A"
    }

    /**
     * 获取性能快照
     */
    fun getSnapshot(): PerformanceSnapshot {
        val mem = getMemoryUsage()
        val cpu = updateAndGetCpuUsage()
        val fps = getFps()

        return PerformanceSnapshot(
            fps = fps,
            cpuUsage = cpu,
            memoryMB = mem.totalPss,
            nativeHeapMB = mem.nativeHeap,
            dalvikHeapMB = mem.dalvikHeap,
            gpuInfo = getGpuUsage(),
            npuInfo = getNpuUsage()
        )
    }

    data class MemoryInfo(
        val totalPss: Float,
        val nativeHeap: Float,
        val dalvikHeap: Float,
        val other: Float,
        val availableSystemMem: Float
    )

    data class PerformanceSnapshot(
        val fps: Float,
        val cpuUsage: Float,
        val memoryMB: Float,
        val nativeHeapMB: Float,
        val dalvikHeapMB: Float,
        val gpuInfo: String,
        val npuInfo: String
    ) {
        override fun toString(): String {
            return """
                FPS: ${fps.roundToInt()}
                CPU: ${cpuUsage.roundToInt()}%
                Memory: ${memoryMB.roundToInt()} MB (Native: ${nativeHeapMB.roundToInt()} MB, Dalvik: ${dalvikHeapMB.roundToInt()} MB)
                GPU: $gpuInfo
                NPU: $npuInfo
            """.trimIndent()
        }

        fun toCompactString(): String {
            return "FPS:${fps.roundToInt()} CPU:${cpuUsage.roundToInt()}% MEM:${memoryMB.roundToInt()}MB"
        }
    }
}
