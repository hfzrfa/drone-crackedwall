package com.example.crackdetection.ui

import android.annotation.SuppressLint
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.example.crackdetection.R
import com.example.crackdetection.model.Detection
import com.example.crackdetection.model.StatsResponse
import com.example.crackdetection.viewmodel.MainUiState
import com.example.crackdetection.viewmodel.MainViewModel
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale

@Composable
fun MainScreen(viewModel: MainViewModel = viewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    Scaffold(modifier = Modifier.fillMaxSize()) { padding ->
        if (state.connected) {
            ConnectedContent(
                state = state,
                onRefresh = { viewModel.refresh() },
                onDisconnect = viewModel::disconnect,
                modifier = Modifier.padding(padding),
            )
        } else {
            ConnectContent(
                state = state,
                onIpChange = viewModel::setServerIp,
                onConnect = viewModel::connect,
                modifier = Modifier.padding(padding),
            )
        }
    }
}

@Composable
private fun ConnectContent(
    state: MainUiState,
    onIpChange: (String) -> Unit,
    onConnect: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxSize().statusBarsPadding().padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(stringResource(R.string.title), style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Text("Connect to the Flask server on the same Wi-Fi or hotspot.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(28.dp))
        OutlinedTextField(
            value = state.serverIp,
            onValueChange = onIpChange,
            modifier = Modifier.fillMaxWidth(),
            label = { Text(stringResource(R.string.server_ip)) },
            placeholder = { Text(stringResource(R.string.ip_hint)) },
            singleLine = true,
            enabled = !state.loading,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        )
        state.errorMessage?.let {
            Spacer(Modifier.height(10.dp))
            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
        }
        Spacer(Modifier.height(18.dp))
        Button(onClick = onConnect, enabled = !state.loading, modifier = Modifier.fillMaxWidth().height(52.dp)) {
            if (state.loading) {
                CircularProgressIndicator(modifier = Modifier.width(22.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
            } else {
                Text(stringResource(R.string.connect))
            }
        }
    }
}

@Composable
private fun ConnectedContent(
    state: MainUiState,
    onRefresh: () -> Unit,
    onDisconnect: () -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize().statusBarsPadding().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column {
                    Text(stringResource(R.string.title), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text("Server: ${state.serverIp}", style = MaterialTheme.typography.bodySmall)
                }
                Text(stringResource(R.string.online), color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
            }
        }
        state.errorMessage?.let { message ->
            item { StatusMessage(message) }
        }
        item { SectionTitle(stringResource(R.string.live_detection)) }
        item { MjpegView(state.baseUrl) }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onRefresh, enabled = !state.loading) { Text(stringResource(R.string.refresh)) }
                OutlinedButton(onClick = onDisconnect) { Text(stringResource(R.string.disconnect)) }
            }
        }
        item { SectionTitle(stringResource(R.string.recent_detections)) }
        if (state.detections.isEmpty()) {
            item { Text(stringResource(R.string.no_detections), color = MaterialTheme.colorScheme.onSurfaceVariant) }
        } else {
            items(state.detections, key = { it.id }) { detection ->
                DetectionCard(detection, state.baseUrl)
            }
        }
        item { SectionTitle(stringResource(R.string.server_stats)) }
        item { StatsCard(state.stats, state.health?.databaseStatus.orEmpty()) }
        item { Spacer(Modifier.height(24.dp)) }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Column(modifier = Modifier.padding(top = 8.dp)) {
        Text(text, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.height(6.dp))
        HorizontalDivider()
    }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun MjpegView(baseUrl: String) {
    val html = """<html><head><meta name="viewport" content="width=device-width"></head><body style="margin:0;background:#17352e"><img src="$baseUrl/video" style="width:100%;height:100%;object-fit:contain" /></body></html>"""
    androidx.compose.ui.viewinterop.AndroidView(
        factory = { context ->
            WebView(context).apply {
                settings.javaScriptEnabled = false
                settings.allowFileAccess = false
                settings.allowContentAccess = false
                settings.domStorageEnabled = false
                webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean = true
                }
                loadDataWithBaseURL(baseUrl, html, "text/html", "UTF-8", null)
            }
        },
        update = { webView ->
            if (webView.tag != baseUrl) {
                webView.tag = baseUrl
                webView.loadDataWithBaseURL(baseUrl, html, "text/html", "UTF-8", null)
            }
        },
        onRelease = { webView -> webView.stopLoading(); webView.destroy() },
        modifier = Modifier.fillMaxWidth().height(230.dp).background(Color(0xFF17352E), RoundedCornerShape(14.dp)),
    )
}

@Composable
private fun DetectionCard(detection: Detection, baseUrl: String) {
    val imageUrl = if (detection.imageUrl.startsWith("http")) detection.imageUrl else "$baseUrl${detection.imageUrl.ifBlank { "/static/images/${detection.imageName}" }}"
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Row(modifier = Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            AsyncImage(
                model = ImageRequest.Builder(LocalContext.current).data(imageUrl).crossfade(true).build(),
                contentDescription = "Crack evidence ${detection.label}",
                modifier = Modifier.width(104.dp).height(78.dp).background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp)),
            )
            Spacer(Modifier.width(12.dp))
            Column {
                Text(detection.label, fontWeight = FontWeight.Bold)
                Text("Confidence: ${(detection.confidence * 100).toInt()}%")
                Text(formatTimestamp(detection.timestamp), style = MaterialTheme.typography.bodySmall)
                Text(detection.source, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun StatsCard(stats: StatsResponse?, databaseStatus: String) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Processed frames: ${stats?.framesProcessed ?: 0}")
            Text("Detections seen: ${stats?.detectionsSeen ?: 0}")
            Text("Saved detections: ${stats?.detectionsSaved ?: 0}")
            Text("Duplicate skips: ${stats?.duplicateSkips ?: 0}")
            Text("Processing FPS: ${stats?.processingFps ?: 0.0}")
            Text("Database: ${databaseStatus.ifBlank { "unknown" }}")
        }
    }
}

@Composable
private fun StatusMessage(message: String) {
    Box(modifier = Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.errorContainer, RoundedCornerShape(10.dp)).padding(12.dp)) {
        Text(message, color = MaterialTheme.colorScheme.onErrorContainer)
    }
}

private fun formatTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value).format(DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM).withLocale(Locale.getDefault()))
}.getOrDefault(value.ifBlank { "Unknown time" })
