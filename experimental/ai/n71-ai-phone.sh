#!/bin/sh
# SPDX-License-Identifier: MIT
# Native Cyberdeck text AI client. Private token and prompts stay in phone RAM.
# The OpenAI API key is never provisioned to the iPhone.
set -e
umask 077
TOKEN=/run/cyberdeck/ai-bridge-token
URL=http://172.16.42.2:18962/v1/chat
[ -s "$TOKEN" ] || { echo "DECK.AI offline: secure Dell bridge not paired."; exit 2; }
[ -f "$TOKEN" ] && [ ! -L "$TOKEN" ] || exit 2

ask() {
    question="$1"
    [ -n "$question" ] || return 0
    [ "${#question}" -le 1800 ] || { echo "Maximum 1800 characters per request."; return 2; }
    mkdir -p /run/cyberdeck
    chmod 700 /run/cyberdeck
    request="$(mktemp /run/cyberdeck/n71-ai-request.XXXXXX)" || return 2
    printf '%s' "$question" >"$request"
    if [ "$(wc -c <"$request")" -gt 2048 ]; then
        rm -f -- "$request"
        echo "Message exceeds the bridge's byte limit."
        return 2
    fi
    token="$(cat "$TOKEN")"
    # GET is forbidden; POST is confined to the Dell's private USB address.
    if wget -q -T 48 -O - --header "Authorization: Bearer $token" \
         --header "Content-Type: text/plain; charset=utf-8" \
         --post-file "$request" "$URL"; then
        result=0
    else
        result=$?
    fi
    rm -f -- "$request"
    return "$result"
}

if [ "$1" = "--chat" ]; then
    echo "DECK.AI / USB companion / text dialogue"
    echo "Commands: /reset (forget context), /exit (return to shell)"
    while printf 'AI> ' && IFS= read -r line; do
        case "$line" in
          /exit|/quit) echo 'DECK.AI closed.'; exit 0 ;;
          '') continue ;;
        esac
        ask "$line" || echo "AI request failed; check Dell USB bridge."
    done
else
    if [ "$#" -eq 0 ]; then
        printf 'Usage: n71-ai --chat | n71-ai question\n'
        exit 0
    fi
    ask "$*"
fi
