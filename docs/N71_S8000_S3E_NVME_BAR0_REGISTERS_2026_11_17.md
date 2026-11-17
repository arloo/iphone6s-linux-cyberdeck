# N71/S8000 S3E: physical NVMe BAR0 register access

17 November2026, real Samsung A9 iPhone6s under Linux. The storage
controller106b:2002 exposed readable NVMe registers through its measured
16KiB BAR0. No NVMe command or endpoint DMA was submitted.

| Item | Actual observation |
| --- | --- |
| BAR0 memory assignment | Bus0xc1000000, CPU0x7c1000000, 16KiB exclusive reservation |
| WLAN resources | CPU0x7c0000000..0x7c07fffff, left intact |
| Original root memory window | 0x00000000 |
| Original prefetchable window | Low0x00010001, upper base/limit0; bus0..0xfffff, outside WLAN and S3E windows |
| Temporary root memory window | 0xc100c100, bus0xc1000000..0xc10fffff |
| Root and endpoint command during reads | 0x0002 each, memory decode only;16-bit writes avoid status W1C |
| CAP, offset0/4 | 0x00000020f00103ff |
| VS, offset8 | 0x00010001, NVMe1.0.1 |
| CC, offset0x14 | 0 |
| CSTS, offset0x1c | 0 |
| BAR, bridge window, commands and bus route restore | Verified |
| DART0 roots and TCR restore | Verified; all owned pages zero and freed |
| GPIO160 and port0 power | Original INPUT restored after port0 OFF |
| CPU MMIO reservation | Released |

CAP decodes to1024 maximum queue entries, contiguous queues required,
4KiB controller page size,4-byte doorbell stride and NVM command-set
support. The advertised timeout field is240 units of500ms (120s);
this was not a readiness test. CC.EN and CSTS.RDY were both clear.

The first MMIO candidate stopped before NVMe reads because it rejected
all active prefetch windows. The qualified version rejects overlap with
the known WLAN or proposed S3E windows, including64-bit upper bounds;
it preserves the unrelated reset prefetch window. Failure tests cover
unsafe command clear and BAR rollback: return-3 retains DART roots,
CPU reservation and module/power ownership instead of freeing resources.

Actual ARM64 artifact SHA256:
`b47badd3a03725a34a1ed105d0d53941bc08343860cea73d97a77b317fb8ee37`.
The inert load/unload and current encrypted backup metadata passed.
All8 pre-arm current samples were positive. Post-trial capacity78%,
Charging,+196mA net,36.8C. Module unload and subsequent native WLAN
ping passed. Full raw hardware logs remain private.

This result proves CPU access to the real controller register file.
It does not prove NVMe queue transport, namespace access, NAND block
reads or persistent Linux storage. The next stage must map only owned
queue/Identify buffers, qualify S8000 NVMMU behavior, and use bounded
read-only admin commands before any storage layout changes.
