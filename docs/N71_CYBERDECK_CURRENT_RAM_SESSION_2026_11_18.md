# CYBERDECK // ARLO — current RAM session acceptance (2026-11-18)

Scope: physically booted Apple iPhone 6s N71/S8000 with Linux
`7.3.0-rc1-n71-batt2-g68aadac820d0-dirty`. Verified over the current
authenticated, pinned-host-key USB SSH channel. These are **live device
results**, not simulated snapshots. No internal NAND block I/O is claimed.

## Identity and safety

- The on-phone integrated runtime SHA-256 **matches** the owner-approved
  hold8/chargepilot private image. A prior boot had unexpectedly used
  an older image; the check now rejects that mismatch.
- S3E controller remains **intentionally quarantined** from the already
  completed one-shot experiment: BME disabled, NAND GPIO160 asserted
  low, DART and DMA/HMB/NVMMU memory still retained. No NVMe module
  reloads, DMA frees or NAND writes were performed in this phase.
- The encrypted iOS backup metadata has previously been verified;
  it is a logical iOS backup, **not** a raw NAND snapshot.

## Native networking

- Broadcom `wlan0` joined the owner LAN with WPA2 authentication,
  DHCP address `192.168.1.7/24`, default route and DNS.
- Router ICMP: **3/3 packets**, ~1.8 ms mean. Dell over Wi-Fi: 3/3,
  no packet loss. DNS `example.org` succeeded.
- Dropbear had deliberately been bound to the USB address only. An
  **85-second**, single-interface, key-only SSH listener was started
  on the WLAN IP, port 2222, without changing or exposing USB SSH.
  The WLAN server key matched the existing authenticated USB
  SSH key, and real root key-based SSH login succeeded.
- A 4 MiB random test file was uploaded and downloaded over this
  authenticated Wi-Fi SSH session; content matched **byte-for-byte**
  and by SHA-256. The test artifact was removed. This is an encrypted
  **transport**, not internal persistent storage. The temporary WLAN
  listener expires automatically; no permanent WLAN SSH service is
  being claimed.

## Touch, framebuffer and interface

- N71 touchscreen is a genuine EVDEV input with 750×1334 coordinates.
  `--probe` on the physical phone passed framebuffer backup and
  touch-device qualification.
- The native `--selftest` passed screen-key hit dispatch, real local
  PTY command echo, terminal parsing and keyboard mode/geometry checks.
  The running graphical process was later found to have exited
  normally, reporting touch events and frames. Its cause was not
  conclusively established; it was relaunched after a successful
  read-only hardware probe, **without rebooting Linux**.
- The visible interface still needs intentional human finger typing,
  long-session usability and international text acceptance. The
  console remains an ASCII-first PTY.
- CPU uses the `schedutil` governor and more than 1.6 GiB RAM was
  available. Brightness was already 1023/2047. A reversible
  A/B test reduced it temporarily to 760/2047; the net cell-current
  readings were too variable to demonstrate a reliable advantage.
  The original brightness was restored.

## Bluetooth and Kali

- `hci0` and BlueZ are active with BR/EDR, LE, SSP and Secure
  Connections enabled; adapter is **not discoverable or pairable**
  until the owner explicitly starts a pairing window. No claim of
  a paired keyboard or mouse.
- The limited `n71-kali` network profile passed ICMP and DNS.
  Its `tcpdump` collected **six passive frames** on `wlan0` with
  bounded snap length/count. No RF injection or monitor-mode claim.
- A full verified Kali ARM64 userland, additional packages including
  nmap, and a persistent Kali workspace remain pending.

## Real file workspace and briefing

- The already existing Dell-backed private file vault was tested
  end-to-end: **restore to phone RAM and backup to Dell both passed**,
  with count and size preserved. The actual phone `/data` remains
  volatile rootfs, not Apple NAND. A separate plaintext NBD lab
  experiment is not being used as internal-storage proof.
- The current 08:45 AI briefing was privately delivered via pinned
  USB SSH to `/run/cyberdeck/today.json` and `today.txt`. Both have
  restrictive permissions and the data is labelled **cached**.
  No Gmail/Calendar passwords, raw messages or private contact
  lists were transferred.
- The existing Dell `n71-briefing-push.timer` was found inactive
  and restarted. systemd now confirms the next scheduled attempt
  on **2026-11-19 08:55 Europe/Rome**, followed by 09:45 and 12:00.
  Delivery still requires a fresh trusted USB host-key pin after
  each new phone RAM boot and a sufficiently recent source briefing.

## Battery and safe supervision

- BQ27540 capacity remained roughly **71–72%**, with temperature
  steadily falling into the mid-35 °C range.
- An SN2400 **300 mA USB input-current** pilot remained active with
  two-second VBUS telemetry; observed net cell current alternated
  between slightly positive, zero and discharge. This is NOT proof
  of reliable positive charge under all load conditions.
- The previously prepared fail-closed **phone-local** supervisor was
  actually started with its lock and 60-second monitoring loop.
  Kernel thermal/voltage checks and the driver's 3600-second
  hardware rollback remain enabled. Automatic supervisor renewal
  has **not yet been validated** unless a distinct future session
  log records `CHARGE_SUPERVISOR_RENEW_CONFIRMED`.
- The Dell-hosted legacy charge guard stays disabled.

## Read-only Dell terminal monitor

Run locally on the Dell:

```bash
python3 ~/Documenti/iphone6s-linux-cyberdeck-public/scripts/n71_live_monitor.py --once
python3 ~/Documenti/iphone6s-linux-cyberdeck-public/scripts/n71_live_monitor.py --watch
```

The monitor uses only the private authorized USB SSH identity and
current strict host-key pin. Output deliberately excludes MAC/BT
addresses, private filenames, messages, credentials and raw logs.
If the phone reboots or the trusted host key changes, the monitor
**fails closed** until the owner revalidates the endpoint.

A separate Linux Mint PC can display the Dell terminal after the
Dell's SSH server is explicitly enabled and an authorized SSH login
is configured. On inspection, the Dell's system SSH server was
**inactive**; no unauthenticated remote listener was opened.

## Next physical checkpoint

Current S3E RAM session is quarantined; do not load further S3E modules.
The subsequent queue-retirement-gate build is compiled with **53
passing host S3E tests** and will log which of thirteen fail-closed
conditions rejects the queue-register-only cleanup. It must be
tested only in a separate fresh Linux boot after full reset, verified
backup, new SSH pin and eight battery safety samples. No DART,
NVMMU, HMB or DMA pages will be freed by that diagnostic.
