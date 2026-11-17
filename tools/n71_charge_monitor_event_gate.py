#!/usr/bin/env python3
"""Validate a fresh, still-active bounded SN2400 charge monitor event.

A loaded module does not prove that its guarded input lease remains active:
monitor-stop restores the input limit while leaving the module resident.
This gate consumes existing kernel telemetry and never changes hardware.
"""
import re


def verify_active_charge_monitor(text, uptime, expected_input_ua=500000,
                                 max_age_s=8.0):
    events = re.findall(r"^\[\s*([0-9.]+)\] n71-sn2400-trial: (.+)$",
                        text, re.M)
    if not events:
        raise RuntimeError("charger monitor telemetry absent")
    timestamp, message = events[-1]
    age = float(uptime) - float(timestamp)
    if age < -1 or age > max_age_s:
        raise RuntimeError("charger monitor telemetry is stale")
    if not message.startswith(("MONITOR ", "APPLIED ")):
        raise RuntimeError("charger input lease stopped or restored: " + message)
    current = re.search(r"\binput_uA=([0-9]+)\b", message)
    voltage = re.search(r"\bVBUS_uV=([0-9]+)\b", message)
    if not current or int(current.group(1)) != expected_input_ua:
        raise RuntimeError("charger monitor does not confirm qualified input limit")
    if not voltage or not 4400000 <= int(voltage.group(1)) <= 5500000:
        raise RuntimeError("charger monitor VBUS outside qualified range")
    return age
