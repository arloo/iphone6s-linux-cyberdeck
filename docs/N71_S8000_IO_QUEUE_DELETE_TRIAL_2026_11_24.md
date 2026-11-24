# N71/S8000 empty I/O queue deletion trial — 2026-11-24

## Evidence and question

The corrected create-only pilot physically completed Admin Create I/O CQ and SQ, QID 1/depth 16/flags 0, then observed CFS during normal shutdown and could not clear RDY. This acceptance is already recorded in [the physical report](N71_S8000_IO_QUEUE_ACCEPTANCE_2026_11_24.json). Create acceptance must not be reported as a stable queue lifecycle or a namespace block-data read.

The tested kernel's native `drivers/nvme/host/pci.c` calls `nvme_delete_io_queues` before `nvme_disable_ctrl`; its helper waits for Delete SQ before issuing Delete CQ. Its `include/linux/nvme.h` defines Admin Delete SQ opcode 0x00, Delete CQ 0x04 and QID at byte 40. The candidate checks this ABI at kernel compile time. This inspected primary source motivates an explicit empty-queue teardown experiment; it does not prove the cause of the S8000 CFS.

## New opt-in

`ans_io_queue_delete_once=1` is disabled by default and requires `ans_io_queue_once=1`, the accepted Identify ownership chain and an explicit queue-command flag. The planned trial keeps byte1=0, matching the physical creation result; its changed variable is the added SQ-before-CQ deletion. Identify and Create CQ/SQ are setup for this new teardown observation, not repeat milestones.

After **both** Create completions validate, the candidate submits exactly Admin Delete SQ CID 4, then Delete CQ CID 5 on QID 0. The fixed target queue identifier is 1. Namespace, PRP, data and reserved fields remain zero. All 64 command bytes must match the canonical encoding; there is no arbitrary command or NVM path. Only existing Admin SQ-tail/CQ-head doorbells are used.

The queues are unused: this candidate never submits an NVM command or writes an I/O queue doorbell. Failed qualification, foreign SQ/CQ memory, invalid completion, timeout or controller state stops the sequence. Delete CQ never follows an unsuccessful Delete SQ. Command phase, copied status, CID, SQID 0 and exact head 4/5 are checked before acknowledgement. Each posted command and the overall deletion attempt have a no-retry latch.

**All backing remains retained**, including after accepted deletion or successful controller shutdown. No DMA page, DART/NVMMU/HMB mapping, GPIO/power owner or original module is freed. Queue-context deletion is not independent proof of transaction drain. The current CFS/quarantined boot cannot be reused or have its driver replaced; a fresh owner-attended RAM boot is required.

## Expected observations

1. Existing Identify/Create CQ/Create SQ setup validates with the previously accepted geometry and flags.
2. `IO_QUEUE_DELETE_ONCE rc=0` reports both validated deletion completions, CID 4/5.
3. `ADMIN_SHUTDOWN_TRACE` reports shutdown rc 0/CSTS 9, disable rc 0/CSTS 0 and master_off=1.
4. All backing remains quarantined and no NVM Read/Write or block device appears. The whole pilot may still report rc=-3 because DMA release remains forbidden.

If deletion succeeds but shutdown still raises CFS, the lifecycle hypothesis is not sufficient. Preserve the distinction between accepted commands and the failure, keep all resources pinned and investigate the retained controller/transport evidence before a new experiment. Do not automatically switch flags or issue a data Read.

## Host validation

The portable C harness checks independent wire bytes, SQ-before-CQ ordering, failure/qualification stops, invalid arguments, all 16-bit completion status values, and single-bit command mutations. Source checks cover early opt-in rejection, both-Create prerequisites, one-shot latching, validation before acknowledgement, Admin-only doorbells and absence of backing release. The exact-kernel ARM64 build and complete suite are recorded after validation; this candidate has not been physically loaded.

The exact-kernel ARM64 build and all **1,919** host tests pass, followed by the HBPP audit and evidence validator. The private RAM image embeds module `a88fe1d4d46fd249779f5767e03419ccaa02ca9d4c26e94db21c9b0a12028f75`, inert at boot; image SHA-256 is `818cd3dd8ec2daeef1095b7536e70c01fb1d485dd02bed84c28f9864c5aa3d0f`. Only the storage module and runtime hash manifest differ from the physically booted reference; the charger, remaining rootfs and entire boot/kernel prefix are unchanged. [Sanitized candidate metadata](N71_S8000_IO_QUEUE_DELETE_CANDIDATE_2026_11_24.json) records the boundaries. The updated attended launcher is ready; this image has not been physically booted.
