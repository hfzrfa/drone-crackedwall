package com.example.crackdetection.storage

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "server_settings")

class SettingsRepository(private val context: Context) {
    private val serverIpKey = stringPreferencesKey("server_ip")
    val serverIp: Flow<String> = context.dataStore.data.map { preferences ->
        preferences[serverIpKey].orEmpty()
    }

    suspend fun saveServerIp(ip: String) {
        context.dataStore.edit { preferences -> preferences[serverIpKey] = ip }
    }
}
