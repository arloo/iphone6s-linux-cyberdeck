# N71/S8000 DART1 DMA encoding and supervised read-only RAM-Linux field test

**2026-11-12 | Target:** owner-controlled original iPhone 6s N71, Samsung A9/S8000, BCM4350 PCIe onboard WLAN at Apple port1. **Outcome:** additional original Apple ARM64 TTBR + 64-bit PTE *software* encoding proven against Linux; a new **physical-device RAM-only read-only diagnostic boot candidate** assembled privately on the Dell with all previously working bootloader/kernel/DTBs unchanged. The field-test image **has not yet been booted**.

## 1. Original software encoding: additional proof

An independent fail-closed checker [`n71_original_s5l_dart1_ttbr_pte_format_gate.py`](../tools/n71_original_s5l_dart1_ttbr_pte_format_gate.py) runs against the locally retained genuine iOS 15.8.8 N71 ARM64 kernelcache and both original N71 Apple Device Trees. It anchors the previously proven original `IODARTFamily` WLAN mapper0 → original Apple S5L DART controller logical lane0 and original instantiated S5L DART vtable TTBR-clear method.

**Original Apple TTBR programming:**

- Original ARM64 `LSR X20,X0,#12` extracts a page-aligned address's page number.
- `MOV W8,#0x80000000` sets **TTBR bit31**.
- `BFXIL W8,W20,#0,#24` places its 24-bit page number into the low 24 bits.
- `STR W8,[X9,#64]` writes the 32-bit word through the indexed DART register window, consistent with the original four-stream × four-table register layout.

The original software field construction is therefore:

```text
TTBR_WORD = (1 << 31) | ((root_page_base >> 12) & 0x00ffffff)
```

The genuine Linux S5L driver independently has `DART_T8020_TTBR_VALID=BIT(31)`, `DART_T8020_TTBR_SHIFT=12` and `DART_T8020_TTBR_ADDR_FIELD_SHIFT=0`, all cross-validated.

**Original Apple page-table-entry software builder:**

- A separate original ARM64 path masks a 24-bit page number and uses `BFI X8,X9,#12,#24` to place that number into **PTE bits 12–35**.
- The path takes **bit0** from a caller-supplied flag, **sets bit1** with `ORR X3,X8,#2` and passes the 64-bit result to a local page-table setter, which stores `X3` into an 8-byte-per-entry table.
- Linux `io-pgtable-dart.c` uses `APPLE_DART1_PADDR_MASK=GENMASK_ULL(35,12)`, `APPLE_DART_PTE_VALID=BIT(0)`, `APPLE_DART1_PTE_PROT_SP_DIS=BIT(1)` and 64-bit `dart_iopte`. These **software format elements match the original routine**.

The check passed both original Apple ADTs, the actual original N71 ARM64 executable, the experimental Linux `apple-dart.c` and `io-pgtable-dart.c`. The [21 targeted adversarial tests](../tests/test_n71_original_s5l_dart1_ttbr_pte_format_gate.py) check original ARM64 instruction mutations, wrong masks, valid bits, page shifts, physical page bounds, source-file redaction and fail-closed behavior.

**What this does NOT prove:** physical BCM4350 PCIe requester-to-DART1 hardware SID routing, correct runtime page-table placement, effective TLB invalidation, IOVA ownership, hardware interpretation of permission bits, real fault isolation or recovery. The source path demonstrates a *caller-controlled* PTE bit0, not a successful device-level DMA transaction. It is therefore **not** a reason to enable the deliberately blocked Linux DART1 probe.

## 2. Actual practical field-test image now staged (private Dell)

The new public [N71 RAM-Linux read-only field-test shell](../scripts/n71_wlan_readonly_fieldtest.sh) is now part of a **privately built** new RAM-only boot image on the authorized Dell. The Linux test runs after normal procfs/sysfs/device setup in the **already physically proven** Linux touchscreen/LCD/USB RAM environment. It reads **only procfs/sysfs metadata**, does not access `/dev/mem` and does not request PCIe, DART, DMA, firmware, radio, GPIO, PHY, MMIO, networking commands, clocks or resets.

It checks exactly `apple,n71` and `apple,s8000`, counts `/sys/bus/pci/devices`, IOMMU groups, existing platform device names for original port1 and DART1 resources and visible WLAN interfaces. It writes a bounded set of sanitized classifications to a **RAM-backed** log `/run/n71_wlan_readonly_fieldtest.log`, never reporting MAC addresses, passwords, SSIDs, device serial numbers or private boot data.

