# S8000 NVMe: Identify succeeds, shutdown completes, post-disable qualifier fails

**Physical date:** 2026-11-18. Platform: iPhone 6s N71, Samsung S8000, RAM Linux `7.3.0-rc1-n71-batt2-g68aadac820d0-dirty`.

## Safeguards before the one-shot physical command

The previous storage module was absent from the fresh RAM boot. The
NAND reset GPIO was unclaimed, PCIe link0 was off, native Wi-Fi was up,
the USB recovery/SSH channel was configured, and the existing encrypted
iOS backup metadata was verified locally. The onboard SN2400 input
pilot was armed at 300 mA with a fresh VBUS monitor.

Eight independent cell-gauge samples passed: 78% SOC, **4.130–4.161 V**,
34.4 °C, and net current -29 to +66 mA. The bounded test would have
aborted if *any* sample reached 4.175 V, or if USB/board identity,
charging safety or resource ownership failed. A SHA-pinned diagnostics
module was staged in `/run` only; no NAND block I/O was requested.

## Physical results: controller data AND shutdown phases

The guarded S3E admin Identify of namespace 1 again returned a valid
completion and a separately arrived DMA data page:

```text
IDENTIFY_NS1_COMPLETION present=1 status=0001 polls=2 csts=00000001
IDENTIFY_NAMESPACE_REAL nsid=1 nsze=15625000 ncap=15625000 nuse=15625000
  lba_bytes=4096 capacity_bytes=64000000000 data_tail_arrived=1
```

New, independently instrumented controller-phase log:

```text
ADMIN_BME_STATE enabled=0 both_command_words=2
ADMIN_SHUTDOWN_TRACE attempted=1 rc=0 csts=00000009 polls=949
  disable_rc=0 disable_csts=00000000 inner_rc=0 master_off=1
ADMIN_IDENTIFY_ONCE rc=-3 ... stopped=0 master_off=1
ADMIN_STAGE rc=-3 prepare_stage=5 dart_fault=00000500 nvmmu_fifo=00000301
```

`CSTS=0x9` contains `RDY=1` and `SHST=2`, which is the
shutdown-complete state requested by the pilot. Subsequently,
`CC=0`, `CSTS=0`, and both PCI command words were verified at `2`
(bus mastering disabled). The Identify command succeeded (`inner_rc=0`).

Nevertheless, `stopped=0`, so the module returned `-3` and kept
all owned HMB/DMA, NVMMU, DART tables, controller mapping and port0
power **pinned in quarantine**, with NAND reset GPIO160 held low.
There is **no** Linux block device and no evidence of safe, independent
storage access yet. Never force-unload the pinned module.

## Narrowed software gate

The current source evaluates the release gate as:

```c
r->stopped = shutdown_ok && disable_ok &&
             r->master_off && o->qualified(ctx);
```

The first three predicates are independently true in the physical log.
Consequently the remaining `qualified(ctx)` gate must evaluate false
at that point. It is presently the *same* prerequisite used **before**
starting NVMe. It includes `n71_admin_memory.prepared`, the installed
DART queue mapping, HMB ownership, NVMMU state, and the ANS HMB base/size
registers.

### Follow-up: actual post-disable predicates isolated on hardware

A third one-shot physical Identify was completed in a **new** Linux boot
after the USB transport was recovered. The BQ27540 temperature cooled
below 38.0 °C; all eight independent preflight samples passed with
75% SOC, 37.7–37.8 °C and no cell-voltage breach.

```text
IDENTIFY_NAMESPACE_REAL nsze=15625000 lba_bytes=4096 capacity_bytes=64000000000
ADMIN_SHUTDOWN_TRACE attempted=1 rc=0 csts=00000009
  disable_rc=0 disable_csts=00000000 inner_rc=0 master_off=1
ADMIN_POST_DISABLE_PREDICATES qualified=0 prepared=1 dart_mapped=1
  hmb_owned=1 ans_ready=1 ans_hmb_base_ok=0 ans_hmb_size_ok=0
  endpoint_ready=1 root_cmd_2=1 endpoint_cmd_2=1 cc_zero=1
  csts_zero=1 nvmmu_ctrl_1=1 nvmmu_inv_zero=1
ADMIN_STAGE rc=-3 dart_fault=00000500 nvmmu_fifo=00000401
```

