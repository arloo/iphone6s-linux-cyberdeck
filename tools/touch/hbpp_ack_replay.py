"""Deterministic offline model of bounded N71 HBPP acknowledgment polling.

This is NOT a hardware oracle. It never accesses an iPhone, SPI, firmware, or
calibration bytes. It mirrors a proposed source-level branch condition.
"""
from __future__ import annotations

ACK_DATA = 0x4BC1
ACK_REG = 0x4AD1
REQ_CAL = 0x1F01
IDLE = 0x4879
NOP = 0x18E1
DEFAULT_POLL_LIMIT = 50

GENERIC_PENDING = frozenset((IDLE, NOP, 0x0000, 0xFFFF))


def classify_status(status: int, expected: int) -> str:
    """Return ACK, PENDING or ERROR for one observed 16-bit status word."""
    if not 0 <= status <= 0xFFFF:
        raise ValueError("status is not a 16-bit HBPP word")
    if expected not in (ACK_DATA, ACK_REG):
        raise ValueError("unexpected ACK type")
    if status == expected:
        return "ACK"
    if status in GENERIC_PENDING:
        return "PENDING"
    if expected == ACK_DATA and status == REQ_CAL:
        return "PENDING"
    return "ERROR"


def replay(statuses: list[int], expected: int = ACK_DATA,
           limit: int = DEFAULT_POLL_LIMIT) -> tuple[str, int]:
    """Return outcome and polls examined, with a strict finite upper bound."""
    if not 1 <= limit <= 300:
        raise ValueError("poll limit out of bounds")
    for n, status in enumerate(statuses[:limit], 1):
        result = classify_status(status, expected)
        if result == "ACK":
            return "ACK", n
        if result == "ERROR":
            return "UNEXPECTED", n
    return "TIMEOUT", min(limit, len(statuses))
