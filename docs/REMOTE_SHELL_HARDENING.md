# Security gate: replace Telnet before a usable Linux cyberdeck

**Current state:** the experimental N71 RAM initramfs exposes a BusyBox **root Telnet** shell through the direct USB gadget link `172.16.42.1`. This is **bench-only** and unauthenticated. Local USB isolation is not a substitute for encryption or authentication.

**Release criterion: BLOCKED.** Do not expose this gadget to another network, bridge it to Wi-Fi or Ethernet, advertise it as a production remote interface, or use it for sensitive data until the following gate is met.

## Target architecture

- Use a small and auditable SSH server (Dropbear or OpenSSH) in the test initramfs, built from verifiable upstream **open-source** code.
- Bind SSH to the device's **USB gadget address only** (or enforce an equivalent interface-specific firewall rule); do not use a WAN listener.
- Root access must be **public-key-only**, with authorized public keys provisioned locally by the operator. No vendor default password; no remote password login.
- Generate a **unique private SSH host key on the device or trusted host**, never check host private keys, user private keys or authorized-key provisioning secrets into Git.
- Verify the host key fingerprint on the Dell through a trusted first-use channel. Document expected key rotation if host keys live only in volatile RAM.
- Keep the USB shell isolated behind the authorized Dell's security controls. Block all non-SSH inbound network ports once the cutover is verified.
- Remove and disable Telnet listener, then demonstrate that TCP/23 is closed; confirm SSH authentication, encryption, connection recovery and clean shutdown across a fresh RAM boot.
- Collect sanitized connection success, refusal-of-password-authentication and Telnet-port-closed results. Never publish public/private host identifiers, client IPs outside test subnet, private keys or raw session transcripts.

## Migration protocol

1. Build a separate **RAM-only recovery image** containing the open-source SSH server and key provisioning logic; preserve the last known working ISO and source.
2. Before closing Telnet on the live phone, independently test SSH port reachability and successful public-key authentication over USB.
3. Verify password login is refused and an unauthorized key fails. Validate that the fingerprint matches the intended host key.
4. Disable Telnet, confirm port 23 is not listening, and test a fresh authenticated SSH login.
5. Repeat after DFU/PongoOS reboot and validate reconnect behavior. Only then update `authenticated_remote_shell` to `live_pass`.

No SSH installation or cutover was performed by adding this document. Until hardware verification, the existing shell remains explicitly insecure and **not production ready**.
