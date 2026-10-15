package com.example.crackdetection.model

data class StatsResponse(
    val uptimeSeconds: Double,
    val framesProcessed: Long,
    val detectionsSeen: Long,
    val detectionsSaved: Long,
    val duplicateSkips: Long,
    val databaseErrors: Long,
    val connectedVideoClients: Long,
    val processingFps: Double,
)
