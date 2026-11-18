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

The next experimental candidate reads the HMB **IOVA descriptor**
base-low/base-high and size once after shutdown, *only* while the
ANS MMIO window remains qualified, recording whether each field is
zero. It adds **no cleanup behavior** and keeps the same quarantine.
It is not yet physically boot-tested.

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

**This successor has not been physically loaded**. It requires a
full fresh phone boot, fresh eight-sample battery qualification,
verified backup and confirmed reset of the previous quarantined
controller session. Do not execute another Identify or unload the
pinned module during the current boot.

Once the exact predicate is known, design a *separate* verified
post-disable safety condition that proves every relevant DMA address
has been retired and all MMIO / IOMMU resources can be freed. Do not
skip the staged queue, HMB/SART, NVMMU and DART teardown order.

This is a controller-admin proof and teardown-diagnostics milestone,
**not** a mounted namespace, read-only filesystem or persistent OS.