**Root cause of the immediate quarantine decision is now isolated:**
after acknowledged shutdown/disabling, the **ANS HMB base comparison
and HMB size comparison both fail**, while every other logged
qualification predicate remains true. The original pre-start
qualification is therefore unsuitable as an *identical* post-stop
condition on this hardware. Exactly which post-stop values are in
those registers is still unknown: the failed comparisons alone do not
establish that the fields cleared to zero.

The next fresh-boot experiment subsequently read the HMB **IOVA
descriptor** base-low/base-high and size after shutdown, with the
ANS MMIO window verified accessible. Its exact results are recorded
below. The implementation added **no cleanup behavior**, and the
quarantine remained intact.

Do **not** remove the gate or free DMA buffers simply because shutdown
succeeded. DART0 reported a retained fault and NVMMU still had FIFO
status; queue, HMB/SART, NVMMU and DART retirement remain independently
unproven. The actual phone session is again quarantined with GPIO160
low, BME off, WLAN and USB functional. Full reboot is required before
another storage-controller hardware experiment.

## Next experimental checkpoint — exact HMB register readback

The post-disable predicate recorder (module hash
`5c38e7a2fd2af773847abbc3b1b68cb6e6955e39fac88d1cb65e0da9af240555`)
**has now been physically tested** in the third one-shot boot, producing
the mismatch matrix above. It retained its full quarantine safeguards.

The successor adds **read-only** capture of the *IOVA descriptor*
registers `0x1810`, `0x1814` and `0x1818`, only if the MMIO
window is accessible. It reports their values and zero-state bits;
these are NOT HMB physical backing addresses. It does not clear the
descriptor, change bus-master state, call a release path or skip the
original post-start qualification check. Host tests: all 47 S3E test
cases pass, including a modeled post-stop qualifier failure. The
next AArch64 module is compiled with SHA-256:

`e1dff6a7fd61a9d4508db4d8011e54178e5da7a7fccde36bc88a4fc00063cd88`

### Fourth physical boot: ANS HMB is cleared by shutdown

The successor with SHA-256
`e1dff6a7fd61a9d4508db4d8011e54178e5da7a7fccde36bc88a4fc00063cd88`
was physically exercised in **one further fresh RAM Linux boot** on
2026-11-18. All eight battery samples passed at 74% state of charge,
37.3 °C, voltage approximately 4.03–4.09 V. It successfully completed
the same single Identify Namespace 1 and both shutdown phases:

```text
IDENTIFY_NAMESPACE_REAL nsid=1 nsze=15625000 lba_bytes=4096
    capacity_bytes=64000000000 data_tail_arrived=1
ADMIN_SHUTDOWN_TRACE attempted=1 rc=0 csts=00000009
    disable_rc=0 disable_csts=00000000 inner_rc=0 master_off=1
ADMIN_POST_DISABLE_PREDICATES qualified=0 prepared=1 dart_mapped=1
    hmb_owned=1 ans_ready=1 ans_hmb_base_ok=0 ans_hmb_size_ok=0
ADMIN_POST_DISABLE_HMB_DESCRIPTOR accessible=1
    iova_base_low=00000000 iova_base_high=00000000
    size_bytes=00000000 base_zero=1 size_zero=1
ADMIN_STAGE rc=-3 dart_fault=00000500 nvmmu_fifo=00000501
```

**Confirmed hardware behavior:** all three ANS HMB descriptor
registers (`0x1810`, `0x1814`, `0x1818`) are **zero after normal
shutdown and disable**. The apparent post-stop qualification failure
was therefore caused by comparing an expected *pre-start* descriptor
against an intentionally cleared *post-stop* descriptor. It is no
longer necessary to guess whether these fields clear or change to
other nonzero values.

**Crucial distinction:** this proves the controller cleared its HMB
*descriptor*, not that all DMA writes are drained, all FlatDMA
descriptors have retired, DART queue translations have been unmapped,
NVMMU invalidations are acknowledged, or SART/HMB physical backing
pages can be freed. The DART fault and NVMMU FIFO remain recorded.
The fourth physical session is left in the original **pinned
quarantine** with bus mastering off and NAND reset low. No Linux
block device, filesystem mount or NAND write has occurred.

### Next offline candidate

A new **read-only** snapshot extends the post-disable diagnostic log with
booleans for queue register zero-state vs. the owned queue IOVAs, DART
queue-translation ownership, the DART fault register, and NVMMU FIFO
status. It does **not** call the DMA release path. The successor was
compiled for the same AArch64 kernel with SHA-256:

`c5ffb202c7511d67b55a8bb4407660086075846b2b7928c607ff444995865f54`

