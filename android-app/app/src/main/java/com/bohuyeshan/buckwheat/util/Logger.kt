package com.bohuyeshan.buckwheat.util

import android.content.Context
import android.util.Log
import java.io.File
import java.io.FileWriter
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object Logger {
    private const val LOG_FILE_NAME = "buckwheat_logs.txt"
    private var logFile: File? = null
    private val dateFmt = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US)

    fun init(context: Context) {
        try {
            logFile = File(context.filesDir, LOG_FILE_NAME)
            if (!logFile!!.exists()) logFile!!.createNewFile()
            i("Logger", "log file: ${logFile!!.absolutePath}")
        } catch (ex: Exception) {
            Log.w("Logger", "failed to init logger", ex)
        }
    }

    private fun append(text: String) {
        try {
            val f = logFile ?: return
            FileWriter(f, true).use { fw ->
                fw.append(text)
                fw.append('\n')
            }
        } catch (ex: Exception) {
            Log.w("Logger", "failed to write log", ex)
        }
    }

    fun i(tag: String, message: String) {
        val stamp = dateFmt.format(Date())
        Log.i(tag, message)
        append("[$stamp] I/$tag: $message")
    }

    fun e(tag: String, message: String, t: Throwable? = null) {
        val stamp = dateFmt.format(Date())
        Log.e(tag, message, t)
        if (t != null) {
            val sw = StringWriter()
            t.printStackTrace(PrintWriter(sw))
            append("[$stamp] E/$tag: $message\n${sw}\n---")
        } else {
            append("[$stamp] E/$tag: $message")
        }
    }

    fun w(tag: String, message: String, t: Throwable? = null) {
        val stamp = dateFmt.format(Date())
        Log.w(tag, message, t)
        if (t != null) {
            val sw = StringWriter()
            t.printStackTrace(PrintWriter(sw))
            append("[$stamp] W/$tag: $message\n${sw}\n---")
        } else {
            append("[$stamp] W/$tag: $message")
        }
    }

    fun getLogFilePath(): String? = logFile?.absolutePath

    fun getLogFile(): File? = logFile

    fun readAll(): String? {
        return try {
            logFile?.readText()
        } catch (ex: Exception) {
            Log.w("Logger", "failed to read log", ex)
            null
        }
    }

    fun clear() {
        try {
            logFile?.writeText("")
        } catch (ex: Exception) {
            Log.w("Logger", "failed to clear log", ex)
        }
    }
}
