"""Synthetic-only EVDEV tests: never claim real panel acceptance from CI."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "evdev_acceptance", ROOT / "tools/touch/evdev_acceptance.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EV = struct.Struct("<qqHHi")


def event(kind: int, code: int, value: int) -> bytes:
    return EV.pack(0, 0, kind, code, value)


def frame(slot: int, x: int, y: int, tracking: int | None = None) -> bytes:
    parts = [event(3, 47, slot)]
    if tracking is not None:
        parts.append(event(3, 57, tracking))
    parts.extend([event(3, 53, x), event(3, 54, y), event(0, 0, 0)])
    return b"".join(parts)


class EvdevAcceptanceTests(unittest.TestCase):
    def test_empty_capture_never_passes(self):
        result = MODULE.check_recording(b"")
        self.assertFalse(result["basic_coordinates_pass"])

    def test_realistic_single_coordinate_basic_only(self):
        capture = (
            frame(0, 375, 667, tracking=7)
            + event(3, 47, 0) + event(3, 57, -1) + event(0, 0, 0)
        )
        result = MODULE.check_recording(capture)
        self.assertTrue(result["basic_coordinates_pass"])
        self.assertFalse(result["full_multitouch_pass"])
        self.assertEqual(result["x_range"], [375, 375])

    def test_rejects_out_of_range_coordinate(self):
        capture = frame(0, 750, 100, tracking=1)
        result = MODULE.check_recording(capture)
        self.assertFalse(result["basic_coordinates_pass"])
        self.assertEqual(result["out_of_bounds_samples"], 1)

    def test_rejects_unaligned_binary(self):
        with self.assertRaisesRegex(ValueError, "aligned"):
            MODULE.check_recording(b"\x00" * 13)

    def test_two_simultaneous_contacts_and_drag_and_edges(self):
        capture = (
            frame(0, 0, 0, tracking=1)
            + frame(1, 749, 1333, tracking=2)
            + frame(0, 400, 800)
            + frame(1, 349, 500)
            + event(3, 47, 0) + event(3, 57, -1) + event(0, 0, 0)
            + event(3, 47, 1) + event(3, 57, -1) + event(0, 0, 0)
        )
        result = MODULE.check_recording(capture)
        self.assertTrue(result["full_multitouch_pass"], result)
        self.assertEqual(result["simultaneous_two_contact_frames"], 3)
        self.assertEqual(
            result["edge_coverage"], ["bottom", "left", "right", "top"]
        )
        self.assertGreaterEqual(result["max_single_contact_axis_drag_pixels"], 100)

    def test_slot_release_removes_active_contact(self):
        capture = (
            frame(0, 25, 25, tracking=1)
            + event(3, 47, 0) + event(3, 57, -1) + event(0, 0, 0)
            + frame(1, 200, 300, tracking=2)
        )
        result = MODULE.check_recording(capture)
        self.assertEqual(result["contact_tracking_ids"], 2)
        self.assertEqual(result["simultaneous_two_contact_frames"], 0)
        self.assertFalse(result["full_multitouch_pass"])

    def test_unreleased_single_contact_is_not_a_usable_tap(self):
        result = MODULE.check_recording(frame(0, 250, 400, tracking=9))
        self.assertEqual(result["released_contact_ids"], 0)
        self.assertFalse(result["basic_coordinates_pass"])

    def test_two_contacts_without_release_are_not_full_multitouch(self):
        result = MODULE.check_recording(
            frame(0, 5, 5, tracking=1) + frame(1, 745, 1325, tracking=2)
            + frame(0, 400, 700) + frame(1, 300, 600)
        )
        self.assertFalse(result["full_multitouch_pass"])

    def test_no_tracking_id_is_not_evidence(self):
        capture = frame(0, 200, 400)
        result = MODULE.check_recording(capture)
        self.assertFalse(result["basic_coordinates_pass"])

    def test_rejects_bad_slot(self):
        capture = event(3, 47, 50) + event(0, 0, 0)
        with self.assertRaisesRegex(ValueError, "slot"):
            MODULE.check_recording(capture)

    def test_pass_is_not_derived_from_kernel_or_ci(self):
        result = MODULE.check_recording(frame(0, 12, 100, tracking=3))
        self.assertEqual(result["source"], "private_evdev_binary")
        self.assertNotIn("kernel", result)
        self.assertNotIn("device_id", result)


if __name__ == "__main__":
    unittest.main()
