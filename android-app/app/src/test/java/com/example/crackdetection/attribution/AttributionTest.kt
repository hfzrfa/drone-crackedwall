package com.example.crackdetection.attribution

import org.junit.Assert.assertEquals
import org.junit.Test

class AttributionTest {
    private fun text(vararg codePoints: Int): String = codePoints.map(Int::toChar).joinToString("")

    @Test
    fun decoderRestoresAboutIdentityAndRepository() {
        assertEquals(
            text(68, 101, 118, 101, 108, 111, 112, 101, 100, 32, 98, 121, 32, 72, 97, 102, 105, 122, 32, 82, 97, 102, 105, 101, 32, 65, 100, 105, 116, 121, 97, 32, 183, 32, 64, 104, 102, 122, 114, 102, 97),
            Attribution.full(),
        )
        assertEquals(
            text(104, 116, 116, 112, 115, 58, 47, 47, 103, 105, 116, 104, 117, 98, 46, 99, 111, 109, 47, 104, 102, 122, 114, 102, 97, 47, 100, 114, 111, 110, 101, 45, 99, 114, 97, 99, 107, 101, 100, 119, 97, 108, 108),
            Attribution.repository(),
        )
    }
}
