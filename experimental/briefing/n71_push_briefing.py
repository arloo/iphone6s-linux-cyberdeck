#!/usr/bin/env python3
"""Push a reduced AI briefing over the existing pinned, USB-only SSH channel.

No Gmail/Calendar OAuth credentials, API tokens, raw messages or chat-history
files travel to the device. Default mode is a metadata-only dry run.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import unicodedata
from zoneinfo import ZoneInfo

STATE = Path.home() / ".local/share/cyberdeck/reader-state.json"
SSH_CONFIG = Path.home() / "Documenti/cyberdeck-a9-linux/private-touch-live-test/n71-ssh-20261116/client-config-PRIVATE.json"
MAX_BYTES = 24576
ZONE = ZoneInfo("Europe/Rome")
ANSI = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")

def clean(value, limit=500):
    if not isinstance(value, str):
        return ""
    return ANSI.sub("", value).strip()[:limit]

def payload_from(state, now=None):
    if not isinstance(state, dict):
        raise ValueError("Briefing state must be a JSON object")
    generated = datetime.fromisoformat(state.get("generated_at", ""))
    if generated.tzinfo is None:
        raise ValueError("Missing timezone in generated_at")
    now = now or datetime.now(ZONE)
    age = (now - generated).total_seconds()
    if age < -300:
        raise ValueError("Briefing timestamp lies in the future")
    if age > 30 * 3600:
        raise ValueError("Briefing is too old for an automatic device push")
    brief = state.get("brief", {})
    if not isinstance(brief, dict) or state.get("error"):
        raise ValueError("Briefing missing or marked as failed")
    summary = clean(brief.get("overview"), 2600)
    if not summary:
        raise ValueError("Empty AI summary")
    def rows(key, fields, limit):
        return [
            {f: clean(row.get(f), 300) for f in fields}
            for row in brief.get(key, [])[:limit]
            if isinstance(row, dict)
        ]
    agenda = []
    for event in state.get("agenda", [])[:8]:
        if isinstance(event, dict):
            agenda.append({f: clean(event.get(f), 150) for f in ("title", "start", "end", "location")})
    src = state.get("source_status", {})
    statuses = {key: clean(str(src.get(key, "unknown")), 40)
                for key in ("mail", "calendar", "whatsapp")}
    compact = {
        "schema_version": 1,
        "generated_at": generated.isoformat(),
        "pushed_at": now.isoformat(),
        "cached": age > 4 * 3600,
        "sources": statuses,
        "whatsapp_is_notification_only": True,
        "overview": summary,
        "actions": rows("actions", ("title", "reason", "source"), 10),
        "todos": rows("suggested_todos", ("text", "priority", "due", "source"), 8),
        "agenda": agenda,
    }
    if not isinstance(brief.get("actions"), list) or not isinstance(brief.get("suggested_todos"), list):
        raise ValueError("Invalid AI result shape")
    encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":")).encode()
    if len(encoded) > MAX_BYTES:
        raise ValueError("Briefing exceeds device output limit")
    lines = [
        "CYBERDECK A9 | TODAY",
        "Generated: " + compact["generated_at"],
        "Status: " + ("CACHED: refresh recommended" if compact["cached"] else "CURRENT"),
        "Sources: mail=" + statuses["mail"] + " calendar=" + statuses["calendar"]
        + " whatsapp=" + statuses["whatsapp"] + " (notifications only)",
        "",
        "OVERVIEW",
        summary,
        "",
        "ACTIONS",
    ]
    for i, action in enumerate(compact["actions"], 1):
        lines.append(str(i) + ". " + action["title"] + " [" + action["source"] + "]")
        if action["reason"]:
            lines.append("   " + action["reason"])
    lines += ["", "UPCOMING AGENDA"]
    for ev in agenda:
        lines.append(ev["start"][:19] + " | " + ev["title"])
    lines += ["", "SUGGESTED TODOS"]
    for todo in compact["todos"]:
        lines.append("* [" + todo["priority"] + "] " + todo["text"] + " [" + todo["source"] + "]")
    lines += ["", "NOTE: AI proposals are not executed automatically.", ""]
    text = unicodedata.normalize("NFKD", "\n".join(lines)).encode("ascii", "replace")
    if len(text) > MAX_BYTES:
        raise ValueError("Text briefing exceeds device output limit")
    return compact, encoded, text

def ssh_push(config, filename, data):
    args = [x for x in config["ssh_common_args"] if x != "-n"]
    command = ("umask 077; mkdir -p /run/cyberdeck && chmod 700 /run/cyberdeck && "
               "cat > /run/cyberdeck/" + filename + ".tmp && "
               "chmod 600 /run/cyberdeck/" + filename + ".tmp && "
               "mv /run/cyberdeck/" + filename + ".tmp /run/cyberdeck/" + filename + " && "
               "printf N71_BRIEF_PUSH_OK")
    call = args + ["-i", config["identity_file"], config["target"], command]
    proc = subprocess.run(call, input=data, capture_output=True, timeout=20)
    if proc.returncode != 0 or proc.stdout.strip() != b"N71_BRIEF_PUSH_OK":
        raise RuntimeError("Authenticated USB briefing transfer failed; no fallback transport")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true", help="Send over pinned USB-only SSH")
    args = parser.parse_args()
    state = json.loads(STATE.read_text())
    compact, binary, display = payload_from(state)
    if not args.push:
        print("BRIEFING_PREVIEW_ONLY items=" + str(len(compact["actions"]))
              + " todos=" + str(len(compact["todos"]))
              + " cached=" + str(compact["cached"])
              + " bytes=" + str(len(binary)))
        return
    config = json.loads(SSH_CONFIG.read_text())
    ssh_push(config, "today.json", binary)
    ssh_push(config, "today.txt", display)
    print("BRIEFING_SSH_PUSH_PASS no_raw_messages=true no_api_keys=true"
          + " cached=" + str(compact["cached"])
          + " actions=" + str(len(compact["actions"])))

if __name__ == "__main__":
    main()
