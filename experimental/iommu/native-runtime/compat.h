#include <linux/bits.h>
#ifndef IO_PGTABLE_QUIRK_APPLE_DART_S5L8960X
#define IO_PGTABLE_QUIRK_APPLE_DART_S5L8960X BIT(10)
#endif

#if defined(N71_PROTOCOL6_DMA_REQUEST) && (!defined(N71_PRIVATE_FIRMWARE_TRIAL) || !defined(N71_PRIVATE_FIRMWARE_BOOT_TRIAL))
#error "Protocol6 endpoint DMA requires the private firmware boot trial"
#endif

#if (defined(N71_PROTOCOL6_CONTROL_SEQUENCE) || defined(N71_PROTOCOL6_MSI_DELIVERY)) && !defined(N71_PROTOCOL6_DMA_REQUEST)
#error "Protocol6 sequence/MSI qualification requires the endpoint DMA trial"
#endif

#if defined(N71_NATIVE_BRCMFMAC_TRIAL) && !defined(N71_NATIVE_MSI_DOMAIN)
#error "Native brcmfmac requires the scoped Linux MSI domain"
#endif
#if defined(N71_NATIVE_WLAN_RUNTIME) && !defined(N71_NATIVE_BRCMFMAC_TRIAL)
#error "Managed WLAN runtime requires native brcmfmac binding"
#endif
