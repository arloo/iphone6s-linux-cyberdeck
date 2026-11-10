#!/usr/bin/env python3
"""Evaluate an offline, local Linux AArch64 EVDEV touch-event recording.

This tool does not read hardware directly, use USB, or publish recordings.
Phone-side manual capture: read ONLY the genuine touch /dev/input/eventX into
a private RAM file, then transfer locally; never commit raw binary recordings.
Input ABI: little-endian AArch64 struct input_event (24 bytes).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

EVENT = struct.Struct("<qqHHi")  # tv_sec, tv_usec, type, code, signed value
EV_SYN, EV_ABS = 0, 3
SYN_REPORT = 0
ABS_MT_SLOT = 47
ABS_MT_POSITION_X, ABS_MT_POSITION_Y = 53, 54
ABS_MT_TRACKING_ID = 57
MAX_RECORDING_BYTES = 16 * 1024 * 1024


def check_recording(raw: bytes, width: int = 750, height: int = 1334) -> dict:
    """Inspect coordinates, tracking and frames without exposing timestamps."""
    if len(raw) % EVENT.size or len(raw) > MAX_RECORDING_BYTES:
        raise ValueError("recording is not aligned to AArch64 input_event frames")
    if width < 1 or height < 1:
        raise ValueError("invalid framebuffer dimensions")
    slots: dict[int, dict] = {}
    current_slot = 0
    tracking_ids: set[int] = set()
    released_tracking_ids: set[int] = set()
    coordinates = 0
    out_of_bounds = 0
    simultaneous_frames = 0
    syn_frames = 0
    min_x, min_y = width, height
    max_x = max_y = -1
    longest_drag = 0
    edge_coverage: set[str] = set()

    for offset in range(0, len(raw), EVENT.size):
        _seconds, _micros, kind, code, value = EVENT.unpack_from(raw, offset)
        if kind == EV_ABS and code == ABS_MT_SLOT:
            if not 0 <= value < 32:
                raise ValueError("invalid multitouch slot")
            current_slot = value
        elif kind == EV_ABS and code == ABS_MT_TRACKING_ID:
            if value < 0:
                departing = slots.pop(current_slot, None)
                if departing and departing["origin"] is not None:
                    released_tracking_ids.add(departing["tracking_id"])
            else:
                tracking_ids.add(value)
                slots[current_slot] = {
                    "tracking_id": value, "x": None, "y": None, "origin": None
                }
        elif kind == EV_ABS and code in (ABS_MT_POSITION_X, ABS_MT_POSITION_Y):
            state = slots.get(current_slot)
            if state is not None:
                state["x" if code == ABS_MT_POSITION_X else "y"] = value
        elif kind == EV_SYN and code == SYN_REPORT:
            syn_frames += 1
            present = 0
            for s in slots.values():
                x, y = s["x"], s["y"]
                if x is None or y is None:
                    continue
                present += 1
                coordinates += 1
                if not (0 <= x < width and 0 <= y < height):
                    out_of_bounds += 1
                    continue
                min_x, min_y = min(min_x, x), min(min_y, y)
                max_x, max_y = max(max_x, x), max(max_y, y)
                if x <= 35: edge_coverage.add("left")
                if x >= width - 36: edge_coverage.add("right")
                if y <= 35: edge_coverage.add("top")
                if y >= height - 36: edge_coverage.add("bottom")
                if s["origin"] is None:
                    s["origin"] = (x, y)
                sx, sy = s["origin"]
                longest_drag = max(longest_drag, abs(x - sx), abs(y - sy))
            if present >= 2:
                simultaneous_frames += 1

    # A single static coordinate is not a completed usable tap: require
    # an actual tracking lifecycle with SYN_REPORT and release. CI synthetic
    # data may exercise this logic, but cannot qualify physical hardware.
    basic = (
        len(released_tracking_ids) >= 1 and coordinates > 0
        and syn_frames >= 2 and out_of_bounds == 0
    )
    full = (
        basic and len(released_tracking_ids) >= 2
        and simultaneous_frames >= 2
        and longest_drag >= 100 and len(edge_coverage) == 4
    )
    return {
        "schema_version": 1,
        "source": "private_evdev_binary",
        "framebuffer": [width, height],
        "syn_frames": syn_frames,
        "contact_tracking_ids": len(tracking_ids),
        "released_contact_ids": len(released_tracking_ids),
        "coordinate_samples": coordinates,
        "out_of_bounds_samples": out_of_bounds,
        "x_range": None if max_x < 0 else [min_x, max_x],
        "y_range": None if max_y < 0 else [min_y, max_y],
        "simultaneous_two_contact_frames": simultaneous_frames,
        "max_single_contact_axis_drag_pixels": longest_drag,
        "edge_coverage": sorted(edge_coverage),
        "basic_coordinates_pass": basic,
        "full_multitouch_pass": full,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--width", type=int, default=750)
    p.add_argument("--height", type=int, default=1334)
    p.add_argument("--require", choices=["basic", "full"], default="basic")
    args = p.parse_args()
    path = args.input.expanduser()
    if not path.is_file() or path.is_symlink():
        p.error("input must be a private regular recording file")
    if path.stat().st_size > MAX_RECORDING_BYTES:
        p.error("recording exceeds bounded memory limit")
    result = check_recording(path.read_bytes(), args.width, args.height)
    print(json.dumps(result, indent=2, sort_keys=True))
    passed = result["full_multitouch_pass"] if args.require == "full" else result["basic_coordinates_pass"]
    print("HARDWARE_EVDEV_ACCEPTANCE=" + ("PASS" if passed else "NOT_YET"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
