package com.bohuyeshan.buckwheat

import android.app.Activity
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.bohuyeshan.buckwheat.databinding.ActivityImageManagerBinding
import com.bohuyeshan.buckwheat.util.Logger
import android.graphics.BitmapFactory
import android.widget.PopupMenu
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.text.DateFormat
import java.util.Date
import java.util.Locale
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class ImageManagerActivity : AppCompatActivity() {

    private lateinit var binding: ActivityImageManagerBinding
    private lateinit var adapter: PhotoListAdapter
    private val items = mutableListOf<PhotoEntry>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityImageManagerBinding.inflate(layoutInflater)
        setContentView(binding.root)

        adapter = PhotoListAdapter(
            onSelect = { entry -> returnSelection(entry) },
            onShare = { entry -> sharePhoto(entry) },
            onDelete = { entry -> deletePhoto(entry) },
            onSaveToGallery = { entry -> saveToGallery(entry) },
            onView = { entry -> viewPhoto(entry) }
        )

        binding.recyclerView.layoutManager = LinearLayoutManager(this)
        binding.recyclerView.adapter = adapter

        binding.buttonBack.setOnClickListener { finish() }
        binding.buttonRefresh.setOnClickListener { refreshList() }
        binding.buttonExportZip.setOnClickListener { exportZip() }

        refreshList()
    }

    private fun refreshList() {
        lifecycleScope.launch {
            val entries = withContext(Dispatchers.IO) { loadPhotoEntries() }
            items.clear()
            items.addAll(entries)
            adapter.submitList(items.toList())
            binding.emptyText.text = if (items.isEmpty()) {
                "No cached photos"
            } else {
                "Tap a photo to run single-frame inference."
            }
        }
    }

    private fun loadPhotoEntries(): List<PhotoEntry> {
        val photosDir = File(cacheDir, "photos")
        if (!photosDir.exists()) return emptyList()
        return photosDir.listFiles { file -> file.isFile && file.extension.lowercase(Locale.US) in setOf("jpg", "jpeg", "png") }
            ?.sortedByDescending { it.lastModified() }
            ?.map { file ->
                val jsonCandidate = File(photosDir, file.nameWithoutExtension + ".json")
                val dumpCandidate = photosDir.listFiles { _, name -> name.startsWith("onnx_dump") && name.contains(file.nameWithoutExtension.takeLast(8)) }?.firstOrNull()
                PhotoEntry(file, jsonCandidate.takeIf { it.exists() }, dumpCandidate)
            }
            ?: emptyList()
    }

    private fun returnSelection(entry: PhotoEntry) {
        val resultIntent = Intent().apply {
            putExtra(EXTRA_SELECTED_PHOTO_PATH, entry.file.absolutePath)
            entry.associatedDump?.let { putExtra(EXTRA_SELECTED_DUMP_PATH, it.absolutePath) }
        }
        setResult(Activity.RESULT_OK, resultIntent)
        finish()
    }

    private fun sharePhoto(entry: PhotoEntry) {
        try {
            val uri = fileToUri(entry.file)
            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "image/jpeg"
                putExtra(Intent.EXTRA_STREAM, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            grantAllReadPermissions(intent, uri)
            startActivity(Intent.createChooser(intent, "Share photo"))
        } catch (e: Exception) {
            Logger.e(TAG, "Failed to share photo", e)
            Toast.makeText(this, "Unable to share photo", Toast.LENGTH_SHORT).show()
        }
    }

    private fun deletePhoto(entry: PhotoEntry) {
        lifecycleScope.launch {
            val success = withContext(Dispatchers.IO) {
                val ok = entry.file.delete()
                entry.associatedJson?.delete()
                entry.associatedDump?.delete()
                ok
            }
            if (success) {
                Toast.makeText(this@ImageManagerActivity, "Photo deleted", Toast.LENGTH_SHORT).show()
                refreshList()
            } else {
                Toast.makeText(this@ImageManagerActivity, "Failed to delete", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun saveToGallery(entry: PhotoEntry) {
        lifecycleScope.launch {
            val uri = withContext(Dispatchers.IO) { exportToMediaStore(entry.file) }
            if (uri != null) {
                Toast.makeText(this@ImageManagerActivity, "Saved to gallery", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this@ImageManagerActivity, "Save failed", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun viewPhoto(entry: PhotoEntry) {
        try {
            val uri = fileToUri(entry.file)
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "image/jpeg")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            grantAllReadPermissions(intent, uri)
            startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "No viewer found", Toast.LENGTH_SHORT).show()
        }
    }

    private fun exportToMediaStore(file: File): Uri? {
        val resolver = contentResolver
        val fileName = file.name
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, fileName)
            put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
            put(MediaStore.Images.Media.DATE_ADDED, System.currentTimeMillis() / 1000)
        }
        val collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        val uri = resolver.insert(collection, values) ?: return null
        resolver.openOutputStream(uri)?.use { output ->
            FileInputStream(file).use { input -> input.copyTo(output) }
        }
        return uri
    }

    private fun exportZip() {
        lifecycleScope.launch {
            val zipFile = withContext(Dispatchers.IO) { createExportZip() }
            if (zipFile == null) {
                Toast.makeText(this@ImageManagerActivity, "Nothing to export", Toast.LENGTH_SHORT).show()
                return@launch
            }
            try {
                val uri = fileToUri(zipFile)
                val intent = Intent(Intent.ACTION_SEND).apply {
                    type = "application/zip"
                    putExtra(Intent.EXTRA_STREAM, uri)
                    putExtra(Intent.EXTRA_SUBJECT, "Buckwheat captures")
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                grantAllReadPermissions(intent, uri)
                startActivity(Intent.createChooser(intent, "Share export"))
            } catch (e: Exception) {
                Logger.e(TAG, "Export share failed", e)
                Toast.makeText(this@ImageManagerActivity, "Share failed", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun createExportZip(): File? {
        val photosDir = File(cacheDir, "photos")
        val files = photosDir.listFiles()?.filter { it.isFile } ?: emptyList()
        val logFile = Logger.getLogFile()
        if (files.isEmpty() && (logFile == null || !logFile.exists())) {
            return null
        }
        val exportDir = File(cacheDir, "exports").apply { mkdirs() }
        val outFile = File(exportDir, "buckwheat_export_${System.currentTimeMillis()}.zip")
        ZipOutputStream(FileOutputStream(outFile)).use { zip ->
            files.forEach { file ->
                FileInputStream(file).use { input ->
                    val entry = ZipEntry("photos/${file.name}")
                    entry.time = file.lastModified()
                    zip.putNextEntry(entry)
                    input.copyTo(zip)
                    zip.closeEntry()
                }
            }
            if (logFile != null && logFile.exists()) {
                FileInputStream(logFile).use { input ->
                    val entry = ZipEntry("logs/${logFile.name}")
                    entry.time = logFile.lastModified()
                    zip.putNextEntry(entry)
                    input.copyTo(zip)
                    zip.closeEntry()
                }
            }
        }
        return outFile
    }

    private fun fileToUri(file: File): Uri {
        return FileProvider.getUriForFile(this, "${packageName}.fileprovider", file)
    }

    private fun grantAllReadPermissions(intent: Intent, uri: Uri) {
        val resInfo = packageManager.queryIntentActivities(intent, 0)
        for (resolveInfo in resInfo) {
            grantUriPermission(resolveInfo.activityInfo.packageName, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }

    data class PhotoEntry(
        val file: File,
        val associatedJson: File? = null,
        val associatedDump: File? = null
    ) {
        val sizeBytes: Long = file.length()
        val lastModified: Long = file.lastModified()

        fun infoText(): String {
            val formatter = DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT)
            val dateStr = formatter.format(Date(lastModified))
            val sizeStr = humanReadableByteCount(sizeBytes)
            return "$dateStr • $sizeStr"
        }

        private fun humanReadableByteCount(bytes: Long): String {
            if (bytes <= 0) return "0 B"
            val units = arrayOf("B", "KB", "MB", "GB", "TB")
            val digitGroups = (Math.log10(bytes.toDouble()) / Math.log10(1024.0)).toInt()
            return String.format(Locale.US, "%.1f %s", bytes / Math.pow(1024.0, digitGroups.toDouble()), units[digitGroups])
        }
    }

    companion object {
        const val EXTRA_SELECTED_PHOTO_PATH = "selected_photo_path"
        const val EXTRA_SELECTED_DUMP_PATH = "selected_dump_path"
        private const val TAG = "ImageManager"

        fun open(context: Context) {
            val intent = Intent(context, ImageManagerActivity::class.java)
            context.startActivity(intent)
        }
    }
}

private class PhotoListAdapter(
    private val onSelect: (ImageManagerActivity.PhotoEntry) -> Unit,
    private val onShare: (ImageManagerActivity.PhotoEntry) -> Unit,
    private val onDelete: (ImageManagerActivity.PhotoEntry) -> Unit,
    private val onSaveToGallery: (ImageManagerActivity.PhotoEntry) -> Unit,
    private val onView: (ImageManagerActivity.PhotoEntry) -> Unit
) : androidx.recyclerview.widget.ListAdapter<ImageManagerActivity.PhotoEntry, PhotoListAdapter.PhotoViewHolder>(DiffCallback()) {

    override fun onCreateViewHolder(parent: android.view.ViewGroup, viewType: Int): PhotoViewHolder {
        val view = android.view.LayoutInflater.from(parent.context).inflate(R.layout.item_cached_photo, parent, false)
        return PhotoViewHolder(view)
    }

    override fun onBindViewHolder(holder: PhotoViewHolder, position: Int) {
        val entry = getItem(position)
    holder.bind(entry, onSelect, onShare, onDelete, onSaveToGallery, onView)
    }

    class PhotoViewHolder(itemView: android.view.View) : androidx.recyclerview.widget.RecyclerView.ViewHolder(itemView) {
        private val thumb: android.widget.ImageView = itemView.findViewById(R.id.image_thumb)
        private val name: android.widget.TextView = itemView.findViewById(R.id.text_name)
        private val info: android.widget.TextView = itemView.findViewById(R.id.text_info)
    private val shareButton: android.widget.ImageButton = itemView.findViewById(R.id.button_share)
    private val deleteButton: android.widget.ImageButton = itemView.findViewById(R.id.button_delete)
    private val contextMenu: PopupMenu = PopupMenu(itemView.context, thumb)

        init {
            contextMenu.menu.add("View")
            contextMenu.menu.add("Save to gallery")
        }

        fun bind(
            entry: ImageManagerActivity.PhotoEntry,
            onSelect: (ImageManagerActivity.PhotoEntry) -> Unit,
            onShare: (ImageManagerActivity.PhotoEntry) -> Unit,
            onDelete: (ImageManagerActivity.PhotoEntry) -> Unit,
            onSaveToGallery: (ImageManagerActivity.PhotoEntry) -> Unit,
            onView: (ImageManagerActivity.PhotoEntry) -> Unit
        ) {
            name.text = entry.file.name
            info.text = entry.infoText()

            val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeFile(entry.file.absolutePath, options)
            options.inJustDecodeBounds = false
            options.inSampleSize = calculateInSampleSize(options, 256, 256)
            val bitmap = BitmapFactory.decodeFile(entry.file.absolutePath, options)
            thumb.setImageBitmap(bitmap)

            itemView.setOnClickListener { onSelect(entry) }
            thumb.setOnClickListener {
                contextMenu.setOnMenuItemClickListener { menuItem ->
                    when (menuItem.title) {
                        "View" -> {
                            onView(entry)
                            true
                        }
                        "Save to gallery" -> {
                            onSaveToGallery(entry)
                            true
                        }
                        else -> false
                    }
                }
                contextMenu.show()
            }
            shareButton.setOnClickListener { onShare(entry) }
            deleteButton.setOnClickListener { onDelete(entry) }
        }

        private fun calculateInSampleSize(options: BitmapFactory.Options, reqWidth: Int, reqHeight: Int): Int {
            val (height: Int, width: Int) = options.run { outHeight to outWidth }
            var inSampleSize = 1
            if (height > reqHeight || width > reqWidth) {
                var halfHeight = height / 2
                var halfWidth = width / 2
                while (halfHeight / inSampleSize >= reqHeight && halfWidth / inSampleSize >= reqWidth) {
                    inSampleSize *= 2
                }
            }
            return inSampleSize
        }
    }

    class DiffCallback : androidx.recyclerview.widget.DiffUtil.ItemCallback<ImageManagerActivity.PhotoEntry>() {
        override fun areItemsTheSame(oldItem: ImageManagerActivity.PhotoEntry, newItem: ImageManagerActivity.PhotoEntry): Boolean {
            return oldItem.file.absolutePath == newItem.file.absolutePath
        }

        override fun areContentsTheSame(oldItem: ImageManagerActivity.PhotoEntry, newItem: ImageManagerActivity.PhotoEntry): Boolean {
            return oldItem.file.length() == newItem.file.length() && oldItem.lastModified == newItem.lastModified
        }
    }
}
