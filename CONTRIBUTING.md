# Contributing

The project seeks **working touchscreen, Wi-Fi and Bluetooth** on iPhone 6s (N71/S8000) before UI or feature expansion.

## First steps

1. Search existing issues: avoid duplicate work.
2. Specify device model (e.g. N71 Samsung `apple,s8000`) and kernel commit.
3. State what was physically tested versus proposed or simulated.
4. Include focused, reproducible steps and the **minimum safe log excerpts**.
5. Send one subsystem per pull request: touch, wireless, Bluetooth, boot, or tooling.

## Required validation

- Build succeeds for the target AArch64 configuration.
- All changes are reviewable patches or original source.
- Runtime report includes exact driver binding/probe result; a present HCI or input device is not proof of full functionality.
- No deliberate changes to iPhone internal storage.
- Describe recovery/rollback and prerequisites.
- Never encourage unauthorized scanning or interference.

## Privacy and firmware

**Do not commit:** private Apple firmware, IPSW, proprietary patches, per-device SysCfg/NVRAM/calibration, serials, IMEI, MAC/Bluetooth addresses, raw `/proc/device-tree/serial-number`, private SSH keys, authentication tokens, user directories, or raw unreviewed `dmesg` logs.

Hardware-specific firmware must be independently sourced and handled according to its license. Our repositories provide **instructions or open-source tools**, not redistributed vendor blobs.

### Git author privacy and push protection

Use a GitHub-generated **noreply** email for both author and committer identities, and enable `user.useConfigOnly` to prevent fallback to a private global email. From the repository directory, run `git config core.hooksPath .githooks` to activate the versioned `pre-push` privacy gate. The gate rejects reachable commits with non-noreply author/committer emails, personal emails in commit messages, and personal email addresses in tracked text; it does not print rejected addresses. Run `python3 tools/security/check_git_privacy.py` manually before publishing.

After a history rewrite, **do not merge or force-push a clone containing the old history**. Re-clone or properly clean old clones, because pushing an old branch can reintroduce removed metadata.

## Style

All repository issues, docs, pull requests and comments should be in English for global collaboration. Prefer focused reproducible experiments over speculative driver claims.
