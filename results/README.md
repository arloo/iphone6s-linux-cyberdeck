# Sanitized hardware evidence

Machine-readable, **manually reviewed** evidence lives here. The CI validator checks syntax, privacy and consistency, but **cannot validate a hardware event merely because a JSON file exists**.

Every real-device result must identify the foundry profile, pinned kernel source commit, specific test ID, test date, pass/partial/failure state and a linked narrative report. Hardware tests are **never executed automatically in GitHub Actions**.

Do **not** upload: proprietary Apple firmware or per-device calibration, raw ADT/iOS data, device serial/UDID, MAC/IP-linked identifier logs, SSH keys, passwords, personal accounts, or full raw evdev/event traces. Prefer aggregate counters, status codes, register values known to be non-unique, and original GPL source with precise preflight/recovery conditions.

Four S8000 records cover **SPI2 host lifecycle, touch-clock rollback, analog-rail rollback and strict HBPP register identification**. None proves working multitouch. No S8003 live-test evidence is currently available.
