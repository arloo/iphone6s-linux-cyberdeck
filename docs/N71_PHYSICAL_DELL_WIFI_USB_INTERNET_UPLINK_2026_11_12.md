# N71 iPhone 6s Linux: physical Internet access via Dell Wi-Fi / USB NCM

**2026-11-12. Physical owner-controlled iPhone 6s Samsung A9 N71/S8000 running Linux ARM64.** This is a useful, temporary **user-space network uplink**, not native iPhone BCM4350 Wi-Fi.

## Actual physical, on-device verification

The owner-controlled Dell XPS 13, running Kubuntu, was connected to the Internet by its internal Wi-Fi interface. The actual iPhone was already booted into RAM-only Linux, exposing the HoolockLinux USB gadget **05ac:4142** and its USB point-to-point interface.

| Link | Address / state |
|---|---|
| Physical iPhone, Linux USB gadget | 05ac:4142 |
| Phone USB network interface | 172.16.42.1 |
| Dell USB network interface | 172.16.42.2 |
| Dell Internet uplink | Internal Wi-Fi; route to public Internet present |
| User-space proxy listener | **172.16.42.2:18080 only** |
| Accepted source peer | **172.16.42.1 only** |
| Real on-phone Wi-Fi interface | **Not present** |

A standard Python HTTP proxy [n71_usb_wifi_uplink_proxy.py](../tools/n71_usb_wifi_uplink_proxy.py) was launched on the Dell as an unprivileged user, bound to the **USB interface only**, and with a fixed allowlist of public upstream domains. No root, system firewall/NAT changes, DHCP server, DNS on iPhone, routing modification or device storage access is required.

The physical on-phone BusyBox wget fetched an ordinary public test website through this proxy via the Dell's outbound HTTPS connection.

**First physical test (HTTP proxy URL upgraded to TLS by the Dell):**

    HTTP/1.1 200 OK
    X-N71-Uplink: dell-wifi-over-usb
    N71_PHONE_PROXY_WGET_EXIT=0

A subsequent GET (not just HEAD) delivered **577 bytes** directly into a pipe in the phone's RAM Linux shell. No downloaded file was committed to original iOS NAND.

**Second physical test (BusyBox wget originally supplied an HTTPS URL):**

    HTTP/1.1 200 OK
    X-N71-Uplink: dell-wifi-over-usb
    N71_HTTPS_WGET_RC=0

The first proxy version did not accept BusyBox wget's absolute HTTPS URL in proxy mode. It returned a correctly surfaced 502 error. This was corrected in the Dell proxy software to accept allowlisted HTTP **and** HTTPS upstream URLs, always fetching by HTTPS from the Dell. The corrected implementation passed the actual subsequent physical test.

**Physical negative security controls:** from the actual iPhone, attempts to use the USB proxy to reach private LAN router address 192.168.1.1, link-local metadata address 169.254.169.254 and localhost were all refused with nonzero wget return codes. A request initiated from the Dell instead of the owner phone was rejected with PHONE_ONLY. No unrestricted LAN proxy was created.

No original data, private MAC, Wi-Fi SSID, credentials, unique hardware ID or identifying phone logs are included in the report.

## Usage on the authorized owner's Dell

The Dell must already be connected by Wi-Fi and the phone's existing Linux USB gadget must be reachable. Start the user-space proxy from a Dell terminal, with no sudo:

    cd ~/Documenti/iphone6s-linux-cyberdeck-public
    python3 -u tools/n71_usb_wifi_uplink_proxy.py

From a shell **on the actual RAM Linux iPhone**, run an anonymous public-domain connectivity check:

    http_proxy=http://172.16.42.2:18080 \
    https_proxy=http://172.16.42.2:18080 \
      wget -S -T 12 -Y on --spider https://example.com/

For a small, public allowlisted download, a wget -O - pipeline avoids writing a file:

    http_proxy=http://172.16.42.2:18080 \
    https_proxy=http://172.16.42.2:18080 \
      wget -q -T 12 -Y on -O - https://example.com/ | wc -c

The proxy only fetches **allowlisted public destinations**, has deliberately capped response/tunnel sizes and rejects redirects rather than following unverified domains. This is a test/development uplink, not a general-purpose open HTTP proxy. An existing bound proxy on port 18080 must be stopped before starting another. The user may stop the proxy with Ctrl+C in the hosting terminal.

### Transport security and scope

- For the tested BusyBox wget URL behavior, **the Dell performs upstream HTTPS and TLS certificate validation**; the return journey from Dell to iPhone uses direct USB HTTP, not end-to-end HTTPS from the phone to the public website. Do not use this tool with credentials, personal data, confidential sessions or sensitive downloads.
- A separate HTTPS CONNECT tunnel is implemented for allowlisted public port-443 endpoints, but **an independently verified end-to-end TLS tunnel on this exact BusyBox phone has NOT been established**. Do not represent it as verified.
- The proxy does not make the iPhone a member of the Wi-Fi LAN, does not supply DHCP/routing/NAT and cannot reach arbitrary private network devices. It requires the Dell to stay connected.
- No modifications to kernel, phone radio, DART, PCIe, NAND, modem, host firewall or privileged operating-system network policy were performed.

## Standalone test and native Wi-Fi objective

The new [offline safety-policy regression suite](../tests/test_n71_usb_wifi_uplink_proxy.py) checks original USB bind/source restrictions, public hostname allowlisting, rejected private/loopback/link-local/mixed DNS resolutions, non-phone client rejection, blocked POST and disallowed arbitrary network/kernel side effects. All tests use mocks and do not access the phone.

**Still outstanding:** native PCIe BCM4350 enumeration on Apple A9/S8000, DART1 physical requester-to-SID mapping and fault-isolated IOVA, safe storage/modem shared-root control, brcmfmac association and wireless LAN DHCP. The [original source-resolved port1 fan-out analysis](N71_S8000_ORIGINAL_PORT1_LOCAL_TO_ROOT_FANOUT_2026_11_12.md) and physical [metadata-guard module proof](N71_S8000_PORT1_GUARD_PHYSICAL_PROBE_PASS_2026_11_12.md) remain prerequisites. **USB-uplink Internet success must never be counted as native iPhone Wi-Fi success.**

At the end of this experiment the iPhone remained physically present as USB **05ac:4142** with the previously loaded passive, hardware-blocked port1 probe module, Linux and initialized touchscreen. The temporary proxy remained running on the authorized Dell, but it is not a persistent boot-time service.
