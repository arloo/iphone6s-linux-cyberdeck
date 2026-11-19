#!/usr/bin/env python3
"""Analyze sanitized S3E gate booleans from one physical boot, without MMIO.

This is a log decoder, NOT a hardware readiness check. In particular,
queue-register retirement is NOT DMA/HMB/DART/NVMMU retirement, and never
implies NAND read/write access.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

PHASE_KEYS = (
    "identify_armed", "shutdown_attempted", "shutdown_ok", "disable_ok",
    "inner_ok", "master_off", "hmb_checked", "hmb_owned"
)
REGISTER_KEYS = (
    "shn", "disable", "master_off", "controller_zero", "command_words_2",
    "reset_low", "prepared", "regs_saved", "dart_mapped", "hmb_owned",
    "hmb_zero", "intms_bit0", "queue_owned"
)
LABEL_PHASE = "ADMIN_QUEUE_RETIRE_PHASE_GATES"
LABEL_REGISTER = "ADMIN_QUEUE_RETIRE_GATES"
LABEL_RESULT = "ADMIN_QUEUE_RETIRE_PROBE"


def _fields(line: str, label: str, keys: tuple[str, ...]) -> dict[str, int] | None:
    if label not in line:
        return None
    tail = line.partition(label)[2]
    matches = re.findall(r"(?<!\w)([a-z][a-z_0-9]*)=([^\s]+)", tail)
    allowed = dict()
    for k, v in matches:
        if k not in keys:
            continue
        if k in allowed or v not in ("0", "1"):
            return None
        allowed[k] = int(v)
    if set(allowed) != set(keys):
        return None
    return allowed


def decode(content: str) -> tuple[str, list[str]]:
    """Return fail-closed classification and allowlisted non-secret reasons."""
    if "N71_ONE_SHOT_START" in content:
        content = content.rsplit("N71_ONE_SHOT_START", 1)[-1]
    lines = content.splitlines()
    phase, register = None, None
    phase_refused = False
    register_refused = False
    queue_cleared = False
    for line in lines:
        if LABEL_PHASE in line:
            phase = _fields(line, LABEL_PHASE, PHASE_KEYS)
        if LABEL_REGISTER in line:
            register = _fields(line, LABEL_REGISTER, REGISTER_KEYS)
        if LABEL_RESULT in line and "refused=1" in line:
            phase_refused |= "phase_gate=0" in line
            register_refused |= "exact_gate=0" in line
        if LABEL_RESULT in line and "armed=1" in line and "queue_regs_zero=1" in line:
            queue_cleared = True
    if phase_refused:
        if phase is None:
            return "PHASE_REFUSED_UNCLASSIFIED", []
        failures = [k for k in PHASE_KEYS if phase[k] == 0]
        if phase["hmb_checked"] == 0:
            failures = [k for k in failures if k != "hmb_owned"]
        return "PHASE_REFUSED", failures
    if register_refused:
        if register is None:
            return "REGISTER_REFUSED_UNCLASSIFIED", []
        return "REGISTER_REFUSED", [k for k in REGISTER_KEYS if register[k] == 0]
    if queue_cleared:
        return "QUEUE_REGS_ZERO_ONLY", []
    return "NOT_OBSERVED", []


def read_private_log(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing, non-regular or symlinked input log")
    if path.stat().st_size > 512 * 1024:
        raise ValueError("Input log exceeds 512 KiB")
    return path.read_text(encoding="utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="Classify one S3E boolean gate trace (read-only)")
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    stage, failed = decode(read_private_log(args.log))
    print("S3E_STAGE=" + stage)
    print("FAILED_GATES=" + (",".join(failed) if failed else "none_observable"))
    print("DMA_QUARANTINE=REQUIRED")
    print("NAND_BLOCK_ACCESS=NOT_PROVEN")


if __name__ == "__main__":
    main()
