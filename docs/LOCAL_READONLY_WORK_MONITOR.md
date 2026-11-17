# Local read-only development monitor

The Dell can stream genuine local job commands and stdout/stderr to a
Linux Mint terminal over the same LAN. The viewer has no command-input
endpoint. No SSH server or Mint agent installation is required.

On the Dell, launch the service on its explicit private LAN address:

    python3 tools/cyberdeck_live_console.py --state-dir /path/to/private/state --bind 192.168.1.10 --network 192.168.1.0/24 serve

The private connection.json in that state directory contains the view URL.
Keep this runtime directory outside the public repository. Its permissions
are 0700; token, connection metadata and log files use 0600.

On Mint, use the owner's actual URL:

    curl -N "$CYBERDECK_VIEW_URL"

Ctrl+C stops that viewer. The service stays on the Dell. Both machines must
retain LAN connectivity; the Dell must remain running.

The operator executes work through the local recording runner:

    python3 tools/cyberdeck_live_console.py --state-dir /path/to/private/state run -- python3 -u /path/to/actual_job.py

Only locally started jobs execute. HTTP accepts authenticated GET streams;
POST/PUT/PATCH/DELETE and execution-like paths are rejected. The service
binds a specific private interface, checks the client subnet and limits
concurrent viewers. Terminal escape sequences and named credential patterns
are filtered. Actual commands must still avoid printing secrets.

The stream includes recent recorded output, followed by new output and
explicit idle heartbeats. Saved phone results must be marked historical.
Disconnecting the iPhone does not stop the Dell monitor; phone hardware
tests and USB telemetry pause until reconnection.
