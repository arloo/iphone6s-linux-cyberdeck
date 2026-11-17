#!/bin/sh
# SPDX-License-Identifier: MIT
# N71 RAM file workspace. Durable copies require the Dell USB SSH vault.
set -eu
BASE=/data
FOLDERS="Music Documents Projects Downloads Notes Kali"

usage() {
 cat <<'EOF'
CYBERDECK FILES (N71/S8000)
  n71-files status
  n71-files ls [Music|Documents|Projects|Downloads|Notes|Kali]
  n71-files copy /local/source.ext Music
  n71-files help

Phone workspace: /data (volatile until internal NAND is supported).
Backup to Dell, from the Dell terminal:
  python3 ~/Documenti/iphone6s-linux-cyberdeck-public/experimental/storage/n71_usb_file_vault.py backup
Restore from Dell to the phone after a new RAM boot:
  python3 ~/Documenti/iphone6s-linux-cyberdeck-public/experimental/storage/n71_usb_file_vault.py restore
This is NOT internal flash, and audio playback is not yet validated.
EOF
}
allowed() {
 case "$1" in
 Music|Documents|Projects|Downloads|Notes|Kali) return 0 ;;
 *) echo "Unknown category" >&2; return 2 ;;
 esac
}
init() {
 mkdir -p "$BASE"
 chmod 700 "$BASE"
 for folder in $FOLDERS; do
   [ ! -L "$BASE/$folder" ] || { echo "Unsafe category directory" >&2; exit 3; }
   mkdir -p "$BASE/$folder"
   chmod 700 "$BASE/$folder"
 done
}
mode="${1:-help}"
case "$mode" in
 help|--help|-h) usage ;;
 status)
   init
   echo "CYBERDECK /data is VOLATILE phone RAM (not internal storage)"
   df -h "$BASE"
   for folder in $FOLDERS; do
     count="$(find "$BASE/$folder" -type f | wc -l)"
     echo "$folder files=$count"
   done
   ;;
 ls)
   init
   folder="${2:-Documents}"
   allowed "$folder"
   ls -lh "$BASE/$folder"
   ;;
 copy)
   init
   source="${2:-}"
   category="${3:-}"
   [ -n "$source" ] && allowed "$category"
   [ -f "$source" ] && [ ! -L "$source" ] || { echo "Source file not found or symlink" >&2; exit 2; }
   name="${source##*/}"
   [ -n "$name" ] && [ "$name" != "." ] && [ "$name" != ".." ] || exit 2
   [ ! -e "$BASE/$category/$name" ] && [ ! -L "$BASE/$category/$name" ] || {
     echo "Refusing to overwrite existing file" >&2; exit 3;
   }
   cp "$source" "$BASE/$category/$name"
   chmod 600 "$BASE/$category/$name"
   sync
   echo "FILE_COPIED_TO_RAM_WORKSPACE. Run Dell vault backup to persist."
   ;;
 *) usage; exit 2 ;;
esac
