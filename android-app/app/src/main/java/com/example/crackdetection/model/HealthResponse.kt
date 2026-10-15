package com.example.crackdetection.model

data class HealthResponse(
    val status: String,
    val modelLoaded: Boolean,
    val modelTask: String,
    val sourceType: String,
    val sourceStatus: String,
    val databaseStatus: String,
    val serverTime: String,
)
