package com.example.crackdetection.attribution

/** Reversible masking only; the shipped decoder intentionally makes recovery possible. */
object Attribution {
    private fun reveal(masked: IntArray, seed: Int): String {
        val bytes = ByteArray(masked.size) { index ->
            (masked[index] xor ((seed + index * 73) and 0xff) xor ((index * index * 17) and 0xff)).toByte()
        }
        return bytes.toString(Charsets.UTF_8)
    }

    fun full(): String = reveal(
        intArrayOf(111, 0, 143, 250, 51, 94, 245, 14, 87, 253, 195, 62, 39, 145, 76, 229, 210, 79, 233, 61, 46, 7, 60, 254, 99, 140, 21, 222, 67, 208, 28, 243, 137, 114, 57, 63, 23, 55, 159, 57, 181, 28),
        43,
    )

    fun repository(): String = reveal(
        intArrayOf(187, 121, 85, 71, 148, 211, 194, 188, 60, 108, 125, 151, 218, 211, 251, 136, 12, 240, 94, 175, 113, 227, 79, 37, 138, 90, 189, 157, 176, 175, 192, 86, 144, 31, 32, 244, 108, 236, 41, 132, 26, 73, 133),
        211,
    )
}
