# N71 isolated USB NBD file-backed storage lab

**Experimental only. Not a production storage system. Not internal iPhone flash.**

A dedicated 64 MiB ext4 image on the Dell can be exported on its direct N71 USB gadget address, `172.16.42.2:18890`, with a static AArch64 userspace client connecting **only** from `172.16.42.1` to the fixed kernel device `/dev/nbd0`. Source: `nbd_export.py`, `n71-nbd-client.c`. Build the device client with `make build/n71-nbd-client-aarch64` from the repo root.

## Physical result, 2026-11-16

On N71/S8000, the client successfully attached 67,108,864 bytes as `/dev/nbd0` and Linux mounted ext4 `ro,noload`. After clean detach and reattachment with explicit write enable, ext4 mounted `rw,sync`; a test file was written and `sync` completed. A clean unmount detached the NBD client, and a host-only ext4 read recovered the exact file. No internal Apple storage accessed. At completion `/sys/block/nbd0/size` was zero.

The lab disk stays privately under `~/.local/share/cyberdeck/storage/n71-lab-64m.img` on the authorized Dell and is deliberately excluded from Git. The USB service is **not** configured to autostart. Do not attach the export as the root filesystem, put secrets/personal data onto it, enable it on WLAN or leave it mounted unattended.

## Reproduction gates

1. Create a **new dedicated regular-file image**, not a block device, with mode 0600 and size between 32 MiB and 1 GiB under the private storage directory. Format that file with ext4 only after checking its exact pathname.
2. Check the phone shows `/dev/nbd0` and its current `size=0`; check the direct USB link and a working authenticated SSH recovery path.
3. Run `python3 experimental/storage/nbd_export.py --image /path/to/dedicated-lab.img` (read-only by default). After a hash-verified private transfer of the ARM64 client, invoke `n71-nbd-client --ro` and mount `-t ext4 -o ro,noload`.
4. **Unmount before stopping NBD.** Detach and verify kernel NBD size returns to zero. The server exits after its single accepted phone client.
5. To qualify writes, explicitly restart the server with `--allow-write`, run the client with `--rw`, mount with `-t ext4 -o sync`, write a short non-sensitive test file, sync, cleanly unmount and detach, then read the filesystem on the Dell for an independent checksum.
6. Do not proceed if source endpoint, server image path, mount target, read-only status or recovery checks differ from expected. No generic disk-path argument is offered to the phone client, by design.

Protocol is a deliberately bounded **oldstyle NBD research subset**, no TLS, no suspend/reconnect recovery, no authenticated client transport beyond the isolated USB link, and no crash/power-loss endurance evidence. For real private storage use a maintained, authenticated/encrypted protocol, a stable filesystem and independent rollback. The internal N71 `apcie` port-0 `s3e` controller still needs its own read-only-safe reverse engineering and must remain untouched by this lab.

## Regression checks

`python3 -m unittest discover -s tests -p test_n71_nbd_lab.py -v` verifies read/write framing, write rejection under RO export, FLUSH and out-of-bounds behavior without an iPhone.
