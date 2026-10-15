package com.example.crackdetection.repository

import com.example.crackdetection.model.Detection
import com.example.crackdetection.model.HealthResponse
import com.example.crackdetection.model.StatsResponse
import com.example.crackdetection.network.ApiService

class DetectionRepository(private val api: ApiService = ApiService()) {
    fun baseUrl(ip: String): String {
        val clean = ip.trim()
        require(isValidIpv4(clean)) { "Enter a valid laptop IPv4 address, for example 192.168.1.10." }
        return "http://$clean:5000"
    }

    suspend fun health(baseUrl: String): HealthResponse = api.health(baseUrl)
    suspend fun stats(baseUrl: String): StatsResponse = api.stats(baseUrl)
    suspend fun detections(baseUrl: String): List<Detection> = api.detections(baseUrl)

    private fun isValidIpv4(value: String): Boolean {
        val parts = value.split('.')
        return parts.size == 4 && parts.all { part ->
            part.isNotEmpty() && part.length <= 3 && part.all(Char::isDigit) &&
                (part.toIntOrNull() ?: -1) in 0..255
        }
    }
}
