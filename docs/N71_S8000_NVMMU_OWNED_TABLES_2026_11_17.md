# N71/S8000: real NVMMU table ownership and bounded invalidation

17 November 2026. Executed on the physical Samsung A9 iPhone 6s.

| Item | Physical result |
| --- | --- |
| NVMMU TCB / auxiliary table sizes | 16 KiB / 4 KiB, backed by two dedicated 16 KiB Linux pages |
| Address checks | Direct DMA, below 36 bits, no overlap with inherited NVMMU/DART roots before zeroing |
| Owned root installation | Auxiliary pair +0x10/+0x14, then TCB pair +0x08/+0x0c; exact readback |
| Invalidate | +0x04 bit16, completed at first poll; at most 1000 one-microsecond ticks |
| Nested controller observation | S3E 106b:2002, BAR0 16 KiB, same five valid NVMe 1.0.1 register reads |
| NVMMU inherited root restoration | Exact readback, second invalidate completed at first poll |
| NVMMU buffers after trial | Entire 32 KiB backing still zero, safely released |
| DART0 | All four streams retained owned empty roots around the nested trial; inherited state restored, buffers freed |
| PCI/reset/power | Bus route, BAR, bridge commands/windows, GPIO160 and port0 power restored |

Actual ARM64 artifact SHA256:
a3c7fb1a0f63a602cff0b95e54ef8327b8ad00f0989830a5c5e8ff8408186144.

The new source gate authenticates original Apple S800x PCIe instructions,
the 16 KiB/4 KiB allocations and register destinations, 128 tags, 256 SGL
entries per tag, the 23-bit tag-address shift and ADT virtual-base 0x40000000.
Original input files, full pointer values and raw logs remain private.

The transaction nests the existing bounded endpoint observer while both
DART0 and NVMMU roots belong to Linux. It restores NVMMU before removing
the DART guard. Unsafe invalidate timeout, observer rollback or pointer
restoration returns -3 and retains pages, translation, GPIO, power and
module ownership. Host regressions exercise those failure paths.

No bus mastering, NVMe admin command, queue DMA, namespace/block access
or NAND host write occurred. This qualifies the ownership/control path,
not end-to-end DMA translation. Queue/Identify buffers and their 4 KiB
DART mappings remain the next engineering stage.

Power: the diagnostic-only SN2400 module identified an actual 4201000 uV
battery sample as the cause of an earlier guarded lease stop. The 4200000 uV
limit and other protections were preserved. At 300 mA USB input, all eight
pre-arm samples were positive, averaging +64.5 mA net. After cleanup, native
WLAN passed 1/1 ping and battery 79%, Charging, +82 mA was observed.
Storage and charger trial modules were then unloaded for the owner's
USB-disconnected demo; Linux remains in RAM.
