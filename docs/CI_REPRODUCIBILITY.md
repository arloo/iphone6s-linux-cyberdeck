# Reproducible A9 bring-up: CI, upstream pins and RAM packaging

**Status: engineering infrastructure, 2026-11-10.** These commands do not establish on-device support. Evidence for physical tests is recorded separately.

## Three levels of proof

| Level | Where | What it proves | What it never proves |
| --- | --- | --- | --- |
| **OFFLINE** | GitHub Actions and any Linux/Python host | Protocol frame models, source contracts, source-pin validation, sanitized result schemas, privacy guards, synthetic EVDEV acceptance tests | Actual controller ACKs, touch coordinates, firmware compatibility, RF operation |
| **BUILD** | GitHub Actions x86_64 runners with AArch64 cross-toolchain | Four public-source AArch64 userspace ELF files, and on explicit manual opt-in the patched Linux ARM64 driver objects | Bootability, correct DTS for an actual board, safe kernel flashing, a functional touch device |
| **HARDWARE** | Physical iPhone 6s with recorded foundry/board, exact booted kernel | RAM boot, SPI2 state, clock/rail readback, checksum-valid HBPP register reads, eventually real EVDEV touches and Wi-Fi/Bluetooth | Behavior on any other board/foundry without independent test |

The check statuses are **NOT interchangeable**. A source test cannot update an S8003 hardware result. CI cannot mark EVDEV functional without a **sanitized, independently reviewed real-device capture**.

## Continuous integration

The [versioned GitHub Actions workflow template](../ci/verify.yml) has been tested locally but is **NOT YET ACTIVE ON GITHUB**. Both the current git-push OAuth credential and the GitHub connector returned a workflow-permission rejection. To activate it, the repository owner must authorize a GitHub identity with **workflow-write** permission and commit the exact template to `.github/workflows/verify.yml`. No credential bypass is attempted.

**Once activated**, the workflow will run on pushes to `main` and pull requests:

1. `OFFLINE`: Python synthetic models, input-validation tests, [test-matrix schema](../manifests/test-matrix.json), and Git identity/PII checks.
2. `BUILD`: cross-compile all four independent public-source userspace tools as static **AArch64** ELF images and verify the ELF machine field. BlueZ headers are copied into an isolated include directory; host-system glibc headers are not added to the AArch64 include path. Only these original userspace diagnostics are retained as CI build artifacts.
3. `BUILD - opt-in`: manual `workflow_dispatch` with `compile_kernel_rfc=true` fetches the pinned public Linux source and compiles the four RFC-patched Z2 and touch-clock ARM64 driver objects. It deliberately does **not** upload boot images, proprietary firmware or kernel artifacts.
4. `HARDWARE`: not runnable on GitHub-hosted runners. An engineer must execute the documented gate on a real device, sanitize the evidence, and commit a manually reviewed entry in `results/` and the foundry-specific matrix.

GitHub Actions produces **software check statuses**, never a fictional hardware-success badge. Until activated, the results in this document are **local manual validations**, not green GitHub-hosted CI checks.

## Upstream source provenance

[manifests/upstreams.json](../manifests/upstreams.json) pins full 40-character Git SHAs and original HTTPS URLs for Linux, m1n1, the boot kit and documentation. The manifest records that **S8000/N71 is live-tested** and **S8003/N71m is not**.

To fetch the exact public source tree (internet access required):

```bash
python3 scripts/fetch_upstreams.py --destination /tmp/a9-upstreams --component linux
python3 scripts/fetch_upstreams.py --destination /tmp/a9-upstreams --component linux --verify-only
bash scripts/check_kernel_rfc.sh /tmp/a9-upstreams/linux /tmp/a9-object-check
```

The fetcher refuses a changed Git origin, dirty source checkout or incorrect SHA. The kernel check copies patches into a temporary disposable worktree rather than modifying its upstream clone. The kernel job is an **object-level compilation smoke test**, not a standalone bootable `Image.gz`.

## RAM-only boot payload (operator-provided inputs)

The [packer](../scripts/pack_ram.py) reproduces the pinned upstream boot concatenation contract using only explicit local inputs. It never accesses an iPhone, launches PongoOS or fetches proprietary blobs:

```bash
python3 scripts/pack_ram.py \
  --m1n1 /path/to/operator-built/m1n1.bin \
  --dtb-s8000 /path/to/s8000-n71.dtb \
  --dtb-s8003 /path/to/s8003-n71m.dtb \
  --image /path/to/Image.gz \
  --initramfs /path/to/operator-supplied/initramfs.gz \
  --output /path/to/new/m1n1-linux.bin
```

It checks DTB and gzip framing, fully verifies gzip CRCs, rejects symlinked inputs, refuses to overwrite an output and prints the SHA-256 of the resulting RAM blob. The m1n1 binary and initramfs must be built or supplied independently by the authorized operator; **this repository does not include them**. Passing a format test or constructing a RAM blob does **not** establish safe bootability.

Two DTBs are packaged so m1n1 can select the matching chip; the existence of the S8003 DTB is **not** S8003 hardware evidence. Physical boot remains a separate, attended DFU → PongoOS → m1n1 → Linux operation with known-good RAM recovery paths. **Never flash iOS NAND.**

## Evidence hygiene

Every `results/*.json` artifact is a reviewed summary with board profile, test identifier, observed date, source SHA, result level and matching documentation. Never upload raw logs, serial numbers, Apple provisioning, calibration, MAC addresses, unique Bluetooth IDs, firmware dumps, tokens, certificates or keys. The public test matrix is [manifests/test-matrix.json](../manifests/test-matrix.json). Changes to hardware status require manually inspected evidence and must not be inferred from CI.
