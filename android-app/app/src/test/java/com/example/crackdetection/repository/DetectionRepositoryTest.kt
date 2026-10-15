package com.example.crackdetection.repository

import org.junit.Assert.assertEquals
import org.junit.Test

class DetectionRepositoryTest {
    private val repository = DetectionRepository()

    @Test
    fun validIpv4BuildsExpectedServerUrl() {
        assertEquals("http://192.168.1.10:5000", repository.baseUrl("192.168.1.10"))
    }

    @Test(expected = IllegalArgumentException::class)
    fun fullHttpUrlIsRejectedBecauseUiAcceptsIpv4Only() {
        repository.baseUrl("http://192.168.1.10:5000")
    }

    @Test(expected = IllegalArgumentException::class)
    fun outOfRangeIpv4IsRejected() {
        repository.baseUrl("192.168.1.999")
    }
}
