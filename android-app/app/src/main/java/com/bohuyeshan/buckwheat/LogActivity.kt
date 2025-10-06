package com.bohuyeshan.buckwheat

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.bohuyeshan.buckwheat.util.Logger

class LogActivity : AppCompatActivity() {

    private lateinit var logText: TextView
    private lateinit var copyAllBtn: Button
    private lateinit var shareBtn: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_log)

        logText = findViewById(R.id.log_text_view)
        copyAllBtn = findViewById(R.id.btn_copy_all)
        shareBtn = findViewById(R.id.btn_share_log)

        refresh()

        copyAllBtn.setOnClickListener {
            val content = Logger.readAll() ?: ""
            val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.setPrimaryClip(ClipData.newPlainText("logs", content))
            Toast.makeText(this, "Log copied", Toast.LENGTH_SHORT).show()
        }

        shareBtn.setOnClickListener {
            val file = Logger.getLogFile()
            if (file == null) {
                Toast.makeText(this, "No logs to share", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            val uri = androidx.core.content.FileProvider.getUriForFile(this, "${packageName}.fileprovider", file)
            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_STREAM, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            startActivity(Intent.createChooser(intent, "Share logs"))
        }
    }

    private fun refresh() {
        logText.text = Logger.readAll() ?: "(no logs)"
    }

    companion object {
        fun open(context: Context) {
            context.startActivity(Intent(context, LogActivity::class.java))
        }
    }
}
