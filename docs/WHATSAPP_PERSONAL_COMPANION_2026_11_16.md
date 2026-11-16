# Personal WhatsApp: AI briefing connector and exclusion policy

2026-11-16 design and offline-test milestone for the N71 Linux Cyberdeck. No personal data, OAuth tokens, contacts or WhatsApp messages belong in this repository.

## Product decision

The owner uses **personal WhatsApp Messenger**, not WhatsApp Business. There is no official Meta API for a complete personal chat inbox or historic messages, and daily export/import is explicitly not acceptable.

**Preferred candidate:** Beeper Desktop **On-Device** on Dell Kubuntu, using the separately documented, locally bound Beeper Desktop API (read-only GET routes for chats and messages). Beeper is a **third-party** linked-device integration, not an official personal Meta API. The owner must separately install it, connect their personal WhatsApp account with an authorized linked-device action, enable the Beeper Developer API and store a private access token locally. No Beeper installation, pairing or personal chat access has occurred in this phase. History may be limited to locally indexed messages; the API is experimental and account/terms/security considerations need acknowledgement.

Sources:
- https://developers.beeper.com/desktop-api/
- https://developers.beeper.com/desktop-api-reference/resources/chats/methods/list/
- https://developers.beeper.com/desktop-api-reference/resources/messages/methods/list/
- https://help.beeper.com/en_US/troubleshooting/beeper-on-device-vs-beeper-cloud-what-goes-to-beeper-servers
- https://www.beeper.com/download/linux

## Implementation, existing private companion repo

In the private DECK backend, the new offline-tested files provide:
- **wa_privacy.py:** exact-match, fail-closed exclusions of contacts and groups; owner-only local JSON file; unknown identities are denied; group processing disabled by default.
- **wa_controls.py:** local interactive add/remove operations with no contact names in shell history; changing policy clears the cached notification preview. Excluded contact/group names are never committed to Git.
- **wa_desktop.py:** existing WhatsApp Web notification fallback, now filtered **before** persistent storage and again on read. It never accesses full chat history and remains inactive.
- **wa_beeper.py:** local GET-only Beeper reader, **disabled by default**; chat/participant identity and platform checked before requesting message contents. Exclusions additionally applied to individual messages. First page of recent chats/messages only, with explicitly partial coverage. No messages are sent or marked read.
- **reader.py:** AI source integration behind an explicit environment flag. Missing local token or unavailable Beeper is reported as incomplete; raw messages remain model input only, never stored in the phone JSON. The privacy rule revision is checked before and after a model call so a policy change cannot silently reauthorize an old briefing.
- **Automated unit tests:** old backend suite plus privacy, source-fail-closed, per-chat exclusion and optional Beeper adapter tests.

**Current physical state:** Gmail/Google Calendar AI briefing and authenticated USB SSH delivery to TODAY have passed on the owner setup. The phone receives only derived briefing text/JSON. No complete WhatsApp feed has been qualified and no live contact has been retrieved through Beeper.

## Acceptance gates for production-like use

1. Explicitly authorize the third-party app and pair an **On-Device** connection for the personal account on the Dell. Avoid Beeper Cloud if only local message storage is desired.
2. Enable the Desktop API locally and verify its listener/authentication. Keep token in mode 0600 server environment, never in Git/device firmware.
3. Build a private selector for the owner's excluded contacts/chats using **stable IDs**, not only potentially duplicated display names. Any unresolved identity is dropped.
4. Test scoped chat pagination, message recency and duplicated/cached results, while leaving groups disabled until member identity is verifiable.
5. Apply exclusions **before any model API call** and prove with controlled messages that excluded content is absent from model input, state files, logs and the Cyberdeck report.
6. Use scheduled companion analysis (weekdays 08:45 Europe/Rome, on-demand refresh) and an authenticated encrypted push. When rules change, invalidate existing derived state and revoke/reissue cached device reports.
7. Handle app absence, delayed indexing, reconnect failures and platform ToS/account risks transparently; do not claim guaranteed complete real-time coverage.

The user-requested Cyberpunk 2077 visual design direction remains reserved for the later interface/UX phase. The current engineering priority is a stable, secure, functional handheld system.