All **50 S3E tests** (including three offline snapshot contract checks)
pass. A private one-shot test harness has been prepared, with the current
kernel boot ID recorded to **reject this quarantined session**. The
new candidate has **not** been physically loaded. A fresh boot must
reverify the USB SSH host key and battery gates before its first and
only Identify. This will separate a normal controller-local descriptor
clear from remaining host/translation retirements.

No further NVMe command is permitted in the currently quarantined
session. A future physical experiment needs its own full restart,
revalidated USB SSH host key, verified iOS backup, eight battery
samples and a unique one-shot marker.

Once the exact predicate is known, design a *separate* verified
post-disable safety condition that proves every relevant DMA address
has been retired and all MMIO / IOMMU resources can be freed. Do not
skip the staged queue, HMB/SART, NVMMU and DART teardown order.

This is a controller-admin proof and teardown-diagnostics milestone,
**not** a mounted namespace, read-only filesystem or persistent OS.


### Fifth physical boot: controller queues and translation state

On a fresh N71/S8000 RAM Linux boot, with a unique verified boot ID,
USB SSH authentication, 72% battery and all eight temperature/voltage
preflight samples passing (37.4–37.5 °C), the next one-shot module
(SHA-256 `c5ffb202c7511d67b55a8bb4407660086075846b2b7928c607ff444995865f54`)
again completed **Identify Namespace 1**, confirmed normal NVMe shutdown
(`CSTS=0x9`), disabled the controller (`CC=CSTS=0`) and turned
both PCIe bus-master bits off. Its read-only snapshot showed:

```text
ADMIN_POST_STOP_DMA_SNAPSHOT hmb_descriptor_zero=1
  queues_zero=0 queues_owned_io_va=1 dart_queues_mapped=1
  dart_fault=00000500 nvmmu_fifo=00000301
  no_dma_release_attempted=YES quarantine_unchanged=YES
```

**New physical finding:** the NVMe controller clears the host-memory
buffer *descriptor* on shutdown but **does not clear the admin queue
registers**. The same Linux-owned SQ/CQ IOVAs remain programmed, and
DART queue leaf mappings remain installed by the pilot. A nonzero DART
fault and NVMMU FIFO readback were also observed. These values are
diagnostics, **not proof of active outstanding DMA** and not proof
that device-side DMA has fully retired.

The driver again returned `-3` and kept its DMA, HMB, NVMMU and DART
memory pinned, with NAND reset low. Linux USB SSH, WLAN and the UI
continued functioning. No block device, filesystem mount, partition
read or NAND write was attempted.

### First controlled queue register retirement pilot: built, NOT loaded

The next step is deliberately smaller than full DMA teardown. A new
explicit module parameter `ans_queue_retire_probe=1` will authorize
**only** writing zero to NVMe `AQA/ASQ/ACQ` *after* a successful
Identify + acknowledged shutdown + disable + readback of BME-off,
CC/CSTS zero, the observed cleared HMB descriptor, owned queue IOVAs,
NAND reset low, and still-owned DART/SART mappings.

Every prerequisite is fail-closed; all 52 S3E host tests pass, including
a separately compiled C gate model that rejects each missing
precondition. Default parameter remains **off**, and after any trial,
successful or not, the module **always forces the original `-3`
quarantine**. There is no DART unmapping, NVMMU invalidation, page
freeing, HMB release or block I/O in this new probe.

The private AArch64 candidate was compiled but has **not been
physically loaded**. SHA-256:

`9eeb73fe5e02b8b65bcfd11cb01b1266482449efb21aa6f6cc29ba02f3d8428c`

A fresh phone boot, independently verified USB host key, validated
backup and eight gauge samples are mandatory before any use. The
present boot already contains a pinned module and must not be reused.

### Boot payload provenance caveat

An independent on-phone runtime-archive SHA-256 check identified the
current running filesystem as the **2026-11-17 three-pillars runtime**,
not the newer hold8/chargepilot bundle, despite native Linux and
connectivity starting normally. The newer shell supervisor was
therefore absent, although the kernel-side 300 mA SN2400 pilot
remained active. The supervisor was staged in the phone's `/run`
RAM filesystem and successfully passed a read-only power preflight.
**Continuous automatic renewal was not enabled.**

A private fail-closed attestation helper now checks the exact runtime
archive checksum, available charging script and splash before a boot
can be called a verified Showcase/chargepilot build. This finding does
not undermine the physically logged NVMe register behavior, but
future test records must distinguish the base Linux runtime from the
intended user-interface bundle.


