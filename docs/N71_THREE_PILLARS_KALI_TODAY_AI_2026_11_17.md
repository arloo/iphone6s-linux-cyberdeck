# Cyberdeck A9: KALI / TODAY / AI — 17 November 2026

## Verified live milestone

The owner-operated iPhone 6s N71/S8000 is running native ARM64 Linux **in
RAM** with touchscreen, framebuffer, native BCM4350 Wi-Fi (LAN gateway ping
verified), Bluetooth HCI, and key-only USB SSH. The three-pillar UI was
compiled as a static AArch64 ELF, verified on the phone with the native
terminal/touch self-test, and activated with the previous UI binary retained
for rollback. No NAND, iOS APFS, or persistent phone storage was written.

The interface has six tabs, with **KALI**, **TODAY**, and **AI** as the
operational priorities, alongside HOME, TERM, and SYS.

### KALI: a real first-stage security toolbox, not yet a Kali distribution

- `/usr/bin/n71-kali`: constrained local command menu providing interface
  status, ping, DNS, bounded traceroute, a single TCP port check, and a
  bounded passive capture command.
- `/opt/kali/bin/tcpdump`: **tcpdump 4.99.7**, ARM64 statically linked against
  **libpcap 1.10.7**, built on the owner's Dell from upstream release sources.
  Both source archives had valid GPG signatures from the release key with
  fingerprint `1F16 6A57 42AB B9E0 249A 8D30 E089 DEF1 D9C1 5D0D`.
  The release key was obtained from the vendor website, so independently
  validating its fingerprint remains recommended for a high-assurance chain.
- Phone verification: `tcpdump --version` passed and an owner-controlled
  two-packet passive capture on the USB link returned `2 packets captured`.
- No nmap, full Kali rolling rootfs, monitor mode, packet injection, or
  third-party USB dongle support has been qualified. Never represent BusyBox
  utilities as a complete Kali distribution.
- Only test explicitly authorized networks and hosts. No active Wi-Fi
  interference, offensive payloads or automatic broad scanning.

For a genuine Kali userspace, plan a **vendor-verified ARM64 minimal rootfs**
and package manager isolated from the base iPhone system. Package downloads
and signature verification belong on the Dell; actual deployment waits for
persistent storage and resource/driver qualification.

### TODAY: privacy-first personal briefing

- The Dell backend generates a bounded AI briefing from connected Gmail,
  Google Calendar, and selected project notes.
- Personal WhatsApp is **not yet linked**. No Business API or daily manual
  export is used. The separate optional companion route and exclusion list
  must be explicitly configured before any personal message intake.
- `n71_push_briefing.py` sends only reduced summaries and agenda elements
  over strict pinned USB SSH, never Gmail OAuth/API keys or raw chats.
- New safeguard: the phone push validates the strict local WhatsApp privacy
  policy's revision against the AI state and revalidates immediately before
  JSON/text transfer. A changed policy requires an AI regeneration.
- The last verified live push succeeded; JSON and ASCII display are stored in
  phone RAM as mode 0600 files.

### AI: on-phone text dialogue over an authenticated Dell bridge

- `experimental/ai/n71_ai_usb_bridge.py` is a Dell-only user service on
  `172.16.42.2:18962`, accessible solely via the direct USB NCM network
  (`172.16.42.1` source) with an owner-private random bearer token.
- `experimental/ai/n71-ai-phone.sh` is installed as `/usr/bin/n71-ai` on
  the phone. The bridge token is kept in phone **RAM**, mode 0600.
  The actual `OPENAI_API_KEY` stays in the Dell's owner-private service
  environment and **is never included in a boot image or Git**.
- OpenAI Responses API is called from the Dell with `store: false`.
  Dialogue context is kept in **Dell process RAM only**, at most four
  exchanges, expiring after 20 minutes of inactivity. `/reset` clears it.
  No prompts/responses are written to application files by the bridge.
- The six-tab native UI starts `n71-ai --chat` in the phone's PTY when the
  AI tab is selected; the verified touch keyboard sends questions; END CHAT,
  RESET AI, and CLEAR VIEW are functional surfaces.
- Successfully exercised live text responses from OpenAI through the
  physical phone, and tested `/reset`. Voice/microphone input is a **future**
  feature, not currently supported by the native interface.
- Sending a question to AI is an explicit external-model disclosure. The
  model does not have independent access to the phone shell, Gmail, Calendar
  or WhatsApp.

### Boot and persistence qualification

The owner also prepared an **offline next-boot candidate** that bundles the
new native UI, `n71-ai`, `n71-kali`, and static tcpdump with previously
validated Wi-Fi/BT/SSH runtime. The candidate is 27,165,131 bytes. It retains
the exact original kernel and Device Trees and has **not yet been boot-tested
on the physical iPhone**. The previous known-good payload remains intact.

**Not persistent:** RAM files, conversation token, dynamically generated
SSH host key, and staged tools disappear when the device powers off. The
Dell keeps the next-boot payload and source trees. A fresh boot must
re-establish strict host-key pinning over the verified USB channel and
reprovision the short-lived AI token. Do not blindly bypass SSH verification.

**Connector:** iPhone 6s exposes **Lightning**, not USB-C. Future external
USB-C tool modules would require a compatible Lightning host/adapter or
custom hardware bridge and verified USB host-mode power/driver support.
Do not assume USB-C peripherals work today.

### Exit criteria for the next vertical slice

1. Physical boot of the offline three-pillar image, with supervised fallback
   and no iOS partition modification.
2. Low-battery and finite-charging-lease validation before long tool use.
3. Persistent storage candidate isolated from iOS data and qualified
   read-only first; add Kali rootfs only after storage/recovery gates.
4. Bluetooth HID pairing plus touchscreen usability tests.
5. Privacy-filtered personal WhatsApp onboarding only after owner consent,
   stable chat identities, and fail-closed exclusion tests.

## Provenance / implementation pointers

- Official tcpdump/libpcap upstream: https://www.tcpdump.org/
- Kali project and ARM distribution documentation: https://www.kali.org/get-kali/
- OpenAI Responses API: https://developers.openai.com/api/reference/resources/responses/methods/create
- Public, credential-free sources: `experimental/ai/`,
  `experimental/kali/`, `examples/cyberdeck-shell/`,
  `experimental/briefing/`, and `tests/`.
- Device calibration, firmware, Wi-Fi/BT identifiers, owner tokens, pairing
  records, private logs and boot payloads must **never** enter this repo.
