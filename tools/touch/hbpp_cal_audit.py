#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic HBPP N71 calibration packet audit. Never reads device data.

Both encoders produce *test-only* packets with synthetic payloads. A byte-for-
byte match does not prove the N71 controller will accept the transmission.
No USB, SPI, MMIO or phone interactions are performed.
"""
from __future__ import annotations

import struct

CMD_DATA = 0x3001
TARGET_CAL = 0x10009000
ACK_DATA = 0x4BC1
REQ_CAL = 0x1F01
IDLE = 0x4879
NOP = 0x18E1
MAX_POLLS = 50


def _wire32(value: int) -> bytes:
    """32-bit HBPP number as big-endian 16-bit words, low half first."""
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("HBPP value outside 32-bit range")
    return struct.pack(">HH", value & 0xFFFF, value >> 16)


def encode_n71_cal(calibration: bytes, addr: int = TARGET_CAL,
                   swap_payload_words: bool = True) -> bytes:
    """Mirror the *observed experimental code*, using synthetic input only."""
    if not 1 <= len(calibration) <= 4096:
        raise ValueError("calibration length outside bounded audit range")
    padded = (len(calibration) + 3) & ~3
    source = calibration.ljust(padded, b"\0")
    wire_payload = bytearray(source)
    if swap_payload_words:
        for i in range(0, padded, 2):
            wire_payload[i], wire_payload[i + 1] = source[i + 1], source[i]
    hdr_fields = struct.pack(">H", padded // 4) + _wire32(addr)
    checksum = sum(hdr_fields) & 0xFFFF
    header = struct.pack(">H", CMD_DATA) + hdr_fields + struct.pack(">H", checksum)
    trailer = _wire32(sum(source))
    return header + bytes(wire_payload) + trailer


def independent_spi16_reference(calibration: bytes,
                                 addr: int = TARGET_CAL) -> bytes:
    """Separate legacy-struct calculation and per-16-bit-word SPI conversion.

    This is a software consistency oracle, *not* a hardware protocol oracle.
    """
    if not 1 <= len(calibration) <= 4096:
        raise ValueError("calibration length outside bounded audit range")
    padded = (len(calibration) + 3) & ~3
    source = calibration.ljust(padded, b"\0")
    little_fields = struct.pack("<HI", padded // 4, addr)
    little_header = struct.pack("<H", CMD_DATA) + little_fields
    little_header += struct.pack("<H", sum(little_fields) & 0xFFFF)
    little_frame = little_header + source + struct.pack("<I", sum(source))
    return b"".join(little_frame[i:i + 2][::-1]
                    for i in range(0, len(little_frame), 2))


def optional_nop_prefix(frame: bytes, enable: bool = False) -> bytes:
    """Compare a framed DATA packet with the documented NOP+DATA sequence.

    This is an *offline hypothesis*. It does not assert the N71 calibration
    handshake requires a prefix, and never interacts with hardware.
    """
    inspect_frame(frame)  # Reject malformed DATA packets before wrapping.
    return struct.pack(">H", NOP) + frame if enable else frame


def inspect_frame(frame: bytes) -> dict[str, int]:
    if len(frame) < 18 or len(frame) % 2:
        raise ValueError("invalid frame size")
    cmd, nwords = struct.unpack_from(">HH", frame)
    if cmd != CMD_DATA:
        raise ValueError("not an HBPP DATA frame")
    size = nwords * 4
    if len(frame) != 10 + size + 4:
        raise ValueError("word count and frame size disagree")
    addr_lo, addr_hi = struct.unpack_from(">HH", frame, 4)
    checksum_hdr = struct.unpack_from(">H", frame, 8)[0]
    checksum_calc = sum(frame[2:8]) & 0xFFFF
    if checksum_hdr != checksum_calc:
        raise ValueError("header checksum mismatch")
    sum_lo, sum_hi = struct.unpack_from(">HH", frame, 10 + size)
    checksum_payload = sum_lo | (sum_hi << 16)
    if checksum_payload != sum(frame[10:10 + size]):
        raise ValueError("data checksum mismatch")
    return {"length": len(frame), "payload_length": size,
            "address": addr_lo | (addr_hi << 16),
            "header_checksum": checksum_hdr, "data_checksum": checksum_payload}


def evaluate_ack(statuses: list[int]) -> str:
    """Treat transient status as pending, never as successful data ACK."""
    for status in statuses[:MAX_POLLS]:
        if status == ACK_DATA:
            return "ACK_DATA"
        if status in (REQ_CAL, IDLE, NOP, 0x0000, 0xFFFF):
            continue
        return "UNEXPECTED"
    return "TIMEOUT"


def main() -> None:
    # Synthetic vector: never substitute private 1024-byte calibration here.
    synthetic = bytes(range(256)) * 4
    frame = encode_n71_cal(synthetic)
    if frame != independent_spi16_reference(synthetic):
        raise SystemExit("FAIL: experimental and reference encoders disagree")
    meta = inspect_frame(frame)
    print("Synthetic HBPP audit PASS")
    for key in ("length", "payload_length", "address", "header_checksum",
                "data_checksum"):
        print(f"  {key}: {meta[key]:#x}" if key in ("address", "header_checksum",
                                                  "data_checksum")
              else f"  {key}: {meta[key]}")
    print("No real calibration data, SPI transfers or proprietary firmware used.")


if __name__ == "__main__":
    main()
