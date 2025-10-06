package com.bohuyeshan.buckwheat.camera

import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.bohuyeshan.buckwheat.inference.InferenceEngine
import com.bohuyeshan.buckwheat.inference.InferenceResult
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

class CameraAnalyzer(
    private val scope: CoroutineScope,
    private val inferenceEngine: InferenceEngine,
    private val onDetections: (InferenceResult) -> Unit,
    private val onError: (Throwable) -> Unit
) : ImageAnalysis.Analyzer {

    override fun analyze(image: ImageProxy) {
        if (!inferenceEngine.isReady()) {
            image.close()
            return
        }

        scope.launch {
            try {
                val result = inferenceEngine.runInference(image)
                result.onSuccess(onDetections)
                result.exceptionOrNull()?.let { ex ->
                    if (ex !is CancellationException) {
                        onError(ex)
                    }
                }
            } catch (ex: Exception) {
                onError(ex)
            } finally {
                image.close()
            }
        }
    }
}
