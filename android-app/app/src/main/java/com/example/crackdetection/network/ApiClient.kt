package com.example.crackdetection.network

import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient

object ApiClient {
    val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(12, TimeUnit.SECONDS)
        .callTimeout(15, TimeUnit.SECONDS)
        .build()
}
