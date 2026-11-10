# N71/S8000 HBPP MEM_READ strict validation — experimental RFC

**Date:** 2026-11-10
**Hardware:** Samsung A9 iPhone 6s with a user-confirmed aftermarket display assembly.

## Why this changed

The actual replacement screen was confirmed by the user to work normally under iOS, including ordinary touchscreen gestures. The screen may have different visual quality from an original Apple panel, but this is **not** evidence that its touch digitizer is defective. The iPhone 6s supports Retina HD with 3D Touch; it does **not** have the later True Tone display feature (Apple [technical specifications](https://support.apple.com/it-it/111952)).

Our prior Linux RAM-only test obtained an authentic N71 HBPP status response and controller-version word but failed to receive calibration `ACK_DATA=0x4bc1`. The mismatch is still open. Neither a screen revision mismatch nor the checksum/pacing hypothesis has been demonstrated as its root cause.

## Additional source-level correctness defect

In the experimental Apple Z2 driver, `apple_z2_hbpp_read_reg()` previously parsed the four-byte register value and **returned 0 (success)** even when the two-byte response status was not `READ_DATA=0x4c39` or the reply checksum did not equal the sum of the four data bytes. It merely logged a warning with raw reply bytes.

The isolated patch `patches/0002-n71-hbpp-read-strict-validation-rfc.patch` now:

- Verifies status and checksum **before assigning** the register value.
- Returns `-EBADMSG` for an invalid response, rather than passing an unvalidated silicon version into the firmware/calibration branch logic.
- Logs only the status and target register address, without dumping the raw response bytes.

This patch is deliberately independent of the prior touch-power rollback RFC. It applies to both the clean N71 source and the earlier power-rollback source tree.

## Validation

- The modified `apple_z2.o` compiled successfully for AArch64 using the same Clang-based kernel configuration, in an isolated **offline** build directory.
- The source-level patch is clean and does not contain Apple firmware or private calibration.
- `tools/touch/hbpp_read_validator.py` implements a **synthetic, read-only** reference for the eight-byte `READ_DATA` reply.
- The tests reject wrong status, bad checksum, truncated or overlong packets, and malformed synthetic version values; they also check the kernel source contract.
- This proves only parsing and error-handling behavior in the test model. It does **not** prove that Linux can initialize this aftermarket screen.

The separate [bounded calibration ACK polling correction](N71_HBPP_ACK_POLL_STRESS_RFC.md) covers an additional, independently identified source defect: the initial \`REQ_CAL\` status was incorrectly terminal in the DATA ACK poller. Neither correction has yet produced a physical Z2 calibration success.

## Next hardware experiment

Maintain the currently booted `touch_ref` provider-only Linux session with the Z2 child disabled. Once the clock, Chestnut analog and core-supply snapshots, reset GPIO and one-variable recovery procedure are reviewed, obtain a bounded **status-only** HBPP controller-identification trace. Compare valid version/status/ACK sequences from this installed panel with the firmware/calibration requirements before attempting another full calibration upload.

Do not bypass the data-ACK requirement, silently accept `REQ_CAL` as success, spray arbitrary vendor opcodes or publish private firmware/calibration. The device remains a RAM-only test target and the original boot images remain preserved.
