# N71/A9 cyberdeck native display proof of concept

**Date:** 2026-11-11. **Hardware:** the same live iPhone 6s Linux RAM boot with automatic Type-1 Z2 multitouch as in the preceding physical acceptance report. **Status:** physical LCD scanout CONFIRMED by operator-supplied photograph; framebuffer rendering and four near-edge touch targets PASS. Full coordinate accuracy and prolonged GUI stability remain unverified.

## Read-only hardware discovery

On the actual device the HoolockLinux kernel already exposes:

- DRM simpledrm: /dev/dri/card0, connected /sys/class/drm/card0-Unknown-1
- Linux fbdev: /dev/fb0, 750x1334, 32-bit, 3000-byte scanline stride (4,002,000-byte visible buffer)
- Backlight: Apple DWI BL, brightness 1505 of 2047 with power 0 (unblanked).
- EVDEV: /dev/input/event0, auto-initialized Type-1 Z2 touchscreen with two simultaneous fingers previously accepted.
- USB network: 172.16.42.1 device side, wired host route operational.

There was **no need to enable new hardware clocks or reboot** for this first graphics experiment. The simpledrm framebuffer is an early-boot handoff, not an accelerated graphics driver.

## Native executable test

A minimal standalone ARM64 statically linked C executable was cross-compiled with aarch64-linux-gnu-gcc and staged on the authorized host. It was transferred into the device's volatile /run filesystem using a temporary HTTP server bound ONLY to the USB network host address. The copy's SHA256 matched the host binary. The transfer server was stopped.

The binary started as Linux process 249, opened fb0 and event0 successfully, and logged:

    CYBERDECK_GUI_START: framebuffer 750x1334 stride=3000 bytes=4002000, evdev ready

It drew a cyberpunk-like dashboard with status text, cyan live finger crosshairs, four amber near-edge tap targets and on-screen reset/exit controls. Read-back of the first framebuffer pixels showed the expected pink color bytes, and the four target center pixels all contained the expected amber bytes *before* operator interaction. The program remained live and USB ping continued to respond.

**At the time of the initial binary test**, this only proved framebuffer writes/readback and native evdev access. The later optical verification below establishes that the actual LCD displays the UI.

## Read-back edge target acceptance after real evdev interaction

A follow-up **read-only** framebuffer inspection of the same still-running ARM64 native GUI showed all four target center pixels had changed from the initial **amber** value to the program's **cyan** confirmation value. Pixel center positions used for the comparison are the top-left, top-right, lower-left and lower-right target centers, each close to a horizontal screen edge. These four color transitions are driven by the application's evdev Type-B finger-down hit-testing logic; the program does not automatically mark targets as successful.

Thus the functional path from the real touch input device, through the on-device app, to the framebuffer's rendered indicator has passed for **4 of 4 targets**. This does **not** measure absolute coordinate error against a certified physical test fixture. The separate operator-supplied optical photograph described below now verifies scanout as well.

No redraw commands, raw proprietary data capture or per-device physical identifier were needed for this validation.

## Optical LCD verification from the physical iPhone 6s

Following the software-side tests, the operator provided a clear, original photograph of the device LCD in operation. The lit display visibly shows the **CYBERDECK / A9** banner, **N71 // NATIVE LINUX // V0.1** subtitle, Linux Online and 2-Finger Ready status panels, the full grid, and RESET / EXIT controls. The four near-edge target markers are all **cyan** and the status reads **EDGES: 4 / 4**. At the instant of the photograph the interface shows 121 input events, 25 synchronized frames and no active finger; a prior dedicated input test already established two-finger concurrency.

This is **physical optical confirmation** of native Linux framebuffer output and the tested touch-to-render end-to-end path, beyond a framebuffer memory readback. The operator's photograph is intentionally not added to the public repository; the technical report contains only non-identifying observations. The photograph does not establish pixel-accurate corner calibration, display refresh/tear characteristics, idle power, suspend-resume or boot persistence.

## Public source and reproducibility

The C source and build rules are under examples/fb-cyberdeck/. The local static font header is generated via tools/gen_cyberdeck_font.py using a *locally installed* TrueType font and is gitignored; neither a raw font file nor the generated glyph bitmap header is shipped. The public repository also does not include the ARM64 executable, Apple firmware, private calibration, per-device geometry tuple, unique identifiers, or personal logs.

The program never grabs the input device, flips GPIOs, transmits touch-controller SPI commands, changes backlight, modifies NAND, installs packages or alters Linux startup configuration. It is a disposable proof of concept in RAM. On SIGTERM or its EXIT touch button, it attempts to restore the previous fbdev contents.

Next: test labelled coordinate accuracy and frame cadence, measure latency and long-duration stability, and iterate towards an actual UI framework. The current framebuffer experiment is not yet a production-quality graphical cyberdeck interface.
