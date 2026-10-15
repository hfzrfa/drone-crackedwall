package com.example.crackdetection.network

import com.example.crackdetection.model.Detection
import com.example.crackdetection.model.HealthResponse
import com.example.crackdetection.model.StatsResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject

class ApiService {
    private suspend fun get(baseUrl: String, path: String): String = withContext(Dispatchers.IO) {
        val request = Request.Builder().url("$baseUrl$path").get().build()
        ApiClient.httpClient.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val detail = runCatching { JSONObject(body).optString("error") }.getOrDefault("")
                throw ApiException(response.code, detail.ifBlank { "HTTP ${response.code}" })
            }
            body
        }
    }

    suspend fun health(baseUrl: String): HealthResponse {
        val json = JSONObject(get(baseUrl, "/health"))
        return HealthResponse(
            status = json.optString("status", "unknown"),
            modelLoaded = json.optBoolean("model_loaded", json.optBoolean("ok")),
            modelTask = json.optString("model_task", "unknown"),
            sourceType = json.optString("source_type", "unknown"),
            sourceStatus = json.optString("source_status", "unknown"),
            databaseStatus = json.optString("database_status", "unknown"),
            serverTime = json.optString("server_time", ""),
        )
    }

    suspend fun stats(baseUrl: String): StatsResponse {
        val json = JSONObject(get(baseUrl, "/stats"))
        return StatsResponse(
            uptimeSeconds = json.optDouble("uptime_seconds", 0.0),
            framesProcessed = json.optLong("frames_processed"),
            detectionsSeen = json.optLong("detections_seen"),
            detectionsSaved = json.optLong("detections_saved"),
            duplicateSkips = json.optLong("detections_skipped_duplicate"),
            databaseErrors = json.optLong("database_errors"),
            connectedVideoClients = json.optLong("connected_video_clients"),
            processingFps = json.optDouble("processing_fps", 0.0),
        )
    }

    suspend fun detections(baseUrl: String): List<Detection> {
        val array = JSONArray(get(baseUrl, "/documents?limit=20"))
        return buildList {
            for (index in 0 until array.length()) {
                val row = array.getJSONObject(index)
                val data = row.optJSONObject("data") ?: JSONObject()
                add(
                    Detection(
                        id = row.optString("_id", index.toString()),
                        label = data.optString("label", "crack"),
                        confidence = data.optDouble("confidence", 0.0),
                        timestamp = data.optString("timestamp", ""),
                        imageName = data.optString("image_name", ""),
                        imageUrl = data.optString("image_url", ""),
                        source = data.optString("source", "unknown"),
                    )
                )
            }
        }
    }
}

class ApiException(val statusCode: Int, message: String) : Exception(message)
