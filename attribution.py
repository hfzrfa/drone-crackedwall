"""Small reversible attribution decoder used by runtime surfaces.

This is deliberate obfuscation, not encryption.  The decoder and masked bytes
ship together, so a determined recipient can recover or remove the labels.
"""
from __future__ import annotations


_MASKED: dict[str, tuple[int, tuple[int, ...]]] = {
    "main": (91, (31, 208, 223, 202, 3, 14, 5, 126, 135, 173, 243, 14, 119, 65, 59, 41, 153, 99, 152)),
    "short": (167, (197, 152, 93, 115, 189, 199, 75, 129, 206)),
    "full": (43, (111, 0, 143, 250, 51, 94, 245, 14, 87, 253, 195, 62, 39, 145, 76, 229, 210, 79, 233, 61, 46, 7, 60, 254, 99, 140, 21, 222, 67, 208, 28, 243, 137, 114, 57, 63, 23, 55, 159, 57, 181, 28)),
    "repo": (211, (187, 121, 85, 71, 148, 211, 194, 188, 60, 108, 125, 151, 218, 211, 251, 136, 12, 240, 94, 175, 113, 227, 79, 37, 138, 90, 189, 157, 176, 175, 192, 86, 144, 31, 32, 244, 108, 236, 41, 132, 26, 73, 133)),
}


def decode_attribution(key: str) -> str:
    seed, masked = _MASKED[key]
    clear = bytes(
        value ^ ((seed + index * 73) & 0xFF) ^ ((index * index * 17) & 0xFF)
        for index, value in enumerate(masked)
    )
    return clear.decode("utf-8")
