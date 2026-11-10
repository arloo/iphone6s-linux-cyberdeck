#!/usr/bin/env python3
"""Offline-only N71/S8000 Z2 touch power-state audit.

This module has NO device access and makes NO register writes. It evaluates
*provided* register readbacks against known A9 hardware experiment snapshots.
A PASS is evidence of readback consistency only, never proof of physical
touch voltage, a working 32 kHz signal, or safe Z2 firmware loading.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

CLK_DISABLE = 1 << 31
CLK_ENABLE = 1 << 19
CLK_BUSY = 1 << 18
CLK_DIV_MASK = 0x3FF
CLK_KNOWN_MASK = CLK_DISABLE | CLK_ENABLE | CLK_BUSY | CLK_DIV_MASK
CHESTNUT_TOUCH_MASK = 0x10
CORE_TOUCH_MASK = 0x01

# Previously observed on the Samsung-fab A9 reference board. These are
# conservative guard signatures, NOT universal values for other iPhones.
HISTORICAL_CLOCK_OFF = 0x800002EE
HISTORICAL_CHESTNUT_OFF = 0x0F
HISTORICAL_CORE_ON = 0x01


@dataclass(frozen=True)
class Snapshot:
    clock: int
    analog: int
    core: int
    reset_level: Optional[int] = None


def _valid_snapshot(snapshot: Snapshot) -> list[str]:
    errors: list[str] = []
    if not (0 <= snapshot.clock <= 0xFFFFFFFF):
        errors.append("clock is not a 32-bit register value")
    elif snapshot.clock & ~CLK_KNOWN_MASK:
        errors.append("clock has unknown bits set")
    if not (0 <= snapshot.analog <= 0xFF):
        errors.append("analog regulator is not an 8-bit register")
    if not (0 <= snapshot.core <= 0xFF):
        errors.append("core regulator is not an 8-bit register")
    if snapshot.reset_level is not None and snapshot.reset_level not in (0, 1):
        errors.append("GPIO reset level is invalid")
    return errors


def audit(before: Snapshot, during: Snapshot, after: Snapshot) -> list[str]:
    """Return a list of test failures; an empty list means matching readbacks.

    'before' and 'after' must be independent physical readbacks, not expected
    values substituted by the caller. A reset baseline is required to claim
    the full power-path safety gate.
    """
    errors: list[str] = []
    for stage, value in (("before", before), ("during", during), ("after", after)):
        errors += [stage + ": " + detail for detail in _valid_snapshot(value)]
    if errors:
        return errors

    if before.clock != HISTORICAL_CLOCK_OFF:
        errors.append("initial touch clock differs from historical disabled baseline")
    if before.analog != HISTORICAL_CHESTNUT_OFF:
        errors.append("initial analog regulator differs from historical disabled baseline")
    if (before.core & CORE_TOUCH_MASK) != HISTORICAL_CORE_ON:
        errors.append("initial core regulator enable bit is not on")

    if not (during.clock & CLK_ENABLE) or (during.clock & CLK_DISABLE):
        errors.append("touch clock did not report enabled state")
    if during.clock & CLK_BUSY:
        errors.append("touch clock reports busy")
    div = during.clock & CLK_DIV_MASK
    if div == 0 or not (32000 <= 24000000 / div <= 33500):
        errors.append("active touch clock divider gives implausible reference rate")

    if (during.analog ^ before.analog) != CHESTNUT_TOUCH_MASK:
        errors.append("analog regulator changed bits beyond expected touch-enable mask")
    if during.core != before.core:
        errors.append("core regulator register changed unexpectedly")

    if after.clock != before.clock:
        errors.append("touch clock not restored to exact original word")
    if after.analog != before.analog:
        errors.append("analog regulator not restored to exact original byte")
    if after.core != before.core:
        errors.append("core regulator not restored to exact original byte")

    if before.reset_level is None or after.reset_level is None:
        errors.append("reset GPIO baseline/readback missing")
    elif after.reset_level != before.reset_level:
        errors.append("reset GPIO not restored to original level")
    return errors


if __name__ == "__main__":
    print("N71 register audit is OFFLINE ONLY; import Snapshot and audit()")
    print("A PASS requires supplied real readbacks and does not validate electrical signaling")
