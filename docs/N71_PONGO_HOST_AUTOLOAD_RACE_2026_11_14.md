# N71 Pongo host USB autoload race, 14 November

The real Dell journal records correct DFU enumeration (05ac:1227) in two owner-triggered wrapper runs. After apple_mfi_fastcharge was removed, it registered again during the first checkm8 reset. USB control transfers then failed with -110/-71; neither Pongo nor the Linux payload was accepted. Later iOS enumeration returned. This establishes a host-driver reload race alongside exploit failures, not proof that it is the sole cause of every failed boot.

The palera1n help confirms --cli -p -k Pongo.bin is the intended override/early-exit invocation. The original wrapper's fresh modprobe-policy check did not prevent the observed reload. The actual host 80-drivers.rules schedules the udev kmod builtin for device modalias events.

The revised wrapper temporarily overrides 80-drivers.rules in /run with a generated copy of the vendor file, prepending one guard that skips device-level autoload for the owner's Apple iOS/recovery/DFU/Pongo/Linux USB IDs. Interface events and all other vendor rules remain unchanged. udev is reloaded and its queue drained BEFORE unloading MFi and invoking palera1n. MODALIAS itself is read-only on this host, so no attempt to alter that property is used. The candidate full rule file passed the real udevadm259 verifier.

Both runtime files must match recognized generated content before either is removed or reused. Custom /etc driver rules cause a stop rather than being overwritten. Restore removes the two temporary /run policies, reloads/settles udev and reloads MFi; a Dell reboot also removes them. The owner script was updated with a private pre-fix backup. No privileged runtime policy was applied by the assistant; the next interactive owner run applies it.

Eight fixture-host tests execute the actual wrapper control flow with isolated paths, fake USB/root commands and a synthetic Pongo file. They verify reload/settle/unload/exploit ordering, vendor-rule preservation, foreign-policy protection, failure stops, and refusal to report Pongo success without USB05ac:4141. A nonzero palera1n exit is reported separately and does not override a confirmed Pongo gadget. No Apple binaries, raw private journal or unique device identifiers are included.

Status: source/rule/fixture validation PASS; corrected physical Pongo handoff PENDING. Do not send the Linux image until Pongo05ac:4141 is actually confirmed.
