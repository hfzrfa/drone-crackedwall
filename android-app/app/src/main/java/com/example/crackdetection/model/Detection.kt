package com.example.crackdetection.model

data class Detection(
    val id: String,
    val label: String,
    val confidence: Double,
    val timestamp: String,
    val imageName: String,
    val imageUrl: String,
    val source: String,
)
