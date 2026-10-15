package com.example.crackdetection.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.crackdetection.model.Detection
import com.example.crackdetection.model.HealthResponse
import com.example.crackdetection.model.StatsResponse
import com.example.crackdetection.network.ApiException
import com.example.crackdetection.repository.DetectionRepository
import com.example.crackdetection.storage.SettingsRepository
import java.net.ConnectException
import java.net.SocketTimeoutException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONException

data class MainUiState(
    val serverIp: String = "",
    val baseUrl: String = "",
    val connected: Boolean = false,
    val loading: Boolean = false,
    val health: HealthResponse? = null,
    val stats: StatsResponse? = null,
    val detections: List<Detection> = emptyList(),
    val errorMessage: String? = null,
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = DetectionRepository()
    private val settings = SettingsRepository(application.applicationContext)
    private val _uiState = MutableStateFlow(MainUiState())
    val uiState: StateFlow<MainUiState> = _uiState.asStateFlow()
    private var pollingJob: Job? = null

    init {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(serverIp = settings.serverIp.first())
        }
    }

    fun setServerIp(value: String) {
        _uiState.value = _uiState.value.copy(serverIp = value, errorMessage = null)
    }

    fun connect() {
        val ip = _uiState.value.serverIp.trim()
        val baseUrl = try {
            repository.baseUrl(ip)
        } catch (error: IllegalArgumentException) {
            _uiState.value = _uiState.value.copy(errorMessage = error.message)
            return
        }
        pollingJob?.cancel()
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(loading = true, errorMessage = null)
            runCatching { repository.health(baseUrl) }
                .onSuccess { health ->
                    if (!health.modelLoaded) {
                        _uiState.value = _uiState.value.copy(
                            loading = false,
                            errorMessage = "Server responded, but best.pt is not loaded.",
                        )
                        return@onSuccess
                    }
                    settings.saveServerIp(ip)
                    _uiState.value = _uiState.value.copy(
                        serverIp = ip,
                        baseUrl = baseUrl,
                        connected = true,
                        loading = false,
                        health = health,
                    )
                    refresh(silent = true)
                    startPolling()
                }
                .onFailure { error ->
                    _uiState.value = _uiState.value.copy(
                        loading = false,
                        connected = false,
                        errorMessage = friendlyMessage(error),
                    )
                }
        }
    }

    fun disconnect() {
        pollingJob?.cancel()
        _uiState.value = _uiState.value.copy(
            connected = false,
            baseUrl = "",
            health = null,
            stats = null,
            detections = emptyList(),
            errorMessage = null,
        )
    }

    fun refresh(silent: Boolean = false) {
        val baseUrl = _uiState.value.baseUrl
        if (baseUrl.isBlank()) return
        viewModelScope.launch {
            if (!silent) _uiState.value = _uiState.value.copy(loading = true)
            runCatching {
                Triple(
                    repository.health(baseUrl),
                    repository.stats(baseUrl),
                    repository.detections(baseUrl),
                )
            }.onSuccess { (health, stats, detections) ->
                _uiState.value = _uiState.value.copy(
                    connected = true,
                    loading = false,
                    health = health,
                    stats = stats,
                    detections = detections,
                    errorMessage = if (health.databaseStatus.startsWith("degraded")) {
                        "MongoDB is degraded; the server is using memory fallback."
                    } else null,
                )
            }.onFailure { error ->
                _uiState.value = _uiState.value.copy(
                    connected = false,
                    loading = false,
                    errorMessage = friendlyMessage(error),
                )
                pollingJob?.cancel()
            }
        }
    }

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (isActive) {
                delay(4_000)
                refresh(silent = true)
            }
        }
    }

    private fun friendlyMessage(error: Throwable): String = when (error) {
        is IllegalArgumentException -> error.message ?: "The server IP is invalid."
        is SocketTimeoutException -> "Connection timed out. Check the IP, Wi-Fi, and Windows Firewall."
        is ConnectException -> "The server is offline or port 5000 is unreachable."
        is ApiException -> "Server request failed (HTTP ${error.statusCode})."
        is JSONException -> "The server returned invalid JSON."
        else -> "Could not connect to the laptop server. Check the IP and network."
    }
}
