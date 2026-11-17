# N71/S8000 storage persistence and file/media workflow — 17 November 2026

**Target:** native persistent Linux system + a writable, independent internal
`/data` filesystem for music, projects, downloads, notes and diagnostic results.

**Verified today:** the Linux iPhone 6s RAM system still exposes **no Apple
internal storage block device**. `/proc/partitions` contains no physical disk,
and `/sys/block` exposes only volatile or virtual devices (loop, NBD, zram).
Kernel 7.3.0-rc1 currently runs with native touch/WLAN/Bluetooth, an
authenticated USB-only SSH service and the KALI/TODAY/AI user interface.
This **does not** qualify internal NAND access.

## Internal flash: proven topology and missing pieces

- Authentic owner-provided Apple N71/S8000 ADT (analyzed **privately/offline**)
  identifies internal storage as **`apcie/pci-bridge0/s3e`**, on Apple PCIe
  port 0 with a logical link to `dart-apcie0/mapper-apcie0`. The Wi-Fi endpoint
  is a separate PCIe port 1, `dart-apcie1`. Source-gated proof:
  `tools/n71_original_apple_adt_iommu_parent_graph_gate.py`.
- The original ADT identifies `nvme-mode`, storage namespaces and separate
  reset/clock functions at port 0, but those properties do **not** prove that
  the current Linux controller can enumerate or safely access the NAND.
- HoolockLinux documentation currently restricts internal-storage support to
  **A11**, not the Apple A9/N71 target.
  https://github.com/HoolockLinux/docs
- The upstream `CONFIG_NVME_APPLE` flag alone is not an S8000 NAND driver.
  The PCIe root/port-0 implementation, DART0 stream/DMA translation,
  Apple boot security, NVMe endpoint access and reliable read-only media
  probing remain open engineering work.
- **No storage MMIO, PCIe port-0 reset, DART0 mapping, internal NAND write,
  iOS APFS resize, disk partitioning or jailbreak filesystem mutation**
  occurred in this milestone.

**Safety gate:** do not touch firmware/iOS partitions until controller identity,
non-destructive read-only block enumeration, IOMMU fault isolation, full iOS
backup and operator-reviewed partition plan are all independently verified.
The isolated port-1 WLAN success cannot be used as evidence of port-0 safety.

## Immediate usable file workspace (host-persistent, phone RAM)

We built a functioning **owner-private Dell file vault** and a temporary
matching `/data` workspace in Linux running on the iPhone.

Directories, identical on both sides:

- `Music` — personally owned audio files (copying proven; playing **not**
  available until the audio driver and userspace player are validated)
- `Documents`
- `Projects`
- `Downloads`
- `Notes`
- `Kali`

On the Dell, the durable private root is
`~/.local/share/cyberdeck/file-vault/current/` (0700/0600).
On the phone, the working path is `/data/` (RAM, 0700/0600).
All transfers use **strictly pinned-key SSH via the direct USB gadget**.
The OpenAI API key, personal WhatsApp account data and tokens are not
part of this file transfer.

### Dell operations

```bash
cyberdeck-files init
cyberdeck-files status

# Example: use a local audio file whose path you choose.
cyberdeck-files import --file "$HOME/Music/example.mp3" --folder Music

# Copy the backed-up files to the live iPhone RAM workspace.
cyberdeck-files restore

# After editing files on the iPhone, persist them back on the Dell.
cyberdeck-files backup
```

The `cyberdeck-files` command is a **private owner-Dell wrapper** for
`experimental/storage/n71_usb_file_vault.py`. Import refuses symlinked or
non-owned sources and never silently overwrites an existing destination.
The host backup importer validates archive paths, rejects symlinks and device
nodes, bounds size/count and retains the preceding host snapshot for recovery.
Backups and restore are **manual** for now: do not power down a session with
unsynchronized changes.

### Phone shell operations

```sh
n71-files status
n71-files ls Music
n71-files ls Documents

# Copy a file already present in the Linux RAM filesystem:
n71-files copy /tmp/example.txt Notes
```

The `n71-files` command is included in the next private RAM image and is
deployed in the currently running iPhone session.

**Bounds:** 512 MiB maximum total local workspace, 256 MiB per file, 4,096
files. These explicit limits keep the device below the approximately 1 GiB
volatile rootfs capacity and prevent an unrestricted backup from filling
RAM. A larger offline music collection needs future **actual internal storage**
or a separately approved persistent-network storage design.

### Physical validation

- Created an owner-private, hash-checked sample file in `Notes`.
- Transferred it over authenticated USB SSH to `/data/Notes`.
- Modified it **on the physical iPhone**, then backed it up and verified the
  modified content on the Dell.
- Deliberately removed **only the sample file** from the volatile iPhone
  workspace, restored the Dell backup, and confirmed identical SHA-256.
- All original iOS NAND content, recovery paths and phone identifiers remain
  untouched. These are file-transfer/restore tests, **not** a cold-boot NAND
  persistence proof.

## New integrated private boot candidate

A separately built `n71-integrated-three-pillars-files-20261117` RAM boot
candidate is **27,164,871 bytes**. It includes the verified native six-tab
KALI/TODAY/AI interface, static ARM64 tcpdump 4.99.7, the KALI tool launcher,
the `n71-ai` text client (without its token), `n71-files` and the initial
empty `/data` directory structure. Existing Linux kernel, m1n1 and both
Device Trees were preserved unchanged and checked against the original RAM
candidate.

This image is held **only on the owner Dell**: it contains privately
provisioned radio data and is not suitable for GitHub. It has passed
**offline integrity tests** but has **not** been booted on the physical phone.
The current known-good session is preserved; a later DFU/Pongo RAM transfer
must remain supervised, with a previous known-good recovery image.

## Exit criteria for native, independent storage

1. Safely enumerate PCIe port-0 `s3e` through a reviewed S8000-specific
   storage driver with independently validated DART0 requester/DMA isolation.
2. Verify exact NAND block geometry, read-only media access, GPT/APFS layout
   and Apple data-protection restrictions **without modifying the disk**.
3. Obtain a complete, recoverable iOS backup and explicit partitioning approval
   before creating any Linux-owned volume.
4. Mount an isolated encrypted Linux filesystem, run independent reboot,
   checksum, write-flush, USB-disconnect and power-loss recovery tests.
5. Move `/data` to the real physical medium, retire the Dell-dependent
   workspace, and only then consider persistent rootfs/bootloader design.
   Independent booting without DFU/Pongo is a further distinct milestone.

**Never label Dell-backed or RAM-backed files as internal NAND persistence.**
