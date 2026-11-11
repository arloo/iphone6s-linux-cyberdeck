# 2026-11-11 — Offline A9 six-patch build and exact RAM payload reproducibility

**Date:** 2026-11-11. **Classification: OFFLINE and BUILD ONLY.** No live iPhone kernel, peripheral or calibration qualification occurred in this verification.

## Scope and source provenance

The build used the clean public HoolockLinux/linux source pinned in manifests/upstreams.json, commit **68aadac820d01d0cd4efbd1fefd4c45f23be0a51**, checked out into an isolated temporary worktree. It applied all six reviewed RFC patches, **0001–0006**, in order:

- 0001: Z2 rollback and touch reference-clock base.
- 0002: strict HBPP READ_DATA/status/checksum.
- 0003: bounded pending REQ_CAL while waiting for DATA ACK.
- 0004: bounded PMGR touch clock register-settling on rollback.
- 0005: optional NOP-prefixed calibration framing, hypothesis only.
- 0006: 256-byte segmented SPI transfers within one SPI message, hypothesis only.

The first four have a history of different hardware validation scopes; **neither RFC 0005 nor RFC 0006 is a validated fix for the lost-USB calibration experiment**. All six patches were compiled together in an isolated ARM64 default-config build using the published scripts/check_kernel_rfc.sh gate. This default-config compile is **not** the private N71 hardware boot configuration.

## Verified outputs

| Gate | Result |
| --- | --- |
| Pinned upstream Linux source SHA and clean state | PASS |
| All six RFC patches applied sequentially without conflicts | PASS |
| ARM64 kernel prepare and compiler dependencies | PASS |
| Apple touch clock driver object, clk-apple-touch.o | PASS, AArch64 ELF relocatable |
| Apple Z2 touchscreen driver object, apple_z2.o | PASS, AArch64 ELF relocatable |
| Temporary worktree cleanup; pinned source unmodified | PASS |
| Python offline protocol, privacy, CI and EVDEV synthetic suite | **136/136 PASS** |
| Synthetic calibration HBPP packet audit | PASS |
| Source manifests, S8000/S8003 matrix and sanitized evidence validation | PASS |

**These object files are not bootable** and are not equivalent to a complete production kernel, a live ACK_DATA response or a touchscreen that reports coordinates.

## Exact RAM payload reproducibility — separate operator-input test

The versioned open-source packer scripts/pack_ram.py was executed using already existing **local operator-controlled inputs** of the previously successful N71 build #5:

- Locally built m1n1 binary (not published).
- Both board-specific DTBs: s8000-n71 and s8003-n71m.
- Previously built ARM64 Image.gz.
- Existing local test initramfs.gz (not published).

The packer checked both DTB headers, both gzip CRCs and the non-overwrite output gate, then assembled the documented upstream m1n1 RAM-only concatenation in a temporary directory.

| Check | Result |
| --- | --- |
| Reconstructed payload size | **11,751,897 bytes** |
| Reconstructed SHA-256 | **0e4d6aca08d40f49233a3180fcd4ee0229ba042038759fa1e4342fccbc456687** |
| Reference build #5 RAM payload SHA-256 | **0e4d6aca08d40f49233a3180fcd4ee0229ba042038759fa1e4342fccbc456687** |
| Byte-for-byte comparison of full files | **PASS** |
| Temporary second payload | Removed after comparison |
| Read/write to iPhone or iOS storage | None |

This demonstrates **byte-identical repackaging from the same available inputs**, not that every upstream binary or proprietary board parameter can be rebuilt from scratch without an independently supplied artifact. It is not an S8003 hardware success despite including an S8003 DTB.

## Physical state and safe next gate

At the start of today's session the Dell xps-ai remained remotely online and AC-powered. The iPhone presented on USB as **05ac:12a8**, rather than the prior Linux USB gadget **05ac:4142**, and Linux gadget ping returned no replies. No remote SPI, DFU or firmware experiment was attempted.

The incident from 2026-11-10 during a single 1,040-byte NOP-prefixed calibration attempt remains open. It produced host-side USB disconnection, not an observed ACK_DATA. See the incident report N71_CAL_NOP_USB_DISCONNECT_2026_11_10.md. The next hardware gate requires attended recovery to a known-good RAM kernel, independent baseline audit, and only then short, bounded, read-only HBPP status transactions. The long calibration write must not be repeated unattended.

## GitHub Actions authorization and security

The project stores a versioned workflow template at ci/verify.yml with visibly distinct **OFFLINE**, **BUILD** and opt-in kernel object jobs. It is **not** installed under .github/workflows/ in the remote repository, because the available GitHub credentials were previously rejected for workflow-write. The duplicate untracked local workflow file was deleted only after its byte-for-byte match to the tracked template was confirmed. **No cloud CI job is claimed to have run.**

All hardware claims remain reviewed and separately recorded in the S8000 matrix. S8003 hardware status remains NOT TESTED across every peripheral. Neither a firmware blob, private calibration, device identity, SSH key nor compiled private diagnostic module is included in this publication.
