# N71/S8000 full-reserve branch for one bounded storage trial — 27 November 2026

## Observed reason and scope

The exact checkpoint-pair RAM image booted with fresh N71/S8000 identity, direct configured500mA USB, strict key-only SSH, all twelve runtime hashes and the expected helper/storage/charger components. The native500mA/7200s charger applied at89.67s but its battery guard observed4.225V at91.77s, stopped monitoring and restored original input00 with rc0. The charger must not be rearmed merely to make a storage power criterion pass.

The first CPU-only eight-sample window then measured97% reported and96.688% RC/FCC,1,080,000uAh Remaining Charge, Good health,32.9C, cell3.984–4.065V and155–293mA discharge with USB configured. Original input is restored. No S3E owner, hardware attempt or probe exists yet. This large measured reserve permits a separately declared full-reserve storage branch; it does not qualify charging, a peak-current limit or runtime endurance. Requalify the window immediately before insertion; the initial window is preparation evidence only.

## Alternative gate, declared before NAND I/O

The existing positive-current charging branch remains unchanged. This additional branch applies only after the exact native battery guard-stop and successful original-input rollback, with no charger rearm/replacement. Require all eight fresh samples over10–40 seconds, increasing timestamps at least0.5s apart, configured direct USB, Good health and known gauge status. Every sample must satisfy reported and RC/FCC at least90%, Remaining Charge at least1,000,000uAh, RC not above FCC and reported/derived agreement within2 points, cell3.6..<4.1V,10..<35C and absolute idle current no more than500mA. RC spread must be at most5000uAh and FCC spread at most1000uAh. An immediate sample must still pass before the one insertion.

Reserve planning uses1A for120 seconds, rounded up to33,334uAh, with at least25 such model windows left in the measured reserve. This is a conservative planning assumption, not proof of a physical peak-current ceiling, a hardware abort timer or autonomous endurance. The unchanged four-Read kernel/helper protocol keeps its existing finite waits and failure/quarantine paths. A longer or different hardware plan is not admitted by this gate.

The host must also independently bind exact source/image/runtime identity, new unused epoch, private GPT pair selection, native rollback state and direct USB. The pure validator does not attest those conditions or control power. No source/native electrical/thermal/voltage limits are relaxed; no charger rearm, NAND Write, DMA release, forced owner unload, ring reuse or retry is authorized.

## Host evidence

Four new independent tests cover the reserve/units calculation, each electrical/gauge/status/schema failure, missing/nonfinite/boolean or sparse/reordered samples, gauge drift and boundary values. The focused four-test gate suite passes. The unchanged RAM/helper/storage candidate retains its prior2004-test evidence; those tests are not relabeled as a new hardware success. [Pure host validator](../scripts/n71_storage_full_reserve_gate.py), [gate tests](../tests/test_n71_storage_full_reserve_gate.py), [checkpoint pair physical contract](N71_S8000_APFS_CHECKPOINT_PAIR_TRIAL_2026_11_27.md).