### Sixth physical boot: queue-retirement safety gate refused

A fresh **exact-runtime-attested** CYBERDECK // ARLO RAM Linux boot
was established over the USB gadget. Unlike the earlier runtime-image
mismatch, the on-device integrated archive SHA-256 matched the
2026-11-18 hold8/chargepilot build and the phone-side SN2400
supervisor script was installed.

The one-shot opt-in queue-register retirement pilot, module SHA-256
`9eeb73fe5e02b8b65bcfd11cb01b1266482449efb21aa6f6cc29ba02f3d8428c`,
passed the verified iOS backup, unique kernel boot ID and all eight
battery preflight samples (72% SOC, ~37.3 °C, ~4.05–4.09 V).
It once again completed the real 64 GB Identify Namespace 1, normal
shutdown, controller disable and PCIe bus-master disable.

At the queue retirement step the fail-closed qualification refused:

```text
ADMIN_POST_STOP_DMA_SNAPSHOT hmb_descriptor_zero=1 queues_zero=0
  queues_owned_io_va=1 dart_queues_mapped=1 dart_fault=00000500
  nvmmu_fifo=00000201 no_dma_release_attempted=YES
ADMIN_QUEUE_RETIRE_PROBE refused=1 exact_gate=0 DMA_QUARANTINE=YES
```

**No queue registers were modified or cleared** by this probe; all
DART/HMB/NVMMU allocations stayed pinned and NAND reset was held low.
The existing snapshot establishes most of the prerequisites, but does
**not** identify the exact failing extra condition. In particular,
`INTMS` after shutdown is not necessarily required to retain its
pre-shutdown value; it is a diagnostic hypothesis rather than a proven
cause. Do not remove this gate or retry in the same boot.

The next AArch64 diagnostics-only build logs each of 13 guard outcomes
as a **boolean**, without printing DMA addresses or sensitive
identifiers. The original strict qualification and no-free quarantine
logic are unchanged. This successor is not physically boot-tested.
Compiled module SHA-256:

`f101215566511f7b638ca33f09ab6000c97a2a3249d7d562a1b762dd7cd570d7`

This checkpoint clarifies the engineering sequence: first determine
why the queue-clearing safety gate refuses; only then consider queue
register retirement. Proving DART/NVMMU/HMB DMA retirement and building
a read-only Linux block device are **separate later milestones**.


### Seventh physical boot: queue qualification blockers (19 November 2026)

The newly tested S8000 RAM-only session again successfully identified
Namespace 1: 64,000,000,000 bytes, 4,096 bytes per LBA. A fresh
authenticated USB SSH kernel boot, verified encrypted iOS logical backup,
active charging lease and eight independent electrical samples all
passed before this one physical S3E attempt. The tested AArch64 module
SHA-256 was 4239d197308190b49594022af840c3cbae12d0e09d1501a78138bee618773849.

The controller acknowledged shutdown at CSTS=0x9, was disabled with
CC=CSTS=0 and both PCIe bus mastering command words restored to 2.
The diagnostic reported 11/13 successful safety predicates, with
exactly reset_low=0 and intms_bit0=0 failing. In particular, the storage
reset was still released at the controller-local queue check, and the
mask bit that was set during queue preparation did not survive into
the post-disable check. No queue register was cleared.

The separate admin-core post-disable qualification also failed because
its original startup predicate still demands a configured 8 MiB HMB
descriptor, whereas the real controller sets that descriptor to zero
during normal shutdown. Startup qualification and post-stop teardown
must be independently modeled; they cannot be treated as identical.

On refusal, all DMA/HMB/DART/NVMMU memory remained pinned; reset GPIO160
was asserted low by the subsequent unwind. The Linux USB, WLAN and UI
continued operating. No block device was created, and there was no
partition read, mount, or NAND write. Never repeat a storage experiment
in the current quarantined kernel session.

A successor, purely observational ARM64 module with opt-in
ans_phase_trace_ro=1 and ans_queue_retire_probe=0, now records INTMS
bit0 and PERST before and after the existing enable, shutdown, and
disable CC operations. It changes no queue or DMA safety gate. The
offline build SHA-256 is
1fd780cad167f93cd0969a32a66436ce7857a17b2a40d8aa603e0f11e8fb6fcf.
This candidate is compiled and host-tested, NOT physically loaded.
No persistent NAND storage or safe DMA-release conclusion follows.