The separately public [USB-only field-test result collector](../tools/n71_usb_wlan_fieldtest_collect.py) reads **only that log** over the previously validated **172.16.42.1:23** RAM-Linux USB gadget shell, verifies Linux USB VID:PID **05ac:4142**, allowlists fixed result fields and deliberately reports:

```text
USB_GADGET_CONNECTION_IS_NOT_NATIVE_WIFI=YES
DIRECT_WLAN_ASSOCIATION_AND_DHCP_PROVEN=NO
PHYSICAL_DART1_DMA_REQUESTER_SID_PROVEN=NO
```

The test cannot be fooled by the still-running iOS USB identity **05ac:12a8**. On a normal iOS-attached phone its collector returns a fail-closed **NOT_YET_AVAILABLE** status without attempting a shell connection.

The actual private boot candidate is in the Dell research tree under `private-touch-live-test/n71-wlan-linux-readonly-fieldtest`. Its 11,821,980-byte blob is assembled by copying **9,086,477 bytes of the previously tested private Linux boot** unchanged and replacing **only the final compressed initramfs**. The copied initramfs differs from the original version by **exactly one added shell script and one extra `/init` call**. The original Z2 firmware, board calibration, touch protocol, base RAM kernel, both A9 Device Trees, Apple m1n1 bootloader and boot arguments are preserved; the original known-good payload remains untouched.

All private boot image, original Apple binary, original iOS IORegistry and private calibration values stay under the owner's Dell private directories, not GitHub.

## 3. How to execute the practical on-phone test

**Requires the owner physically present at the iPhone; no device state change was attempted to create this report.**

1. Keep the original iPhone 6s connected directly over USB to the Dell. Physically enter **DFU** while supervised. This is distinct from iOS or ordinary recovery; the research boot procedure already used the owner's attended DFU/PongoOS route successfully for the touchscreen/LCD/USB tests.
2. On the Dell, run the established PongoOS chain **without `-l`** (which historically caused problems on this device): `sudo env PALERA1N_BYPASS_PASSCODE_CHECK=1 /private/hoolock/bin/palera1n --cli -p -k /private/hoolock/bin/Pongo.bin`, then use `pongoterm` to `/send` the staged private read-only field-test `m1n1-linux-n71-wlan-readonly-fieldtest.bin` followed by `bootm`. **Do not flash, restore, repartition, write NAND, or force power down the modem.** Use the precise owner-private file paths on the Dell; no proprietary image is included in this public report.
3. Once the device boots RAM Linux and the **Linux** USB gadget appears, execute `python3 tools/n71_usb_wlan_fieldtest_collect.py` on the Dell. The collector classifies actual PCIe, IOMMU, DART1 device and WLAN interface state visible under Linux; the USB gadget itself is **not** Wi-Fi.
4. Only after read-only results establish actual runtime topology should a *separate*, carefully gated controller/DART path be developed and physically tested. The original experimental 0012 packed-TCR fix and 0013 **pre-MMIO DART1 block remain in place**, with no bypass.

The public suite also contains [11 real-shell diagnostic tests](../tests/test_n71_wlan_readonly_fieldtest.py) and [9 mocked/local-USB-collector tests](../tests/test_n71_usb_wlan_fieldtest_collect.py). The boot package was built and validated offline; a practical on-phone Linux execution is **pending attended DFU**.

## 4. Remaining hard blockers to a true wireless association

We have verified a stable **native BCM4350 PCIe Gen1×1 link under original stock iOS**, original DART1 logical mapper index0, its TCR lane0, its TTBR physical register addresses and substantial original software TTBR/PTE encoding. The still-open *physical-hardware* gates are:

- Confirm the live BCM4350 **PCIe requester** really selects original DART1 hardware SID0, not merely logical mapper0.
- Establish safe live DMA table backing and page-table placement, IOVA, cache coherence, translation/fault handling, rollback and per-stream-only initialization.
- Establish safe S8000 port1 REFCLK/PHY/PERST#/MSI sequence and shared root controller status/register cross-port impact while preserving port0 NAND/storage and port2 modem.
- Enumerate the BCM4350 under an actual **RAM-only Linux** PCIe host, load the correct private board C5 firmware/calibration, then authenticate and obtain network connectivity over **on-device Wi-Fi**, with USB disconnected or shown not to carry the data path.

**No actual Linux Wi-Fi, Linux PCIe endpoint, working DART DMA transfer or on-phone run of this new diagnostic is claimed.**
