package com.example.crackdetection

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.example.crackdetection.ui.MainScreen
import com.example.crackdetection.ui.theme.CrackDetectionTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            CrackDetectionTheme {
                MainScreen()
            }
        }
    }
}
