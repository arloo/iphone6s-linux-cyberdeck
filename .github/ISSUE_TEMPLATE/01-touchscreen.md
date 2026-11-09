---
name: "Hardware: iPhone 6s touchscreen bring-up"
about: "Investigate and enable N71/S8000 multitouch under Linux"
title: "[TOUCH] Bring up the iPhone 6s touchscreen controller"
labels: ["hardware", "touchscreen", "help wanted"]
assignees: []
---

## Observed baseline
- iPhone 6s, Apple A9 Samsung `apple,n71` / `apple,s8000`.
- `CONFIG_INPUT_TOUCHSCREEN` disabled in tested kernel config.
- Only `gpio-keys` exposed as `/dev/input/event0`; no multitouch device.
- Display framebuffer works independently at 750×1334.

## Research questions
- What is the exact N71 touch controller and interface (SPI/other)?
- Which clocks, IRQs, pinctrl, power rails, DMA, reset and wake signals are required?
- Which upstream Apple Z2/related driver work is adaptable to A9?
- What firmware/calibration requirements are device-specific and not redistributable?

## Implementation steps
- [ ] Establish controller/transport identity from public DTS or properly sanitized traces.
- [ ] Determine upstream driver support and Kconfig dependencies.
- [ ] Draft a board-specific Device Tree patch and corresponding driver changes.
- [ ] Confirm driver probe without error.
- [ ] Demonstrate non-zero, repeatable multitouch events on `/dev/input/eventX`.
- [ ] Verify rotation, coordinate range, multiple fingers and resume behavior.

## Evidence requested
Provide kernel commit, board model, minimal safe logs, tested image hash and steps to reproduce. Do not include Apple firmware, calibration blobs or unique device identifiers.
