"""Offline N71 HBPP MEM_READ reply validator.

Synthetic protocol reference only; does not access hardware, firmware,
private calibration or per-device identifiers.
"""
from __future__ import annotations

READ_DATA = 0x4C39
REPLY_SIZE = 8


def decode_register_reply(reply: bytes) -> int:
    """Return validated 32-bit register word or raise ValueError.

    Wire format: BE status, BE low-word, BE high-word, BE checksum
    where checksum is an unsigned 16-bit sum of four register data bytes.
    """
    if len(reply) != REPLY_SIZE:
        raise ValueError("unexpected HBPP register read reply length")
    status = int.from_bytes(reply[:2], "big")
    if status != READ_DATA:
        raise ValueError("unexpected HBPP register reply status")
    body = reply[2:6]
    got_checksum = int.from_bytes(reply[6:8], "big")
    if got_checksum != (sum(body) & 0xFFFF):
        raise ValueError("invalid HBPP register reply checksum")
    lo = int.from_bytes(body[:2], "big")
    hi = int.from_bytes(body[2:], "big")
    return lo | (hi << 16)


def make_synthetic_reply(value: int) -> bytes:
    """Create a local test frame; not a firmware/calibration serializer."""
    if not (0 <= value <= 0xFFFFFFFF):
        raise ValueError("value out of range")
    body = (value & 0xFFFF).to_bytes(2, "big") + (value >> 16).to_bytes(2, "big")
    return READ_DATA.to_bytes(2, "big") + body + sum(body).to_bytes(2, "big")
