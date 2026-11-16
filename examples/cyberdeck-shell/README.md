# Native cyberdeck shell 0.2

Static Linux AArch64 fbdev/EVDEV dashboard with a real local PTY shell, on-screen keyboard and reversible display controls. Physically launched in the current N71/S8000 RAM session. [Evidence and limitations](../../docs/N71_SESSION_FINALIZATION_UI_POWER_2026_11_16.md).

```sh
make -C examples/cyberdeck-shell
# Host-only tests use synthetic glyphs and do not need phone hardware:
python3 -m unittest discover -s tests -p test_cyberdeck_native_shell.py -v
```

The build reuses the locally generated, gitignored font header from examples/fb-cyberdeck. The TTF/glyph raster and executable are not distributed. The font generator and framebuffer proof-of-concept sources remain independently attributed/licensed.

Run modes: default opens the qualified framebuffer/touchscreen and starts a local shell; --probe only checks the framebuffer backup and qualified input; --selftest executes a controlled echo through the actual PTY using simulated on-screen-key hit dispatch; --preview PRIVATE_PPM produces synthetic demonstration pixels on the build host. N71_PREVIEW_PAGE=0..3 selects a preview view. Preview values are simulated and must never be cited as phone telemetry.

The live UI discovers the named N71 touchscreen and checks its pixel coordinate range rather than assuming event0. It does not grab the input device or send controller firmware commands. It samples telemetry every two seconds, redraws on change, uses bounded input batches, handles SYN_DROPPED by discarding the incomplete contact state and caps redraw frequency at 10 Hz. It attempts to restore the framebuffer and KD display mode on normal exit/SIGTERM.

The console is ASCII/TERM=dumb, 48 columns × 24 visible rows. It has no full ANSI terminal emulation or scrollback browser; full-screen editors are not qualified. The shell runs with the existing bench environment's privileges. Ctrl-C is sent through the PTY; closing the application closes the PTY and signals its shell. Normal exit/SIGTERM invoke cleanup; SIGKILL cannot run cleanup.

Host sanitizer/selftests and a native phone selftest passed. Actual human touch typing in this new UI and optical confirmation are still pending. Kali packages, authenticated remote SSH, boot persistence and full product acceptance are separate gates. Nothing here should be described as a finished distribution or full VT desktop terminal.
