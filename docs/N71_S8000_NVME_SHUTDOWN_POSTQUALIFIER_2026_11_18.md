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

Some hardware registers may legitimately change upon NVMe shutdown,
but it is **not yet proven** which specific predicate failed on this
S8000. This finding does **not** authorize removal of the gate or the
freeing of DMA buffers.

## Prepared next step — diagnostic only

A stricter post-disable predicate recorder has been added to the
public research sources. It reports only boolean / comparison
results for each precondition (prepared flag, DART mapping, HMB
owner, ANS readiness and base/size, endpoint/root command bits,
CC/CSTS zero, NVMMU control/invalidations) and **retains exactly the
same quarantine behavior**. The core's qualification callback keeps
the original short-circuit ordering.

Host tests: 47 S3E test cases pass, including a modeled case with
successful NVMe shutdown and controller disable but a failed
post-disable qualifier. The matching AArch64 kernel module has been
compiled, SHA-256:

`5c38e7a2fd2af773847abbc3b1b68cb6e6955e39fac88d1cb65e0da9af240555`

**This next candidate has not been physically loaded**. It must be
tested only after a full phone reboot, fresh battery/USB preflight,
owner-verified backup and confirmation that the previous quarantined
controller session has been cleared. The presently booted device
remains in its intentional quarantine state. No further Identify
should be attempted in the current RAM session.

Once the exact predicate is known, design a *separate* verified
post-disable safety condition that proves every relevant DMA address
has been retired and all MMIO / IOMMU resources can be freed. Do not
skip the staged queue, HMB/SART, NVMMU and DART teardown order.

This is a controller-admin proof and teardown-diagnostics milestone,
**not** a mounted namespace, read-only filesystem or persistent OS.
